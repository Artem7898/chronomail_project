from django.core.mail import send_mail
from django.conf import settings
from django.utils import timezone
from .models import TimeCapsule
import logging

logger = logging.getLogger(__name__)


def send_time_capsule(capsule_id):
    """Функция для отправки капсулы времени"""
    try:
        capsule = TimeCapsule.objects.get(id=capsule_id)

        # Проверка времени отправки
        if capsule.scheduled_date > timezone.now():
            logger.info(f"Капсула {capsule_id} ещё не готова к отправке")
            return False

        # Проверка статуса
        if capsule.status == 'sent':
            logger.info(f"Капсула {capsule_id} уже отправлена")
            return True

        # Обновление статуса
        capsule.status = 'processing'
        capsule.save(update_fields=['status'])

        # Дешифрование сообщения
        try:
            message = capsule.decrypt_message()
        except Exception as e:
            capsule.mark_as_failed(f"Ошибка дешифрования: {str(e)}")
            logger.error(f"Ошибка дешифрования капсулы {capsule_id}: {str(e)}")
            return False

        # Эмуляция отправки (в консоль)
        print("\n" + "=" * 60)
        print("ЭМУЛЯЦИЯ ОТПРАВКИ ПИСЬМА")
        print("=" * 60)
        print(f"От: ChronoMail System <noreply@chronomail.com>")
        print(f"Кому: {capsule.recipient_email}")
        print(f"Тема: Ваша капсула времени готова!")
        print(f"Дата отправки: {capsule.scheduled_date}")
        print("-" * 60)
        print(f"Содержание:\n{message}")
        print("=" * 60 + "\n")

        # В реальном приложении:
        # send_mail(
        #     'Ваша капсула времени готова!',
        #     message,
        #     'noreply@chronomail.com',
        #     [capsule.recipient_email],
        #     fail_silently=False,
        # )

        # Отметить как отправленное
        capsule.mark_as_sent()
        logger.info(f"Капсула {capsule_id} успешно отправлена")
        return True

    except TimeCapsule.DoesNotExist:
        logger.error(f"Капсула {capsule_id} не найдена")
        return False
    except Exception as e:
        logger.error(f"Ошибка при отправке капсулы {capsule_id}: {str(e)}")

        # Пометить как ошибочную
        try:
            capsule.mark_as_failed(str(e))
        except:
            pass

        return False


def check_and_send_pending_capsules():
    """Проверка и отправка капсул, время которых наступило"""
    now = timezone.now()
    pending_capsules = TimeCapsule.objects.filter(
        status='pending',
        scheduled_date__lte=now
    )

    for capsule in pending_capsules:
        send_time_capsule(capsule.id)

    return pending_capsules.count()