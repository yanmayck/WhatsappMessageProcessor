from flask import Blueprint, render_template, request, jsonify, url_for
from sqlalchemy import desc, func
from app import db
from models import Conversation, Message, AIResponse, MediaFile, HumanAgentRequest, SilentMode
from services.ai_service import AIService
# from services.whatsapp_service import WhatsAppService
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

dashboard_bp = Blueprint('dashboard', __name__)

# whatsapp_service_instance = WhatsAppService()

@dashboard_bp.route('/')
def index():
    """Main dashboard page"""
    try:
        # Get statistics
        total_conversations = Conversation.query.count()
        total_messages = Message.query.count()
        total_media_files = MediaFile.query.count()
        active_conversations = Conversation.query.filter_by(is_active=True).count()
        
        # Get recent conversations with message counts
        recent_conversations = db.session.query(
            Conversation,
            func.count(Message.id).label('message_count'),
            func.max(Message.timestamp).label('last_message_time')
        ).outerjoin(Message).group_by(Conversation.id).order_by(
            desc('last_message_time')
        ).limit(10).all()
        
        # Get recent media files
        recent_media = db.session.query(MediaFile, Message, Conversation).join(
            Message, MediaFile.message_id == Message.id
        ).join(
            Conversation, Message.conversation_id == Conversation.id
        ).order_by(desc(MediaFile.uploaded_at)).limit(10).all()
        
        stats = {
            'total_conversations': total_conversations,
            'total_messages': total_messages,
            'total_media_files': total_media_files,
            'active_conversations': active_conversations
        }
        
        return render_template('dashboard.html', 
                             stats=stats,
                             recent_conversations=recent_conversations,
                             recent_media=recent_media)
        
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return render_template('dashboard.html', 
                             stats={'error': str(e)},
                             recent_conversations=[],
                             recent_media=[])

