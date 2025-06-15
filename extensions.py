from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.ext.declarative import declarative_base

# Create base class for models
Base = declarative_base()

# Initialize SQLAlchemy
db = SQLAlchemy()

# Function to initialize the database with the Flask app
def init_db(app):
    db.init_app(app)
    with app.app_context():
        db.create_all() 