import json
import logging
import threading
from flask import Blueprint, request, jsonify, current_app
from app import db
from models import Conversation, Message, AIResponse, MediaFile, HumanAgentRequest
from services.whatsapp_service import WhatsAppService
from services.media_processor import MediaProcessor
from services.ai_service import AIService
from services.cloud_storage import CloudStorageService
from config import Config
from typing import Optional, Dict, Any
import requests # Adicionado para Pushover

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__)

# Initialize services
whatsapp_service = WhatsAppService()
media_processor = MediaProcessor()
ai_service = AIService()
cloud_storage = CloudStorageService()

@webhook_bp.route('/webhook/whatsapp', methods=['GET'])
def verify_webhook():
    """Verify WhatsApp webhook (required for setup)"""
    try:
        # WhatsApp sends these parameters for verification
        mode = request.args.get('hub.mode')
        token = request.args.get('hub.verify_token')
        challenge = request.args.get('hub.challenge')
        
        logger.info(f"Webhook verification attempt: mode={mode}, token={token}")
        
        # Verify the token matches what we expect
        if mode == 'subscribe' and token == Config.WEBHOOK_VERIFY_TOKEN:
            logger.info("Webhook verified successfully")
            return challenge, 200
        else:
            logger.warning("Webhook verification failed - invalid token")
            return 'Forbidden', 403
            
    except Exception as e:
        logger.error(f"Webhook verification error: {str(e)}")
        return 'Internal Server Error', 500

@webhook_bp.route('/webhook/whatsapp', methods=['POST'])
def handle_webhook():
    """Handle incoming WhatsApp messages"""
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("Received empty webhook data")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400
        
        logger.info(f"Received webhook data: {json.dumps(data, indent=2)}")
        
        # Extract messages from the webhook data
        entry = data.get('entry', [])
        
        for entry_item in entry:
            changes = entry_item.get('changes', [])
            
            for change in changes:
                value = change.get('value', {})
                messages = value.get('messages', [])
                
                # Process each message
                for message_data in messages:
                    try:
                        # Process the message in a separate thread to avoid blocking
                        if Config.ENABLE_ASYNC_PROCESSING:
                            thread = threading.Thread(
                                target=process_message_async,
                                args=(message_data, value)
                            )
                            thread.daemon = True
                            thread.start()
                        else:
                            process_message_sync(message_data, value)
                            
                    except Exception as e:
                        logger.error(f"Error processing message: {str(e)}")
                        continue
        
        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Webhook handling error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def process_message_async(message_data, webhook_value):
    """Process a message asynchronously"""
    with current_app.app_context():
        process_message_sync(message_data, webhook_value)

