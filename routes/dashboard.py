from fastapi import APIRouter, Request, HTTPException, Depends, Query, Path, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates # For rendering HTML templates
from sqlalchemy import desc, func
from sqlalchemy.orm import Session
from pydantic import BaseModel # Import BaseModel

from database_session import get_db # Import the get_db dependency
from models import Conversation, Message, AIResponse, MediaFile, HumanAgentRequest, SilentMode, Order, UserProfile # Add Order and UserProfile if they are used
from services.ai_service import AIService
# from services.whatsapp_service import WhatsAppService
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

router = APIRouter()

# Configure Jinja2Templates
templates = Jinja2Templates(directory="templates") # Assumes templates are in a 'templates' directory

# whatsapp_service_instance = WhatsAppService()

class AssignRequest(BaseModel):
    agent_id: str

class SilentModeEnable(BaseModel):
    duration_hours: int = 24
    admin_name: str = "admin"

@router.get("/", response_class=HTMLResponse)
async def index(request: Request, db: Session = Depends(get_db)):
    """Main dashboard page"""
    try:
        # Get statistics
        total_conversations = db.query(Conversation).count()
        total_messages = db.query(Message).count()
        total_media_files = db.query(MediaFile).count()
        active_conversations = db.query(Conversation).filter_by(is_active=True).count()
        
        # Get recent conversations with message counts
        recent_conversations = db.query(
            Conversation,
            func.count(Message.id).label('message_count'),
            func.max(Message.timestamp).label('last_message_time')
        ).outerjoin(Message).group_by(Conversation.id).order_by(
            desc('last_message_time')
        ).limit(10).all()
        
        # Get recent media files
        recent_media = db.query(MediaFile, Message, Conversation).join(
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
        
        return templates.TemplateResponse("dashboard.html", 
                                      {"request": request,
                                       "stats": stats,
                                       "recent_conversations": recent_conversations,
                                       "recent_media": recent_media})
        
    except Exception as e:
        logger.error(f"Dashboard error: {str(e)}")
        return templates.TemplateResponse("dashboard.html", 
                                      {"request": request,
                                       "stats": {'error': str(e)},
                                       "recent_conversations": [],
                                       "recent_media": []})

@router.get("/conversations", response_class=HTMLResponse)
async def conversations(request: Request, db: Session = Depends(get_db),
                        page: int = Query(1, alias="page"), per_page: int = Query(20, alias="per_page")):
    """List all conversations"""
    try:
        # Get conversations with message counts and last message time
        conversations_query = db.query(
            Conversation,
            func.count(Message.id).label('message_count'),
            func.max(Message.timestamp).label('last_message_time')
        ).outerjoin(Message).group_by(Conversation.id).order_by(
            desc('last_message_time')
        )
        
        # Manual pagination
        total_items = conversations_query.count() # Count before slicing
        conversations_data = conversations_query.offset((page - 1) * per_page).limit(per_page).all()
        
        total_pages = (total_items + per_page - 1) // per_page

        pagination = {
            "page": page,
            "pages": total_pages,
            "per_page": per_page,
            "total": total_items,
            "has_next": page < total_pages,
            "has_prev": page > 1,
        }

        return templates.TemplateResponse("conversations.html", 
                                      {"request": request,
                                       "conversations": conversations_data,
                                       "pagination": pagination})
        
    except Exception as e:
        logger.error(f"Conversations listing error: {str(e)}")
        return templates.TemplateResponse("conversations.html", 
                                      {"request": request,
                                       "conversations": [], 
                                       "pagination": {},
                                       "error": str(e)})

@router.get("/conversation/{conversation_id}", response_class=HTMLResponse)
async def conversation_detail(request: Request, conversation_id: int = Path(...), db: Session = Depends(get_db)):
    """View detailed conversation with messages"""
    try:
        conversation = db.query(Conversation).get(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get all messages for this conversation
        messages = db.query(Message).filter_by(
            conversation_id=conversation_id
        ).order_by(Message.timestamp.asc()).all()
        
        # Get AI responses for messages
        message_responses = {}
        for message in messages:
            responses = db.query(AIResponse).filter_by(message_id=message.id).all()
            message_responses[message.id] = responses
        
        # Get media files for messages
        message_media = {}
        for message in messages:
            if message.message_type in ['image', 'audio', 'video', 'document']:
                media = db.query(MediaFile).filter_by(message_id=message.id).first()
                message_media[message.id] = media
        
        return templates.TemplateResponse("conversation.html",
                                      {"request": request,
                                       "conversation": conversation,
                                       "messages": messages,
                                       "message_responses": message_responses,
                                       "message_media": message_media})
        
    except HTTPException as he:
        raise he # Re-raise HTTPException to be caught by FastAPI's exception handler
    except Exception as e:
        logger.error(f"Conversation detail error: {str(e)}")
        return templates.TemplateResponse("conversation.html",
                                      {"request": request,
                                       "conversation": None,
                                       "messages": [],
                                       "error": str(e)})

@router.get("/api/conversations")
async def api_conversations(db: Session = Depends(get_db),
                          page: int = Query(1, alias="page"),
                          per_page: int = Query(20, alias="per_page"),
                          search: str = Query('', alias="search")):
    """API endpoint for conversations list"""
    try:
        query = db.query(
            Conversation,
            func.count(Message.id).label('message_count'),
            func.max(Message.timestamp).label('last_message_time')
        ).outerjoin(Message).group_by(Conversation.id)
        
        if search:
            # Assuming 'phone_number' and 'contact_name' are attributes of Conversation
            query = query.filter(
                Conversation.user_phone.contains(search) |
                Conversation.contact_name.contains(search)
            )
        
        # Manual pagination for API
        total_items = query.count()
        conversations_data = query.order_by(
            desc('last_message_time')
        ).offset((page - 1) * per_page).limit(per_page).all()
        
        total_pages = (total_items + per_page - 1) // per_page

        result = {
            'conversations': [],
            'pagination': {
                'page': page,
                'pages': total_pages,
                'per_page': per_page,
                'total': total_items,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }
        
        for conv, msg_count, last_time in conversations_data:
            result['conversations'].append({
                'id': conv.id,
                'user_phone': conv.user_phone, # Changed from phone_number to user_phone
                'contact_name': conv.contact_name,
                'message_count': msg_count or 0,
                'last_message_time': last_time.isoformat() if last_time else None,
                'is_active': conv.is_active,
                'created_at': conv.created_at.isoformat(),
                'url': f"/dashboard/conversation/{conv.id}" # Manual URL construction
            })
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"API conversations error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/conversation/{conversation_id}/messages")
async def api_conversation_messages(conversation_id: int = Path(...), db: Session = Depends(get_db),
                                  page: int = Query(1, alias="page"), per_page: int = Query(50, alias="per_page")):
    """API endpoint for conversation messages"""
    try:
        messages_query = db.query(Message).filter_by(
            conversation_id=conversation_id
        ).order_by(Message.timestamp.desc())
        
        total_items = messages_query.count()
        messages_data = messages_query.offset((page - 1) * per_page).limit(per_page).all()
        
        total_pages = (total_items + per_page - 1) // per_page
        
        result = {
            'messages': [],
            'pagination': {
                'page': page,
                'pages': total_pages,
                'per_page': per_page,
                'total': total_items,
                'has_next': page < total_pages,
                'has_prev': page > 1
            }
        }
        
        for message in messages_data:
            # Get AI responses
            ai_responses = db.query(AIResponse).filter_by(message_id=message.id).all()
            
            # Get media file if exists
            media_file = None
            if message.message_type in ['image', 'audio', 'video', 'document']:
                media_file = db.query(MediaFile).filter_by(message_id=message.id).first()
            
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
        
        return JSONResponse(content=result)
        
    except Exception as e:
        logger.error(f"API conversation messages error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/stats")
async def api_stats(db: Session = Depends(get_db)):
    """API endpoint for dashboard statistics"""
    try:
        # Basic counts
        total_conversations = db.query(Conversation).count()
        total_messages = db.query(Message).count()
        total_media_files = db.query(MediaFile).count()
        active_conversations = db.query(Conversation).filter_by(is_active=True).count()
        
        # Message type distribution
        message_types = db.query(
            Message.message_type,
            func.count(Message.id).label('count')
        ).group_by(Message.message_type).all()
        
        # AI response statistics
        ai_responses_count = db.query(AIResponse).count()
        successful_responses = db.query(AIResponse).filter_by(sent_to_whatsapp=True).count()
        
        # Processing statistics
        processed_messages = db.query(Message).filter_by(processed=True).count()
        failed_messages = db.query(Message).filter(Message.processing_error.isnot(None)).count()
        
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
        
        return JSONResponse(content=stats)
        
    except Exception as e:
        logger.error(f"API stats error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/conversation/{conversation_id}/summary")
async def api_conversation_summary(conversation_id: int = Path(...), db: Session = Depends(get_db)):
    """Generate AI summary of a conversation"""
    try:
        conversation = db.query(Conversation).get(conversation_id)
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
        
        # Get conversation messages
        messages = db.query(Message).filter_by(
            conversation_id=conversation_id
        ).order_by(Message.timestamp.asc()).all()
        
        if not messages:
            return JSONResponse(content={'summary': 'No messages in this conversation yet.'})
        
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
        
        return JSONResponse(content={
            'summary': summary,
            'message_count': len(messages),
            'conversation_id': conversation_id
        })
        
    except Exception as e:
        logger.error(f"Conversation summary error: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/human-handoff-requests", response_class=HTMLResponse)
async def api_get_human_handoff_requests(request: Request, db: Session = Depends(get_db),
                                         page: int = Query(1, alias="page"),
                                         per_page: int = Query(20, alias="per_page"),
                                         status_filter: str = Query(default="pending")):
    """API endpoint para listar solicitações de atendimento humano."""
    try:
        query = db.query(HumanAgentRequest)
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
                'conversation_url': f"/dashboard/conversation/{req.conversation_id}"
            })
        
        return templates.TemplateResponse("human_handoff.html", {"request": request, "requests": result['requests']})

    except Exception as e:
        logger.error(f"API human handoff requests error: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/api/human-handoff-requests/{request_id}", response_class=HTMLResponse)
