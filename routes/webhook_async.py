# routes/webhook_async.py

import logging
from fastapi import APIRouter, Request, Response, BackgroundTasks, HTTPException, Header, Query
from typing import Optional, Dict, Any

from config import Config

logger = logging.getLogger(__name__)

# No FastAPI, um APIRouter é o equivalente a um Blueprint do Flask.
# Ele nos ajuda a organizar as rotas.
router = APIRouter()

# Vamos definir a "forma" dos dados que esperamos receber usando Pydantic
# Isto é opcional, mas é uma prática recomendada para validação.
# Por simplicidade, vamos usar um Dicionário Genérico por enquanto.
# Em um projeto real, definiríamos cada campo (key, message, etc.)

@router.get("/whatsapp")
async def verify_webhook(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Verifica a assinatura do webhook do WhatsApp.
    """
    if hub_mode == "subscribe" and hub_verify_token == Config.WEBHOOK_VERIFY_TOKEN:
        logger.info("Webhook verificado com sucesso via FastAPI.")
        return Response(content=hub_challenge, media_type="text/plain")
    logger.warning(f"Falha na verificação do webhook. Token recebido: {hub_verify_token}")
    raise HTTPException(status_code=403, detail="Token de verificação inválido.")


@router.post("/whatsapp")
async def handle_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    apikey: Optional[str] = Header(None)
):
    """
    Recebe e processa as mensagens do WhatsApp em segundo plano.
    """
    # 1. Validação de Segurança
    if not apikey or apikey != Config.EVOLUTION_API_KEY:
        logger.warning("Tentativa de acesso ao webhook sem API Key válida.")
        raise HTTPException(status_code=403, detail="Acesso não autorizado.")

    # 2. Recebimento dos Dados
    try:
        webhook_data = await request.json()
    except:
        raise HTTPException(status_code=400, detail="Payload JSON inválido.")
    
    logger.info("Payload recebido no webhook FastAPI.")

    # 3. Processamento em Segundo Plano
    # Aqui usamos o BackgroundTasks, que é a forma correta e eficiente
    # de fazer o que você estava fazendo com 'threading'.
    # A função 'process_message_task' será chamada DEPOIS que a resposta 200 OK for enviada.
    
    # background_tasks.add_task(process_message_task, webhook_data) # Vamos implementar essa função depois

    # 4. Resposta Imediata
    return {"status": "recebido"}