def process_message_sync(message_data, webhook_value):
    """Process a single WhatsApp message"""
    processed_media_bytes_for_ai: Optional[bytes] = None
    conversation_id_for_logging = None # Para log em caso de erro antes de message.id estar disponível
    try:
        # Extract message information
        message_id = message_data.get('id')
        from_number = message_data.get('from')
        timestamp = message_data.get('timestamp')
        message_type = message_data.get('type')
        
        logger.info(f"Processing message: {message_id}, type: {message_type}, from: {from_number}")
        
        # Find or create conversation
        conversation = Conversation.query.filter_by(phone_number=from_number).first()
        if not conversation:
            # Get contact name from webhook data if available
            contacts = webhook_value.get('contacts', [])
            contact_name = None
            for contact in contacts:
                if contact.get('wa_id') == from_number:
                    profile = contact.get('profile', {})
                    contact_name = profile.get('name')
                    break
            
            conversation = Conversation(
                phone_number=from_number,
                contact_name=contact_name,
                # Adicionar whatsapp_business_account_id se disponível e necessário para identificar o cliente
                # whatsapp_business_account_id=webhook_value.get('metadata', {}).get('phone_number_id') 
            )
            db.session.add(conversation)
            db.session.commit()
            logger.info(f"Created new conversation for {from_number}, ID: {conversation.id}")
        
        conversation_id_for_logging = conversation.id

        # Check if message already exists (avoid duplicates)
        existing_message = Message.query.filter_by(whatsapp_message_id=message_id).first()
        if existing_message:
            logger.info(f"Message {message_id} already processed")
            return
        
        # Create message record
        message = Message(
            conversation_id=conversation.id,
            whatsapp_message_id=message_id,
            sender_phone=from_number, # Este é o telefone do usuário final
            message_type=message_type,
            is_from_user=True
        )
        
        # Process different message types
        if message_type == 'text':
            text_content = message_data.get('text', {}).get('body', '')
            message.content = text_content
            
        elif message_type in ['image', 'audio', 'video', 'document']:
            media_info = message_data.get(message_type, {})
            media_id = media_info.get('id')
            caption = media_info.get('caption', '')
            filename = media_info.get('filename', f'{message_type}_{message_id}')
            mime_type = media_info.get('mime_type')
            
            message.content = caption
            message.mime_type = mime_type
            message.file_name = filename
            
            media_data = whatsapp_service.download_media(media_id)
            if media_data:
                processed_data, metadata = None, None
                actual_mime_type_for_ai = mime_type
                
                if message_type == 'image':
                    processed_data, metadata = media_processor.process_image(media_data, filename)
                    if metadata and metadata.get('output_format'):
                        actual_mime_type_for_ai = f"image/{metadata['output_format'].lower()}"
                elif message_type == 'audio':
                    processed_data, metadata = media_processor.process_audio(media_data, filename)
                    if metadata and metadata.get('output_format'):
                        actual_mime_type_for_ai = f"audio/{metadata['output_format'].lower()}"
                
                upload_data = processed_data if processed_data else media_data
                processed_media_bytes_for_ai = upload_data
                message.mime_type = actual_mime_type_for_ai
                
                blob_name, public_url = cloud_storage.upload_file(
                    upload_data, 
                    filename, 
                    actual_mime_type_for_ai
                )
                
                if blob_name and public_url:
                    message.cloud_storage_url = public_url
                    media_file = MediaFile(
                        message_id=message.id, # Será definido após o commit da mensagem
                        original_url=media_info.get('url', ''),
                        cloud_storage_bucket=Config.GOOGLE_CLOUD_BUCKET_NAME,
                        cloud_storage_path=blob_name,
                        public_url=public_url,
                        file_name=filename,
                        file_size=len(upload_data),
                        mime_type=mime_type, # mime_type original
                        processing_status='processed'
                    )
                    # Adia o add e commit do media_file para depois que message.id estiver disponível
                else:
                    logger.error(f"Failed to upload media for message {message_id}")
                    message.processing_error = "Failed to upload media to cloud storage"
        
        db.session.add(message)
        db.session.commit() # Commit para message ter um ID

        # Agora que message.id está disponível, podemos adicionar MediaFile se houver
        if 'media_file' in locals() and media_file:
            media_file.message_id = message.id
            db.session.add(media_file)
            db.session.commit()
            logger.info(f"MediaFile record created for message {message.id}")

        # Mark message as read
        whatsapp_service.mark_message_as_read(message_id)
        
        # Generate AI response (esta função agora também lida com HumanAgentRequest)
        ai_response_text, ai_service_response_data = generate_ai_response(message, media_bytes=processed_media_bytes_for_ai)

        # Checar se um HumanAgentRequest foi criado e notificar
        if ai_service_response_data and ai_service_response_data.get("action") == "REQUEST_HUMAN_AGENT":
            human_request_id = ai_service_response_data.get("human_request_id")
            if human_request_id:
                human_request = HumanAgentRequest.query.get(human_request_id)
                if human_request:
                    logger.info(f"Human agent requested (ID: {human_request.id}) for conversation {conversation.id}. Sending Pushover notification.")
                    
                    # Determinar a Pushover User Key
                    # Para agora, usando DEFAULT. No futuro, isso viria de uma config do cliente.
                    # Ex: client_settings = ClientSettings.query.filter_by(waba_id=conversation.whatsapp_business_account_id).first()
                    # pushover_user_key = client_settings.pushover_user_key if client_settings else Config.DEFAULT_PUSHOVER_USER_KEY
                    pushover_user_key = Config.DEFAULT_PUSHOVER_USER_KEY

                    if pushover_user_key:
                        dashboard_url = f"{Config.BASE_URL}/dashboard/human-handoff?conversation_id={conversation.id}"
                        notification_message = f"Nova solicitação para ID conversa: {conversation.id}. Usuário: {conversation.phone_number}. Razão: {human_request.request_reason}"
                        
                        send_pushover_notification(
                            title="Solicitação de Atendimento Humano",
                            message=notification_message,
                            user_key=pushover_user_key,
                            url=dashboard_url,
                            url_title="Abrir no Dashboard"
                            # Você pode adicionar priority=1 para notificações de alta prioridade que podem contornar o modo silencioso do usuário
                            # priority=1 
                        )
                    else:
                        logger.warning(f"Pushover USER_KEY não encontrada para notificar sobre HumanAgentRequest {human_request.id}")
        
        logger.info(f"Message {message_id} (DB ID: {message.id}) processed successfully for conversation {conversation.id}")
        
    except Exception as e:
        logger.error(f"Error processing message {message_data.get('id', 'unknown')} for conversation {conversation_id_for_logging if conversation_id_for_logging else 'unknown'}: {str(e)}", exc_info=True)
        db.session.rollback()

