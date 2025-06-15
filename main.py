import os
from app import create_app

# A instância da aplicação é agora criada pela fábrica create_app()
# Gunicorn (e outros servidores WSGI) procurará por uma variável 'app' 
# ou poderá ser configurado para chamar a fábrica diretamente (ex: 'main:create_app()').
app = create_app()

# Adicionado para permitir rodar o servidor de desenvolvimento com python main.py
if __name__ == '__main__':
    # Usa a porta da variável de ambiente PORT ou 8080 como padrão
    # debug=True é útil para desenvolvimento
    port = int(os.environ.get('PORT', 8080))
    app.run(host='0.0.0.0', port=port, debug=True)
