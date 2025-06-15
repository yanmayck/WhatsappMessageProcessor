from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, UniqueConstraint, Index, JSON
from sqlalchemy.sql import func
from datetime import datetime, timezone
from extensions import db
from sqlalchemy.orm import relationship

# Defina o nome do schema se estiver usando PostgreSQL e um schema específico
# SCHEMA_NAME = "whatsapp_schema" # Exemplo
SCHEMA_NAME = None # Defina como None se não estiver usando um schema ou para outros DBs

# Classe base para os modelos, pode incluir colunas comuns como created_at, updated_at
class BaseModel(db.Model):
    __abstract__ = True # Indica que esta classe não é mapeada para uma tabela
    # __table_args__ = {"schema": SCHEMA_NAME} if SCHEMA_NAME else {}

    id = Column(Integer, primary_key=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

class Conversation(BaseModel):
    __tablename__ = 'conversations'
    # __table_args__ = BaseModel.__table_args__.copy()
    # __table_args__["comment"] = "Tabela para armazenar conversas com usuários"
    
    user_phone = Column(String(20), nullable=False, unique=True, index=True)
    contact_name = Column(String(100))
    is_active = Column(Boolean, default=True)
    
    # Relationship with messages
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    # Relationship with user profile
    profile = relationship("UserProfile", back_populates="conversation", uselist=False, cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Conversation {self.user_phone}>'

class UserProfile(BaseModel):
    __tablename__ = 'user_profiles'
    
    conversation_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.conversations.id' if SCHEMA_NAME else 'conversations.id'), nullable=False, unique=True, index=True)
    
    # Usar JSON para armazenar dados de perfil de forma flexível (ex: {'name': 'João', 'address': 'Rua X, 123'})
    profile_data = Column(JSON, nullable=False, default={})
    
    # Relationship with conversation
    conversation = relationship("Conversation", back_populates="profile")

    def __repr__(self):
        return f'<UserProfile for Conversation {self.conversation_id}>'

class Order(BaseModel):
    __tablename__ = 'orders'
    
    conversation_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.conversations.id' if SCHEMA_NAME else 'conversations.id'), nullable=False, index=True)
    
    # Usar JSON para armazenar detalhes do pedido de forma flexível
    # Ex: {"items": [{"name": "Pizza de Calabresa", "quantity": 1}, {"name": "Refrigerante", "quantity": 2}], "total": 55.50}
    order_details = Column(JSON, nullable=False)
    
    # Status do pedido, ex: 'completed', 'pending', 'canceled'
    status = Column(String, nullable=False, default='completed', index=True)

    # Relacionamento (um pedido pertence a uma conversa)
    conversation = relationship("Conversation")

    def __repr__(self):
        return f'<Order {self.id} for Conversation {self.conversation_id}>'

class Message(BaseModel):
    __tablename__ = 'messages'
    
    conversation_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.conversations.id' if SCHEMA_NAME else 'conversations.id'), nullable=False, index=True)
    whatsapp_message_id = Column(String(100), unique=True, nullable=False)
    sender_phone = Column(String(20), nullable=False)
    message_type = Column(String(20), nullable=False)  # text, image, audio, video, document
    content = Column(Text)  # Text content or description
    media_url = Column(String(500))  # Original WhatsApp media URL
    cloud_storage_url = Column(String(500))  # Google Cloud Storage URL
    file_name = Column(String(200))
    file_size = Column(Integer)
    mime_type = Column(String(100))
    is_from_user = Column(Boolean, default=True)
    is_reply_to_admin = Column(Boolean, default=False)  # Nova coluna para identificar respostas ao admin
    replied_to_message_id = Column(String(100))  # ID da mensagem que está sendo respondida
    timestamp = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processed = Column(Boolean, default=False)
    ai_response_sent = Column(Boolean, default=False)
    processing_error = Column(Text)
    
    # Relationship with conversation
    conversation = relationship("Conversation", back_populates="messages")
    
    # Relationship with AI responses
    ai_responses = relationship("AIResponse", back_populates="message", cascade="all, delete-orphan")
    
    # Relationship with MediaFiles (uma mensagem pode ter vários arquivos de mídia)
    media_files = relationship("MediaFile", back_populates="message", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Message {self.whatsapp_message_id}>'

class AIResponse(BaseModel):
    __tablename__ = 'ai_responses'
    
    message_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.messages.id' if SCHEMA_NAME else 'messages.id'), nullable=False, index=True)
    agent_name = Column(String(100), nullable=False)  # Which agno agent processed this
    response_content = Column(Text, nullable=False)
    processing_time = Column(Integer)  # Time in milliseconds
    model_used = Column(String(50))  # gemini-2.0-flash-exp, etc.
    sent_to_whatsapp = Column(Boolean, default=False)
    whatsapp_response_id = Column(String(100))
    
    # Relationship with message
    message = relationship("Message", back_populates="ai_responses")
    
    def __repr__(self):
        return f'<AIResponse for message {self.message_id}>'

class MediaFile(BaseModel):
    __tablename__ = 'media_files'
    # __table_args__ = BaseModel.__table_args__.copy()
    # __table_args__["comment"] = "Tabela para armazenar informações de arquivos de mídia"
    
    message_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.messages.id' if SCHEMA_NAME else 'messages.id'), nullable=False, index=True)
    original_url = Column(String(500), nullable=False)
    cloud_storage_bucket = Column(String(100), nullable=False)
    cloud_storage_path = Column(String(500), nullable=False)
    public_url = Column(String(500))
    file_name = Column(String(200), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    uploaded_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    processing_status = Column(String(20), default='pending')  # pending, processed, error
    
    # Adicionando relacionamento reverso para fácil acesso a partir da Mensagem, se necessário
    # message = relationship("Message", back_populates="media_files_associated") # Descomente se criar media_files_associated em Message
    # CORRIGIDO: Definindo o relacionamento message
    message = relationship("Message", back_populates="media_files")

    def __repr__(self):
        return f'<MediaFile {self.file_name}>'

class HumanAgentRequest(BaseModel):
    __tablename__ = 'human_agent_requests' # Nome da tabela corrigido para plural e snake_case
    conversation_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.conversations.id' if SCHEMA_NAME else 'conversations.id'), nullable=False, index=True)
    phone_number = Column(String(30), nullable=False)
    contact_name = Column(String(150), nullable=True)
    request_time = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(50), default='pending', nullable=False) # pending, assigned, resolved_by_human, resolved_by_ai, closed
    
    # Novos campos para contexto e escalonamento
    last_message_id_before_escalation = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.messages.id' if SCHEMA_NAME else 'messages.id'), nullable=True)
    escalation_reason = Column(String(100), nullable=True) # ex: user_explicit_request, ai_unable_to_answer, detected_frustration
    ai_summary_of_issue = Column(Text, nullable=True) # Resumo gerado pela IA
    full_conversation_history_json = Column(JSON, nullable=True) # Snapshot do histórico da conversa no momento do escalonamento

    # Campos para o agente humano
    assigned_agent_id = Column(String(100), nullable=True) # ID ou nome do agente humano
    assigned_time = Column(DateTime, nullable=True)
    resolution_notes = Column(Text, nullable=True) # Notas do agente humano sobre a resolução
    closed_time = Column(DateTime, nullable=True)

    # Relacionamentos
    conversation = relationship('Conversation', backref=db.backref('human_agent_requests', lazy='dynamic', cascade="all, delete-orphan"))
    last_message_before_escalation = relationship('Message', foreign_keys=[last_message_id_before_escalation])

    def __repr__(self):
        return f'<HumanAgentRequest id={self.id} phone={self.phone_number} status={self.status} time={self.request_time}>'

class SilentMode(BaseModel):
    __tablename__ = 'silent_mode'
    # __table_args__ = BaseModel.__table_args__.copy()
    # __table_args__["comment"] = "Tabela para controlar o modo silencioso das conversas"
    
    conversation_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.conversations.id' if SCHEMA_NAME else 'conversations.id'), nullable=False, index=True)
    enabled_by = Column(String(100), nullable=False)  # Quem ativou o modo silencioso
    enabled_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    expires_at = Column(DateTime, nullable=False)  # Quando o modo silencioso expira
    is_active = Column(Boolean, default=True)
    
    # Relacionamento com a conversa
    conversation = relationship("Conversation", backref=db.backref('silent_mode', lazy=True))
    
    @staticmethod
    def is_conversation_silent(conversation_id):
        """Verifica se uma conversa está em modo silencioso"""
        now = datetime.now(timezone.utc)
        silent = SilentMode.query.filter_by(
            conversation_id=conversation_id,
            is_active=True
        ).filter(SilentMode.expires_at > now).first()
        return bool(silent)
    
    def __repr__(self):
        return f'<SilentMode {self.conversation_id} expires={self.expires_at}>'

class CompanyInfo(BaseModel):
    __tablename__ = 'company_info'
    # __table_args__ = BaseModel.__table_args__.copy()
    # __table_args__["comment"] = "Tabela para armazenar informações da empresa para o banco vetorial"

    info_type = Column(String(100), nullable=False)  # Ex: 'sobre_nos', 'produto_x', 'faq_y'

class VectorEmbedding(BaseModel):
    __tablename__ = 'vector_embeddings'
    # __table_args__ = BaseModel.__table_args__.copy()
    # __table_args__["comment"] = "Tabela para armazenar embeddings vetoriais"

    company_info_id = Column(Integer, ForeignKey(f'{SCHEMA_NAME}.company_info.id' if SCHEMA_NAME else 'company_info.id'), nullable=False, index=True)
    embedding = Column(Text, nullable=False)  # Store embedding as text, or use a specific type if your DB supports it (e.g., ARRAY or a vector type)
    model_name = Column(String(100)) # e.g., 'text-embedding-ada-002'

    company_info = relationship("CompanyInfo", backref=db.backref('vector_embeddings', lazy=True, cascade="all, delete-orphan"))

    def __repr__(self):
        return f'<VectorEmbedding for CompanyInfo {self.company_info_id}>'

# Adicionar Índices (Opcional, mas bom para performance)
Index('idx_messages_conversation_timestamp', Message.conversation_id, Message.timestamp)
Index('idx_ai_responses_message_created', AIResponse.message_id, AIResponse.created_at)
Index('idx_media_files_message', MediaFile.message_id)
Index('idx_human_agent_requests_conversation_created', HumanAgentRequest.conversation_id, HumanAgentRequest.created_at)
Index('idx_silent_mode_conversation_active_expires', SilentMode.conversation_id, SilentMode.is_active, SilentMode.expires_at)
Index('idx_user_profiles_conversation', UserProfile.conversation_id)
Index('idx_orders_conversation_status', Order.conversation_id, Order.status)
Index('idx_company_info_type', CompanyInfo.info_type)
Index('idx_vector_embeddings_company_info', VectorEmbedding.company_info_id)
