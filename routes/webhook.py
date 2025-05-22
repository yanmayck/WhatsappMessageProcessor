import json
import logging
import threading
from flask import Blueprint, request, jsonify, current_app
from app import db
from models import Conversation, Message, AIResponse, MediaFile
from services.whatsapp_service import WhatsAppService
from services.media_processor import MediaProcessor
from services.ai_service import AIService
from services.cloud_storage import CloudStorageService
from config import Config

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
                contact_name=contact_name
            )
            db.session.add(conversation)
            db.session.commit()
            logger.info(f"Created new conversation for {from_number}")
        
        # Check if message already exists (avoid duplicates)
        existing_message = Message.query.filter_by(whatsapp_message_id=message_id).first()
        if existing_message:
            logger.info(f"Message {message_id} already processed")
            return
        
        # Create message record
        message = Message(
            conversation_id=conversation.id,
            whatsapp_message_id=message_id,
            sender_phone=from_number,
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
            
            # Download and process media
            media_data = whatsapp_service.download_media(media_id)
            if media_data:
                # Process the media file
                processed_data, metadata = None, None
                
                if message_type == 'image':
                    processed_data, metadata = media_processor.process_image(media_data, filename)
                elif message_type == 'audio':
                    processed_data, metadata = media_processor.process_audio(media_data, filename)
                
                # Use processed data if available, otherwise use original
                upload_data = processed_data if processed_data else media_data
                
                # Upload to cloud storage
                blob_name, public_url = cloud_storage.upload_file(
                    upload_data, 
                    filename, 
                    mime_type
                )
                
                if blob_name and public_url:
                    message.cloud_storage_url = public_url
                    
                    # Create media file record
                    media_file = MediaFile(
                        message_id=message.id,
                        original_url=media_info.get('url', ''),
                        cloud_storage_bucket=Config.GOOGLE_CLOUD_BUCKET_NAME,
                        cloud_storage_path=blob_name,
                        public_url=public_url,
                        file_name=filename,
                        file_size=len(upload_data),
                        mime_type=mime_type,
                        processing_status='processed'
                    )
                    db.session.add(media_file)
                else:
                    logger.error(f"Failed to upload media for message {message_id}")
                    message.processing_error = "Failed to upload media to cloud storage"
        
        # Save message to database
        db.session.add(message)
        db.session.commit()
        
        # Mark message as read
        whatsapp_service.mark_message_as_read(message_id)
        
        # Generate AI response
        generate_ai_response(message)
        
        logger.info(f"Message {message_id} processed successfully")
        
    except Exception as e:
        logger.error(f"Error processing message {message_data.get('id', 'unknown')}: {str(e)}")
        db.session.rollback()

def generate_ai_response(message):
    """Generate and send AI response for a message"""
    try:
        # Get conversation history
        recent_messages = Message.query.filter_by(
            conversation_id=message.conversation_id
        ).order_by(Message.timestamp.desc()).limit(10).all()
        
        conversation_history = []
        for msg in reversed(recent_messages):
            conversation_history.append({
                'content': msg.content or '',
                'message_type': msg.message_type,
                'is_from_user': msg.is_from_user,
                'timestamp': msg.timestamp
            })
        
        # Generate response based on message type
        ai_result = None
        
        if message.message_type == 'text':
            ai_result = ai_service.process_text_message(
                message.content, 
                conversation_history
            )
        elif message.message_type == 'image' and message.cloud_storage_url:
            # Download image data for AI processing
            image_data = cloud_storage.download_file(message.cloud_storage_url.split('/')[-1])
            if image_data:
                ai_result = ai_service.process_image_message(
                    image_data,
                    message.content,  # caption
                    conversation_history
                )
        elif message.message_type == 'audio' and message.cloud_storage_url:
            # Download audio data for AI processing
            audio_data = cloud_storage.download_file(message.cloud_storage_url.split('/')[-1])
            if audio_data:
                ai_result = ai_service.process_audio_message(
                    audio_data,
                    conversation_history
                )
        
        if ai_result and ai_result.get('success'):
            # Create AI response record
            ai_response = AIResponse(
                message_id=message.id,
                agent_name='gemini-2.0-flash-exp',
                response_content=ai_result['response'],
                processing_time=ai_result.get('processing_time', 0),
                model_used=ai_result.get('model_used', 'unknown')
            )
            db.session.add(ai_response)
            
            # Send response via WhatsApp
            response_message_id = whatsapp_service.send_text_message(
                message.sender_phone,
                ai_result['response']
            )
            
            if response_message_id:
                ai_response.sent_to_whatsapp = True
                ai_response.whatsapp_response_id = response_message_id
                message.ai_response_sent = True
                
                # Create response message record
                response_message = Message(
                    conversation_id=message.conversation_id,
                    whatsapp_message_id=response_message_id,
                    sender_phone=Config.WHATSAPP_PHONE_NUMBER_ID,
                    message_type='text',
                    content=ai_result['response'],
                    is_from_user=False
                )
                db.session.add(response_message)
            
            message.processed = True
            db.session.commit()
            
            logger.info(f"AI response generated and sent for message {message.whatsapp_message_id}")
        else:
            error_msg = ai_result.get('error', 'Unknown error') if ai_result else 'No AI result'
            message.processing_error = f"AI processing failed: {error_msg}"
            db.session.commit()
            logger.error(f"AI processing failed for message {message.whatsapp_message_id}: {error_msg}")
            
    except Exception as e:
        logger.error(f"Error generating AI response for message {message.whatsapp_message_id}: {str(e)}")
        message.processing_error = f"AI response generation failed: {str(e)}"
        db.session.commit()
