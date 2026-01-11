from django.apps import AppConfig


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """Выполняется при запуске приложения"""
        # Импорт здесь, чтобы избежать циклических импортов
        try:
            from .encryption import key_manager
            # Менеджер ключей уже инициализирован при импорте
            print("Менеджер ключей загружен")
        except ImportError as e:
            print(f"Ошибка импорта менеджера ключей: {e}")