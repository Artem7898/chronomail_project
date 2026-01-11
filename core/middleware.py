import ipaddress
from django.utils import timezone
from django.core.cache import cache
from django.http import HttpResponseForbidden
from django.conf import settings
import logging

logger = logging.getLogger(__name__)


class IPFilterMiddleware:
    """Мидлварь для фильтрации по IP и ограничения попыток"""

    def __init__(self, get_response):
        self.get_response = get_response
        self.blocked_ips = getattr(settings, 'BLOCKED_IPS', [])
        self.allowed_ips = getattr(settings, 'ALLOWED_IPS', [])
        self.rate_limit = getattr(settings, 'RATE_LIMIT', {
            'requests': 100,  # Максимум запросов
            'period': 60,  # За период в секундах
        })

    def __call__(self, request):
        client_ip = self.get_client_ip(request)

        # Проверка блокировки
        if self.is_ip_blocked(client_ip):
            logger.warning(f"Заблокированный IP пытается получить доступ: {client_ip}")
            return HttpResponseForbidden(
                "Ваш IP-адрес временно заблокирован за подозрительную активность."
            )

        # Проверка списка разрешенных IP (если настроен)
        if self.allowed_ips and not self.is_ip_allowed(client_ip):
            logger.warning(f"IP не в белом списке: {client_ip}")
            return HttpResponseForbidden(
                "Доступ с вашего IP-адреса запрещен."
            )

        # Проверка черного списка
        if self.is_ip_in_blacklist(client_ip):
            logger.warning(f"IP в черном списке: {client_ip}")
            return HttpResponseForbidden(
                "Ваш IP-адрес заблокирован."
            )

        # Ограничение скорости запросов
        if not self.check_rate_limit(client_ip, request.path):
            logger.warning(f"Превышен лимит запросов для IP: {client_ip}")
            return HttpResponseForbidden(
                "Слишком много запросов. Пожалуйста, подождите."
            )

        response = self.get_response(request)

        # Логирование подозрительных запросов
        if response.status_code == 403 or response.status_code == 400:
            self.log_suspicious_request(client_ip, request)

        return response

    def get_client_ip(self, request):
        """Получение реального IP клиента"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip

    def is_ip_blocked(self, ip):
        """Проверка, заблокирован ли IP"""
        cache_key = f"blocked_ip_{ip}"
        return cache.get(cache_key) is not None

    def is_ip_allowed(self, ip):
        """Проверка IP в белом списке"""
        for allowed_ip in self.allowed_ips:
            if ipaddress.ip_address(ip) in ipaddress.ip_network(allowed_ip):
                return True
        return False

    def is_ip_in_blacklist(self, ip):
        """Проверка IP в черном списке"""
        for blocked_ip in self.blocked_ips:
            if ipaddress.ip_address(ip) in ipaddress.ip_network(blocked_ip):
                return True
        return False

    def check_rate_limit(self, ip, path):
        """Проверка ограничения скорости запросов"""
        cache_key = f"rate_limit_{ip}_{path}"
        requests = cache.get(cache_key, [])

        # Удаление старых записей
        now = timezone.now()
        requests = [req_time for req_time in requests
                    if (now - req_time).seconds < self.rate_limit['period']]

        # Проверка лимита
        if len(requests) >= self.rate_limit['requests']:
            # Блокировка IP на 5 минут
            cache.set(f"blocked_ip_{ip}", True, 300)
            return False

        # Добавление текущего запроса
        requests.append(now)
        cache.set(cache_key, requests, self.rate_limit['period'])

        return True

    def log_suspicious_request(self, ip, request):
        """Логирование подозрительных запросов"""
        log_entry = {
            'ip': ip,
            'path': request.path,
            'method': request.method,
            'user_agent': request.META.get('HTTP_USER_AGENT', ''),
            'timestamp': timezone.now().isoformat(),
            'params': dict(request.GET),
            'data': dict(request.POST) if request.method == 'POST' else {}
        }

        # Сохранение в кэше для анализа
        suspicious_key = f"suspicious_{ip}_{int(timezone.now().timestamp())}"
        cache.set(suspicious_key, log_entry, 3600)  # Хранение 1 час

        logger.warning(f"Подозрительный запрос от {ip}: {request.path}")