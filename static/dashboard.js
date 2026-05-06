const eventsContainer = document.getElementById("eventsContainer");
const cameraStatusText = document.getElementById("cameraStatus");
const sourceTypeText = document.getElementById("sourceType");
const hasFrameText = document.getElementById("hasFrame");
const agentStatusText = document.getElementById("agentStatus");
const chatLog = document.getElementById("chatLog");
const chatQuestion = document.getElementById("chatQuestion");
const askBtn = document.getElementById("askBtn");

const history = [];

function pushChat(role, text) {
  history.push({ role, content: text });
  if (history.length > 8) {
    history.shift();
  }

  const el = document.createElement("div");
  el.className = "chat-entry";
  const label = role === "user" ? "Usuario" : "Agente";
  el.innerHTML = `<strong>${label}:</strong> ${text.replace(/\n/g, "<br>")}`;
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
        <img src="${event.image_path}" alt="Evidencia ${event.label}" />
        <div>
          <strong>${event.label}</strong>
          <p>Confianca: ${Number(event.confidence).toFixed(2)}</p>
          <p>${event.event_time}</p>
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

setInterval(loadEvents, 5000);
setInterval(loadCameraStatus, 5000);
setInterval(loadAgentStatus, 10000);
