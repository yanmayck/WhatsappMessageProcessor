from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from unittest.mock import patch
from datetime import datetime, timedelta

from models import Conversation, Message, HumanAgentRequest, AIResponse, MediaFile, SilentMode, UserProfile # Import all models needed

def test_dashboard_index(client: TestClient, db_session: Session):
    # Create some dummy data
    conv1 = Conversation(user_phone="1234567890", contact_name="Test User 1")
    conv2 = Conversation(user_phone="9876543210", contact_name="Test User 2", is_active=False)
    db_session.add_all([conv1, conv2])
    db_session.commit()
    db_session.refresh(conv1)
    db_session.refresh(conv2)

    msg1 = Message(conversation_id=conv1.id, whatsapp_message_id="msg1", sender_phone="1234567890", message_type="text", content="Hello", timestamp=datetime.utcnow() - timedelta(minutes=10))
    msg2 = Message(conversation_id=conv1.id, whatsapp_message_id="msg2", sender_phone="1234567890", message_type="image", content="", timestamp=datetime.utcnow() - timedelta(minutes=5))
    db_session.add_all([msg1, msg2])
    db_session.commit()
    db_session.refresh(msg1)
    db_session.refresh(msg2)

    media1 = MediaFile(message_id=msg2.id, original_url="http://example.com/img.jpg", cloud_storage_bucket="test-bucket", cloud_storage_path="path/img.jpg", public_url="http://public.com/img.jpg", file_name="img.jpg", mime_type="image/jpeg", uploaded_at=datetime.utcnow())
    db_session.add(media1)
    db_session.commit()

    response = client.get("/dashboard/")
    assert response.status_code == 200
    assert "Total Conversations" in response.text
    assert "Test User 1" in response.text # Check for conversation data

def test_dashboard_conversations(client: TestClient, db_session: Session):
    conv1 = Conversation(user_phone="11111", contact_name="Conv A")
    conv2 = Conversation(user_phone="22222", contact_name="Conv B")
    db_session.add_all([conv1, conv2])
    db_session.commit()

    response = client.get("/dashboard/conversations")
    assert response.status_code == 200
    assert "Conv A" in response.text
    assert "Conv B" in response.text

def test_dashboard_conversation_detail(client: TestClient, db_session: Session):
    conv = Conversation(user_phone="33333", contact_name="Detail Test")
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    msg = Message(conversation_id=conv.id, whatsapp_message_id="detail_msg", sender_phone="33333", message_type="text", content="Detail message", timestamp=datetime.utcnow())
    db_session.add(msg)
    db_session.commit()
    db_session.refresh(msg)

    response = client.get(f"/dashboard/conversation/{conv.id}")
    assert response.status_code == 200
    assert "Detail Test" in response.text
    assert "Detail message" in response.text

def test_dashboard_conversation_detail_not_found(client: TestClient):
    response = client.get("/dashboard/conversation/99999") # Non-existent ID
    assert response.status_code == 404

def test_api_conversations(client: TestClient, db_session: Session):
    conv1 = Conversation(user_phone="44444", contact_name="API Conv 1")
    conv2 = Conversation(user_phone="55555", contact_name="API Conv 2")
    db_session.add_all([conv1, conv2])
    db_session.commit()

    response = client.get("/dashboard/api/conversations")
    assert response.status_code == 200
    data = response.json()
    assert len(data['conversations']) >= 2
    assert data['conversations'][0]['user_phone'] == "55555" # Assuming ordering by last_message_time (default None)
    assert data['pagination']['total'] >= 2

def test_api_conversations_search(client: TestClient, db_session: Session):
    conv = Conversation(user_phone="66666", contact_name="Search User")
    db_session.add(conv)
    db_session.commit()

    response = client.get("/dashboard/api/conversations?search=Search")
    assert response.status_code == 200
    data = response.json()
    assert len(data['conversations']) == 1
    assert data['conversations'][0]['contact_name'] == "Search User"

def test_api_conversation_messages(client: TestClient, db_session: Session):
    conv = Conversation(user_phone="77777", contact_name="Msg Test")
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    msg1 = Message(conversation_id=conv.id, whatsapp_message_id="msg_api_1", sender_phone="77777", message_type="text", content="Msg One", timestamp=datetime.utcnow() - timedelta(minutes=2))
    msg2 = Message(conversation_id=conv.id, whatsapp_message_id="msg_api_2", sender_phone="77777", message_type="text", content="Msg Two", timestamp=datetime.utcnow() - timedelta(minutes=1))
    db_session.add_all([msg1, msg2])
    db_session.commit()

    response = client.get(f"/dashboard/api/conversation/{conv.id}/messages")
    assert response.status_code == 200
    data = response.json()
    assert len(data['messages']) == 2
    assert data['messages'][0]['content'] == "Msg Two" # Ordered by desc timestamp

def test_api_stats(client: TestClient, db_session: Session):
    conv = Conversation(user_phone="88888")
    msg_text = Message(conversation_id=conv.id, whatsapp_message_id="stat_msg_text", sender_phone="88888", message_type="text", content="Stat text", processed=True)
    msg_img = Message(conversation_id=conv.id, whatsapp_message_id="stat_msg_img", sender_phone="88888", message_type="image", content="", processed=True)
    ai_resp = AIResponse(message_id=msg_text.id, agent_name="TestAI", response_content="AI response", sent_to_whatsapp=True)

    db_session.add_all([conv, msg_text, msg_img, ai_resp])
    db_session.commit()

    response = client.get("/dashboard/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data['totals']['total_conversations'] >= 1
    assert data['totals']['total_messages'] >= 2
    assert data['message_types']['text'] >= 1

# Mocking AIService for summary generation
@patch('services.ai_service.AIService.generate_summary')
def test_api_conversation_summary(mock_generate_summary, client: TestClient, db_session: Session):
    mock_generate_summary.return_value = "This is a generated summary."

    conv = Conversation(user_phone="99999", contact_name="Summary Test")
    db_session.add(conv)
    db_session.commit()
    db_session.refresh(conv)

    msg1 = Message(conversation_id=conv.id, whatsapp_message_id="sum_msg1", sender_phone="99999", message_type="text", content="First message.", timestamp=datetime.utcnow() - timedelta(minutes=2))
    msg2 = Message(conversation_id=conv.id, whatsapp_message_id="sum_msg2", sender_phone="99999", message_type="text", content="Second message.", timestamp=datetime.utcnow() - timedelta(minutes=1))
    db_session.add_all([msg1, msg2])
    db_session.commit()

    response = client.get(f"/dashboard/api/conversation/{conv.id}/summary")
    assert response.status_code == 200
    data = response.json()
    assert data['summary'] == "This is a generated summary."
    assert data['message_count'] == 2
    mock_generate_summary.assert_called_once() 