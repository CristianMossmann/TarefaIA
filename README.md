# AgroVision AI

Sistema de monitoramento em tempo real com FastAPI + YOLO (Ultralytics) + Ollama.

## O que o sistema faz

- Captura video de camera local, stream HTTP/RTSP ou arquivo.
- Detecta objetos com YOLO e filtro de classes alvo.
- Aplica regra de confirmacao por frames consecutivos.
- Aplica cooldown por classe para reduzir alertas repetidos.
- Salva evidencias em imagem e registra eventos em SQLite.
- Exibe dashboard com stream ao vivo e eventos recentes.
- Oferece chat operacional com contexto dos ultimos eventos via Ollama.

## Requisitos

### Sistema

- Linux (testado neste projeto).
- Python 3.11+.
- Acesso de rede para baixar dependencias e modelo YOLO na primeira execucao.

### Python

Dependencias do arquivo `requirements.txt`:

- fastapi==0.115.0
- uvicorn[standard]==0.30.6
- opencv-python==4.10.0.84
- ultralytics==8.3.0
- jinja2==3.1.4
- python-multipart==0.0.9

### Ollama

- Ollama instalado localmente.
- Modelo `llama3` baixado.
- Servico Ollama acessivel em `http://127.0.0.1:11434`.

## Estrutura principal

- `app.py`: API principal e rotas.
- `services/video_monitor.py`: camera, inferencia YOLO, stream MJPEG.
- `services/event_repository.py`: persistencia SQLite (`detections.db`).
- `services/monitoring_agent.py`: construcao de contexto e mensagens do agente.
- `services/ollama_client.py`: cliente HTTP do Ollama.
- `templates/index.html`: dashboard.
- `static/dashboard.css`: estilos.
- `static/dashboard.js`: atualizacao do painel e chat.
- `static/captures/`: evidencias capturadas.

## Passo a passo para rodar

1. Entrar na pasta do projeto

```bash
cd /home/user/Documents/BioPark_Projects/IA/TreinamentoIA
```

2. Criar e ativar ambiente virtual

```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. Instalar dependencias Python

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

4. Configurar variaveis de ambiente

```bash
cp .env.example .env
```

Revise pelo menos estes campos no `.env`:

- `CAMERA_SOURCE`
- `OLLAMA_URL`
- `OLLAMA_MODEL`
- `CONFIDENCE_THRESHOLD`

5. Subir o Ollama

Se nao estiver rodando:

```bash
ollama serve
```

Em outro terminal, baixar modelo:

```bash
ollama pull llama3
```

6. Subir o backend

```bash
.venv/bin/python -m uvicorn app:app --reload
```

7. Abrir dashboard

- `http://127.0.0.1:8000`

## Validacao rapida

Com o backend ativo, rode:

1. Health check

```bash
curl -sS http://127.0.0.1:8000/health
```

2. Status da camera

```bash
curl -sS http://127.0.0.1:8000/camera/status
```

3. Teste do chat com Ollama

```bash
curl -sS -X POST http://127.0.0.1:8000/chat \
  -H 'Content-Type: application/json' \
  -d '{"question":"Responda apenas OK.","history":[]}'
```

Se estiver tudo certo, o campo `answer` retorna texto do modelo (ex.: `OK`).

## Endpoints principais

- `GET /`: dashboard
- `GET /health`: status da API
- `GET /events`: eventos recentes
- `GET /frame`: ultimo frame JPEG
- `GET /video_feed`: stream MJPEG
- `GET /camera/status`: status da camera/fonte
- `GET /agent/status`: status do agente
- `POST /chat`: pergunta contextual para o agente
- `GET /scraping/weather`: clima atual + previsao (camada de scraping)
- `GET /scraping/commodities`: cotacoes agro (camada de scraping)

## Camada de Web Scraping

O pacote `services/scraping/` busca dados publicos e gratuitos para
enriquecer o sistema:

- **Clima** via `wttr.in` (sem chave de API). Justificativa: o sistema
  detecta movimentacao em ambiente agricola, e o "normal" depende
  fortemente do clima. O contexto climatico em cache eh injetado no
  prompt do agente Ollama em cada `/chat`.
- **Cotacoes agro** via `noticiasagricolas.com.br`. Justificativa:
  picos de movimentacao costumam acompanhar dias de alta nos precos
  (mais caminhoes, mais pessoas).

Boas praticas aplicadas:

- Cliente HTTP com timeout, User-Agent declarado e limite de payload (1 MB).
- Cache em memoria (TTL configuravel) para nao bater na fonte a cada refresh.
- Rate limiter (janela deslizante de 60s) para nao sobrecarregar a fonte.
- Tratamento de erro: a rota devolve `503` com `status="error"` se a fonte estiver fora.
- Saida sempre em JSON estruturado.

Variaveis de ambiente da camada de scraping:

- `SCRAPING_WEATHER_LOCATION` (default `Cascavel`)
- `SCRAPING_WEATHER_TTL` (segundos, default `900`)
- `SCRAPING_COMMODITIES_TTL` (segundos, default `1800`)
- `SCRAPING_REQUEST_TIMEOUT` (segundos, default `8`)
- `SCRAPING_MAX_RPM` (requisicoes por minuto, default `10`)

## Troubleshooting

### No module named uvicorn

Use o Python do ambiente virtual:

```bash
.venv/bin/python -m uvicorn app:app --reload
```

### connection refused no /chat

O Ollama nao esta ativo no `OLLAMA_URL`.

- Verifique servico: `curl -sS http://127.0.0.1:11434/api/tags`
- Inicie: `ollama serve`

### Timeout no /chat

- O primeiro request pode demorar por carga do modelo.
- Se usar timeout curto (ex.: 30s), o request pode falhar mesmo com sistema correto.
- Em testes manuais, use timeout maior (ex.: 120s a 600s) no primeiro request.
- Aumente temporariamente `OLLAMA_TIMEOUT` no `.env`.
- Reenvie o teste apos o modelo estar aquecido.

### Porta 11434 ocupada

Ja existe Ollama rodando na maquina. Normalmente isso e suficiente.
Se precisar usar outra porta, ajuste `OLLAMA_URL` no `.env` para o host/porta corretos.

## Observacoes

- O YOLO pode baixar pesos automaticamente na primeira execucao.
- O banco `detections.db` e criado automaticamente.
- Evidencias sao salvas em `static/captures/`.