def generate_ai_response(message: Message, media_bytes: Optional[bytes] = None) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Generate AI response for a message.
    Handles HumanAgentRequest creation if AI requests it.
    Returns the AI response text and the raw AI service response data.
    """
    ai_response_text = None
    ai_service_response_data = None
    try:
        conversation = message.conversation # Assumindo que a relação está carregada ou pode ser acessada
        if not conversation:
            logger.error(f"Conversation not found for message {message.id}. Cannot generate AI response.")
            return None, None

        # Get conversation history for AI and for potential handoff
        recent_messages_db = Message.query.filter_by(
            conversation_id=message.conversation_id
        ).order_by(Message.timestamp.asc()).all() # Get all messages in ascending order for full history
        
        # Prepare history for AI (last 10, reversed for AI's typical processing order)
        ai_conversation_history = []
        for msg in reversed(recent_messages_db[-10:]): # Last 10 messages
            ai_conversation_history.append({
                # Usar 'sender_type' em vez de 'is_from_user' para ser mais explícito no AIService
                'sender_type': 'user' if msg.is_from_user else 'assistant',
                'message_text': msg.content or '',
                'message_type': msg.message_type,
                'timestamp': msg.timestamp.isoformat() if msg.timestamp else None
            })
        
        # Prepare full history for potential handoff record (more detailed)
        full_conversation_history_for_handoff = [
            {
                "id": msg.id,
                "whatsapp_message_id": msg.whatsapp_message_id,
                "sender_phone": msg.sender_phone,
                "sender_type": 'user' if msg.is_from_user else 'assistant',
                "text": msg.content,
                "media_url": msg.media_files[0].public_url if msg.media_files else None,
                "timestamp": msg.timestamp.isoformat()
            } for msg in recent_messages_db
        ]

        ai_service_response_data = ai_service.generate_response(
            conversation_id=str(conversation.id), # UID para o Agno Agent
            user_phone_number=conversation.phone_number,
            message_text=message.content,
            message_type=message.message_type,
            media_bytes=media_bytes,
            media_mime_type=message.mime_type,
            conversation_history=ai_conversation_history
        )

        if not ai_service_response_data or not ai_service_response_data.get("response_text"):
            logger.error(f"AI service did not return a valid response for message {message.id}")
            ai_response_text = "Desculpe, não consegui processar sua solicitação no momento."
            # Não criar AIResponse aqui, será tratada pelo fallback
        else:
            ai_response_text = ai_service_response_data.get("response_text")
            logger.info(f"AI response generated for message {message.id}: {ai_response_text[:100]}...")

            # Criar AIResponse no banco de dados
            ai_db_response = AIResponse(
                message_id=message.id,
                response_text=ai_response_text,
                raw_ai_response=ai_service_response_data 
            )
            db.session.add(ai_db_response)
            db.session.commit()

            # Verificar se a IA solicitou um agente humano
            if ai_service_response_data.get("action") == "REQUEST_HUMAN_AGENT":
                logger.info(f"AI requested human agent for conversation {conversation.id} (message {message.id})")
                
                handoff_context = {
                    "reason": ai_service_response_data.get("reason_for_escalation", "Solicitado pela IA"),
                    "conversation_history": full_conversation_history_for_handoff, # Usar o histórico completo
                    "ai_confidence": ai_service_response_data.get("ai_confidence"),
                    "suggested_next_steps_for_human": ai_service_response_data.get("suggested_next_steps_for_human")
                }

                human_request = HumanAgentRequest(
                    conversation_id=conversation.id,
                    message_id_trigger=message.id,
                    request_reason=handoff_context["reason"],
                    status="pending",
                    context_data=handoff_context,
                    ai_confidence=handoff_context.get("ai_confidence")
                )
                db.session.add(human_request)
                db.session.commit()
                logger.info(f"HumanAgentRequest {human_request.id} created for conversation {conversation.id}")
                # Adicionar o ID ao response_data para que a função chamadora possa acessá-lo
                ai_service_response_data["human_request_id"] = human_request.id


        # Enviar resposta via WhatsApp
        if ai_response_text: # Enviar apenas se houver um texto de resposta
            whatsapp_service.send_message(
                to_number=conversation.phone_number,
                message_text=ai_response_text
            )
        else: # Fallback se não houve resposta da IA
            fallback_message = "Não consegui entender sua última mensagem. Poderia tentar de outra forma?"
            whatsapp_service.send_message(
                to_number=conversation.phone_number,
                message_text=fallback_message
            )
            # Registrar que um fallback foi usado
            ai_db_response = AIResponse(
                message_id=message.id,
                response_text=fallback_message,
                raw_ai_response={"error": "No AI response text, fallback used."},
                is_fallback=True
            )
            db.session.add(ai_db_response)
            db.session.commit()
        
        return ai_response_text, ai_service_response_data

    except Exception as e:
        logger.error(f"Error in generate_ai_response for message {message.id if message else 'unknown'}: {str(e)}", exc_info=True)
        db.session.rollback()
        # Tentar enviar uma mensagem de erro genérica se possível
        if message and message.conversation:
            try:
                whatsapp_service.send_message(
                    to_number=message.conversation.phone_number,
                    message_text="Ocorreu um erro ao processar sua solicitação. Tente novamente mais tarde."
                )
            except Exception as send_err:
                logger.error(f"Falha ao enviar mensagem de erro para {message.conversation.phone_number}: {send_err}")
        return None, None

def send_pushover_notification(title: str, message: str, user_key: str, app_token: str = Config.PUSHOVER_APP_TOKEN, **kwargs: Optional[Dict[str, Any]]):
    """Envia uma notificação via Pushover."""
    if not app_token or not user_key:
        logger.warning("Pushover APP_TOKEN ou USER_KEY não configurados. Notificação não enviada.")
        return

    payload = {
        "token": app_token,
        "user": user_key,
        "title": title,
        "message": message,
    }
    # Adicionar quaisquer outros parâmetros opcionais suportados pela API Pushover (ex: url, url_title, priority, sound)
    for key, value in kwargs.items():
        if value is not None: # Garantir que apenas valores não nulos sejam adicionados
            payload[key] = value

    try:
        response = requests.post("https://api.pushover.net/1/messages.json", data=payload, timeout=10)
        response.raise_for_status()  # Levanta um erro para respostas 4xx/5xx
        logger.info(f"Pushover notification sent successfully to user_key: {user_key[:5]}...") # Log apenas parte da chave
    except requests.exceptions.RequestException as e:
        logger.error(f"Error sending Pushover notification: {str(e)}")
