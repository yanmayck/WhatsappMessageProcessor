import json
import logging
import threading
from flask import Blueprint, request, jsonify, current_app
from app import db
from models import Conversation, Message, AIResponse, MediaFile, HumanAgentRequest, UserProfile, Order
from services.whatsapp_service import WhatsAppService
from services.media_processor import MediaProcessor
from services.ai_service import AIService
from services.cloud_storage import CloudStorageService
from config import Config
from typing import Optional, Dict, Any, List
import requests # Adicionado para Pushover

logger = logging.getLogger(__name__)

webhook_bp = Blueprint('webhook', __name__)

# Initialize services
whatsapp_service = WhatsAppService()
media_processor = MediaProcessor()
ai_service = AIService()
cloud_storage = CloudStorageService()

@webhook_bp.route('/whatsapp', methods=['GET'])
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

@webhook_bp.route('/whatsapp', methods=['POST'])
def handle_webhook():
    """Handle incoming WhatsApp messages"""
    try:
        data = request.get_json()
        
        if not data:
            logger.warning("Received empty webhook data")
            return jsonify({'status': 'error', 'message': 'No data received'}), 400
        
        # Verify API Key from Evolution API
        received_api_key = data.get('apikey')
        if not received_api_key or received_api_key != Config.EVOLUTION_API_KEY:
            logger.warning(f"Webhook authentication failed. Received API Key: {received_api_key}")
            return jsonify({'status': 'error', 'message': 'Forbidden'}), 403
        
        logger.info(f"Received webhook data: {json.dumps(data, indent=2)}")
        
        # Check for the new event type
        if data.get('event') == 'messages.upsert':
            message_payload = data.get('data')
            if message_payload:
                try:
                    # Pass the inner 'data' object as message_data, and the root 'data' as webhook_context_data
                    if Config.ENABLE_ASYNC_PROCESSING:
                        flask_app = current_app._get_current_object() # Obter a instância real da app
                        thread = threading.Thread(
                            target=process_message_async,
                            args=(flask_app, message_payload, data) # Passar flask_app como primeiro argumento
                        )
                        thread.daemon = True
                        thread.start()
                    else:
                        process_message_sync(message_payload, data) # Pass full data as second arg for context
                except Exception as e:
                    logger.error(f"Error processing 'messages.upsert' event: {str(e)}")
            else:
                logger.warning("Event 'messages.upsert' received but no 'data' payload found.")

        # Retain old logic for compatibility or other event types if necessary
        elif 'entry' in data: 
            entry = data.get('entry', [])
            for entry_item in entry:
                changes = entry_item.get('changes', [])
                for change in changes:
                    value = change.get('value', {})
                    messages = value.get('messages', [])
                    for message_data_old_format in messages:
                        try:
                            if Config.ENABLE_ASYNC_PROCESSING:
                                flask_app = current_app._get_current_object() # Obter a instância real da app
                                thread = threading.Thread(
                                    target=process_message_async,
                                    args=(flask_app, message_data_old_format, value) # Passar flask_app
                                )
                                thread.daemon = True
                                thread.start()
                            else:
                                process_message_sync(message_data_old_format, value)
                        except Exception as e:
                            logger.error(f"Error processing message (old format): {str(e)}")
                            continue
        else:
            logger.warning(f"Received webhook data with unknown structure or event type: {data.get('event')}")

        return jsonify({'status': 'success'}), 200
        
    except Exception as e:
        logger.error(f"Webhook handling error: {str(e)}")
        return jsonify({'status': 'error', 'message': str(e)}), 500

def process_message_async(app, message_data, webhook_context_data): # Adicionado app como parâmetro
    """Process a message asynchronously"""
    with app.app_context(): # Usar a instância 'app' passada
        process_message_sync(message_data, webhook_context_data)

