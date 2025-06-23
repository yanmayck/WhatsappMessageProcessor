from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch

from models import HumanAgentRequest

def test_reset_human_agent_queue_success(client: TestClient, db_session: Session):
    # Set a dummy token for testing
    with patch('config.Config.INTERNAL_TASK_TOKEN', 'test_secret_token'):
        # Add a dummy request to be deleted
        req = HumanAgentRequest(conversation_id=1, phone_number="12345", request_reason="test")
        db_session.add(req)
        db_session.commit()

        response = client.post(
            "/tasks/reset-human-agent-queue",
            headers={'Authorization': 'Bearer test_secret_token'}
        )
        assert response.status_code == 200
        assert response.json()['status'] == "success"
        assert response.json()['rows_deleted'] == 1

        # Verify queue is empty
        assert db_session.query(HumanAgentRequest).count() == 0

def test_reset_human_agent_queue_unauthorized(client: TestClient):
    with patch('config.Config.INTERNAL_TASK_TOKEN', 'test_secret_token'):
        response = client.post(
            "/tasks/reset-human-agent-queue",
            headers={'Authorization': 'Bearer wrong_token'}
        )
        assert response.status_code == 403
        assert response.json() == {"detail": "Unauthorized"}

def test_reset_human_agent_queue_no_token_configured(client: TestClient):
    with patch('config.Config.INTERNAL_TASK_TOKEN', None):
        response = client.post(
            "/tasks/reset-human-agent-queue",
            headers={'Authorization': 'Bearer any_token'} # Token header is irrelevant if config is None
        )
        assert response.status_code == 500
        assert response.json() == {"detail": "Configuration error: Task token not set."} 