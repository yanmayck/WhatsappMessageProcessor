#!/usr/bin/env python3
"""
Script para configurar ngrok para o webhook do WhatsApp AI System
Execute este script para expor seu servidor local publicamente
"""

import subprocess
import sys
import os
import json
import time
import requests
import shutil  # Adicionado para verificação de comando multiplataforma
from urllib.parse import urljoin

def check_ngrok_installed():
    """Verifica se o ngrok está instalado e no PATH do sistema"""
    return shutil.which('ngrok') is not None

def install_ngrok():
    """Instruções para instalar ngrok"""
    print("🔧 Para instalar o ngrok:")
    print("1. Visite: https://ngrok.com/download")
    print("2. Baixe e instale o ngrok para seu sistema")
    print("3. Execute: ngrok authtoken SEU_TOKEN")
    print("4. Execute novamente este script")
    return False

def get_ngrok_tunnels():
    """Pega os túneis ativos do ngrok"""
    try:
        response = requests.get('http://localhost:4040/api/tunnels')
        if response.status_code == 200:
            return response.json()
        return None
    except:
        return None

def start_ngrok_tunnel(port=8080):
    """Inicia o túnel ngrok"""
    print(f"🚀 Iniciando túnel ngrok na porta {port}...")
    
    # Inicia ngrok em background
    process = subprocess.Popen(
        ['ngrok', 'http', str(port)],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE
    )
    
    # Aguarda um pouco para o ngrok inicializar
    time.sleep(3)
    
    # Pega a URL pública
    tunnels = get_ngrok_tunnels()
    if tunnels and tunnels.get('tunnels'):
        for tunnel in tunnels['tunnels']:
            if tunnel['proto'] == 'https':
                public_url = tunnel['public_url']
                webhook_url = urljoin(public_url, '/webhook/whatsapp')
                
                print("✅ Túnel ngrok criado com sucesso!")
                print(f"🌐 URL Pública: {public_url}")
                print(f"📱 Webhook URL: {webhook_url}")
                print(f"🔗 Dashboard ngrok: http://localhost:4040")
                
                return {
                    'public_url': public_url,
                    'webhook_url': webhook_url,
                    'process': process
                }
    
    print("❌ Erro ao criar túnel ngrok")
    process.terminate()
    return None

def save_webhook_config(webhook_url):
    """Salva a configuração do webhook"""
    config = {
        'webhook_url': webhook_url,
        'created_at': time.time()
    }
    
    with open('ngrok_config.json', 'w') as f:
        json.dump(config, f, indent=2)
    
    print(f"💾 Configuração salva em ngrok_config.json")

def show_integration_instructions(webhook_url):
    """Mostra instruções para configurar no WhatsApp Business API"""
    print("\n" + "="*60)
    print("📱 CONFIGURAÇÃO DO WEBHOOK NO WHATSAPP")
    print("="*60)
    print(f"URL do Webhook: {webhook_url}")
    print("\n🔧 Passos para configurar:")
    print("1. Acesse seu provedor de WhatsApp Business API")
    print("2. Configure o webhook com a URL acima")
    print("3. Use o token de verificação configurado no .env")
    print("4. Teste enviando uma mensagem")
    print("\n💡 Dica: Mantenha este terminal aberto para o ngrok funcionar!")

def main():
    print("🎯 WhatsApp AI System - Configuração do Ngrok")
    print("=" * 50)
    
    if not check_ngrok_installed():
        print("❌ Ngrok não encontrado!")
        install_ngrok()
        return
    
    # Verifica se o servidor Flask está rodando
    try:
        response = requests.get('http://localhost:8080')
        print("✅ Servidor Flask detectado na porta 8080")
    except:
        print("⚠️  Servidor Flask não está rodando na porta 8080")
        print("   Inicie o servidor primeiro: python main.py")
        return
    
    # Inicia o túnel ngrok
    tunnel_info = start_ngrok_tunnel()
    
    if tunnel_info:
        webhook_url = tunnel_info['webhook_url']
        save_webhook_config(webhook_url)
        show_integration_instructions(webhook_url)
        
        try:
            print("\n⏳ Pressione Ctrl+C para parar o ngrok...")
            tunnel_info['process'].wait()
        except KeyboardInterrupt:
            print("\n🛑 Parando ngrok...")
            tunnel_info['process'].terminate()
            print("✅ Ngrok parado com sucesso!")

if __name__ == "__main__":
    main()