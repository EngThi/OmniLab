# OmniLab 🧪

[![Python](https://img.shields.io/badge/python-3.10%2B-blue.svg)](https://www.python.org/downloads/)
[![CI](https://github.com/EngThi/OmniLab/actions/workflows/ci.yml/badge.svg)](https://github.com/EngThi/OmniLab/actions)

Ambiente de teste e desenvolvimento para IAs modulares, agentes autônomos e automação fluída.

> "A interface invisível entre pensamento e execução"

## 🚀 GIF Demo
![OmniLab HUD Demo](https://via.placeholder.com/800x450?text=GIF:+Abrir+HUD+->+Mover+mão+->+IA+responde)
*(Placeholder: Abrir HUD → mover mão → IA responde)*

## ⚡ Optimization (Sidequest v0.2)

OmniLab implementa três técnicas de otimização de performance para reduzir custos de API, latência e pressão de memória.

### Técnica 1 — Application-Level Caching (Deduplicação de Frames)
**O que:** Antes de chamar a API Gemini, o servidor calcula um hash MD5 da imagem otimizada. Se o hash existir em um cache LRU (em memória) com TTL de 30s, a resposta salva é retornada instantaneamente.

**Por que:** Feeds de câmera frequentemente enviam frames quase idênticos. Sem cache, cada frame dispararia uma chamada de API completa (~800ms latência + custo de tokens).

**Resultados:**
| Cenário | Antes | Depois |
|---|---|---|
| Frames repetidos/similares | ~800ms | **~0ms** (cache hit) |
| Chamadas API por 60s de stream | ~60 | **~3–8** (apenas em mudanças de cena) |

### Técnica 2 — Efficient Data Structures (Gestão O(1))
**O que:** Substituído o uso de `list` por `set` para gerenciar `hud_connections` e `vision_connections`. `set.discard()` é O(1), enquanto `list.remove()` é O(n).

**Por que:** Sob carga com múltiplas conexões WebSocket, a remoção O(n) cria gargalos perceptíveis nas atualizações do HUD.

### Técnica 3 — Optimize Asset Sizes (Downscaling de Imagem)
**O que:** Antes de enviar o frame ao Gemini, o OmniLab o redimensiona para no máximo 512×512px e re-encoda como JPEG qualidade 70 usando filtros LANCZOS.

**Por que:** Frames HD (1280x720+) desperdiçam largura de banda e aumentam a latência de resposta sem melhorar a qualidade da descrição técnica.

**Resultados:**
| Métrica | Antes (HD) | Depois (512px) |
|---|---|---|
| Tamanho do Payload | ~180 KB | **~28 KB** (84% menor) |
| Latência da Resposta API | ~820ms | **~540ms** |

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
2. **OpenCV frame**: Processa a imagem para detecção de mãos (MediaPipe Tasks API).
3. **Gemini Vision**: Quando solicitado, o frame é enviado para a API do Gemini para análise técnica.
4. **WebSocket**: Gestos e resultados de análise são transmitidos instantaneamente para o HUD.
5. **HUD**: Interface modular imersiva (Three.js) servida via `static/index.html`.
