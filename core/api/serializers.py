from rest_framework import serializers
from rest_framework.authtoken.models import Token
from django.contrib.auth import authenticate
from ..models import TimeCapsule, CapsuleAttachment, MessageTemplate, CustomUser


class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = CustomUser
        fields = ['id', 'username', 'email', 'first_name', 'last_name', 'date_joined']
        read_only_fields = ['date_joined']


class TokenSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField(write_only=True)
    token = serializers.CharField(read_only=True)

    def validate(self, data):
        username = data.get('username')
        password = data.get('password')

        user = authenticate(username=username, password=password)

        if not user:
            raise serializers.ValidationError('Неверные учетные данные')

        if not user.is_active:
            raise serializers.ValidationError('Пользователь неактивен')

        token, created = Token.objects.get_or_create(user=user)

        return {
            'token': token.key,
            'user': UserSerializer(user).data
        }


class CapsuleAttachmentSerializer(serializers.ModelSerializer):
    download_url = serializers.SerializerMethodField()

    class Meta:
        model = CapsuleAttachment
        fields = ['id', 'file_name', 'file_size', 'file_type', 'uploaded_at', 'download_url']
        read_only_fields = fields

    def get_download_url(self, obj):
        return f"/api/attachments/{obj.id}/download/"


class TimeCapsuleSerializer(serializers.ModelSerializer):
    attachments = CapsuleAttachmentSerializer(many=True, read_only=True)
    message_preview = serializers.SerializerMethodField()
    status_display = serializers.CharField(source='get_status_display', read_only=True)

    class Meta:
        model = TimeCapsule
        fields = [
            'id', 'recipient_email', 'scheduled_date', 'status',
            'status_display', 'created_at', 'sent_at', 'failure_reason',
            'attachments', 'message_preview'
        ]
        read_only_fields = ['id', 'created_at', 'sent_at', 'status']

    def get_message_preview(self, obj):
        # Возвращаем превью сообщения (первые 100 символов)
        try:
            decrypted = obj.decrypt_message()
            return decrypted[:100] + '...' if len(decrypted) > 100 else decrypted
        except:
            return '[Зашифрованное сообщение]'

    def validate_scheduled_date(self, value):
        from django.utils import timezone
        if value < timezone.now():
            raise serializers.ValidationError('Дата отправки не может быть в прошлом')
        return value


class CreateCapsuleSerializer(serializers.ModelSerializer):
    message = serializers.CharField(write_only=True)
    attachments = serializers.ListField(
        child=serializers.FileField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = TimeCapsule
        fields = ['recipient_email', 'scheduled_date', 'message', 'attachments']

    def create(self, validated_data):
        # Извлечение сообщения и вложений
        message = validated_data.pop('message')
        attachments = validated_data.pop('attachments', [])

        # Создание капсулы
        capsule = TimeCapsule.objects.create(**validated_data)

        # Шифрование сообщения
        capsule.encrypt_message(message)
        capsule.save()

        # Обработка вложений
        for file in attachments:
            CapsuleAttachment.objects.create(
                capsule=capsule,
                file=file,
                file_name=file.name,
                file_size=file.size,
                file_type=file.content_type
            )

        # Запуск отправки
        from ..tasks import send_time_capsule
        send_time_capsule(capsule.id)

        return capsule


class MessageTemplateSerializer(serializers.ModelSerializer):
    class Meta:
        model = MessageTemplate
        fields = ['id', 'name', 'content', 'category', 'is_active', 'created_at']
        read_only_fields = ['created_at']


class BulkCreateSerializer(serializers.Serializer):
    capsules = CreateCapsuleSerializer(many=True)

    def create(self, validated_data):
        capsules_data = validated_data['capsules']
        capsules = []

        for capsule_data in capsules_data:
            serializer = CreateCapsuleSerializer(data=capsule_data)
            if serializer.is_valid():
                capsule = serializer.save()
                capsules.append(capsule)

        return {'created': len(capsules), 'capsules': capsules}