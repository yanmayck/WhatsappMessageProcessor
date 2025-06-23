from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

# Assuming your app and models are correctly imported in conftest.py
# and that the client fixture provides access to your FastAPI app

def test_verify_webhook_success(client: TestClient):
    response = client.get("/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=YOUR_VERIFY_TOKEN&hub.challenge=CHALLENGE_ACCEPTED")
    assert response.status_code == 200
    assert response.text == "CHALLENGE_ACCEPTED"

def test_verify_webhook_failure(client: TestClient):
    response = client.get("/webhook/whatsapp?hub.mode=subscribe&hub.verify_token=WRONG_TOKEN&hub.challenge=CHALLENGE_ACCEPTED")
    assert response.status_code == 403
    assert response.json() == {"detail": "Forbidden"}

# You would add more comprehensive tests here for the POST /whatsapp endpoint,
# including various message types, media handling, and AI interactions.
# This would involve mocking external services (WhatsAppService, AIService, CloudStorageService).

# Example of a simplified test for handle_webhook (needs mocking of external services)
# def test_handle_webhook_text_message(client: TestClient, db_session: Session):
#     # Mock Config.EVOLUTION_API_KEY and other external services
#     from unittest.mock import patch
#     with patch('config.Config.EVOLUTION_API_KEY', 'test_api_key'), \
#          patch('services.whatsapp_service.WhatsAppService.send_text_message') as mock_send_text_message, \
#          patch('services.ai_service.AIService.process_text_message') as mock_process_text_message:

#         mock_process_text_message.return_value = {'success': True, 'response': 'AI response'}

#         payload = {
#             "event": "messages.upsert",
#             "apikey": "test_api_key",
#             "data": {
#                 "key": {"id": "test_msg_id", "remoteJid": "5511999999999@s.whatsapp.net"},
#                 "messageTimestamp": 1678886400,
#                 "messageType": "conversation",
#                 "message": {"conversation": "Hello, bot!"}
#             }
#         }
#         response = client.post("/webhook/whatsapp", json=payload)

#         assert response.status_code == 200
#         assert response.json() == {"status": "success"}
#         mock_send_text_message.assert_called_once_with(to_number="5511999999999", text="AI response")

#         # Verify database entries (requires querying db_session)
#         message = db_session.query(Message).filter_by(whatsapp_message_id="test_msg_id").first()
#         assert message is not None
#         assert message.content == "Hello, bot!"
#         ai_response = db_session.query(AIResponse).filter_by(message_id=message.id).first()
#         assert ai_response is not None
#         assert ai_response.response_content == "AI response" 