import os

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SESSION_SECRET', 'dev-secret-key-change-in-production')
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = os.environ.get('DATABASE_URL', 'sqlite:///whatsapp_ai.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # WhatsApp API configuration (waho - unofficial API)
    WHATSAPP_API_URL = os.environ.get('WHATSAPP_API_URL', 'https://api.waho.com')
    WHATSAPP_API_TOKEN = os.environ.get('WHATSAPP_API_TOKEN', 'your-waho-api-token')
    WHATSAPP_PHONE_NUMBER_ID = os.environ.get('WHATSAPP_PHONE_NUMBER_ID', 'your-phone-number-id')
    
    # Webhook configuration
    WEBHOOK_VERIFY_TOKEN = os.environ.get('WEBHOOK_VERIFY_TOKEN', 'your-webhook-verify-token')
    
    # Google Cloud Storage configuration
    GOOGLE_CLOUD_PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT_ID', 'your-project-id')
    GOOGLE_CLOUD_BUCKET_NAME = os.environ.get('GOOGLE_CLOUD_BUCKET_NAME', 'whatsapp-media-bucket')
    GOOGLE_APPLICATION_CREDENTIALS = os.environ.get('GOOGLE_APPLICATION_CREDENTIALS')
    
    # Gemini AI configuration
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # Configurações do Pushover para Notificações
    PUSHOVER_APP_TOKEN = os.environ.get('PUSHOVER_APP_TOKEN') # Token da sua aplicação Pushover
    DEFAULT_PUSHOVER_USER_KEY = os.environ.get('DEFAULT_PUSHOVER_USER_KEY') # User Key para testes ou fallback

    # Media processing configuration
    MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB
    ALLOWED_EXTENSIONS = {
        'image': ['.jpg', '.jpeg', '.png', '.gif', '.webp'],
        'audio': ['.mp3', '.wav', '.ogg', '.m4a', '.opus'],
        'video': ['.mp4', '.avi', '.mov', '.webm'],
        'document': ['.pdf', '.doc', '.docx', '.txt']
    }
    
    # Processing configuration
    ENABLE_ASYNC_PROCESSING = True
    MAX_PROCESSING_THREADS = 5

    # Token for internal task processing (e.g., called by Cloud Scheduler)
    INTERNAL_TASK_TOKEN = os.environ.get('INTERNAL_TASK_TOKEN', 'super-secret-dev-token-change-me')

    # Configuração do logging
    LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'INFO').upper()