def process_message_sync(message_data, webhook_context_data): # Renamed webhook_value for clarity
    """Process a single WhatsApp message (handles both old and new formats via duck-typing in extraction)"""
    processed_media_bytes_for_ai: Optional[bytes] = None
    conversation_id_for_logging = None
    
    is_new_format = 'key' in message_data and 'messageTimestamp' in message_data # Heuristic for new format

    try:
        if is_new_format:
            message_id = message_data.get('key', {}).get('id')
            from_number = message_data.get('key', {}).get('remoteJid')
            # Ensure from_number is stripped of any server details if present (e.g. @s.whatsapp.net)
            if from_number and '@' in from_number:
                from_number = from_number.split('@')[0]
            
            # ---> VERIFICAÇÃO DA LISTA DE IGNORADOS <---
            if from_number in Config.IGNORE_LIST_NUMBERS:
                logger.info(f"Mensagem de um número na lista de ignorados ({from_number}). Ignorando.")
                return # Para o processamento aqui

            timestamp_val = message_data.get('messageTimestamp') # This is a Unix timestamp
            message_type_raw = message_data.get('messageType') # e.g., "conversation", "imageMessage"
            
            # Normalize message_type to existing categories if possible
            if message_type_raw == 'conversation':
                message_type = 'text'
            elif message_type_raw == 'imageMessage':
                message_type = 'image'
            elif message_type_raw == 'audioMessage': # Assuming 'audioMessage' based on 'imageMessage'
                message_type = 'audio'
            elif message_type_raw == 'videoMessage': # Assuming 'videoMessage'
                message_type = 'video'
            elif message_type_raw == 'documentMessage': # Assuming 'documentMessage'
                 message_type = 'document'
            elif message_type_raw == 'locationMessage': # Novo tipo de mensagem
                 message_type = 'location'
            else:
                message_type = message_type_raw # Keep original if no direct mapping
            
            contact_name = message_data.get('pushName')
            
            # For logging, use the instanceId from the new format if available
            instance_id_for_logging = webhook_context_data.get('instance') 
            logger.info(f"Processing message (new format): {message_id}, type: {message_type_raw} (normalized to {message_type}), from: {from_number}, instance: {instance_id_for_logging}")

        else: # Old format extraction
            message_id = message_data.get('id')
            from_number = message_data.get('from')
            
            # ---> VERIFICAÇÃO DA LISTA DE IGNORADOS (também para o formato antigo) <---
            if from_number in Config.IGNORE_LIST_NUMBERS:
                logger.info(f"Mensagem de um número na lista de ignorados ({from_number}). Ignorando.")
                return # Para o processamento aqui

            timestamp_val = message_data.get('timestamp') # Already a string timestamp for old format?
            message_type = message_data.get('type')
            logger.info(f"Processing message (old format): {message_id}, type: {message_type}, from: {from_number}")
            # Contact name extraction for old format
            contacts = webhook_context_data.get('contacts', []) # webhook_context_data is 'value' for old fmt
            contact_name = None
            for contact in contacts:
                if contact.get('wa_id') == from_number:
                    profile = contact.get('profile', {})
                    contact_name = profile.get('name')
                    break

        # Find or create conversation
        conversation = Conversation.query.filter_by(user_phone=from_number).first()
        if not conversation:
            conversation = Conversation(
                user_phone=from_number,
                contact_name=contact_name,
                # whatsapp_business_account_id for new format might come from webhook_context_data.get('sender') if it represents the business account ID
                # or from a fixed config if the instance implies the business account.
                # For old format: webhook_context_data.get('metadata', {}).get('phone_number_id')
            )
            db.session.add(conversation)
            db.session.commit()
            logger.info(f"Created new conversation for {from_number} (Name: {contact_name}), ID: {conversation.id}")
        elif not conversation.contact_name and contact_name: # Update contact name if it was missing
            conversation.contact_name = contact_name
            db.session.commit()
            logger.info(f"Updated contact name for {from_number} to {contact_name}")

        conversation_id_for_logging = conversation.id

        existing_message = Message.query.filter_by(whatsapp_message_id=message_id).first()
        if existing_message:
            logger.info(f"Message {message_id} already processed")
            return
        
        message = Message(
            conversation_id=conversation.id,
            whatsapp_message_id=message_id,
            sender_phone=from_number,
            message_type=message_type, # Normalized type
            is_from_user=True,
            # timestamp field in Message model needs to handle Unix timestamp or string
            # Assuming it can handle it, or needs conversion here.
            # For now, passing as is. If timestamp_val is Unix, and DB expects datetime:
            # timestamp=datetime.fromtimestamp(int(timestamp_val)) if is_new_format and timestamp_val else timestamp_val
        )
        if timestamp_val: # Add timestamp if available
            try:
                # If new format, timestamp is Unix epoch. If old, it might be different.
                # Assuming Message.timestamp can handle datetime objects.
                from datetime import datetime
                if isinstance(timestamp_val, (int, float, str)) and str(timestamp_val).isdigit():
                     message.timestamp = datetime.fromtimestamp(int(str(timestamp_val)))
                # else: # Potentially handle other old formats if they exist
                #    message.timestamp = parse_some_other_format(timestamp_val)
            except ValueError as ve:
                logger.warning(f"Could not parse timestamp {timestamp_val}: {ve}")


        if message_type == 'text':
            if is_new_format:
                text_content = message_data.get('message', {}).get('conversation', '')
            else: # Old format
                text_content = message_data.get('text', {}).get('body', '')
            message.content = text_content
            
        elif message_type == 'location':
            if is_new_format:
                location_payload = message_data.get('message', {}).get('locationMessage', {})
                latitude = location_payload.get('degreesLatitude')
                longitude = location_payload.get('degreesLongitude')
                if latitude is not None and longitude is not None:
                    # Salvar as coordenadas como um JSON no conteúdo da mensagem para o histórico.
                    message.content = json.dumps({'latitude': latitude, 'longitude': longitude})
                    logger.info(f"Received location: lat={latitude}, lon={longitude}")
                else:
                    message.content = "Received a location message with missing coordinates."
                    message.processing_error = "Missing coordinates in locationMessage"
            else:
                # Adicionar lógica para o formato antigo se ele também puder enviar localizações.
                # Por agora, assumimos que não é suportado ou é igual.
                logger.warning("Location message processing not implemented for old format.")
                message.content = "Location message from old format not supported."
                message.processing_error = "Unsupported location message format"
            
        elif message_type in ['image', 'audio', 'video', 'document']:
            if is_new_format:
                media_object_key = message_type_raw # e.g., "audioMessage", "imageMessage"
                media_specific_payload = message_data.get('message', {}).get(media_object_key, {})
                
                download_url = media_specific_payload.get('url')
                media_key = media_specific_payload.get('mediaKey') # Pode ser usado como fallback ou ID alternativo
                mime_type = media_specific_payload.get('mimetype')
                
                # Caption pode estar em lugares diferentes dependendo da API ou tipo de mídia.
                # Tentativa 1: Dentro do objeto específico da mídia (ex: imageMessage.caption)
                caption = media_specific_payload.get('caption')
                # Tentativa 2: Diretamente no objeto 'message' (comum para alguns tipos de mídia)
                if not caption:
                    caption = message_data.get('message', {}).get('caption')
                # Tentativa 3: Para "text" dentro de "extendedTextMessage" que acompanha mídia (se aplicável à Evolution)
                if not caption and message_data.get('message', {}).get('extendedTextMessage', {}).get('text'):
                    caption = message_data.get('message', {}).get('extendedTextMessage', {}).get('text')


                message.content = caption if caption else f"Received {message_type_raw}"
                message.mime_type = mime_type
                
                # Gerar um nome de arquivo se não estiver disponível
                # A Evolution API pode fornecer 'fileName' em media_specific_payload para alguns tipos.
                filename = media_specific_payload.get('fileName')
                if not filename:
                    extension_from_mime = mime_type.split('/')[-1].split(';')[0] if mime_type else message_type
                    filename = f"{message_type}_{message_id}.{extension_from_mime}"
                message.file_name = filename

                if download_url or media_key:
                    logger.info(f"Attempting to download media for new format: url={bool(download_url)}, media_key={media_key}")
                    # Passar message_type_raw (ex: "audioMessage") para que o serviço possa determinar o app_info correto para HKDF.
                    media_data_bytes = whatsapp_service.download_media(
                        media_url=download_url, 
                        media_key_b64=media_key, 
                        original_message_type=message_type_raw # ex: "audioMessage"
                    )
                    
                    if media_data_bytes: # Agora media_data_bytes são os bytes descriptografados
                        # A IA deve sempre receber os bytes originais e descriptografados para melhor análise.
                        processed_media_bytes_for_ai = media_data_bytes
                        
                        # Para o upload na nuvem, podemos usar uma versão processada e padronizada.
                        upload_data_bytes = media_data_bytes
                        upload_mime_type = mime_type
                        
                        if message_type == 'image':
                            processed_for_upload, metadata = media_processor.process_image(media_data_bytes, filename)
                            if processed_for_upload:
                                upload_data_bytes = processed_for_upload
                                if metadata and metadata.get('output_format'):
                                    upload_mime_type = f"image/{metadata['output_format'].lower()}"
                        elif message_type == 'audio':
                            processed_for_upload, metadata = media_processor.process_audio(media_data_bytes, filename)
                            if processed_for_upload:
                                upload_data_bytes = processed_for_upload
                                if metadata and metadata.get('output_format'):
                                   upload_mime_type = f"audio/{metadata['output_format'].lower()}"
                        
                        # O mime_type da mensagem no banco deve refletir o que foi salvo na nuvem.
                        message.mime_type = upload_mime_type
                        
                        blob_name, public_url = cloud_storage.upload_file(
                            upload_data_bytes, 
                            filename, 
                            upload_mime_type
                        )
                        
                        if blob_name and public_url:
                            message.cloud_storage_url = public_url
                            media_file_obj = MediaFile(
                                original_url=download_url, # Salvar o URL original de onde baixamos
                                cloud_storage_bucket=Config.GOOGLE_CLOUD_BUCKET_NAME,
                                cloud_storage_path=blob_name,
                                public_url=public_url,
                                file_name=filename,
                                file_size=len(upload_data_bytes),
                                mime_type=mime_type, # Mime type original da Evolution API
                                processing_status='processed'
                            )
                        else:
                            logger.error(f"Failed to upload media for message {message_id} (new format)")
                            message.processing_error = "Failed to upload media to cloud storage (new format)"
                    else:
                        logger.error(f"Failed to download media for message {message_id} (new format) using url/media_key")
                        message.processing_error = "Failed to download media from WhatsApp (new format)"
                else:
                    logger.warning(f"No download_url or media_key found for media message {message_id} (new format)")
                    message.processing_error = "No download information for media (new format)"
            
            else: # Old format media processing (existing logic)
                media_info = message_data.get(message_type, {}) # e.g. message_data.get('image', {})
                media_id = media_info.get('id') # This is the Meta media ID
                caption = media_info.get('caption', '')
                # Use a more specific filename if available from the message, else default
                base_filename = media_info.get('filename', f'{message_type}_{message_id}')
                # Ensure filename has an extension based on mime_type if not present
                # This is a simplified example; a proper mime-to-extension mapping might be needed
                if '.' not in base_filename and media_info.get('mime_type'):
                    extension = media_info.get('mime_type').split('/')[-1]
                    if extension:
                         base_filename = f"{base_filename}.{extension}"
                
                filename = base_filename

                message.content = caption # Caption for the message
                message.mime_type = media_info.get('mime_type') # Original mime_type
                message.file_name = filename

                # This download_media is for the OLD API. It might need adjustment or a new method for new API.
                media_data_bytes = whatsapp_service.download_media(media_id) 
                if media_data_bytes:
                    processed_data_bytes, processing_metadata = None, None
                    actual_mime_type_for_ai = message.mime_type # Start with original
                    
                    if message_type == 'image':
                        processed_data_bytes, processing_metadata = media_processor.process_image(media_data_bytes, filename)
                        if processing_metadata and processing_metadata.get('output_format'):
                            actual_mime_type_for_ai = f"image/{processing_metadata['output_format'].lower()}"
                    elif message_type == 'audio':
                        # Assuming process_audio also returns (data, metadata)
                        processed_data_bytes, processing_metadata = media_processor.process_audio(media_data_bytes, filename) 
                        if processing_metadata and processing_metadata.get('output_format'):
                           actual_mime_type_for_ai = f"audio/{processing_metadata['output_format'].lower()}"
                    
                    upload_data_bytes = processed_data_bytes if processed_data_bytes else media_data_bytes
                    processed_media_bytes_for_ai = upload_data_bytes # This is what AI service gets
                    message.mime_type = actual_mime_type_for_ai # Store the potentially converted mime type for AI
                    
                    blob_name, public_url = cloud_storage.upload_file(
                        upload_data_bytes, 
                        filename, # Use the derived filename
                        actual_mime_type_for_ai # Use the mime type for AI
                    )
                    
                    if blob_name and public_url:
                        message.cloud_storage_url = public_url
                        # Prepare MediaFile object, will be committed after message has an ID
                        media_file_obj = MediaFile(
                            # message_id will be set after message is committed
                            original_url=media_info.get('url', ''), # If available from original payload
                            cloud_storage_bucket=Config.GOOGLE_CLOUD_BUCKET_NAME,
                            cloud_storage_path=blob_name,
                            public_url=public_url,
                            file_name=filename, # Store the derived filename
                            file_size=len(upload_data_bytes),
                            mime_type=media_info.get('mime_type'), # Original mime_type from provider
                            processing_status='processed'
                        )
                    else:
                        logger.error(f"Failed to upload media for message {message_id}")
                        message.processing_error = "Failed to upload media to cloud storage"
                else:
                    logger.error(f"Failed to download media for message {message_id} (old format)")
                    message.processing_error = "Failed to download media from WhatsApp"
        
        else: # Other message types not explicitly handled yet
            logger.warning(f"Received unhandled message_type: {message_type_raw if is_new_format else message_type} for message {message_id}")
            message.content = f"Received {message_type_raw if is_new_format else message_type} (type not fully supported)"
            message.processing_error = "Unsupported message type by current logic"


        db.session.add(message)
        db.session.commit() # Commit for message to get an ID

        #---> ATUALIZAÇÃO DO PERFIL DO USUÁRIO <---
        # Após salvar a mensagem, tentamos extrair e salvar informações de perfil do texto.
        # Isso é feito independentemente do tipo de mensagem, pois mesmo uma imagem pode ter uma legenda com informações.
        if message.content and isinstance(message.content, str) and message.content.strip():
            update_user_profile(conversation, message.content)


        if 'media_file_obj' in locals() and media_file_obj: # Check if media_file_obj was created (old format media)
            media_file_obj.message_id = message.id
            db.session.add(media_file_obj)
            db.session.commit()
            logger.info(f"MediaFile record created for message {message.id}")

        # Mark message as read - This uses OLD API message_id. 
        # If new API has a different way or doesn't need explicit read marking, this needs change.
        # For now, it will try with the message_id we have.
        if not is_new_format: # Assuming new API might not need/support this or has different mechanism
            whatsapp_service.mark_message_as_read(message_id) 
        else:
            logger.info(f"Mark as read skipped for new format message {message_id} (mechanism TBD).")
        
        # Generate AI response
        # Ensure message.content and message.mime_type are correctly set before this call.
        # For new format media, message.content might be a placeholder and mime_type might be missing.
        ai_response_text, ai_metadata = generate_ai_response(message, media_bytes=processed_media_bytes_for_ai)

        # Enviar a resposta da IA para o usuário se houver uma
        if ai_response_text:
            whatsapp_service.send_text_message(
                to_number=conversation.user_phone,
                text=ai_response_text
            )
        else:
            logger.warning(f"Nenhuma resposta de texto da IA foi gerada para a mensagem {message.id}. Nenhuma mensagem enviada.")

        # Checar se um HumanAgentRequest foi criado e notificar
        if ai_metadata and ai_metadata.get("action") == "REQUEST_HUMAN_AGENT":
            # Aqui, criamos o HumanAgentRequest e obtemos seu ID.
            reason_for_request = ai_metadata.get("reason", "AI requested assistance") # Obtenha a razão do metadata se houver
            human_request_id = create_human_agent_request(
                conversation_id=conversation.id,
                reason=reason_for_request
            )
            
            if human_request_id:
                logger.info(f"Human agent requested (ID: {human_request_id}) for conversation {conversation.id}. Sending Pushover notification.")
                
                # Determinar a Pushover User Key
                pushover_user_key = Config.DEFAULT_PUSHOVER_USER_KEY

                if pushover_user_key:
                    dashboard_url = f"http://localhost:5000/dashboard/human-handoff?conversation_id={conversation.id}" # Usando um URL de exemplo
                    notification_message = f"Nova solicitação para ID conversa: {conversation.id}. Usuário: {conversation.user_phone}. Razão: {reason_for_request}"
                    
                    send_pushover_notification(
                        title="Solicitação de Atendimento Humano",
                        message=notification_message,
                        user_key=pushover_user_key,
                        url=dashboard_url,
                        url_title="Abrir no Dashboard"
                    )
                else:
                    logger.warning(f"Pushover USER_KEY não encontrada para notificar sobre HumanAgentRequest {human_request_id}")
        
        # ---> DETECÇÃO E CRIAÇÃO DE PEDIDO <---
        # Após a resposta ser gerada, verificamos se a interação resultou em um pedido.
        # Usamos a mensagem original do usuário e o histórico para dar contexto ao Order Manager.
        if message.content and isinstance(message.content, str) and message.content.strip():
            # Precisamos do histórico mais recente para que o Order Manager possa extrair os itens
            full_history_for_order = get_conversation_history(message.conversation_id, limit=20) # Pega um histórico maior
            create_order_from_interaction(message.conversation, message.content, full_history_for_order)
        
        logger.info(f"Message {message_id} (DB ID: {message.id}) processed successfully for conversation {conversation.id}")
        
    except Exception as e:
        logger.error(f"Error processing message {message_data.get('id', 'unknown')} for conversation {conversation_id_for_logging if conversation_id_for_logging else 'unknown'}: {str(e)}", exc_info=True)
        db.session.rollback()

