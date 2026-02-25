# 🌐 OmniLab

> Interface multimodal estilo Laboratório Stark — autossuficiente, modular e escalável.

**Status:** Desenvolvimento ativo · [Hackatime/Flavortown](https://flavortown.hackclub.com)

---

## O que é?

OmniLab é uma plataforma de interação multimodal que combina:

- 👁️ **Visão Computacional** — gestos de mão detectados pela câmera
- 🗣️ **Voz** — comandos de linguagem natural
- 🧠 **IA Orquestradora** — JARVIS-like, processa intenção e despacha ações
- 🖥️ **HUD 3D no Browser** — interface holográfica renderizada em Three.js

Processamento pesado roda na nuvem. O módulo local só é necessário para acessar a câmera.

---

## Setup Local

> Só necessário quando for usar a câmera. Nada de dependência suja no seu PC.

```bash
# 1. Clone o repo
git clone https://github.com/EngThi/OmniLab.git
cd OmniLab

# 2. Crie o ambiente virtual (fica só aqui, não vai pro Git)
python -m venv .venv
source .venv/bin/activate  # Linux/Mac

# 3. Instale as dependências
pip install -r requirements.txt

# 4. Baixe o modelo MediaPipe (não vai pro Git)
python scripts/download_model.py

# 5. Rode o módulo de visão
python vision.py
```

---

## Estrutura

```
OmniLab/
├── vision.py              # Módulo de câmera: detecta gestos, envia JSON
├── requirements.txt       # Dependências Python (só módulo local)
├── scripts/
│   └── download_model.py  # Baixa o hand_landmarker.task (~7.8MB)
└── README.md
```

> ⚠️ O modelo `hand_landmarker.task` e o `.venv/` **não estão no repo** — são gerados localmente via scripts acima.
