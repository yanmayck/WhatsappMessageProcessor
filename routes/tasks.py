import logging
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from database_session import get_db # Import the get_db dependency
from models import HumanAgentRequest
from config import Config

logger = logging.getLogger(__name__)
router = APIRouter()

@router.post("/reset-human-agent-queue")
async def reset_human_agent_queue(request: Request, db: Session = Depends(get_db)):
    """Endpoint para ser chamado pelo Cloud Scheduler para resetar a fila de solicitações de agente humano."""
    auth_header = request.headers.get('Authorization')
    expected_token = f"Bearer {Config.INTERNAL_TASK_TOKEN}"

    if not Config.INTERNAL_TASK_TOKEN:
        logger.error("INTERNAL_TASK_TOKEN não está configurado no servidor. Endpoint de reset não pode ser executado com segurança.")
        raise HTTPException(status_code=500, detail="Configuration error: Task token not set.")

    if not auth_header or auth_header != expected_token:
        logger.warning(f"Tentativa não autorizada de resetar a fila de agentes humanos. Header: {auth_header}")
        raise HTTPException(status_code=403, detail="Unauthorized")

    try:
        num_rows_deleted = db.query(HumanAgentRequest).delete()
        db.commit()
        logger.info(f"Fila de solicitações de agente humano resetada com sucesso. {num_rows_deleted} registros excluídos.")
        return JSONResponse(content={"status": "success", "message": "Human agent request queue reset.", "rows_deleted": num_rows_deleted}, status_code=200)
    except Exception as e:
        db.rollback()
        logger.error(f"Erro ao resetar fila de solicitações de agente humano: {str(e)}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"Failed to reset queue: {str(e)}") 