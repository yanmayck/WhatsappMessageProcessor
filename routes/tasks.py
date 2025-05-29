import logging
from flask import Blueprint, jsonify, request, current_app
from app import db
from models import HumanAgentRequest

logger = logging.getLogger(__name__)
tasks_bp = Blueprint('tasks', __name__)

@tasks_bp.route('/tasks/reset-human-agent-queue', methods=['POST'])
def reset_human_agent_queue():
    """Endpoint para ser chamado pelo Cloud Scheduler para resetar a fila de solicitações de agente humano."""
    # Medida de segurança: Verificar um token bearer no header Authorization
    # Em produção, o Cloud Scheduler pode ser configurado para enviar um token OIDC 
    # que pode ser verificado pelo Cloud Run para uma segurança ainda maior.
    # Por agora, usaremos um token bearer simples.
    auth_header = request.headers.get('Authorization')
    expected_token = f"Bearer {current_app.config.get('INTERNAL_TASK_TOKEN')}"

    if not current_app.config.get('INTERNAL_TASK_TOKEN'):
        logger.error("INTERNAL_TASK_TOKEN não está configurado no servidor. Endpoint de reset não pode ser executado com segurança.")
        # Em um cenário de produção real, você pode querer retornar 500 ou uma mensagem mais genérica.
        return jsonify({"status": "error", "message": "Configuration error: Task token not set."}), 500

    if not auth_header or auth_header != expected_token:
        logger.warning(f"Tentativa não autorizada de resetar a fila de agentes humanos. Header: {auth_header}")
        return jsonify({"status": "error", "message": "Unauthorized"}), 403

    try:
        num_rows_deleted = db.session.query(HumanAgentRequest).delete()
        db.session.commit()
        logger.info(f"Fila de solicitações de agente humano resetada com sucesso. {num_rows_deleted} registros excluídos.")
        return jsonify({"status": "success", "message": "Human agent request queue reset.", "rows_deleted": num_rows_deleted}), 200
    except Exception as e:
        db.session.rollback()
        logger.error(f"Erro ao resetar fila de solicitações de agente humano: {str(e)}", exc_info=True)
        return jsonify({"status": "error", "message": f"Failed to reset queue: {str(e)}"}), 500 