def update_user_profile(conversation: Conversation, message_text: str):
    """
    Chama o AI Service para extrair informações de perfil e as salva no banco de dados.
    """
    try:
        profile_action = ai_service.extract_profile_info(message_text)
        
        if not profile_action or profile_action.get('action') != 'SAVE':
            return # Nenhuma ação de salvamento necessária

        profile_data = profile_action.get('data')
        if not profile_data or not isinstance(profile_data, dict):
            logger.warning(f"Ação 'SAVE' recebida, mas os dados do perfil são inválidos: {profile_data}")
            return
        
        key = profile_data.get('key')
        value = profile_data.get('value')

        if not key or not value:
            logger.warning(f"Chave ou valor ausente nos dados do perfil: {profile_data}")
            return

        # Busca ou cria o perfil do usuário
        user_profile = conversation.profile
        if not user_profile:
            user_profile = UserProfile(conversation_id=conversation.id, profile_data={})
            db.session.add(user_profile)
        
        # Atualiza os dados do perfil.
        # Usar .copy() para garantir que o SQLAlchemy detecte a mudança no JSON.
        updated_data = user_profile.profile_data.copy()
        updated_data[key] = value
        user_profile.profile_data = updated_data
        
        db.session.commit()
        logger.info(f"Perfil do usuário para a conversa {conversation.id} atualizado. Chave: '{key}', Valor: '{value}'")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Falha ao atualizar o perfil do usuário para a conversa {conversation.id}: {e}", exc_info=True)