async def api_get_human_handoff_request_detail(request_id: int = Path(...), *, request: Request, db: Session = Depends(get_db)):
    """API endpoint para obter detalhes de uma solicitação de atendimento humano, incluindo histórico completo."""
    try:
        req = db.query(HumanAgentRequest).get_or_404(request_id)
        return templates.TemplateResponse("human_handoff_detail.html", {
            "request": request,
            "id": req.id,
            "conversation_id": req.conversation_id,
            "phone_number": req.phone_number,
            "contact_name": req.contact_name,
            "request_time": req.request_time.isoformat() if req.request_time else None,
            "status": req.status,
            "escalation_reason": req.escalation_reason,
            "ai_summary_of_issue": req.ai_summary_of_issue,
            "full_conversation_history_json": req.full_conversation_history_json,
            "assigned_agent_id": req.assigned_agent_id,
            "assigned_time": req.assigned_time.isoformat() if req.assigned_time else None,
            "resolution_notes": req.resolution_notes,
            "closed_time": req.closed_time.isoformat() if req.closed_time else None,
            "conversation_url": f"/dashboard/conversation/{req.conversation_id}"
        })
    except Exception as e:
        logger.error(f"API human handoff request detail error for ID {request_id}: {str(e)}", exc_info=True)
        raise HTTPException(status_code=404 if isinstance(e, Exception) and "404 Not Found" in str(e) else 500, detail=str(e))

