import os
import logging
from flask import Flask
from werkzeug.middleware.proxy_fix import ProxyFix
from config import Config
from extensions import db # Importa db de extensions.py

# Configure logging for debugging
logging.basicConfig(level=logging.DEBUG)

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    # Initialize Flask extensions here
    db.init_app(app)

    # ProxyFix
    app.wsgi_app = ProxyFix(app.wsgi_app, x_proto=1, x_host=1)

    # Register blueprints here
    from routes.webhook import webhook_bp
    from routes.dashboard import dashboard_bp
    from routes.tasks import tasks_bp

    app.register_blueprint(webhook_bp, url_prefix='/webhook')
    app.register_blueprint(dashboard_bp, url_prefix='/dashboard')
    app.register_blueprint(tasks_bp, url_prefix='/tasks')

    # Create database tables if they don't exist
    # É importante fazer isso dentro do contexto da aplicação
    with app.app_context():
        db.create_all()
        # Aqui você pode adicionar qualquer outra inicialização que dependa do app_context
        # Exemplo: initialize_vector_db(app)

    return app

# Se você quiser rodar localmente com 'flask run' ou 'python app.py'
# esta parte é útil, mas para Gunicorn, ele usará a fábrica create_app.
if __name__ == '__main__':
    app = create_app()
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 8080)), debug=True)
