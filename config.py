import os
from dotenv import load_dotenv
from database import getconn

load_dotenv()

def get_list_from_env(key, default=""):
    """Converts a comma-separated string from environment variable to a list."""
    value = os.environ.get(key, default)
    return [item.strip() for item in value.split(',') if item.strip()]

class Config:
    # Flask configuration
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')
    
    # Database configuration
    SQLALCHEMY_DATABASE_URI = 'postgresql+pg8000://'
    SQLALCHEMY_ENGINE_OPTIONS = {
        'creator': getconn,
        'pool_size': 5,
        'max_overflow': 2,
        'pool_timeout': 30,
        'pool_recycle': 1800,
    }
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    
    # Evolution API (WhatsApp) Configuration
    EVOLUTION_API_URL = os.environ.get('EVOLUTION_API_URL', 'http://localhost:8080')
    EVOLUTION_API_KEY = os.environ.get('EVOLUTION_API_KEY')
    EVOLUTION_INSTANCE_NAME = os.environ.get('EVOLUTION_INSTANCE_NAME', 'my-instance')
    
    # Webhook configuration
    WEBHOOK_VERIFY_TOKEN = os.environ.get('WEBHOOK_VERIFY_TOKEN', 'your-webhook-verify-token')
    
    # Google Cloud Storage configuration
    GOOGLE_CLOUD_PROJECT_ID = os.environ.get('GOOGLE_CLOUD_PROJECT_ID')
    GOOGLE_CLOUD_BUCKET_NAME = os.environ.get('GOOGLE_CLOUD_BUCKET_NAME')
    
    # Google Maps API configuration
    GOOGLE_MAPS_API_KEY = os.environ.get('GOOGLE_MAPS_API_KEY')
    
    # Company's Default Address for Shipping Calculation
    COMPANY_DEFAULT_ADDRESS = os.environ.get('COMPANY_DEFAULT_ADDRESS', 'Avenida Paulista, 1000, São Paulo, SP, Brasil')
    
    # Gemini AI configuration
    GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')
    
    # Knowledge Base Configuration
    KNOWLEDGE_BASE_FILE = os.environ.get('KNOWLEDGE_BASE_FILE', 'knowledge_base.txt')
    
    # AI Customization
    AI_NAME = os.environ.get('AI_NAME', 'Assistente IA')
    AI_PERSONALITY_DESCRIPTION = os.environ.get(
        'AI_PERSONALITY_DESCRIPTION', 
        "amigável, natural e empático. Use emojis quando apropriado."
    )
    AI_BUSINESS_CONTEXT = os.environ.get(
        'AI_BUSINESS_CONTEXT', 
        "Você é um assistente de uso geral para uma empresa."
    )
    AI_RESPONSE_STYLE = os.environ.get(
        'AI_RESPONSE_STYLE',
        "Responda em parágrafos curtos. Mantenha um tom positivo."
    )
    
    # Vector Database and Embedding Model Configuration
    VECTOR_DB_ENABLED = os.environ.get('VECTOR_DB_ENABLED', 'False').lower() == 'true'
    VECTOR_DB_PROVIDER = os.environ.get('VECTOR_DB_PROVIDER', 'chroma')
    VECTOR_DB_API_KEY = os.environ.get('VECTOR_DB_API_KEY')
    VECTOR_DB_ENVIRONMENT = os.environ.get('VECTOR_DB_ENVIRONMENT')
    VECTOR_DB_INDEX_NAME = os.environ.get('VECTOR_DB_INDEX_NAME', 'company-info')
    VECTOR_DB_URL = os.environ.get('VECTOR_DB_URL')
    
    EMBEDDING_MODEL_PROVIDER = os.environ.get('EMBEDDING_MODEL_PROVIDER', 'google')
    EMBEDDING_MODEL_NAME = os.environ.get('EMBEDDING_MODEL_NAME', 'textembedding-gecko@003')

    # Pushover Notifications Configuration
    PUSHOVER_APP_TOKEN = os.environ.get('PUSHOVER_APP_TOKEN')
    DEFAULT_PUSHOVER_USER_KEY = os.environ.get('DEFAULT_PUSHOVER_USER_KEY')

    # Media processing configuration
    MAX_FILE_SIZE = int(os.environ.get('MAX_FILE_SIZE', 50 * 1024 * 1024))
    ALLOWED_EXTENSIONS_IMAGE = get_list_from_env('ALLOWED_EXTENSIONS_IMAGE', '.jpg,.jpeg,.png,.gif,.webp')
    ALLOWED_EXTENSIONS_AUDIO = get_list_from_env('ALLOWED_EXTENSIONS_AUDIO', '.mp3,.wav,.ogg,.m4a,.opus')
    ALLOWED_EXTENSIONS_VIDEO = get_list_from_env('ALLOWED_EXTENSIONS_VIDEO', '.mp4,.avi,.mov,.webm')
    ALLOWED_EXTENSIONS_DOCUMENT = get_list_from_env('ALLOWED_EXTENSIONS_DOCUMENT', '.pdf,.doc,.docx,.txt')
    
    # Processing configuration
    ENABLE_ASYNC_PROCESSING = os.environ.get('ENABLE_ASYNC_PROCESSING', 'True').lower() == 'true'
    MAX_PROCESSING_THREADS = int(os.environ.get('MAX_PROCESSING_THREADS', '5'))

    # Token for internal task processing
    INTERNAL_TASK_TOKEN = os.environ.get('INTERNAL_TASK_TOKEN', 'super-secret-dev-token')

    # Logging configuration
    LOGGING_LEVEL = os.environ.get('LOGGING_LEVEL', 'INFO').upper()

    # List of phone numbers to ignore
    IGNORE_LIST_NUMBERS = get_list_from_env('IGNORE_LIST_NUMBERS', '5511999998888')
