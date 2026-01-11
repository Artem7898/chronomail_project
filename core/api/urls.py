from django.urls import path, include
from rest_framework.routers import DefaultRouter
from . import views

router = DefaultRouter()
# Позже добавим viewset'ы

urlpatterns = [
    path('', include(router.urls)),
    path('auth/', include('rest_framework.urls')),
]