def create_human_agent_request(conversation_id: int, reason: str):
    """Creates a request for a human agent and saves it to the database."""
    try:
        conversation = Conversation.query.get(conversation_id)
        if not conversation:
            logger.error(f"Cannot create human agent request: Conversation {conversation_id} not found.")
            return

        # Check for an existing active request
        existing_request = HumanAgentRequest.query.filter_by(
            conversation_id=conversation_id,
            status='pending'
        ).first()

        if existing_request:
            logger.info(f"Human agent request already pending for conversation {conversation_id}.")
            return

        human_request = HumanAgentRequest(
            conversation_id=conversation.id,
            phone_number=conversation.user_phone,
            contact_name=conversation.contact_name,
            request_reason=reason,
            status='pending'
        )
        db.session.add(human_request)
        db.session.commit()
        logger.info(f"Human agent request created for conversation {conversation_id} with reason: {reason}")
        return human_request.id  # Retornar o ID da solicitação criada
    
    except Exception as e:
        db.session.rollback()
        logger.error(f"Failed to create human agent request for conversation {conversation_id}: {e}", exc_info=True)
        return None

def get_conversation_history(conversation_id: int, limit: int = 10) -> List[Dict[str, Any]]:
    """Fetches and formats the recent conversation history for the AI service."""
    # Fetches messages in ascending order to get the latest ones at the end
    recent_messages = Message.query.filter_by(
        conversation_id=conversation_id
    ).order_by(Message.timestamp.asc()).all()

    # Get the last 'limit' messages
    limited_messages = recent_messages[-limit:]

    history_for_ai = []
    for msg in limited_messages:
        history_for_ai.append({
            'sender_type': 'user' if msg.is_from_user else 'assistant',
            'message_text': msg.content or '[conteúdo não textual]',
        })
    return history_for_ai

