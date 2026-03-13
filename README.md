# OmniLab 🧪

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/your-username/OmniLab/actions/workflows/ci.yml/badge.svg)](https://github.com/your-username/OmniLab/actions)

Ambiente de teste e desenvolvimento para IAs modulares, agentes autônomos e automação fluída.

> "A interface invisível entre pensamento e execução"

## 🚀 GIF Demo
![OmniLab HUD Demo](https://via.placeholder.com/800x450?text=GIF:+Abrir+HUD+->+Mover+mão+->+IA+responde)
*(Placeholder: Abrir HUD → mover mão → IA responde)*

## 🛠️ Quick Start (3 comandos)

```bash
# 1. Instalar as dependências
pip install -r requirements.txt

# 2. Configurar ambiente (adicione sua GEMINI_API_KEY no .env)
cp .env.example .env 

# 3. Iniciar o sistema (Server + Vision)
python server.py & python vision.py
```

*Nota: Se `server.py` não iniciar o loop, rode em terminais separados.*

## 🧠 How it works
1. **Webcam**: Captura frames em tempo real via OpenCV.
2. **OpenCV frame**: Processa a imagem para detecção de mãos (MediaPipe).
3. **Gemini Vision**: Quando solicitado, o frame é enviado para a API do Gemini para análise técnica.
4. **WebSocket**: Gestos e resultados de análise são transmitidos instantaneamente para o HUD.
5. **HUD**: Interface imersiva (Three.js) que renderiza o feedback visual e dados da IA.

## 🚀 Deploy & Demo
- **Local**: Runs locally, open [http://localhost:8000](http://localhost:8000)
- **Replit**: [OmniLab on Replit](https://replit.com/@username/OmniLab) (Demo)
- **HuggingFace Spaces**: [OmniLab Spaces](https://huggingface.co/spaces/username/OmniLab)

## 📋 Requisitos
- Python 3.10+
- Webcam funcional
- Conexão com a internet (para Gemini API)

---
*OmniLab - O futuro da interação humano-IA.*
