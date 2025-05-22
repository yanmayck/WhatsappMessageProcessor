from app import db
from datetime import datetime
from sqlalchemy import Column, Integer, String, Text, DateTime, Boolean, ForeignKey
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
    
    def __repr__(self):
        return f'<MediaFile {self.file_name}>'
