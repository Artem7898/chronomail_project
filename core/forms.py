# forms.py - ИСПРАВЛЕННАЯ ВЕРСИЯ
from django import forms
from django.core.exceptions import ValidationError
from django.utils import timezone
from .models import TimeCapsule, CapsuleAttachment
from ckeditor.widgets import CKEditorWidget
from django.core.validators import FileExtensionValidator


class TimeCapsuleForm(forms.ModelForm):
    """Форма для создания капсулы времени"""
    message = forms.CharField(
        widget=forms.Textarea(attrs={
            'rows': 5,
            'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
            'placeholder': 'Введите ваше сообщение здесь...',
            'id': 'message-input'
        }),
        label='Сообщение',
        required=True
    )

    # Используем ClearableFileInput без multiple для модели
    attachments = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'hidden',
            'id': 'file-input'
        }),
        label='Вложения',
        required=False,
        validators=[
            FileExtensionValidator(
                allowed_extensions=[
                    'jpg', 'jpeg', 'png', 'gif', 'pdf', 'doc', 'docx',
                    'txt', 'md', 'zip', 'rar', 'mp3', 'mp4'
                ]
            )
        ]
    )

    class Meta:
        model = TimeCapsule
        fields = ['recipient_email', 'scheduled_date']
        widgets = {
            'recipient_email': forms.EmailInput(attrs={
                'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'placeholder': 'email@example.com'
            }),
            'scheduled_date': forms.DateTimeInput(attrs={
                'type': 'datetime-local',
                'class': 'w-full px-3 py-2 border rounded-lg focus:outline-none focus:ring-2 focus:ring-blue-500',
                'min': timezone.now().strftime('%Y-%m-%dT%H:%M')
            })
        }
        labels = {
            'recipient_email': 'Email получателя',
            'scheduled_date': 'Дата и время отправки'
        }

    def __init__(self, *args, **kwargs):
        self.user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)
        # Обновляем атрибуты виджета (multiple будет работать только на фронтенде)
        self.fields['attachments'].widget.attrs.update({
            'accept': '.jpg,.jpeg,.png,.gif,.pdf,.doc,.docx,.txt,.md,.zip,.rar,.mp3,.mp4',
        })

    def clean_scheduled_date(self):
        """Проверка, что дата отправки не в прошлом"""
        scheduled_date = self.cleaned_data.get('scheduled_date')
        if scheduled_date and scheduled_date < timezone.now():
            raise ValidationError('Нельзя запланировать отправку в прошлом!')
        return scheduled_date

    def save(self, commit=True):
        """Сохраняет капсулу с шифрованием сообщения"""
        capsule = super().save(commit=False)

        if self.user:
            capsule.created_by = self.user

        # Шифруем сообщение
        message = self.cleaned_data.get('message')
        if message:
            capsule.encrypt_message(message)

        if commit:
            capsule.save()

            # Обрабатываем вложения
            attachments = self.files.getlist('attachments')
            for attachment in attachments:
                CapsuleAttachment.objects.create(
                    capsule=capsule,
                    file=attachment,
                    file_name=attachment.name,
                    file_size=attachment.size,
                    file_type=attachment.content_type or 'application/octet-stream'
                )

        return capsule


class RichTimeCapsuleForm(TimeCapsuleForm):
    """Форма с CKEditor для редактирования сообщения"""
    message = forms.CharField(
        widget=CKEditorWidget(config_name='default'),
        label='Сообщение',
        required=True
    )

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Убираем классы, так как CKEditor сам управляет стилями
        self.fields['message'].widget.attrs.pop('class', None)
        self.fields['message'].widget.attrs.pop('rows', None)


# УДАЛЯЕМ AttachmentForm или исправляем ее:

class AttachmentForm(forms.Form):  # Используем forms.Form вместо ModelForm
    """Форма для отдельной загрузки вложений"""
    files = forms.FileField(
        widget=forms.ClearableFileInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
            'accept': '.jpg,.jpeg,.png,.gif,.pdf,.doc,.docx,.txt,.md,.zip,.rar,.mp3,.mp4'
        }),
        label='Загрузите файлы',
        required=False
    )


class SearchForm(forms.Form):
    """Форма поиска капсул"""
    query = forms.CharField(
        required=False,
        widget=forms.TextInput(attrs={
            'class': 'w-full px-3 py-2 border rounded-lg',
            'placeholder': 'Поиск по email или сообщению...'
        }),
        label=''
    )

    status = forms.ChoiceField(
        required=False,
        choices=[
            ('', 'Все статусы'),
            ('pending', 'Ожидает'),
            ('sent', 'Отправлено'),
            ('failed', 'Ошибка'),
            ('processing', 'В процессе')
        ],
        widget=forms.Select(attrs={
            'class': 'px-3 py-2 border rounded-lg'
        }),
        label='Статус'
    )