def generate_ai_response(message: Message, media_bytes: Optional[bytes] = None) -> tuple[Optional[str], Optional[Dict[str, Any]]]:
    """
    Generates a response from the AI service based on the message and conversation history.
    Also handles creating a HumanAgentRequest if the AI signals it.
    """
    try:
        # ---> VERIFICAÇÃO DE FRETE PROATIVO <---
        # Se a mensagem atual for um texto e a anterior for uma localização, calcula o frete automaticamente.
        if message.message_type == 'text' and message.content and message.content.strip():
            previous_message = Message.query.filter(
                Message.conversation_id == message.conversation_id,
                Message.timestamp < message.timestamp
            ).order_by(Message.timestamp.desc()).first()

            if previous_message and previous_message.message_type == 'location':
                logger.info(f"Sequência de localização -> texto detectada. Tentando cálculo de frete proativo.")
                try:
                    location_data = json.loads(previous_message.content)
                    origin_coords = f"{location_data.get('latitude')},{location_data.get('longitude')}"
                    destination_address = message.content.strip()

                    # Usar diretamente o serviço de geolocalização do ai_service
                    geo_service = ai_service.geolocation_service
                    result = geo_service.get_distance_and_duration(origin_coords, destination_address)
                    
                    if result:
                        distance_km, _, _, duration_text = result
                        shipping_fee = geo_service.calculate_shipping_fee(distance_km)
                        
                        response_text = f"Cálculo de frete automático da sua localização para '{destination_address}':\n\n" \
                                      f"📍 *Distância:* {distance_km:.2f} km\n" \
                                      f"⏳ *Duração Estimada:* {duration_text}\n" \
                                      f"💰 *Custo do Frete:* R$ {shipping_fee:.2f}"

                        ai_metadata = {'agent_name': 'Proactive Shipping Calculator', 'proactive': True}
                        
                        # Salvar a resposta da IA no banco de dados
                        ai_response = AIResponse(
                            message_id=message.id,
                            response_content=response_text,
                            agent_name=ai_metadata.get('agent_name')
                        )
                        db.session.add(ai_response)
                        db.session.commit()
                        logger.info(f"Resposta de frete proativo para mensagem {message.id} salva no DB.")

                        return response_text, ai_metadata
                    else:
                        logger.warning("Cálculo proativo de frete falhou, pois a distância não pôde ser determinada. Seguindo fluxo normal.")

                except (json.JSONDecodeError, ValueError, KeyError) as e:
                    logger.error(f"Erro ao tentar o cálculo de frete proativo: {e}. Seguindo fluxo normal.")
                    # Em caso de erro, simplesmente segue para o processamento normal da IA.

        conversation_history = get_conversation_history(message.conversation_id)
        
        # ---> CARREGAR DADOS DO PERFIL DO USUÁRIO <---
        user_profile = UserProfile.query.filter_by(conversation_id=message.conversation_id).first()
        profile_data = user_profile.profile_data if user_profile else None

        # ---> CARREGAR ÚLTIMO PEDIDO DO USUÁRIO <---
        last_order = Order.query.filter_by(
            conversation_id=message.conversation_id,
            status='completed'
        ).order_by(Order.created_at.desc()).first()
        last_order_data = last_order.order_details if last_order else None
        
        # O text_prompt inicial é o conteúdo da mensagem atual
        text_prompt = message.content or ""
        
        ai_result = None
        
        # Decidir qual função do AI Service chamar com base no tipo de mensagem
        if message.message_type == 'image' and media_bytes:
            # Para imagens, o texto acompanhante é o prompt. Se não houver, um prompt padrão é usado dentro do serviço.
            ai_result = ai_service.process_image_message(image_data=media_bytes, text_prompt=text_prompt, conversation_history=conversation_history, profile_data=profile_data)
        elif message.message_type == 'video' and media_bytes:
            # Para vídeo, o texto (legenda) é o prompt.
            ai_result = ai_service.process_video_message(video_data=media_bytes, text_prompt=text_prompt, conversation_history=conversation_history, profile_data=profile_data)
        elif message.message_type == 'audio' and media_bytes:
            # Para áudio, o texto é ignorado e o áudio é processado. O histórico e o perfil são enviados para contexto.
            ai_result = ai_service.process_audio_message(audio_data=media_bytes, conversation_history=conversation_history, profile_data=profile_data)
        elif message.message_type == 'location':
            try:
                location_data = json.loads(message.content)
                latitude = location_data.get('latitude')
                longitude = location_data.get('longitude')
                if latitude is not None and longitude is not None:
                    ai_result = ai_service.process_location_message(
                        latitude=latitude,
                        longitude=longitude,
                        conversation_history=conversation_history,
                        profile_data=profile_data
                    )
                else:
                    raise ValueError("Latitude ou longitude ausentes no conteúdo da mensagem")
            except (json.JSONDecodeError, ValueError) as e:
                logger.error(f"Não foi possível processar a localização da mensagem {message.id}: {e}")
                ai_result = {'success': False, 'error': str(e)}
        else: # Para texto e outros tipos sem mídia especial
            ai_result = ai_service.process_text_message(text=text_prompt, conversation_history=conversation_history, profile_data=profile_data, last_order_data=last_order_data)

        if not ai_result or not ai_result.get('success'):
            logger.error(f"AI service failed to generate a response for message {message.id}. Error: {ai_result.get('error') if ai_result else 'No result'}")
            return "Desculpe, não consegui processar sua mensagem. Tente novamente mais tarde.", None

        response_text = ai_result.get('response', '')
        ai_metadata = ai_result.get('metadata', {})

        # ---> ATUALIZAÇÃO DE PERFIL PÓS-TRANSCRIÇÃO <---
        # Se a resposta veio de um áudio, o texto transcrito estará no metadata.
        # Usamos esse texto para tentar uma atualização de perfil.
        if message.message_type == 'audio' and ai_metadata and ai_metadata.get('transcribed_text'):
            transcribed_text = ai_metadata['transcribed_text']

            # ---> ARMAZENAR TRANSCRIÇÃO NO HISTÓRICO <---
            # Atualiza o conteúdo da mensagem original com o texto transcrito para que
            # ele se torne parte permanente do histórico da conversa.
            message.content = transcribed_text
            db.session.add(message) # Adiciona a mudança à sessão do DB
            logger.info(f"Conteúdo da mensagem de áudio (ID: {message.id}) atualizado com o texto transcrito.")

            logger.info(f"Texto transcrito do áudio ('{transcribed_text}') será usado para atualização de perfil.")
            # A função `update_user_profile` já existe e faz o que precisamos.
            update_user_profile(message.conversation, transcribed_text)
        
        # ---> DETECÇÃO E CRIAÇÃO DE PEDIDO <---
        # Após a resposta ser gerada, verificamos se a interação resultou em um pedido.
        # Usamos a mensagem original do usuário e o histórico para dar contexto ao Order Manager.
        if message.content and isinstance(message.content, str) and message.content.strip():
            # Precisamos do histórico mais recente para que o Order Manager possa extrair os itens
            full_history_for_order = get_conversation_history(message.conversation_id, limit=20) # Pega um histórico maior
            create_order_from_interaction(message.conversation, message.content, full_history_for_order)
    
        # Salvar a resposta da IA no banco de dados
        ai_response = AIResponse(
            message_id=message.id,
            response_content=response_text,
            agent_name=ai_metadata.get('agent_name'),
            processing_time=ai_metadata.get('processing_time_ms')
        )
        db.session.add(ai_response)
        db.session.commit()
        logger.info(f"AI response for message {message.id} saved to DB.")
        
        # Checar pela ação de solicitar um agente humano
        if ai_metadata and ai_metadata.get("action") == "REQUEST_HUMAN_AGENT":
            # O serviço de IA agora não cria o registro, apenas sinaliza.
            # O webhook irá criar o registro e enviar a notificação.
            logger.info(f"AI signaled for human agent for conversation {message.conversation_id}.")
            # Passar a razão para a lógica de chamada se disponível
            ai_metadata['reason'] = response_text # A própria resposta pode conter a razão
        
        return response_text, ai_metadata

    except Exception as e:
        logger.error(f"Error generating AI response for message {message.id}: {e}", exc_info=True)
        db.session.rollback()
        # Fallback response
        return "Ops! Aconteceu um erro com a nossa IA. Já estamos verificando.", None

def create_order_from_interaction(conversation: Conversation, user_message: str, conversation_history: List[Dict]):
    """
    Chama o AI Service para detectar uma confirmação de pedido e o salva no banco de dados.
    """
    try:
        order_action = ai_service.extract_order_info(user_message, conversation_history)
        
        if not order_action or order_action.get('action') != 'CREATE_ORDER':
            return # Nenhuma ação de criação de pedido necessária

        order_data = order_action.get('data')
        if not order_data or not isinstance(order_data, dict) or 'items' not in order_data:
            logger.warning(f"Ação 'CREATE_ORDER' recebida, mas os dados do pedido são inválidos: {order_data}")
            return
        
        # Cria o novo pedido no banco de dados
        new_order = Order(
            conversation_id=conversation.id,
            order_details=order_data, # Salva o JSON completo com itens, etc.
            status='completed' # Ou o status que fizer sentido no seu fluxo
        )
        db.session.add(new_order)
        db.session.commit()
        logger.info(f"Novo pedido (ID: {new_order.id}) criado para a conversa {conversation.id} com base na interação do usuário.")

    except Exception as e:
        db.session.rollback()
        logger.error(f"Falha ao criar pedido a partir da interação para a conversa {conversation.id}: {e}", exc_info=True)

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
