# core/monitoring.py
import sentry_sdk
from sentry_sdk import capture_message, capture_exception
from django.core.cache import cache
import time
import functools


class ChronoMailMonitor:
    """Мониторинг и трекинг приложения"""

    @staticmethod
    def track_operation(name, **tags):
        """Декоратор для трекинга операций"""

        def decorator(func):
            @functools.wraps(func)
            def wrapper(*args, **kwargs):
                with sentry_sdk.start_transaction(op=name, name=name) as transaction:
                    # Установка тегов
                    for key, value in tags.items():
                        transaction.set_tag(key, value)

                    # Запуск функции
                    try:
                        result = func(*args, **kwargs)
                        transaction.set_status("ok")
                        return result
                    except Exception as e:
                        transaction.set_status("internal_error")
                        capture_exception(e)
                        raise

            return wrapper

        return decorator

    @staticmethod
    def log_encryption_operation(capsule_id, operation, success=True, error=None):
        """Логирование операций шифрования"""
        with sentry_sdk.configure_scope() as scope:
            scope.set_tag("capsule_id", capsule_id)
            scope.set_tag("operation", operation)
            scope.set_tag("success", success)

            if error:
                scope.set_extra("error_details", str(error))

            if success:
                capture_message(
                    f"Encryption {operation} completed for capsule {capsule_id}",
                    level="info"
                )
            else:
                capture_exception(error)

    @staticmethod
    def track_metrics(metric_name, value, tags=None):
        """Трекинг метрик"""
        tags = tags or {}
        sentry_sdk.set_measurement(metric_name, value)

        # Также можно отправлять в StatsD или другую систему
        cache_key = f"metric_{metric_name}_{int(time.time())}"
        cache.set(cache_key, value, 300)  # 5 минут

    @staticmethod
    def performance_monitor():
        """Монитор производительности"""
        import psutil
        import platform

        metrics = {
            'cpu_percent': psutil.cpu_percent(interval=1),
            'memory_percent': psutil.virtual_memory().percent,
            'disk_usage': psutil.disk_usage('/').percent,
            'process_memory': psutil.Process().memory_info().rss / 1024 / 1024,  # MB
        }

        # Отправка метрик
        for name, value in metrics.items():
            ChronoMailMonitor.track_metrics(name, value)

        # Проверка критических значений
        if metrics['memory_percent'] > 90:
            capture_message(
                f"High memory usage: {metrics['memory_percent']}%",
                level="warning"
            )

        return metrics