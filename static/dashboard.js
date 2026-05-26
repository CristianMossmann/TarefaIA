const eventsContainer = document.getElementById("eventsContainer");
const cameraStatusText = document.getElementById("cameraStatus");
const sourceTypeText = document.getElementById("sourceType");
const hasFrameText = document.getElementById("hasFrame");
const agentStatusText = document.getElementById("agentStatus");
const weatherBox = document.getElementById("weatherBox");
const commoditiesBox = document.getElementById("commoditiesBox");
const chatLog = document.getElementById("chatLog");
const chatQuestion = document.getElementById("chatQuestion");
const askBtn = document.getElementById("askBtn");

function escapeHtml(value) {
  return String(value ?? "")
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .replace(/"/g, "&quot;")
    .replace(/'/g, "&#39;");
}

const history = [];

function pushChat(role, text) {
  history.push({ role, content: text });
  if (history.length > 8) {
    history.shift();
  }

  const el = document.createElement("div");
  el.className = "chat-entry";
  const label = role === "user" ? "Usuario" : "Agente";
  el.innerHTML = `<strong>${label}:</strong> ${escapeHtml(text).replace(/\n/g, "<br>")}`;
  chatLog.appendChild(el);
  chatLog.scrollTop = chatLog.scrollHeight;
}

function renderEvents(events) {
  if (!events || events.length === 0) {
    eventsContainer.innerHTML = '<p class="note">Nenhum evento detectado ainda.</p>';
    return;
  }

  const html = events
    .map(
      (event) => `
      <li class="item">
        <img src="${escapeHtml(event.image_path)}" alt="Evidencia ${escapeHtml(event.label)}" />
        <div>
          <strong>${escapeHtml(event.label)}</strong>
          <p>Confianca: ${Number(event.confidence).toFixed(2)}</p>
          <p>${escapeHtml(event.event_time)}</p>
        </div>
      </li>
    `,
    )
    .join("");

  eventsContainer.innerHTML = `<ul class="list">${html}</ul>`;
}

async function loadEvents() {
  try {
    const response = await fetch("/events");
    const events = await response.json();
    renderEvents(events);
  } catch (err) {
    eventsContainer.innerHTML = '<p class="note">Falha ao carregar eventos.</p>';
  }
}

async function loadCameraStatus() {
  try {
    const response = await fetch("/camera/status");
    const status = await response.json();

    cameraStatusText.textContent = status.online ? "Online" : "Offline";
    sourceTypeText.textContent = status.source_type || "-";
    hasFrameText.textContent = status.has_live_frame ? "Sim" : "Nao";
  } catch (err) {
    cameraStatusText.textContent = "Falha";
    sourceTypeText.textContent = "-";
    hasFrameText.textContent = "-";
  }
}

async function loadAgentStatus() {
  try {
    const response = await fetch("/agent/status");
    const status = await response.json();
    agentStatusText.textContent = `${status.name} | Eventos no contexto: ${status.events_in_context}`;
  } catch (err) {
    agentStatusText.textContent = "Falha ao consultar agente";
  }
}

function renderWeather(result) {
  if (!result || result.status !== "ok") {
    const msg = result?.message || "Indisponivel no momento.";
    weatherBox.innerHTML = `<span class="note">${escapeHtml(msg)}</span>`;
    return;
  }
  const data = result.data || {};
  const c = data.current || {};
  const forecast = (data.forecast || [])
    .map(
      (d) => `<li>${escapeHtml(d.date)}: ${escapeHtml(d.min_c)}°C - ${escapeHtml(d.max_c)}°C (chuva ${escapeHtml(d.rain_chance_pct)}%)</li>`,
    )
    .join("");
  weatherBox.innerHTML = `
    <p><strong>${escapeHtml(data.location || "")}</strong></p>
    <p>${escapeHtml(c.description || "-")}</p>
    <p>Temp.: ${escapeHtml(c.temperature_c || "?")}°C (sens. ${escapeHtml(c.feels_like_c || "?")}°C)</p>
    <p>Umidade: ${escapeHtml(c.humidity_pct || "?")}% | Vento: ${escapeHtml(c.wind_kmph || "?")} km/h</p>
    <p>Precipitacao: ${escapeHtml(c.precip_mm || "?")} mm</p>
    <ul class="mini-list">${forecast}</ul>
    <p class="note">Fonte: ${escapeHtml(result.source || "")}</p>
  `;
}

function renderCommodities(result) {
  if (!result || result.status !== "ok") {
    const msg = result?.message || "Indisponivel no momento.";
    commoditiesBox.innerHTML = `<span class="note">${escapeHtml(msg)}</span>`;
    return;
  }
  const prices = (result.data?.prices || [])
    .map(
      (p) => `<li><strong>${escapeHtml(p.commodity)}</strong>: ${escapeHtml(p.value_raw)} ${escapeHtml(p.currency)}</li>`,
    )
    .join("");
  commoditiesBox.innerHTML = `
    <ul class="mini-list">${prices || '<li class="note">Sem itens reconhecidos.</li>'}</ul>
    <p class="note">Fonte: ${escapeHtml(result.source || "")}</p>
  `;
}

async function loadWeather() {
  try {
    const response = await fetch("/scraping/weather");
    const data = await response.json();
    renderWeather(data);
  } catch (err) {
    renderWeather({ status: "error", message: "Falha ao consultar clima." });
  }
}

async function loadCommodities() {
  try {
    const response = await fetch("/scraping/commodities");
    const data = await response.json();
    renderCommodities(data);
  } catch (err) {
    renderCommodities({ status: "error", message: "Falha ao consultar cotacoes." });
  }
}

async function askAgent() {
  const question = chatQuestion.value.trim();
  if (!question) {
    return;
  }

  askBtn.disabled = true;
  pushChat("user", question);
  chatQuestion.value = "";

  try {
    const response = await fetch("/chat", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question, history }),
    });

    const data = await response.json();
    pushChat("assistant", data.answer || "Sem resposta no momento.");
  } catch (err) {
    pushChat("assistant", "Nao foi possivel responder agora. Verifique o Ollama.");
  } finally {
    askBtn.disabled = false;
  }
}

askBtn.addEventListener("click", askAgent);
chatQuestion.addEventListener("keydown", (ev) => {
  if (ev.key === "Enter" && (ev.ctrlKey || ev.metaKey)) {
    askAgent();
  }
});

loadEvents();
loadCameraStatus();
loadAgentStatus();
loadWeather();
loadCommodities();

setInterval(loadEvents, 5000);
setInterval(loadCameraStatus, 5000);
setInterval(loadAgentStatus, 10000);
setInterval(loadWeather, 60000);
setInterval(loadCommodities, 120000);