@router.post("/api/human-handoff-requests/{request_id}/assign", response_class=JSONResponse)
async def api_assign_human_handoff_request(request_id: int = Path(...), *, assign_request: AssignRequest, db: Session = Depends(get_db)):
    """API endpoint para um agente se atribuir a uma solicitação."""
    try:
        agent_id = assign_request.agent_id

        if not agent_id:
            return JSONResponse(content={'error': 'agent_id é obrigatório'}, status_code=400)

        req = db.query(HumanAgentRequest).get_or_404(request_id)
        
        if req.status != 'pending':
            return JSONResponse(content={'error': f'Solicitação {request_id} não está pendente (status atual: {req.status})'}, status_code=400)

        req.status = 'assigned'
        req.assigned_agent_id = agent_id
        req.assigned_time = datetime.utcnow()
        db.commit()

        logger.info(f"HumanAgentRequest {request_id} atribuído ao agente {agent_id}")
        return JSONResponse(content={
            'message': 'Solicitação atribuída com sucesso',
            'request': {
                'id': req.id,
                'status': req.status,
                'assigned_agent_id': req.assigned_agent_id,
                'assigned_time': req.assigned_time.isoformat()
            }
        }, status_code=200)

    except Exception as e:
        logger.error(f"Erro ao atribuir HumanAgentRequest {request_id}: {str(e)}", exc_info=True)
        db.rollback()
        return JSONResponse(content={'error': str(e)}, status_code=500)

