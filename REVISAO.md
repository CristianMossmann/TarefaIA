# Revisão Crítica do Projeto AgroVision AI

Projeto analisado: AgroVision AI (FastAPI + YOLO + Ollama + SQLite).
Estrutura de pastas atual: `app.py`, `services/`, `templates/`, `static/`.

---

## Parte 1 — Revisão da Arquitetura

### Camadas hoje no projeto

| Camada                  | Onde mora                                                 | Estado |
|-------------------------|-----------------------------------------------------------|--------|
| Frontend                | `templates/index.html`, `static/dashboard.js`, `dashboard.css` | Existe, separado |
| Backend / API           | `app.py` (FastAPI)                                        | Existe, separado |
| Banco de dados          | `services/event_repository.py` (SQLite)                   | Isolado em repositório |
| Serviços internos       | `services/capture_store.py`, `services/monitoring_agent.py` | Separado |
| Camada de IA / YOLO     | `services/video_monitor.py`                               | Acoplada ao laço de captura |
| Integração externa (LLM)| `services/ollama_client.py`                               | Isolado |
| Camada de scraping      | **não existia** — implementada nesta entrega em `services/scraping/` | Nova |

### Respostas exigidas pelo enunciado

**A interface está apenas exibindo dados ou também possui regra de negócio indevida?**
A interface é majoritariamente apresentação. Há um detalhe: `static/dashboard.js` mantém manualmente o histórico de chat truncado em 8 mensagens (`history.shift()` quando passa de 8). Esse limite é uma **regra de negócio do agente** — está também repetida em `services/monitoring_agent.py:MAX_HISTORY_MESSAGES = 8`. Hoje funciona, mas é duplicação: o backend já trunca, então o cliente não precisa decidir nada. **Recomendação:** o frontend só deve exibir e enviar; o limite fica no backend. Ação concreta: remover o `history.shift()` do JS, ou expor o limite via `/agent/status`.

**O backend concentra a lógica principal do sistema?**
Sim. `app.py` é fino (delega para serviços), `services/monitoring_agent.py` carrega prompt do agente e contexto, `services/video_monitor.py` carrega o pipeline YOLO. **Mas** `app.py:39-43` registra `startup_event` que inicializa banco + thread de câmera + warmup do LLM. Está aceitável para um projeto deste porte, porém qualquer crescimento deve mover esses *bootstraps* para um módulo `services/bootstrap.py` para reduzir o número de responsabilidades em `app.py`.

**O acesso ao banco está isolado em uma camada própria ou aparece espalhado pelo código?**
Isolado. `EventRepository` é o único ponto que toca SQLite. Nenhuma outra rota ou serviço importa `sqlite3` direto. ✔️ Bom design.

**A chamada ao modelo de IA / YOLO está separada da regra de negócio?**
Parcialmente. O `VideoMonitor` mistura três responsabilidades:
1. Conexão e leitura da câmera (`_run`, `cv2.VideoCapture`);
2. Inferência YOLO (`self.model(frame, ...)`);
3. Regra de alerta (frames consecutivos, cooldown, salvar evidência, gravar evento).

Em um sistema maior eu separaria em `CameraSource`, `Detector` e `AlertPolicy`. Para o escopo atual o acoplamento é tolerável, mas vale registrar como dívida.

A chamada ao Ollama está bem separada (`OllamaClient` só faz HTTP; `monitoring_agent.py` cuida do prompt). ✔️

**A nova camada de scraping será implementada como serviço separado ou ficará misturada em rotas, telas ou controllers?**
Foi implementada como pacote separado em `services/scraping/`, com:
- `http_client.py`: cliente HTTP com timeout, User-Agent e cabeçalhos seguros;
- `rate_limiter.py`: limitador de requisições por janela;
- `cache.py`: cache em memória com TTL;
- `weather_scraper.py`: scraper de clima (wttr.in);
- `commodity_scraper.py`: scraper de cotações agro (HTML);
- `scraping_service.py`: fachada usada pela rota `/scraping/...`.

`app.py` apenas instancia e expõe — nenhuma lógica de scraping vaza para a rota.

### Resumo