@dashboard_bp.route('/conversations')
def conversations():
    """List all conversations"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = 20
        
        # Get conversations with message counts and last message time
        conversations_query = db.session.query(
            Conversation,
            func.count(Message.id).label('message_count'),
            func.max(Message.timestamp).label('last_message_time')
        ).outerjoin(Message).group_by(Conversation.id).order_by(
            desc('last_message_time')
        )
        
        conversations = conversations_query.paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        return render_template('conversations.html', conversations=conversations)
        
    except Exception as e:
        logger.error(f"Conversations listing error: {str(e)}")
        return render_template('conversations.html', 
                             conversations=None, 
                             error=str(e))

@dashboard_bp.route('/conversation/<int:conversation_id>')
def conversation_detail(conversation_id):
    """View detailed conversation with messages"""
    try:
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Get all messages for this conversation
        messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.timestamp.asc()).all()
        
        # Get AI responses for messages
        message_responses = {}
        for message in messages:
            responses = AIResponse.query.filter_by(message_id=message.id).all()
            message_responses[message.id] = responses
        
        # Get media files for messages
        message_media = {}
        for message in messages:
            if message.message_type in ['image', 'audio', 'video', 'document']:
                media = MediaFile.query.filter_by(message_id=message.id).first()
                message_media[message.id] = media
        
        return render_template('conversation.html',
                             conversation=conversation,
                             messages=messages,
                             message_responses=message_responses,
                             message_media=message_media)
        
    except Exception as e:
        logger.error(f"Conversation detail error: {str(e)}")
        return render_template('conversation.html',
                             conversation=None,
                             messages=[],
                             error=str(e))

@dashboard_bp.route('/api/conversations')
def api_conversations():
    """API endpoint for conversations list"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        search = request.args.get('search', '')
        
        query = db.session.query(
            Conversation,
            func.count(Message.id).label('message_count'),
            func.max(Message.timestamp).label('last_message_time')
        ).outerjoin(Message).group_by(Conversation.id)
        
        if search:
            query = query.filter(
                Conversation.phone_number.contains(search) |
                Conversation.contact_name.contains(search)
            )
        
        conversations = query.order_by(
            desc('last_message_time')
        ).paginate(page=page, per_page=per_page, error_out=False)
        
        result = {
            'conversations': [],
            'pagination': {
                'page': conversations.page,
                'pages': conversations.pages,
                'per_page': conversations.per_page,
                'total': conversations.total,
                'has_next': conversations.has_next,
                'has_prev': conversations.has_prev
            }
        }
        
        for conv, msg_count, last_time in conversations.items:
            result['conversations'].append({
                'id': conv.id,
                'phone_number': conv.phone_number,
                'contact_name': conv.contact_name,
                'message_count': msg_count or 0,
                'last_message_time': last_time.isoformat() if last_time else None,
                'is_active': conv.is_active,
                'created_at': conv.created_at.isoformat(),
                'url': url_for('dashboard.conversation_detail', conversation_id=conv.id)
            })
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"API conversations error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/conversation/<int:conversation_id>/messages')
def api_conversation_messages(conversation_id):
    """API endpoint for conversation messages"""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 50, type=int)
        
        messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.timestamp.desc()).paginate(
            page=page, per_page=per_page, error_out=False
        )
        
        result = {
            'messages': [],
            'pagination': {
                'page': messages.page,
                'pages': messages.pages,
                'per_page': messages.per_page,
                'total': messages.total,
                'has_next': messages.has_next,
                'has_prev': messages.has_prev
            }
        }
        
        for message in messages.items:
            # Get AI responses
            ai_responses = AIResponse.query.filter_by(message_id=message.id).all()
            
            # Get media file if exists
            media_file = None
            if message.message_type in ['image', 'audio', 'video', 'document']:
                media_file = MediaFile.query.filter_by(message_id=message.id).first()
            
            message_data = {
                'id': message.id,
                'whatsapp_message_id': message.whatsapp_message_id,
                'sender_phone': message.sender_phone,
                'message_type': message.message_type,
                'content': message.content,
                'cloud_storage_url': message.cloud_storage_url,
                'file_name': message.file_name,
                'mime_type': message.mime_type,
                'is_from_user': message.is_from_user,
                'timestamp': message.timestamp.isoformat(),
                'processed': message.processed,
                'ai_response_sent': message.ai_response_sent,
                'processing_error': message.processing_error,
                'ai_responses': [
                    {
                        'id': resp.id,
                        'agent_name': resp.agent_name,
                        'response_content': resp.response_content,
                        'processing_time': resp.processing_time,
                        'model_used': resp.model_used,
                        'created_at': resp.created_at.isoformat(),
                        'sent_to_whatsapp': resp.sent_to_whatsapp
                    } for resp in ai_responses
                ]
            }
            
            if media_file:
                message_data['media_file'] = {
                    'id': media_file.id,
                    'public_url': media_file.public_url,
                    'file_size': media_file.file_size,
                    'processing_status': media_file.processing_status,
                    'uploaded_at': media_file.uploaded_at.isoformat()
                }
            
            result['messages'].append(message_data)
        
        return jsonify(result)
        
    except Exception as e:
        logger.error(f"API conversation messages error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/stats')
def api_stats():
    """API endpoint for dashboard statistics"""
    try:
        # Basic counts
        total_conversations = Conversation.query.count()
        total_messages = Message.query.count()
        total_media_files = MediaFile.query.count()
        active_conversations = Conversation.query.filter_by(is_active=True).count()
        
        # Message type distribution
        message_types = db.session.query(
            Message.message_type,
            func.count(Message.id).label('count')
        ).group_by(Message.message_type).all()
        
        # AI response statistics
        ai_responses_count = AIResponse.query.count()
        successful_responses = AIResponse.query.filter_by(sent_to_whatsapp=True).count()
        
        # Processing statistics
        processed_messages = Message.query.filter_by(processed=True).count()
        failed_messages = Message.query.filter(Message.processing_error.isnot(None)).count()
        
        stats = {
            'totals': {
                'conversations': total_conversations,
                'messages': total_messages,
                'media_files': total_media_files,
                'active_conversations': active_conversations,
                'ai_responses': ai_responses_count,
                'successful_responses': successful_responses,
                'processed_messages': processed_messages,
                'failed_messages': failed_messages
            },
            'message_types': {
                msg_type: count for msg_type, count in message_types
            },
            'success_rates': {
                'processing': (processed_messages / total_messages * 100) if total_messages > 0 else 0,
                'ai_responses': (successful_responses / ai_responses_count * 100) if ai_responses_count > 0 else 0
            }
        }
        
        return jsonify(stats)
        
    except Exception as e:
        logger.error(f"API stats error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/conversation/<int:conversation_id>/summary')
def api_conversation_summary(conversation_id):
    """Generate AI summary of a conversation"""
    try:
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Get conversation messages
        messages = Message.query.filter_by(
            conversation_id=conversation_id
        ).order_by(Message.timestamp.asc()).all()
        
        if not messages:
            return jsonify({'summary': 'No messages in this conversation yet.'})
        
        # Build conversation history for AI
        conversation_history = []
        for msg in messages:
            conversation_history.append({
                'content': msg.content or f'[{msg.message_type} message]',
                'message_type': msg.message_type,
                'is_from_user': msg.is_from_user,
                'timestamp': msg.timestamp
            })
        
        # Generate summary using AI service
        ai_service = AIService()
        summary = ai_service.generate_summary(conversation_history)
        
        return jsonify({
            'summary': summary,
            'message_count': len(messages),
            'conversation_id': conversation_id
        })
        
    except Exception as e:
        logger.error(f"Conversation summary error: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/human-handoff-requests', methods=['GET'])
def api_get_human_handoff_requests():
    """API endpoint para listar solicitações de atendimento humano."""
    try:
        page = request.args.get('page', 1, type=int)
        per_page = request.args.get('per_page', 20, type=int)
        status_filter = request.args.get('status', 'pending')

        query = HumanAgentRequest.query
        if status_filter != 'all':
            query = query.filter(HumanAgentRequest.status == status_filter)
        
        requests_page = query.order_by(desc(HumanAgentRequest.request_time)).paginate(
            page=page, per_page=per_page, error_out=False
        )

        result = {
            'requests': [],
            'pagination': {
                'page': requests_page.page,
                'pages': requests_page.pages,
                'per_page': requests_page.per_page,
                'total': requests_page.total,
                'has_next': requests_page.has_next,
                'has_prev': requests_page.has_prev
            }
        }

        for req in requests_page.items:
            result['requests'].append({
                'id': req.id,
                'conversation_id': req.conversation_id,
                'phone_number': req.phone_number,
                'contact_name': req.contact_name,
                'request_time': req.request_time.isoformat() if req.request_time else None,
                'status': req.status,
                'escalation_reason': req.escalation_reason,
                'ai_summary_of_issue': req.ai_summary_of_issue,
                'assigned_agent_id': req.assigned_agent_id,
                'assigned_time': req.assigned_time.isoformat() if req.assigned_time else None,
                'closed_time': req.closed_time.isoformat() if req.closed_time else None,
                'conversation_url': url_for('dashboard.conversation_detail', conversation_id=req.conversation_id)
            })
        
        return jsonify(result)

    except Exception as e:
        logger.error(f"API human handoff requests error: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/human-handoff-requests/<int:request_id>', methods=['GET'])
def api_get_human_handoff_request_detail(request_id):
    """API endpoint para obter detalhes de uma solicitação de atendimento humano, incluindo histórico completo."""
    try:
        req = HumanAgentRequest.query.get_or_404(request_id)
        return jsonify({
            'id': req.id,
            'conversation_id': req.conversation_id,
            'phone_number': req.phone_number,
            'contact_name': req.contact_name,
            'request_time': req.request_time.isoformat() if req.request_time else None,
            'status': req.status,
            'escalation_reason': req.escalation_reason,
            'ai_summary_of_issue': req.ai_summary_of_issue,
            'full_conversation_history_json': req.full_conversation_history_json,
            'assigned_agent_id': req.assigned_agent_id,
            'assigned_time': req.assigned_time.isoformat() if req.assigned_time else None,
            'resolution_notes': req.resolution_notes,
            'closed_time': req.closed_time.isoformat() if req.closed_time else None,
            'conversation_url': url_for('dashboard.conversation_detail', conversation_id=req.conversation_id)
        })
    except Exception as e:
        logger.error(f"API human handoff request detail error for ID {request_id}: {str(e)}", exc_info=True)
        return jsonify({'error': str(e)}), 404 if isinstance(e, Exception) and "404 Not Found" in str(e) else 500

@dashboard_bp.route('/api/human-handoff-requests/<int:request_id>/assign', methods=['POST'])
def api_assign_human_handoff_request(request_id):
    """API endpoint para um agente se atribuir a uma solicitação."""
    try:
        data = request.get_json()
        agent_id = data.get('agent_id')

        if not agent_id:
            return jsonify({'error': 'agent_id é obrigatório'}), 400

        req = HumanAgentRequest.query.get_or_404(request_id)
        
        if req.status != 'pending':
            return jsonify({'error': f'Solicitação {request_id} não está pendente (status atual: {req.status})'}), 400

        req.status = 'assigned'
        req.assigned_agent_id = agent_id
        req.assigned_time = datetime.utcnow()
        db.session.commit()

        logger.info(f"HumanAgentRequest {request_id} atribuído ao agente {agent_id}")
        return jsonify({
            'message': 'Solicitação atribuída com sucesso',
            'request': {
                'id': req.id,
                'status': req.status,
                'assigned_agent_id': req.assigned_agent_id,
                'assigned_time': req.assigned_time.isoformat()
            }
        }), 200

    except Exception as e:
        logger.error(f"Erro ao atribuir HumanAgentRequest {request_id}: {str(e)}", exc_info=True)
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/human-handoff')
def human_handoff_page():
    """Página do dashboard para gerenciar solicitações de atendimento humano."""
    # Esta rota simplesmente renderizaria um template HTML.
    # A lógica de dados viria das chamadas de API (api_get_human_handoff_requests).
    # Por enquanto, apenas uma resposta placeholder.
    # return render_template('human_handoff.html', title="Atendimento Humano") 
    return jsonify({"message": "Página de Atendimento Humano (template HTML a ser criado)"}), 200

@dashboard_bp.route('/api/conversation/<int:conversation_id>/silent_mode', methods=['POST'])
def enable_silent_mode(conversation_id):
    """Ativa o modo silencioso para uma conversa"""
    try:
        duration_hours = request.json.get('duration_hours', 24)  # Padrão de 24 horas
        admin_name = request.json.get('admin_name', 'admin')
        
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Desativa qualquer modo silencioso existente
        existing_silent = SilentMode.query.filter_by(
            conversation_id=conversation_id,
            is_active=True
        ).all()
        for silent in existing_silent:
            silent.is_active = False
        
        # Cria novo modo silencioso
        silent_mode = SilentMode(
            conversation_id=conversation_id,
            enabled_by=admin_name,
            expires_at=datetime.utcnow() + timedelta(hours=duration_hours)
        )
        
        db.session.add(silent_mode)
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': f'Silent mode enabled for {duration_hours} hours',
            'expires_at': silent_mode.expires_at.isoformat()
        })
        
    except Exception as e:
        logger.error(f"Error enabling silent mode: {str(e)}")
        return jsonify({'error': str(e)}), 500

@dashboard_bp.route('/api/conversation/<int:conversation_id>/silent_mode', methods=['DELETE'])
def disable_silent_mode(conversation_id):
    """Desativa o modo silencioso para uma conversa"""
    try:
        conversation = Conversation.query.get_or_404(conversation_id)
        
        # Desativa todos os modos silenciosos ativos
        silent_modes = SilentMode.query.filter_by(
            conversation_id=conversation_id,
            is_active=True
        ).all()
        
        if not silent_modes:
            return jsonify({
                'status': 'warning',
                'message': 'Silent mode was not active'
            })
        
        for silent in silent_modes:
            silent.is_active = False
        
        db.session.commit()
        
        return jsonify({
            'status': 'success',
            'message': 'Silent mode disabled'
        })
        
    except Exception as e:
        logger.error(f"Error disabling silent mode: {str(e)}")
        return jsonify({'error': str(e)}), 500
