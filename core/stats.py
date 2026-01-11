from django.db.models import Count, Avg, Max
from django.utils import timezone
from datetime import timedelta
import tldextract
import geoip2.database
import logging

logger = logging.getLogger(__name__)


class StatisticsCollector:
    """Сборщик статистики"""

    def __init__(self):
        self.geoip_reader = None
        try:
            self.geoip_reader = geoip2.database.Reader('GeoLite2-City.mmdb')
        except:
            logger.warning("GeoIP база данных не найдена")

    def collect_daily_stats(self, date=None):
        """Сбор ежедневной статистики"""
        from .models import TimeCapsule, CapsuleStatistics

        date = date or timezone.now().date()
        start_date = date
        end_date = date + timedelta(days=1)

        # Получение капсул за день
        capsules = TimeCapsule.objects.filter(
            created_at__gte=start_date,
            created_at__lt=end_date
        )

        if not capsules.exists():
            logger.info(f"Нет капсул для статистики за {date}")
            return None

        # Основная статистика
        stats = {
            'date': date,
            'total_created': capsules.count(),
            'total_sent': capsules.filter(status='sent').count(),
            'total_failed': capsules.filter(status='failed').count(),
            'total_pending': capsules.filter(status='pending').count(),
        }

        # Время доставки
        sent_capsules = capsules.filter(status='sent', sent_at__isnull=False)
        if sent_capsules.exists():
            delivery_times = []
            for capsule in sent_capsules:
                if capsule.sent_at and capsule.created_at:
                    hours = (capsule.sent_at - capsule.created_at).total_seconds() / 3600
                    delivery_times.append(hours)

            if delivery_times:
                stats['avg_delivery_time'] = sum(delivery_times) / len(delivery_times)
                stats['max_delivery_time'] = max(delivery_times)

        # Анализ доменов получателей
        domains = {}
        countries = {}
        recipients = set()

        for capsule in capsules:
            # Уникальные получатели
            recipients.add(capsule.recipient_email)

            # Домены
            domain = tldextract.extract(capsule.recipient_email).registered_domain
            domains[domain] = domains.get(domain, 0) + 1

            # География (если есть GeoIP)
            if self.geoip_reader:
                try:
                    # Извлечение IP из email (в реальном приложении нужен отдельный сбор IP)
                    # Здесь упрощенный пример
                    country = "Unknown"
                    countries[country] = countries.get(country, 0) + 1
                except:
                    pass

        stats['unique_recipients'] = len(recipients)
        stats['top_domains'] = sorted(
            domains.items(),
            key=lambda x: x[1],
            reverse=True
        )[:10]
        stats['countries'] = countries

        # Сохранение в БД
        stat_obj, created = CapsuleStatistics.objects.update_or_create(
            date=date,
            defaults=stats
        )

        logger.info(f"Собрана статистика за {date}: {stats}")
        return stat_obj

    def update_realtime_metrics(self):
        """Обновление метрик в реальном времени"""
        from .models import TimeCapsule, RealTimeMetrics

        now = timezone.now()

        metrics = {
            # Текущее состояние
            'total_capsules': TimeCapsule.objects.count(),
            'pending_capsules': TimeCapsule.objects.filter(status='pending').count(),
            'sent_today': TimeCapsule.objects.filter(
                status='sent',
                sent_at__date=now.date()
            ).count(),
            'created_today': TimeCapsule.objects.filter(
                created_at__date=now.date()
            ).count(),

            # Производительность
            'success_rate': self.calculate_success_rate(),
            'avg_processing_time': self.calculate_avg_processing_time(),

            # Системные метрики
            'last_updated': now.isoformat(),
        }

        # Обновление метрик
        RealTimeMetrics.update_metric('system_metrics', metrics, ttl=300)

        # Обновление каждые 5 минут
        return metrics

    def calculate_success_rate(self):
        """Расчет процента успешных отправок"""
        from .models import TimeCapsule

        total_sent = TimeCapsule.objects.filter(status='sent').count()
        total_failed = TimeCapsule.objects.filter(status='failed').count()

        total = total_sent + total_failed
        if total == 0:
            return 100.0

        return (total_sent / total) * 100

    def calculate_avg_processing_time(self):
        """Расчет среднего времени обработки"""
        from .models import TimeCapsule
        from django.db.models import Avg

        result = TimeCapsule.objects.filter(
            status='sent',
            sent_at__isnull=False,
            created_at__isnull=False
        ).aggregate(
            avg_time=Avg('sent_at' - 'created_at')
        )

        if result['avg_time']:
            return result['avg_time'].total_seconds()
        return 0

    def get_statistics_dashboard(self):
        """Получение данных для дашборда"""
        from .models import CapsuleStatistics
        from django.db.models import Sum, Avg

        # Последние 7 дней
        end_date = timezone.now().date()
        start_date = end_date - timedelta(days=7)

        stats = CapsuleStatistics.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).order_by('date')

        # Форматирование для графиков
        dates = [stat.date.strftime('%Y-%m-%d') for stat in stats]
        created = [stat.total_created for stat in stats]
        sent = [stat.total_sent for stat in stats]

        dashboard_data = {
            'labels': dates,
            'datasets': [
                {
                    'label': 'Создано',
                    'data': created,
                    'borderColor': 'rgb(59, 130, 246)',
                    'backgroundColor': 'rgba(59, 130, 246, 0.1)',
                },
                {
                    'label': 'Отправлено',
                    'data': sent,
                    'borderColor': 'rgb(16, 185, 129)',
                    'backgroundColor': 'rgba(16, 185, 129, 0.1)',
                }
            ],
            'summary': {
                'total_created': sum(created),
                'total_sent': sum(sent),
                'success_rate': (sum(sent) / sum(created) * 100) if sum(created) > 0 else 0,
            }
        }

        return dashboard_data