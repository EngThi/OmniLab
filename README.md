
# OmniLab

Ambiente de teste e desenvolvimento para IAs modulares, agentes autônomos e automação fluída.

> "A interface invisível entre pensamento e execução"

## Arquitetura
O OmniLab foca em rodar localmente no momento (Python + MediaPipe + FastAPI), renderizando um HUD (Heads-Up Display) no próprio navegador em tempo real usando WebSockets. A "nuvem" (n8n, Supabase, LLMs pesados) só é acessada quando necessário para tarefas cognitivas.

## Como rodar

1. Instalar as dependências:
   ```bash
   pip install -r requirements.txt
   ```

2. Baixar o modelo de visão localmente:
   ```bash
   python scripts/download_model.py
   ```

3. Iniciar o servidor web com o HUD (abre a porta 8000):
   ```bash
   uvicorn server:app --reload
   ```
   > Acesse http://localhost:8000 para ver a tela do seu HUD (ficará com status "Connected" verde se funcionar).

4. Em outro terminal (na mesma pasta), iniciar a visão computacional:
   ```bash
   python vision.py
   ```
   > Seu navegador começará a rastrear seu dedo indicador (uma bolinha verde que muda quando você faz "pinça"). O OmniLab tá vivo.
