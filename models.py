from app import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey, func, JSON
from sqlalchemy.orm import relationship

class Conversation(db.Model):
    __tablename__ = 'conversations'
    
    id = Column(Integer, primary_key=True)
    phone_number = Column(String(20), nullable=False, index=True)
    contact_name = Column(String(100))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    # Relationship with messages
    messages = relationship("Message", back_populates="conversation", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Conversation {self.phone_number}>'

class Message(db.Model):
    __tablename__ = 'messages'
    
    id = Column(Integer, primary_key=True)
    conversation_id = Column(Integer, ForeignKey('conversations.id'), nullable=False)
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
    timestamp = Column(DateTime, default=datetime.utcnow)
    processed = Column(Boolean, default=False)
    ai_response_sent = Column(Boolean, default=False)
    processing_error = Column(Text)
    
    # Relationship with conversation
    conversation = relationship("Conversation", back_populates="messages")
    
    # Relationship with AI responses
    ai_responses = relationship("AIResponse", back_populates="message", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f'<Message {self.whatsapp_message_id}>'

class AIResponse(db.Model):
    __tablename__ = 'ai_responses'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), nullable=False)
    agent_name = Column(String(100), nullable=False)  # Which agno agent processed this
    response_content = Column(Text, nullable=False)
    processing_time = Column(Integer)  # Time in milliseconds
    model_used = Column(String(50))  # gemini-2.0-flash-exp, etc.
    created_at = Column(DateTime, default=datetime.utcnow)
    sent_to_whatsapp = Column(Boolean, default=False)
    whatsapp_response_id = Column(String(100))
    
    # Relationship with message
    message = relationship("Message", back_populates="ai_responses")
    
    def __repr__(self):
        return f'<AIResponse for message {self.message_id}>'

class MediaFile(db.Model):
    __tablename__ = 'media_files'
    
    id = Column(Integer, primary_key=True)
    message_id = Column(Integer, ForeignKey('messages.id'), nullable=False)
    original_url = Column(String(500), nullable=False)
    cloud_storage_bucket = Column(String(100), nullable=False)
    cloud_storage_path = Column(String(500), nullable=False)
    public_url = Column(String(500))
    file_name = Column(String(200), nullable=False)
    file_size = Column(Integer)
    mime_type = Column(String(100))
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    processing_status = Column(String(20), default='pending')  # pending, processed, error
    
    # Adicionando relacionamento reverso para fácil acesso a partir da Mensagem, se necessário
    # message = relationship("Message", back_populates="media_files_associated") # Descomente se criar media_files_associated em Message

    def __repr__(self):
        return f'<MediaFile {self.file_name}>'

class HumanAgentRequest(db.Model):
    __tablename__ = 'human_agent_requests' # Nome da tabela corrigido para plural e snake_case
    id = db.Column(db.Integer, primary_key=True)
    conversation_id = db.Column(db.Integer, db.ForeignKey('conversations.id'), nullable=False) # ForeignKey para 'conversations.id'
    phone_number = db.Column(db.String(30), nullable=False)
    contact_name = db.Column(db.String(150), nullable=True)
    request_time = db.Column(db.DateTime, server_default=func.now())
    status = db.Column(db.String(50), default='pending', nullable=False) # pending, assigned, resolved_by_human, resolved_by_ai, closed
    
    # Novos campos para contexto e escalonamento
    last_message_id_before_escalation = db.Column(db.Integer, db.ForeignKey('messages.id'), nullable=True)
    escalation_reason = db.Column(db.String(100), nullable=True) # ex: user_explicit_request, ai_unable_to_answer, detected_frustration
    ai_summary_of_issue = db.Column(db.Text, nullable=True) # Resumo gerado pela IA
    full_conversation_history_json = db.Column(JSON, nullable=True) # Snapshot do histórico da conversa no momento do escalonamento

    # Campos para o agente humano
    assigned_agent_id = db.Column(db.String(100), nullable=True) # ID ou nome do agente humano
    assigned_time = db.Column(db.DateTime, nullable=True)
    resolution_notes = db.Column(db.Text, nullable=True) # Notas do agente humano sobre a resolução
    closed_time = db.Column(db.DateTime, nullable=True)

    # Relacionamentos
    conversation = db.relationship('Conversation', backref=db.backref('human_agent_requests', lazy='dynamic', cascade="all, delete-orphan"))
    last_message_before_escalation = db.relationship('Message', foreign_keys=[last_message_id_before_escalation])

    def __repr__(self):
        return f'<HumanAgentRequest id={self.id} phone={self.phone_number} status={self.status} time={self.request_time}>'
