# core/urls.py
from django.urls import path
from . import views

urlpatterns = [
    # Главная страница
    path('', views.home, name='home'),

    # Создание капсулы
    path('create/', views.create_capsule, name='create_capsule'),

    # Список капсул
    path('capsules/', views.CapsuleListView.as_view(), name='capsule_list'),

    # Повторная отправка
    path('capsules/<int:capsule_id>/resend/', views.resend_capsule, name='resend_capsule'),

    # Статистика
    path('statistics/', views.statistics_dashboard, name='statistics'),
    path('api/statistics/', views.api_statistics, name='api_statistics'),

    # Массовое создание
    path('bulk-create/', views.bulk_create_capsules, name='bulk_create'),

    # API эндпоинты
    path('api/upload/', views.upload_attachment, name='upload_attachment'),
    path('api/preview/', views.preview_capsule, name='preview_capsule'),
]