A arquitetura está saudável para o tamanho atual. Pontos fortes: repositório de eventos isolado, cliente LLM isolado, frontend pequeno. Pontos a melhorar (não bloqueadores): separar `VideoMonitor` em câmera + detector + política, mover bootstrap de startup, eliminar duplicação do limite de histórico entre frontend e backend.

---

## Parte 2 — Revisão de Segurança

### Riscos encontrados (com referência no código original)

| # | Risco                                                                                       | Onde                                            | Severidade |
|---|---------------------------------------------------------------------------------------------|-------------------------------------------------|------------|
| 1 | Mensagens técnicas vazadas ao usuário (stack/`exc` em string)                              | `services/ollama_client.py:47-54`               | Média      |
| 2 | Rotas da API sem autenticação ou rate-limit (`/chat`, `/events`, `/frame`, `/video_feed`)  | `app.py` inteiro                                | Alta em produção / OK em demo local |
| 3 | `limit` em `/events` aceita qualquer inteiro sem validação (`limit: int = 50`)             | `app.py:71-73`                                  | Baixa-Média |
| 4 | CORS não configurado — o dashboard só funciona no mesmo host, mas qualquer site pode atacar via CSRF nas rotas POST se forem expostas | `app.py`                                | Média se exposto |
| 5 | `cv2.VideoCapture(self.camera_source)` aceita qualquer string vinda do `.env`. Fonte hostil pode levar a leitura de arquivo local (`file:///etc/passwd` por OpenCV/ffmpeg) | `services/video_monitor.py:91`                  | Média      |
| 6 | Banco SQLite usa parâmetros (`?`) — **sem SQL Injection**. ✔️                              | `services/event_repository.py:40,64`            | OK         |
| 7 | Diretório de capturas é servido público por `/static` — qualquer um na rede vê todas as evidências | `app.py:15`                                | Médio em produção |
| 8 | Frontend monta HTML com `innerHTML` usando `event.label`, `event.image_path` vindos do banco. Hoje só o backend insere — mas é XSS latente se um dia o `label` vier de input do usuário | `static/dashboard.js:36-45,21` | Baixa hoje, Alta no futuro |
| 9 | `_read_dotenv_file` faz `setdefault` em `os.environ`; se a variável já existir no shell, o `.env` é ignorado silenciosamente — risco operacional, não de segurança | `services/config.py:24` | Baixa |
| 10 | `OllamaClient` envia `messages` ao LLM com conteúdo do usuário (`payload.question`). Pydantic limita a 5000 chars, mas o **prompt injection** ainda é possível: usuário pode pedir ao agente que ignore o system prompt. Para um agente operacional isso pode mudar o tom da resposta | `services/monitoring_agent.py:86-91` | Média |
| 11 | Arquivo de evidência usa `datetime.now().strftime('%H%M%S')` como event_id no nome — colisão possível se dois alertas ocorrerem no mesmo segundo | `services/video_monitor.py:160-161` | Baixa (corrigido na Parte 3) |
| 12 | Senhas/chaves no código: **nenhuma encontrada**. ✔️ `.env.example` não traz segredo, `.gitignore` exclui `.env`. | — | OK |

### Avaliação para IA / scraping / upload

- **Upload de arquivos**: o projeto **não** aceita upload do usuário. Sem risco aqui.
- **IA (LLM)**: aceita texto livre. Validado tamanho via Pydantic. **Prompt injection é possível** mas o agente é só de leitura (não executa ações nem ferramentas) — impacto limitado a resposta enganosa.
- **Scraping** (camada nova): risco é o **inverso** — fonte externa pode devolver HTML/JSON malicioso. Mitigações implementadas:
  - timeout fixo em cada requisição;
  - User-Agent declarado;
  - resposta limitada por tamanho (`HTTPClient` corta payload acima de 1 MB);
  - parser usa `html.parser` (stdlib) — não executa JS;
  - todos os campos extraídos são **strings simples** e passam por `strip()` + truncamento;
  - cache + rate-limit impedem que um erro vire DoS contra o site público.

### Mitigações aplicadas nesta entrega

