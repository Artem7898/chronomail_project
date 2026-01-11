from datetime import datetime
from django import forms
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib import messages
from django.utils import timezone
from django.views.generic import ListView
from .models import TimeCapsule, CapsuleAttachment, MessageTemplate, CustomUser
from .forms import TimeCapsuleForm, SearchForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.views.decorators.csrf import csrf_exempt
from django.http import JsonResponse
import csv
import json
from io import TextIOWrapper
from django.db import transaction


def home(request):
    """Главная страница"""
    return render(request, 'core/home.html')


@login_required
def create_capsule(request):
    """Создание новой капсулы времени с вложениями"""
    if request.method == 'POST':
        form = TimeCapsuleForm(request.POST, request.FILES, user=request.user)
        if form.is_valid():
            try:
                # Создание капсулы
                capsule = form.save()

                messages.success(
                    request,
                    f'Капсула успешно создана и будет отправлена {capsule.scheduled_date.strftime("%d.%m.%Y в %H:%M")}!'
                )
                return redirect('capsule_list')
            except Exception as e:
                messages.error(request, f'Ошибка при создании капсулы: {str(e)}')
    else:
        form = TimeCapsuleForm(user=request.user)

    return render(request, 'core/create_capsule.html', {'form': form})


class CapsuleListView(ListView):
    """Список всех капсул пользователя"""
    model = TimeCapsule
    template_name = 'core/capsule_list.html'
    context_object_name = 'capsules'
    paginate_by = 10

    def get_queryset(self):
        # Показываем только капсулы текущего пользователя
        return TimeCapsule.objects.filter(created_by=self.request.user).order_by('-created_at')


@login_required
def resend_capsule(request, capsule_id):
    """Повторная отправка капсулы"""
    capsule = get_object_or_404(TimeCapsule, id=capsule_id, created_by=request.user)

    # В реальном приложении здесь будет вызов задачи Celery
    try:
        capsule.status = 'pending'
        capsule.sent_at = None
        capsule.failure_reason = ''
        capsule.save()

        messages.success(request, 'Капсула помечена для повторной отправки!')
    except Exception as e:
        messages.error(request, f'Не удалось обновить капсулу: {str(e)}')

    return redirect('capsule_list')


@login_required
@user_passes_test(lambda u: u.is_staff)
def statistics_dashboard(request):
    """Дашборд статистики (только для администраторов)"""
    # Простая статистика
    context = {
        'total_capsules': TimeCapsule.objects.count(),
        'total_users': CustomUser.objects.count(),
        'pending_capsules': TimeCapsule.objects.filter(status='pending').count(),
        'sent_capsules': TimeCapsule.objects.filter(status='sent').count(),
        'failed_capsules': TimeCapsule.objects.filter(status='failed').count(),
        'title': 'Статистика ChronoMail'
    }

    return render(request, 'core/statistics.html', context)


@csrf_exempt
@login_required
def upload_attachment(request):
    """Загрузка вложения через AJAX"""
    if request.method == 'POST' and request.FILES:
        try:
            files = []
            for file in request.FILES.getlist('files'):
                # Временное сохранение информации о файле
                file_info = {
                    'name': file.name,
                    'size': file.size,
                    'type': file.content_type,
                    'url': '#',  # В реальном приложении - URL загруженного файла
                    'id': f'temp_{len(files)}'  # Временный ID
                }
                files.append(file_info)

            return JsonResponse({
                'success': True,
                'files': files,
                'message': 'Файлы успешно загружены'
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            }, status=500)

    return JsonResponse({'success': False, 'error': 'Нет файлов'}, status=400)


@csrf_exempt
@login_required
def preview_capsule(request):
    """Предпросмотр капсулы без сохранения"""
    if request.method == 'POST':
        try:
            data = json.loads(request.body)

            # Валидация данных
            recipient_email = data.get('recipient_email', '')
            message = data.get('message', '')
            scheduled_date = data.get('scheduled_date', '')
            attachments = data.get('attachments', [])

            # Проверка email
            from django.core.validators import validate_email
            from django.core.exceptions import ValidationError

            try:
                validate_email(recipient_email)
            except ValidationError:
                return JsonResponse({
                    'success': False,
                    'error': 'Неверный формат email'
                })

            # Проверка даты
            try:
                scheduled_datetime = timezone.datetime.fromisoformat(scheduled_date.replace('Z', '+00:00'))
                if scheduled_datetime < timezone.now():
                    return JsonResponse({
                        'success': False,
                        'error': 'Дата отправки не может быть в прошлом'
                    })
            except ValueError:
                return JsonResponse({
                    'success': False,
                    'error': 'Неверный формат даты'
                })

            # Генерация предпросмотра
            preview_html = f"""
            <div class="preview-container p-6 bg-white rounded-xl shadow">
                <h3 class="text-xl font-bold text-gray-800 mb-4">Предпросмотр капсулы</h3>

                <div class="space-y-4">
                    <div>
                        <p class="text-sm text-gray-500">Получатель</p>
                        <p class="font-medium">{recipient_email}</p>
                    </div>

                    <div>
                        <p class="text-sm text-gray-500">Дата отправки</p>
                        <p class="font-medium">{scheduled_datetime.strftime('%d.%m.%Y %H:%M')}</p>
                    </div>

                    <div>
                        <p class="text-sm text-gray-500">Сообщение</p>
                        <div class="border rounded p-4 bg-gray-50 mt-1 max-h-60 overflow-y-auto">
                            {message}
                        </div>
                    </div>

                    {f'<div><p class="text-sm text-gray-500">Вложения</p><p class="font-medium">{len(attachments)} файл(ов)</p></div>' if attachments else ''}
                </div>

                <div class="mt-6 p-4 bg-blue-50 rounded-lg">
                    <p class="text-sm text-blue-800">
                        <span class="mr-2">ℹ️</span>
                        Это предпросмотр. Капсула будет зашифрована и сохранена только после нажатия "Запечатать капсулу".
                    </p>
                </div>
            </div>
            """

            return JsonResponse({
                'success': True,
                'preview': preview_html
            })

        except Exception as e:
            return JsonResponse({
                'success': False,
                'error': str(e)
            })

    return JsonResponse({'success': False, 'error': 'Неверный метод запроса'})


