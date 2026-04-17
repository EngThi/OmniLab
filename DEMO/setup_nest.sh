#!/bin/bash
echo "🛠️ Instalando dependências no Nest..."
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m playwright install chromium
echo "✅ Setup concluído. Para rodar: source .venv/bin/activate && python3 server.py"
