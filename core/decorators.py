# core/decorators.py
from functools import wraps
from django.core.cache import cache
from django.utils import timezone
from django.http import HttpResponseForbidden
import time


def rate_limit(rate='5/m', key='ip', block=True):
    """
    Декоратор для ограничения частоты запросов
    rate: формат 'число/период' (10/m, 100/h, 1000/d)
    key: 'ip', 'user', 'session'
    """

    def decorator(view_func):
        @wraps(view_func)
        def wrapped(request, *args, **kwargs):
            # Парсинг параметров лимита
            count, period = rate.split('/')
            count = int(count)

            # Определение периода в секундах
            period_map = {'s': 1, 'm': 60, 'h': 3600, 'd': 86400}
            period_seconds = period_map.get(period.lower(), 60)

            # Определение ключа для кэша
            if key == 'ip':
                x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
                if x_forwarded_for:
                    client_ip = x_forwarded_for.split(',')[0]
                else:
                    client_ip = request.META.get('REMOTE_ADDR')
                cache_key = f"rate_limit_{view_func.__name__}_{client_ip}"
            elif key == 'user':
                if request.user.is_authenticated:
                    cache_key = f"rate_limit_{view_func.__name__}_{request.user.id}"
                else:
                    return view_func(request, *args, **kwargs)
            else:
                cache_key = f"rate_limit_{view_func.__name__}_{request.session.session_key}"

            # Проверка лимита
            requests = cache.get(cache_key, [])
            now = timezone.now()

            # Удаление старых запросов
            requests = [req_time for req_time in requests
                        if (now - req_time).seconds < period_seconds]

            # Проверка превышения лимита
            if len(requests) >= count:
                if block:
                    return HttpResponseForbidden(
                        "Превышен лимит запросов. Пожалуйста, подождите."
                    )
                else:
                    # Можно вернуть специальный заголовок
                    response = HttpResponseForbidden("Превышен лимит")
                    response['X-RateLimit-Limit'] = count
                    response['X-RateLimit-Remaining'] = 0
                    response['X-RateLimit-Reset'] = int(requests[0].timestamp()) + period_seconds
                    return response

            # Добавление текущего запроса
            requests.append(now)
            cache.set(cache_key, requests, period_seconds)

            # Добавление заголовков
            response = view_func(request, *args, **kwargs)
            response['X-RateLimit-Limit'] = count
            response['X-RateLimit-Remaining'] = count - len(requests)
            response['X-RateLimit-Reset'] = int(now.timestamp()) + period_seconds

            return response

        return wrapped

    return decorator