@login_required
def bulk_create_capsules(request):
    """Массовое создание капсул из CSV"""
    if request.method == 'POST':
        form = BulkCapsuleForm(request.POST, request.FILES, user=request.user)

        if form.is_valid():
            csv_file = form.cleaned_data['csv_file']
            template_id = form.cleaned_data['template']
            common_message = form.cleaned_data['common_message']

            # Чтение CSV
            decoded_file = TextIOWrapper(csv_file.file, encoding='utf-8')
            csv_reader = csv.DictReader(decoded_file)

            created_count = 0
            error_count = 0
            errors = []

            with transaction.atomic():
                for i, row in enumerate(csv_reader, 1):
                    try:
                        # Валидация строки
                        if not row.get('email'):
                            errors.append(f"Строка {i}: Отсутствует email")
                            error_count += 1
                            continue

                        # Создание сообщения
                        if template_id:
                            template = MessageTemplate.objects.get(
                                id=template_id,
                                created_by=request.user
                            )
                            message = template.render(row)
                        elif common_message:
                            message = common_message
                            # Подстановка значений из CSV
                            for key, value in row.items():
                                message = message.replace(f'{{{{{key}}}}}', value)
                        else:
                            errors.append(f"Строка {i}: Не указано сообщение")
                            error_count += 1
                            continue

                        # Создание капсулы
                        capsule = TimeCapsule(
                            recipient_email=row['email'],
                            scheduled_date=row.get('date') or form.cleaned_data['scheduled_date'],
                            created_by=request.user
                        )

                        capsule.encrypt_message(message)
                        capsule.save()

                        created_count += 1

                    except Exception as e:
                        errors.append(f"Строка {i}: {str(e)}")
                        error_count += 1

            messages.success(
                request,
                f'Успешно создано {created_count} капсул. Ошибок: {error_count}.'
            )

            if errors:
                messages.warning(
                    request,
                    'Ошибки при обработке: ' + '; '.join(errors[:5]) +
                    ('...' if len(errors) > 5 else '')
                )

            return redirect('capsule_list')
    else:
        form = BulkCapsuleForm(user=request.user)

    return render(request, 'core/bulk_create.html', {'form': form})


class BulkCapsuleForm(forms.Form):
    """Форма для массового создания капсул"""
    csv_file = forms.FileField(
        label='CSV файл',
        help_text='CSV с колонками: email, date (опционально), дополнительные поля для шаблона'
    )
    template = forms.ModelChoiceField(
        queryset=MessageTemplate.objects.none(),
        required=False,
        label='Шаблон сообщения',
        help_text='Выберите шаблон для генерации сообщений'
    )
    common_message = forms.CharField(
        widget=forms.Textarea(attrs={'rows': 5}),
        required=False,
        label='Общее сообщение',
        help_text='Используйте {{имя_колонки}} для подстановки значений из CSV'
    )
    scheduled_date = forms.DateTimeField(
        label='Дата отправки по умолчанию',
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}),
        help_text='Используется, если в CSV нет даты'
    )

    def __init__(self, *args, **kwargs):
        user = kwargs.pop('user', None)
        super().__init__(*args, **kwargs)

        if user:
            self.fields['template'].queryset = MessageTemplate.objects.filter(
                created_by=user
            ) | MessageTemplate.objects.filter(is_public=True)


@login_required
def search_capsules(request):
    """Поиск капсул"""
    form = SearchForm(request.GET or None)
    capsules = TimeCapsule.objects.filter(created_by=request.user)

    if form.is_valid():
        query = form.cleaned_data.get('query')
        status = form.cleaned_data.get('status')

        if query:
            capsules = capsules.filter(recipient_email__icontains=query)

        if status:
            capsules = capsules.filter(status=status)

    return render(request, 'core/search.html', {
        'form': form,
        'capsules': capsules,
        'title': 'Поиск капсул'
    })


# API view для статистики (простая версия)
@login_required
def api_statistics(request):
    """API для статистики"""
    from django.forms.models import model_to_dict

    if request.user.is_staff:
        data = {
            'total_capsules': TimeCapsule.objects.count(),
            'total_users': CustomUser.objects.count(),
            'pending': TimeCapsule.objects.filter(status='pending').count(),
            'sent': TimeCapsule.objects.filter(status='sent').count(),
            'failed': TimeCapsule.objects.filter(status='failed').count(),
        }
    else:
        data = {
            'total_capsules': TimeCapsule.objects.filter(created_by=request.user).count(),
            'pending': TimeCapsule.objects.filter(created_by=request.user, status='pending').count(),
            'sent': TimeCapsule.objects.filter(created_by=request.user, status='sent').count(),
            'failed': TimeCapsule.objects.filter(created_by=request.user, status='failed').count(),
        }

    return JsonResponse(data)