1. **`OllamaClient.chat`** — não retorna mais `str(exc)` ao usuário (Parte 3, snippet 1).
2. **`/events`** — `limit` agora restringido a `1..200` (mudança em `app.py`).
3. **Scraping** — todos os mitigantes listados acima.
4. **Filename de evidência** — passou a usar UUID para evitar colisão (Parte 3, snippet 2).

Mitigações **não aplicadas nesta entrega** (precisariam de decisão do grupo):
- Autenticação nas rotas → exige escolha de mecanismo (token, OAuth, etc.) e cadastro de usuários.
- CORS + CSRF token → só faz sentido depois que existir autenticação.
- Proteção do `/static/captures` → exige migrar para rota autenticada que serve imagem.

---

## Parte 3 — Melhoria de Código Gerado com IA

Foram escolhidos três trechos que claramente passaram pela IA e tinham problema real (não cosmético).

### Snippet 1 — Vazamento de detalhes técnicos no cliente Ollama

**Arquivo:** `services/ollama_client.py:42-54`

**O que o código fazia originalmente:**
Capturava `urllib.error.URLError` e `Exception` e retornava a string com `exc` direto para o usuário final via `/chat`:

```python
except urllib.error.URLError as exc:
    return (
        "Nao foi possivel conectar ao Ollama. "
        "Verifique se o servico esta ativo em http://127.0.0.1:11434. "
        f"Detalhe tecnico: {exc}"
    )
except Exception as exc:
    return f"Falha ao consultar o Ollama: {exc}"
```

**Problema encontrado:**
1. **Vazamento de informação** — devolve URL interna, traceback parcial, mensagens de socket e às vezes path local para o navegador.
2. **Mensagem para humano misturada com diagnóstico** — quem opera o dashboard vê "Detalhe técnico" no chat.
3. **`except Exception`** engole qualquer bug do código (não só erro de rede), mascarando defeito.

**O que foi melhorado:**
- Resposta ao usuário ficou genérica e operacional.
- Detalhe técnico vai para `print` (log) para o operador, **não** para o cliente.
- `except Exception` foi reduzido a categorias específicas (`URLError`, `TimeoutError`, `json.JSONDecodeError`); o resto sobe e aparece como erro no log do servidor.

**Por que a nova versão é melhor:**
- Não vaza topologia interna nem stack de execução.
- Bugs reais aparecem nos logs ao invés de virar string no chat.
- Mais fácil de monitorar (erros viram log estruturado).

### Snippet 2 — Nome de evidência colidindo no mesmo segundo

**Arquivo:** `services/video_monitor.py:159-169`

**O que o código fazia originalmente:**
```python
def _save_alert_frame(self, frame, label: str, confidence: float) -> None:
    event_id = datetime.now().strftime("%H%M%S")
    filename = f"{datetime.now().strftime('%Y%m%d_%H%M%S')}_{label}_{event_id}.jpg"
    filepath = self.save_dir / filename
    os.makedirs(self.save_dir, exist_ok=True)
    cv2.imwrite(str(filepath), frame)
    image_path = f"/static/captures/{filename}"
    self.event_repository.save_event(label, confidence, image_path)
    print(f"[ALERTA] {label} detectado. Evidencia salva em {filepath}")
```

**Problema encontrado:**
1. `event_id` é apenas `HHMMSS` — colide com o próprio `%Y%m%d_%H%M%S` do filename (mesma informação duas vezes).
2. Se dois alertas diferentes (ex.: `person` e `car`) caem no mesmo segundo, ainda colidem — `cv2.imwrite` sobrescreve.
3. `os.makedirs` toda chamada é desperdício — o diretório já é criado no startup (`services/config.py:77`).
4. `print` direto ao stdout é frágil; nenhuma severidade ou timestamp formatado.

**O que foi melhorado:**
- Filename agora usa `uuid.uuid4().hex[:8]` como sufixo único.
- Remoção do `os.makedirs` redundante.
- `print` substituído por `logging.getLogger(__name__).info(...)` com nível adequado.

**Por que a nova versão é melhor:**
- Zero risco de colisão de arquivo, mesmo em rajadas.
- Menos I/O de sistema (não chama `mkdir` por alerta).
- Loga via `logging`, permitindo redirecionar para arquivo / agregador.

### Snippet 3 — `/chat` síncrono bloqueia o event loop do FastAPI

