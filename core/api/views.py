from django.forms import model_to_dict
from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from django.contrib.auth import get_user_model
from django.shortcuts import get_object_or_404
from django.http import FileResponse
from ..models import TimeCapsule, CapsuleAttachment, MessageTemplate
from .serializers import (
    UserSerializer, TokenSerializer, TimeCapsuleSerializer,
    CreateCapsuleSerializer, MessageTemplateSerializer,
    BulkCreateSerializer, CapsuleAttachmentSerializer
)
import json

User = get_user_model()


class CustomAuthToken(ObtainAuthToken):
    """Кастомный endpoint для получения токена"""

    def post(self, request, *args, **kwargs):
        serializer = TokenSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        return Response(serializer.validated_data)


class UserViewSet(viewsets.ModelViewSet):
    """API для управления пользователями"""
    queryset = User.objects.all()
    serializer_class = UserSerializer
    permission_classes = [permissions.IsAdminUser]

    @action(detail=False, methods=['get'])
    def me(self, request):
        """Получение информации о текущем пользователе"""
        serializer = self.get_serializer(request.user)
        return Response(serializer.data)


class TimeCapsuleViewSet(viewsets.ModelViewSet):
    """API для управления капсулами времени"""
    serializer_class = TimeCapsuleSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Пользователи видят только свои капсулы
        # Админы видят все
        if self.request.user.is_staff:
            return TimeCapsule.objects.all()
        return TimeCapsule.objects.filter(created_by=self.request.user)

    def get_serializer_class(self):
        if self.action == 'create':
            return CreateCapsuleSerializer
        return TimeCapsuleSerializer

    def perform_create(self, serializer):
        # Привязка капсулы к пользователю
        capsule = serializer.save()
        capsule.created_by = self.request.user
        capsule.save()

    @action(detail=True, methods=['post'])
    def resend(self, request, pk=None):
        """Повторная отправка капсулы"""
        capsule = self.get_object()

        from ..tasks import send_time_capsule
        success = send_time_capsule(capsule.id)

        if success:
            return Response({'status': 'sent'})
        else:
            return Response(
                {'status': 'error', 'message': capsule.failure_reason},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    @action(detail=True, methods=['get'])
    def decrypt(self, request, pk=None):
        """Расшифрование и получение сообщения капсулы"""
        capsule = self.get_object()

        # Проверка прав доступа
        if not (request.user.is_staff or capsule.created_by == request.user):
            return Response(
                {'error': 'Доступ запрещен'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            message = capsule.decrypt_message()
            return Response({'message': message})
        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class AttachmentViewSet(viewsets.ReadOnlyModelViewSet):
    """API для работы с вложениями"""
    serializer_class = CapsuleAttachmentSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Только вложения капсул пользователя
        user_capsules = TimeCapsule.objects.filter(created_by=self.request.user)
        return CapsuleAttachment.objects.filter(capsule__in=user_capsules)

    @action(detail=True, methods=['get'])
    def download(self, request, pk=None):
        """Скачивание вложения"""
        attachment = self.get_object()

        # Проверка прав доступа
        if not (request.user.is_staff or attachment.capsule.created_by == request.user):
            return Response(
                {'error': 'Доступ запрещен'},
                status=status.HTTP_403_FORBIDDEN
            )

        try:
            # Дешифрование файла
            file_data = attachment.decrypt_file()

            # Создание временного файла
            import tempfile
            with tempfile.NamedTemporaryFile(delete=False) as tmp_file:
                tmp_file.write(file_data)
                tmp_file.flush()

            response = FileResponse(
                open(tmp_file.name, 'rb'),
                as_attachment=True,
                filename=attachment.file_name
            )

            # Удаление временного файла после отправки
            import os
            response.callback = lambda: os.unlink(tmp_file.name)

            return response

        except Exception as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class MessageTemplateViewSet(viewsets.ModelViewSet):
    """API для работы с шаблонами сообщений"""
    serializer_class = MessageTemplateSerializer
    permission_classes = [permissions.IsAuthenticated]

    def get_queryset(self):
        # Пользовательские шаблоны + общие
        return MessageTemplate.objects.filter(
            created_by=self.request.user
        ) | MessageTemplate.objects.filter(is_public=True)

    def perform_create(self, serializer):
        serializer.save(created_by=self.request.user)


class BulkCapsuleView(APIView):
    """API для массового создания капсул"""
    permission_classes = [permissions.IsAuthenticated]

    def post(self, request):
        serializer = BulkCreateSerializer(data=request.data)

        if serializer.is_valid():
            result = serializer.save()
            return Response(result, status=status.HTTP_201_CREATED)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class StatisticsAPIView(APIView):
    """API для получения статистики"""
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        from ..stats import StatisticsCollector

        collector = StatisticsCollector()

        # Тип статистики
        stats_type = request.GET.get('type', 'summary')

        if stats_type == 'summary':
            data = collector.update_realtime_metrics()
        elif stats_type == 'daily':
            date_str = request.GET.get('date')
            if date_str:
                from datetime import datetime
                date = datetime.strptime(date_str, '%Y-%m-%d').date()
                stat = collector.collect_daily_stats(date)
                data = model_to_dict(stat) if stat else {}
            else:
                data = collector.collect_daily_stats()
        elif stats_type == 'dashboard':
            data = collector.get_statistics_dashboard()
        else:
            data = {}

        return Response(data)