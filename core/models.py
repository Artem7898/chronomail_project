# models.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from cryptography.fernet import Fernet, InvalidToken
from django.conf import settings
from django.contrib.auth.models import AbstractUser
import base64
import os
import logging
import time

logger = logging.getLogger('core.encryption')


# models.py - исправленная модель CustomUser

class CustomUser(AbstractUser):
    """Расширенная модель пользователя с поддержкой 2FA"""
    two_factor_enabled = models.BooleanField(
        '2FA включена',
        default=False,
        help_text='Включена ли двухфакторная аутентификация'
    )
    phone_number = models.CharField(
        'Номер телефона',
        max_length=20,
        blank=True,
        null=True,
        help_text='Для SMS аутентификации'
    )
    last_login_ip = models.GenericIPAddressField(
        'Последний IP входа',
        blank=True,
        null=True
    )
    failed_login_attempts = models.IntegerField(
        'Неудачные попытки входа',
        default=0
    )
    account_locked_until = models.DateTimeField(
        'Аккаунт заблокирован до',
        blank=True,
        null=True
    )

    # Переопределяем groups и user_permissions с кастомными related_name
    groups = models.ManyToManyField(
        'auth.Group',
        verbose_name='Группы',
        blank=True,
        help_text='Группы, к которым принадлежит пользователь',
        related_name='customuser_set',
        related_query_name='customuser'
    )
    user_permissions = models.ManyToManyField(
        'auth.Permission',
        verbose_name='Права пользователя',
        blank=True,
        help_text='Конкретные права для этого пользователя',
        related_name='customuser_set',
        related_query_name='customuser'
    )

    class Meta:
        verbose_name = 'Пользователь'
        verbose_name_plural = 'Пользователи'


    def reset_failed_logins(self):
        """Сброс счетчика неудачных попыток"""
        self.failed_login_attempts = 0
        self.account_locked_until = None
        self.save()

    def increment_failed_login(self):
        """Увеличение счетчика неудачных попыток"""
        self.failed_login_attempts += 1

        if self.failed_login_attempts >= 5:  # Блокировка после 5 попыток
            self.account_locked_until = timezone.now() + timezone.timedelta(minutes=15)

        self.save()

    def is_account_locked(self):
        """Проверка, заблокирован ли аккаунт"""
        if self.account_locked_until:
            return timezone.now() < self.account_locked_until
        return False


class EncryptionKey(models.Model):
    """Модель для хранения ключей шифрования"""
    key_id = models.CharField(
        'ID ключа',
        max_length=50,
        unique=True,
        help_text='Уникальный идентификатор ключа'
    )
    key = models.TextField(
        'Ключ шифрования',
        help_text='Fernet ключ в base64'
    )
    created_at = models.DateTimeField(
        'Дата создания',
        auto_now_add=True
    )
    expires_at = models.DateTimeField(
        'Истекает',
        null=True,
        blank=True,
        help_text='Дата истечения срока действия ключа'
    )
    is_active = models.BooleanField(
        'Активен',
        default=True,
        help_text='Используется ли ключ для шифрования'
    )
    is_current = models.BooleanField(
        'Текущий',
        default=False,
        help_text='Текущий ключ для шифрования'
    )
    usage_count = models.IntegerField(
        'Количество использований',
        default=0
    )
    metadata = models.JSONField(
        'Метаданные',
        default=dict,
        blank=True
    )

    class Meta:
        verbose_name = 'Ключ шифрования'
        verbose_name_plural = 'Ключи шифрования'
        ordering = ['-created_at']

    def __str__(self):
        status = "Текущий" if self.is_current else "Активный" if self.is_active else "Неактивный"
        return f"Ключ {self.key_id} ({status})"

    def rotate(self):
        """Пометить ключ как неактивный и создать новый"""
        self.is_current = False
        self.is_active = False
        self.save()

        # Генерация нового ключа
        new_key = Fernet.generate_key()

        return EncryptionKey.objects.create(
            key_id=base64.urlsafe_b64encode(os.urandom(16)).decode()[:16],
            key=new_key.decode(),
            is_current=True,
            is_active=True
        )


