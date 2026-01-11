from django.contrib import admin
from django.utils.html import format_html
from .models import TimeCapsule
from .tasks import send_time_capsule


@admin.register(TimeCapsule)
class TimeCapsuleAdmin(admin.ModelAdmin):
    list_display = [
        'id',
        'recipient_email',
        'scheduled_date',
        'status_colored',
        'created_at',
        'sent_at'
    ]
    list_filter = ['status', 'scheduled_date', 'created_at']
    search_fields = ['recipient_email', 'encrypted_message']
    readonly_fields = ['created_at', 'sent_at', 'encrypted_message_preview']
    actions = ['send_selected_capsules', 'resend_selected_capsules']

    fieldsets = (
        ('Основная информация', {
            'fields': ('recipient_email', 'scheduled_date', 'status')
        }),
        ('Данные сообщения', {
            'fields': ('encrypted_message_preview',),
            'classes': ('collapse',)
        }),
        ('Метаданные', {
            'fields': ('created_at', 'sent_at', 'failure_reason'),
            'classes': ('collapse',)
        }),
    )

    def status_colored(self, obj):
        """Цветовая индикация статуса"""
        colors = {
            'pending': 'orange',
            'sent': 'green',
            'failed': 'red',
            'processing': 'blue'
        }
        color = colors.get(obj.status, 'gray')
        return format_html(
            '<span style="color: {}; font-weight: bold;">{}</span>',
            color,
            obj.get_status_display()
        )

    status_colored.short_description = 'Статус'

    def encrypted_message_preview(self, obj):
        """Превью зашифрованного сообщения"""
        preview = obj.encrypted_message[:100] + '...' if len(obj.encrypted_message) > 100 else obj.encrypted_message
        return format_html('<code style="word-break: break-all;">{}</code>', preview)

    encrypted_message_preview.short_description = 'Зашифрованное сообщение (превью)'

    def send_selected_capsules(self, request, queryset):
        """Действие для отправки выбранных капсул"""
        success_count = 0
        for capsule in queryset:
            if capsule.status != 'sent':
                if send_time_capsule(capsule.id):
                    success_count += 1

        self.message_user(
            request,
            f'Успешно отправлено {success_count} из {queryset.count()} капсул.'
        )

    send_selected_capsules.short_description = "Отправить выбранные капсулы"

    def resend_selected_capsules(self, request, queryset):
        """Действие для повторной отправки выбранных капсул"""
        success_count = 0
        for capsule in queryset:
            if send_time_capsule(capsule.id):
                success_count += 1

        self.message_user(
            request,
            f'Успешно переотправлено {success_count} из {queryset.count()} капсул.'
        )

    resend_selected_capsules.short_description = "Переотправить выбранные капсулы"