**Arquivo:** `app.py:106-113`

**O que o código fazia originalmente:**
```python
@app.post("/chat", response_model=ChatResponse)
def chat(payload: ChatRequest):
    events = event_repository.list_events(settings.agent_event_limit)
    history = [msg.model_dump() for msg in payload.history]
    messages = build_agent_messages(payload.question, history, events)
    answer = ollama_client.chat(messages)
    return ChatResponse(answer=answer, model=settings.ollama_model)
```

**Problema encontrado:**
1. Rota declarada `def` (síncrona) — FastAPI executa em threadpool, mas a chamada `ollama_client.chat()` usa `urllib.request.urlopen` que pode **bloquear até 120s** (`OLLAMA_TIMEOUT`).
2. Apesar do threadpool, requisições simultâneas no `/chat` competem com `/events` e `/video_feed`, podendo esgotar workers do uvicorn.
3. Não há limite de tamanho **além** do Pydantic (5 000 chars) — aceita 5k chars 100 vezes por segundo de um cliente abusivo.
4. Não há tratamento explícito quando o Ollama está offline (a mensagem volta no JSON como `answer`, então status code é 200 — não dá para o cliente saber que falhou).

**O que foi melhorado:**
- A chamada externa virou `await asyncio.to_thread(ollama_client.chat, messages)`, mantendo o event loop livre.
- `limit` da rota `/events` ficou restrito (`Query(default=50, ge=1, le=200)`).
- Quando o cliente Ollama retorna a string de falha, a rota agora devolve `503` em vez de `200`.

**Por que a nova versão é melhor:**
- O servidor segue respondendo `/video_feed` e `/events` enquanto o LLM responde.
- Cliente entende que `503` significa "serviço de IA indisponível" sem precisar parsear texto.
- Limites explícitos reduzem superfície de DoS local.

---

## Parte 4 — Camada de Web Scraping

Ver `services/scraping/` e seção dedicada no final do README do projeto.
Justificativa, fontes, limites, formato e integração estão lá; o resumo está abaixo.

### Dado coletado e por quê

**Dado:** previsão do tempo da localidade configurada + cotações de commodities agrícolas (soja, milho, boi gordo).

**Por que isso enriquece o AgroVision:**
- O sistema detecta movimentação de pessoas, veículos e máquinas em ambiente agrícola.
- Clima muda drasticamente o que é "normal" — em chuva forte, **ausência** de máquinas é esperada; em dia seco, ausência pode indicar paralisação. O agente Ollama recebe esse contexto e qualifica melhor o alerta.
- Cotação de commodities ajuda a interpretar picos de movimentação: dia de alta no boi gordo costuma trazer mais caminhões e pessoas para a fazenda; o operador entende o aumento como **planejado**, não anomalia.

### Fontes (públicas e gratuitas)

| Dado          | Fonte                            | Tipo de coleta            |
|---------------|----------------------------------|---------------------------|
| Clima atual / forecast | `wttr.in` (formato JSON `?format=j1`) | HTTP GET, sem chave |
| Cotações agro | `melhorcambio.com.br` / fallback estático | HTML, BeautifulSoup-like (parser stdlib) |

Ambas são públicas, sem cadastro, sem chave de API.

### Requisitos técnicos atendidos

- ✔ **Função/serviço separado**: `services/scraping/` (pacote isolado).
- ✔ **Fonte pública e gratuita**: wttr.in (clima) — sem chave; HTML público para cotações.
- ✔ **Tratamento de erro**: `try/except` por scraper; retorna `ScrapingResult(status="error", ...)` em vez de quebrar.
- ✔ **Limite de requisições**: `RateLimiter` (janela deslizante) — máximo configurável por host.
- ✔ **Dados estruturados em JSON**: todo retorno é `dict` serializável.
- ✔ **Integração com o sistema**: rotas `/scraping/weather` e `/scraping/commodities`; painel no dashboard; **contexto do clima é injetado no prompt do agente Ollama** quando há cache válido.
- ✔ **Cache com TTL**: evita re-scraping a cada refresh do dashboard.

Detalhes técnicos da implementação estão nos próprios arquivos do pacote `services/scraping/`.
