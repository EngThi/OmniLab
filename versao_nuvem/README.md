
# Teste na Nuvem (Google VM) ☁️

Essa pasta tem a versão adaptada do OmniLab pra rodar num servidor que não tem webcam física (tipo uma instância lá no Google Cloud).

A mágica aqui é: o **seu navegador (no seu PC)** liga a câmera, comprime o vídeo e joga os frames pro backend via WebSocket. O backend processa o MediaPipe lá na nuvem e devolve a posição do dedo, a pinça e o vídeo desenhado pra sua tela.

## Como rodar lá na VM

1. Dá um `git pull` na VM.
2. Certifique-se de que instalou as dependências (`pip install -r requirements.txt` na raiz) e baixou o modelo.
3. Entra nessa pasta: 
   ```bash
   cd versao_nuvem
   ```
4. Sobe o bicho liberando o acesso externo:
   ```bash
   uvicorn main:app --host 0.0.0.0 --port 8000
   ```

## ⚠️ AVISO IMPORTANTE SOBRE A CÂMERA ⚠️

O Google Chrome (e os outros tbm) **bloqueia** o acesso à câmera se a página não tiver HTTPS ou não for `localhost`. Se você tentar abrir direto pelo IP da VM tipo `http://34.123...:8000`, a câmera não vai ligar e vai dar erro no console.

**Como burlar isso rapidão:**
- **Se você tá acessando a VM pelo VS Code (Remote SSH):** O próprio VS Code faz um túnel. Só abrir no seu navegador `http://localhost:8000` que ele redireciona automático pra VM como se fosse local e a câmera liga feliz.
- **Se quiser abrir via IP mesmo (Ngrok):** Instala o ngrok na VM, roda `ngrok http 8000` e acessa o link seguro HTTPS que ele vai gerar no terminal.
