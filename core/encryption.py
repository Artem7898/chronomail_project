from cryptography.fernet import Fernet
from django.conf import settings
import base64
import os
import logging

logger = logging.getLogger(__name__)


class SimpleKeyManager:
    """Упрощенный менеджер ключей для начала работы"""

    def __init__(self):
        self.current_key_id = 'default'
        self.keys = {}
        self.load_key()

    def load_key(self):
        """Загрузка ключа из настроек или генерация нового"""
        if hasattr(settings, 'FERNET_KEY') and settings.FERNET_KEY:
            self.keys[self.current_key_id] = {
                'key': settings.FERNET_KEY.encode(),
                'created_at': None,
                'expires_at': None,
                'usage_count': 0
            }
            print("Ключ шифрования загружен из настроек")
        else:
            # Генерация ключа для разработки
            key = Fernet.generate_key()
            self.keys[self.current_key_id] = {
                'key': key,
                'created_at': None,
                'expires_at': None,
                'usage_count': 0
            }
            print(f"ВНИМАНИЕ: Сгенерирован новый ключ для разработки: {key.decode()}")
            print("Добавьте его в .env файл как FERNET_KEY для постоянного использования")

    def encrypt_with_key_id(self, data, key_id=None):
        """Шифрование с указанием ID ключа"""
        key_id = key_id or self.current_key_id
        if key_id not in self.keys:
            raise ValueError(f"Ключ {key_id} не найден")

        fernet = Fernet(self.keys[key_id]['key'])
        encrypted = fernet.encrypt(data.encode())

        # Обновление счетчика использования
        self.keys[key_id]['usage_count'] = self.keys[key_id].get('usage_count', 0) + 1

        # Возвращаем с идентификатором ключа
        return f"{key_id}:{encrypted.decode()}"

    def decrypt_with_key_id(self, encrypted_data):
        """Дешифрование с автоматическим определением ключа"""
        if ':' in encrypted_data:
            key_id, data = encrypted_data.split(':', 1)
            if key_id in self.keys:
                fernet = Fernet(self.keys[key_id]['key'])
                return fernet.decrypt(data.encode()).decode()

        # Попытка дешифрования с текущим ключом
        if self.current_key_id in self.keys:
            try:
                fernet = Fernet(self.keys[self.current_key_id]['key'])
                return fernet.decrypt(encrypted_data.encode()).decode()
            except:
                pass

        raise ValueError("Не удалось расшифровать данные. Неверный ключ или повреждённые данные.")


# Глобальный экземпляр менеджера ключей
key_manager = SimpleKeyManager()