class TimeCapsule(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Ожидает отправки'),
        ('sent', 'Отправлено'),
        ('failed', 'Ошибка'),
        ('processing', 'В процессе отправки'),
    ]

    recipient_email = models.EmailField('Email получателя')
    encrypted_message = models.TextField('Зашифрованное сообщение')
    scheduled_date = models.DateTimeField('Дата отправки')
    status = models.CharField(
        'Статус',
        max_length=20,
        choices=STATUS_CHOICES,
        default='pending'
    )
    created_at = models.DateTimeField('Дата создания', auto_now_add=True)
    sent_at = models.DateTimeField('Дата отправки', null=True, blank=True)
    failure_reason = models.TextField('Причина ошибки', blank=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='capsules'
    )

    class Meta:
        verbose_name = 'Капсула времени'
        verbose_name_plural = 'Капсулы времени'
        ordering = ['-created_at']

    def __str__(self):
        return f"Капсула для {self.recipient_email} ({self.scheduled_date.date()})"

    def clean(self):
        """Валидация данных модели"""
        if self.scheduled_date < timezone.now():
            raise ValidationError({
                'scheduled_date': 'Нельзя запланировать отправку в прошлое!'
            })

    def encrypt_message(self, raw_message):
        """Шифрование сообщения с логированием"""
        start_time = time.time()

        try:
            from .encryption import key_manager

            # Шифрование
            encrypted = key_manager.encrypt_with_key_id(raw_message)
            self.encrypted_message = encrypted

            # Логирование
            encryption_time = time.time() - start_time
            logger.info(
                f"Сообщение зашифровано",
                extra={
                    'capsule_id': self.id if self.id else 'new',
                    'operation': 'encrypt',
                    'key_id': key_manager.current_key_id,
                    'message_length': len(raw_message),
                    'encryption_time': encryption_time,
                }
            )

            return True

        except Exception as e:
            logger.error(
                f"Ошибка шифрования: {str(e)}",
                extra={
                    'capsule_id': self.id if self.id else 'new',
                    'operation': 'encrypt',
                    'error': str(e)
                },
                exc_info=True
            )
            raise

    def decrypt_message(self):
        """Дешифрование сообщения с логированием"""
        start_time = time.time()

        try:
            from .encryption import key_manager

            # Дешифрование
            decrypted = key_manager.decrypt_with_key_id(self.encrypted_message)

            # Логирование
            decryption_time = time.time() - start_time
            logger.info(
                f"Сообщение расшифровано",
                extra={
                    'capsule_id': self.id,
                    'operation': 'decrypt',
                    'decryption_time': decryption_time,
                }
            )

            return decrypted

        except Exception as e:
            logger.error(
                f"Ошибка дешифрования: {str(e)}",
                extra={
                    'capsule_id': self.id,
                    'operation': 'decrypt',
                    'error': str(e)
                },
                exc_info=True
            )
            raise

    def mark_as_sent(self):
        """Отметить капсулу как отправленную"""
        self.status = 'sent'
        self.sent_at = timezone.now()
        self.save(update_fields=['status', 'sent_at'])

    def mark_as_failed(self, reason):
        """Отметить капсулу как неотправленную с указанием причины"""
        self.status = 'failed'
        self.failure_reason = reason
        self.save(update_fields=['status', 'failure_reason'])


class CapsuleStatistics(models.Model):
    """Статистика по капсулам"""
    date = models.DateField(
        'Дата',
        unique=True,
        help_text='Дата для агрегации статистики'
    )

    # Количественные показатели
    total_created = models.IntegerField(
        'Всего создано',
        default=0
    )
    total_sent = models.IntegerField(
        'Всего отправлено',
        default=0
    )
    total_failed = models.IntegerField(
        'Всего ошибок',
        default=0
    )
    total_pending = models.IntegerField(
        'В ожидании',
        default=0
    )

    # Временные показатели
    avg_delivery_time = models.FloatField(
        'Среднее время доставки (часы)',
        default=0
    )
    max_delivery_time = models.FloatField(
        'Максимальное время доставки (часы)',
        default=0
    )

    # Категории получателей
    unique_recipients = models.IntegerField(
        'Уникальных получателей',
        default=0
    )
    top_domains = models.JSONField(
        'Топ доменов',
        default=list,
        help_text='Топ-10 доменов получателей'
    )

    # География
    countries = models.JSONField(
        'Распределение по странам',
        default=dict,
        help_text='Количество капсул по странам'
    )

    class Meta:
        verbose_name = 'Статистика капсул'
        verbose_name_plural = 'Статистика капсул'
        ordering = ['-date']

    def __str__(self):
        return f"Статистика за {self.date}"


