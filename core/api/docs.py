from django.urls import path
from rest_framework.documentation import include_docs_urls

urlpatterns = [
    path('api/docs/', include_docs_urls(
        title='ChronoMail API',
        description='API для интеграции с системой капсул времени',
        public=True
    )),
]