@router.get("/human-handoff", response_class=HTMLResponse)
async def human_handoff_page(request: Request):
    """Página do dashboard para gerenciar solicitações de atendimento humano."""
    # Esta rota simplesmente renderizaria um template HTML.
    # A lógica de dados viria das chamadas de API (api_get_human_handoff_requests).
    # Por enquanto, apenas uma resposta placeholder.
    # return render_template('human_handoff.html', title="Atendimento Humano") 
    return HTMLResponse(content="Página de Atendimento Humano (template HTML a ser criado)")

@router.post("/api/conversation/{conversation_id}/silent_mode", response_class=JSONResponse)
async def enable_silent_mode(conversation_id: int = Path(...), *, silent_mode_data: SilentModeEnable, db: Session = Depends(get_db)):
    """Ativa o modo silencioso para uma conversa"""
    try:
        duration_hours = silent_mode_data.duration_hours  # Padrão de 24 horas
        admin_name = silent_mode_data.admin_name
        
        conversation = db.query(Conversation).get_or_404(conversation_id)
        
        # Desativa qualquer modo silencioso existente
        existing_silent = db.query(SilentMode).filter_by(
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
        
        db.add(silent_mode)
        db.commit()
        
        return JSONResponse(content={
            'status': 'success',
            'message': f'Silent mode enabled for {duration_hours} hours',
            'expires_at': silent_mode.expires_at.isoformat()
        }, status_code=200)
        
    except Exception as e:
        logger.error(f"Error enabling silent mode: {str(e)}")
        return JSONResponse(content={'error': str(e)}, status_code=500)

@router.delete("/api/conversation/{conversation_id}/silent_mode", response_class=JSONResponse)
async def disable_silent_mode(conversation_id: int = Path(...), db: Session = Depends(get_db)):
    """Desativa o modo silencioso para uma conversa"""
    try:
        conversation = db.query(Conversation).get_or_404(conversation_id)
        
        # Desativa todos os modos silenciosos ativos
        silent_modes = db.query(SilentMode).filter_by(
            conversation_id=conversation_id,
            is_active=True
        ).all()
        
        if not silent_modes:
            return JSONResponse(content={
                'status': 'warning',
                'message': 'Silent mode was not active'
            }, status_code=200)
        
        for silent in silent_modes:
            silent.is_active = False
        
        db.commit()
        
        return JSONResponse(content={
            'status': 'success',
            'message': 'Silent mode disabled'
        }, status_code=200)
        
    except Exception as e:
        logger.error(f"Error disabling silent mode: {str(e)}")
        return JSONResponse(content={'error': str(e)}, status_code=500)
