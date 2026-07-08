"""
app.py
------
Servidor Flask que expõe a crew de agentes (crew_agents.py) a um
chatbot frontend em HTML/CSS/JS.

Endpoints:
  GET  /                -> serve a página do chat
  POST /api/chat        -> resposta simples (sem progresso em tempo real)
  POST /api/chat/stream -> resposta com progresso em tempo real (SSE),
                            mostrando qual agente está a trabalhar
"""

import json
import queue
import threading
import uuid

from flask import Flask, request, jsonify, render_template, Response, stream_with_context
from flask_cors import CORS

from crew_agents import run_crew

app = Flask(__name__)
CORS(app)

# Histórico de conversa em memória, por sessão (uso simples/demo).
# Em produção, substituir por uma base de dados ou cache (ex: Redis).
CONVERSATIONS = {}

AGENT_LABELS = {
    "Coordenador de Atendimento": "🧭 Coordenador a analisar o pedido...",
    "Pesquisador": "🔎 Pesquisador a reunir informação...",
    "Especialista Técnico": "🛠️ Especialista a preparar o conteúdo técnico...",
    "Redator Final": "✍️ Redator a escrever a resposta final...",
}


def get_history_text(session_id: str) -> str:
    history = CONVERSATIONS.get(session_id, [])
    linhas = []
    for msg in history[-6:]:  # últimas 6 mensagens é suficiente de contexto
        quem = "Humano" if msg["role"] == "user" else "Assistente"
        linhas.append(f"{quem}: {msg['content']}")
    return "\n".join(linhas)


def save_message(session_id: str, role: str, content: str):
    CONVERSATIONS.setdefault(session_id, []).append({"role": role, "content": content})


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True) or {}
    user_message = (data.get("message") or "").strip()
    session_id = data.get("session_id") or str(uuid.uuid4())

    if not user_message:
        return jsonify({"error": "Mensagem vazia."}), 400

    history_text = get_history_text(session_id)
    resposta = run_crew(user_message, history_text)

    save_message(session_id, "user", user_message)
    save_message(session_id, "assistant", resposta)

    return jsonify({"session_id": session_id, "reply": resposta})


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    data = request.get_json(force=True) or {}
    user_message = (data.get("message") or "").strip()
    session_id = data.get("session_id") or str(uuid.uuid4())

    if not user_message:
        return jsonify({"error": "Mensagem vazia."}), 400

    history_text = get_history_text(session_id)
    save_message(session_id, "user", user_message)

    q: "queue.Queue" = queue.Queue()

    def task_callback(task_output):
        agent_role = getattr(task_output, "agent", "Agente")
        label = AGENT_LABELS.get(agent_role, f"{agent_role} a trabalhar...")
        q.put({"type": "progress", "agent": agent_role, "label": label})

    def worker():
        try:
            resposta = run_crew(user_message, history_text, task_callback=task_callback)
            save_message(session_id, "assistant", resposta)
            q.put({"type": "final", "reply": resposta, "session_id": session_id})
        except Exception as exc:  # noqa: BLE001
            q.put({"type": "error", "message": str(exc)})
        finally:
            q.put(None)  # sentinel

    threading.Thread(target=worker, daemon=True).start()

    def generate():
        while True:
            item = q.get()
            if item is None:
                break
            yield f"data: {json.dumps(item, ensure_ascii=False)}\n\n"

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


if __name__ == "__main__":
    import os
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)