class RealTimeMetrics(models.Model):
    """Метрики в реальном времени"""
    metric_key = models.CharField(
        'Ключ метрики',
        max_length=100,
        unique=True
    )
    metric_value = models.JSONField(
        'Значение метрики',
        default=dict
    )
    updated_at = models.DateTimeField(
        'Обновлено',
        auto_now=True
    )
    expires_at = models.DateTimeField(
        'Истекает',
        null=True,
        blank=True
    )

    class Meta:
        verbose_name = 'Метрика в реальном времени'
        verbose_name_plural = 'Метрики в реальном времени'

    @classmethod
    def update_metric(cls, key, value, ttl=None):
        """Обновление метрики"""
        metric, created = cls.objects.get_or_create(metric_key=key)
        metric.metric_value = value

        if ttl:
            metric.expires_at = timezone.now() + timezone.timedelta(seconds=ttl)

        metric.save()
        return metric

    @classmethod
    def get_metric(cls, key, default=None):
        """Получение метрики"""
        try:
            metric = cls.objects.get(metric_key=key)
            if metric.expires_at and metric.expires_at < timezone.now():
                metric.delete()
                return default
            return metric.metric_value
        except cls.DoesNotExist:
            return default


class CapsuleAttachment(models.Model):
    """Вложение к капсуле"""
    capsule = models.ForeignKey(
        TimeCapsule,
        on_delete=models.CASCADE,
        related_name='attachments'
    )
    file = models.FileField(
        'Файл',
        upload_to='attachments/%Y/%m/%d/',
        max_length=500
    )
    file_name = models.CharField(
        'Имя файла',
        max_length=255
    )
    file_size = models.BigIntegerField(
        'Размер файла',
        default=0
    )
    file_type = models.CharField(
        'Тип файла',
        max_length=100
    )
    is_encrypted = models.BooleanField(
        'Зашифрован',
        default=True
    )
    encryption_key_id = models.CharField(
        'ID ключа шифрования',
        max_length=50,
        blank=True,
        null=True
    )
    uploaded_at = models.DateTimeField(
        'Дата загрузки',
        auto_now_add=True
    )

    class Meta:
        verbose_name = 'Вложение'
        verbose_name_plural = 'Вложения'

    def __str__(self):
        return f"{self.file_name} ({self.capsule.id})"

    def save(self, *args, **kwargs):
        """Автоматическое заполнение полей при сохранении"""
        if not self.file_name and self.file:
            self.file_name = os.path.basename(self.file.name)

        if not self.file_size and self.file:
            self.file_size = self.file.size

        if not self.file_type and self.file:
            import mimetypes
            mime_type, _ = mimetypes.guess_type(self.file_name)
            self.file_type = mime_type or 'application/octet-stream'

        super().save(*args, **kwargs)


class MessageTemplate(models.Model):
    """Шаблон сообщения для капсул"""
    CATEGORY_CHOICES = [
        ('personal', 'Личное'),
        ('business', 'Деловое'),
        ('holiday', 'Праздничное'),
        ('reminder', 'Напоминание'),
        ('custom', 'Пользовательский'),
    ]

    name = models.CharField(
        'Название шаблона',
        max_length=100
    )
    content = models.TextField(
        'Содержание шаблона',
        help_text='Используйте {{имя}} для подстановки значений'
    )
    category = models.CharField(
        'Категория',
        max_length=20,
        choices=CATEGORY_CHOICES,
        default='personal'
    )
    variables = models.JSONField(
        'Переменные',
        default=list,
        help_text='Список переменных для подстановки'
    )
    is_public = models.BooleanField(
        'Публичный шаблон',
        default=False,
        help_text='Доступен всем пользователям'
    )
    is_active = models.BooleanField(
        'Активен',
        default=True
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='templates'
    )
    created_at = models.DateTimeField(
        'Дата создания',
        auto_now_add=True
    )
    usage_count = models.IntegerField(
        'Количество использований',
        default=0
    )

    class Meta:
        verbose_name = 'Шаблон сообщения'
        verbose_name_plural = 'Шаблоны сообщений'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.name} ({self.get_category_display()})"

    def render(self, context=None):
        """Рендеринг шаблона с подстановкой значений"""
        from django.template import Template, Context

        template = Template(self.content)
        context = Context(context or {})

        return template.render(context)

    def get_variables_list(self):
        """Получение списка переменных из шаблона"""
        import re
        variables = re.findall(r'\{\{(\w+)\}\}', self.content)
        return list(set(variables))