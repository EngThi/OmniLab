#!/bin/bash

# --- CONFIGURAÇÃO ---
SERVER_USER="chefthi"
SERVER_IP="hackclub.app"
REMOTE_PATH="~/omnilab"

echo "🚀 Preparando OmniLab para deploy..."

# Criar um tarball ignorando venv e node_modules
tar --exclude='.venv' --exclude='__pycache__' --exclude='.git' --exclude='.idx' -czf omnilab_deploy.tar.gz .

echo "📤 Enviando para o servidor ($SERVER_IP)..."
scp omnilab_deploy.tar.gz $SERVER_USER@$SERVER_IP:~/

echo "🏗️  Executando build remoto..."
ssh $SERVER_USER@$SERVER_IP << EOF
  mkdir -p $REMOTE_PATH
  tar -xzf ~/omnilab_deploy.tar.gz -C $REMOTE_PATH
  cd $REMOTE_PATH
  # Se o seu .env já estiver lá, use-o. Se não, você precisará configurar as variáveis.
  docker compose up -d --build
  rm ~/omnilab_deploy.tar.gz
EOF

echo "✅ Deploy finalizado! Acesse http://$SERVER_IP:8000"
rm omnilab_deploy.tar.gz
