from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


MAX_HISTORY_MESSAGES = 8


@dataclass(frozen=True)
class AgentProfile:
    name: str
    role: str
    goal: str


AGENT_PROFILE = AgentProfile(
    name="Agente AgroVision",
    role="triagem operacional de eventos",
    goal="Analisar deteccoes recentes, explicar riscos e sugerir a proxima acao.",
)


def normalize_history(history: list[dict]) -> list[dict]:
    normalized: list[dict] = []

    for msg in history[-MAX_HISTORY_MESSAGES:]:
        role = msg.get("role", "user")
        content = (msg.get("content") or "").strip()
        if role not in {"user", "assistant"}:
            continue
        if not content:
            continue
        normalized.append({"role": role, "content": content[:5000]})

    return normalized


def build_event_context(events: list[dict]) -> str:
    if not events:
        return (
            "Contexto operacional para o agente:\n"
            "- Eventos considerados: 0\n"
            "- Ainda nao ha eventos detectados no periodo analisado."
        )

    label_counter = Counter([event["label"] for event in events])
    distribution = ", ".join(
        f"{label}: {count}" for label, count in label_counter.most_common()
    )

    avg_conf = sum(float(event["confidence"]) for event in events) / len(events)
    latest = events[0]

    lines = [
        "Contexto operacional para o agente:",
        f"- Eventos considerados: {len(events)}",
        f"- Evento mais recente: {latest['label']} em {latest['event_time']}",
        f"- Distribuicao recente: {distribution}",
        f"- Confianca media: {avg_conf:.2f}",
        "Eventos recentes:",
    ]

    for event in events[:8]:
        lines.append(
            "- #{id} | {event_time} | {label} | conf={confidence:.2f}".format(
                **event
            )
        )

    return "\n".join(lines)


def build_agent_messages(question: str, history: list[dict], events: list[dict]) -> list[dict]:
    system_prompt = (
        f"Voce e o {AGENT_PROFILE.name}, um agente de {AGENT_PROFILE.role}. "
        f"Objetivo: {AGENT_PROFILE.goal} "
        "Trate os dados como monitoramento operacional autorizado de ambiente real. "
        "Responda em portugues do Brasil, de forma direta e util. "
        "Use os eventos fornecidos como fonte principal. "
        "Nao invente dados que nao aparecem no contexto. "
        "Nao tente identificar pessoas; fale apenas sobre eventos, riscos e proximas acoes. "
        "Quando fizer sentido, organize a resposta em: Leitura, Risco e Recomendacao."
    )

    return [
        {"role": "system", "content": system_prompt},
        {"role": "system", "content": build_event_context(events)},
        *normalize_history(history),
        {"role": "user", "content": question.strip()},
    ]


def build_agent_status(events: list[dict]) -> dict:
    return {
        "name": AGENT_PROFILE.name,
        "role": AGENT_PROFILE.role,
        "goal": AGENT_PROFILE.goal,
        "events_in_context": len(events),
        "context_preview": build_event_context(events)[:1200],
    }
