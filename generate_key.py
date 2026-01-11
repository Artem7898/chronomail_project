from cryptography.fernet import Fernet

# Генерация нового ключа
key = Fernet.generate_key()
print(f"FERNET_KEY={key.decode()}")
print("\nСкопируйте этот ключ в файл .env")