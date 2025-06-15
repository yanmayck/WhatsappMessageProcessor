import pytest
from app import create_app  # Import the app factory
from config import Config   # Import your config

class TestConfig(Config):
    TESTING = True
    SQLALCHEMY_DATABASE_URI = "sqlite:///:memory:"  # Use an in-memory SQLite DB for tests
    # Add other test-specific configurations here if needed

@pytest.fixture
def app():
    """Create and configure a new app instance for each test."""
    _app = create_app(TestConfig) # Use the test config
    yield _app

@pytest.fixture

def client(app):
    """A test client for the app."""
    return app.test_client()


def test_home_page_not_found(client):
    """Test the home page (/) returns 404 as it's not explicitly defined."""
    # Assuming '/' is not a defined route and should return 404
    # If you have a blueprint registered at '/', this test will need adjustment
    response = client.get('/')
    assert response.status_code == 404

# Example for testing a blueprint route, e.g., a route in webhook_bp
# You might need to adjust the route and expected status code
def test_webhook_get(client):
    """Test a GET request to the /webhook/ endpoint."""
    # This is an example. Your /webhook might not support GET or might expect specific headers/payload
    # Adjust this test based on your actual webhook implementation.
    response = client.get('/webhook/') 
    # If your webhook is POST only, this might be 405 (Method Not Allowed)
    # Or if GET is allowed but expects something, it might be another status.
    # For now, let's assume GET to /webhook/ itself might be a 404 or a specific page if you have an index for it.
    # If it's just for POST, then a GET could be 405 or 404 depending on Flask's behavior with your setup.
    # Let's assume it's 404 if no specific GET handler is there.
    assert response.status_code == 404 # Or 405, or 200 if you have a GET handler for /webhook/

# You should add more tests for your actual routes and logic.
# For example, if your dashboard has an index page:
# def test_dashboard_index(client):
#     response = client.get('/dashboard/')
#     assert response.status_code == 200
#     assert b"Welcome to the Dashboard" in response.data # Check for some content 