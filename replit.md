# WhatsApp AI System

## Overview

This is a Flask-based WhatsApp AI chatbot system that integrates with WhatsApp's API to receive messages, process multimedia content, and respond using Google's Gemini AI. The system handles text, image, audio, video, and document messages, stores them in a database, processes them through AI services, and provides a web dashboard for monitoring conversations.

## User Preferences

Preferred communication style: Simple, everyday language.

## System Architecture

### Backend Architecture
- **Framework**: Flask with SQLAlchemy ORM
- **Database**: SQLite (default) with PostgreSQL support via environment configuration
- **WSGI Server**: Gunicorn for production deployment
- **Deployment**: Autoscaling on Replit infrastructure

### Frontend Architecture
- **Templates**: Jinja2 templating with Bootstrap dark theme
- **Static Assets**: CSS/JS for dashboard interface
- **UI Framework**: Bootstrap with Replit's dark theme CSS
- **Icons**: Feather Icons for consistent iconography

### AI Integration
- **Primary AI**: Google Gemini 2.0 Flash (for text, image, and multimodal processing)
- **Content Processing**: Specialized models for different content types (text, vision, multimodal)
- **Response Generation**: Context-aware responses with conversation history

## Key Components

### Database Models
- **Conversation**: Tracks WhatsApp conversations by phone number
- **Message**: Stores individual messages with metadata and processing status
- **AIResponse**: Stores AI-generated responses linked to messages
- **MediaFile**: Handles multimedia file storage and metadata

### Service Layer
- **WhatsAppService**: Handles WhatsApp API communication (sending/receiving messages)
- **AIService**: Manages Gemini AI integration and response generation
- **MediaProcessor**: Processes images, audio, video, and documents
- **CloudStorageService**: Manages Google Cloud Storage for media files

### API Routes
- **Webhook Endpoint**: `/webhook/whatsapp` (GET for verification, POST for message handling)
- **Dashboard Routes**: Web interface for monitoring conversations and system stats
- **Conversation Views**: Individual conversation management and viewing

### Media Processing Pipeline
1. **Media Reception**: Download media from WhatsApp API
2. **Processing**: Optimize images, convert audio formats, extract document content
3. **Storage**: Upload to Google Cloud Storage with public access
4. **AI Analysis**: Process media through appropriate Gemini models
5. **Response Generation**: Generate contextual AI responses

## Data Flow

1. **Incoming Messages**: WhatsApp webhook receives messages
2. **Message Storage**: Store message data and metadata in database
3. **Media Processing**: Download and process any attached media
4. **Cloud Upload**: Store processed media in Google Cloud Storage
5. **AI Processing**: Send content to Gemini AI for analysis
6. **Response Generation**: Generate appropriate AI response
7. **Message Sending**: Send AI response back via WhatsApp API
8. **Dashboard Updates**: Real-time updates to web dashboard

### Async Processing
- Uses threading for non-blocking media processing
- Background tasks for AI response generation
- Configurable processing thread pool

## External Dependencies

### Required APIs
- **WhatsApp Business API**: For message sending/receiving (via waho.com unofficial API)
- **Google Gemini AI**: For content analysis and response generation
- **Google Cloud Storage**: For media file storage and serving

### Python Packages
- **Flask Ecosystem**: Flask, Flask-SQLAlchemy, Werkzeug
- **Database**: SQLAlchemy, psycopg2-binary (PostgreSQL support)
- **AI/ML**: google-generativeai, google-cloud-storage
- **Media Processing**: Pillow (images), pydub (audio)
- **HTTP Client**: requests for API communication
- **Server**: gunicorn for production serving

### Environment Variables
- `WHATSAPP_API_URL`: WhatsApp API endpoint
- `WHATSAPP_API_TOKEN`: Authentication token
- `WEBHOOK_VERIFY_TOKEN`: Webhook verification token
- `GEMINI_API_KEY`: Google AI API key
- `GOOGLE_CLOUD_PROJECT_ID`: GCP project identifier
- `DATABASE_URL`: Database connection string

## Deployment Strategy

### Replit Configuration
- **Runtime**: Python 3.11 with Nix package management
- **Packages**: Includes ffmpeg, image libraries, PostgreSQL client
- **Auto-scaling**: Configured for automatic scaling based on demand
- **Process Management**: Gunicorn with port binding and reload capability

### Production Considerations
- **Security**: Environment-based secrets management
- **Monitoring**: Comprehensive logging throughout the application
- **Error Handling**: Graceful degradation with error logging
- **Performance**: Connection pooling, async processing, media optimization

### File Structure
- **Routes**: Modular blueprint-based routing (`routes/`)
- **Services**: Business logic separation (`services/`)
- **Templates**: Jinja2 templates with inheritance (`templates/`)
- **Static Assets**: CSS/JS for frontend functionality (`static/`)
- **Configuration**: Centralized config management (`config.py`)

The system is designed for scalability and maintainability, with clear separation of concerns between data handling, AI processing, media management, and user interface components.