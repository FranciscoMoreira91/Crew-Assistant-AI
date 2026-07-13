"""
app.py
------
Servidor Flask que expõe a crew de agentes (crew_agents.py) a um
chatbot frontend em HTML/CSS/JS.

Endpoints:
  GET  /                    -> serve a página do chat
  POST /api/chat             -> resposta simples (sem progresso em tempo real)
  POST /api/chat/stream      -> resposta com progresso em tempo real (SSE):
                                 texto, geração de imagem, ou anexos (OCR + PDF)
  GET  /pdf-files/<filename> -> download dos PDFs gerados a partir de anexos
"""

import base64
import json
import os
import queue
import threading
import uuid

from logger import CrewLogger
from datetime import datetime

from flask import Flask, request, jsonify, render_template, Response, stream_with_context, send_from_directory
from flask_cors import CORS

from crew_agents import run_crew
from ocr_tool import images_to_searchable_pdf, PDF_DIR
from image_tool import ImageTool, IMAGENS_DIR

image_tool = ImageTool()

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
    "Assistente de Email": "📧 A verificar o email...",
    "Especialista em Geração de Imagens por Inteligência Artificial": "🎨 A gerar a imagem...",
}

EMAIL_KEYWORDS = (
    "email", "emails", "gmail", "outlook",
    "fatura", "invoice", "anexo", "recibo",
)

IMAGE_KEYWORDS = (
    "gera uma imagem", "gerar uma imagem", "gerar imagem", "cria uma imagem",
    "criar uma imagem", "desenha", "desenhar", "ilustra", "ilustração",
    "faz um desenho", "fazer um desenho", "imagem de", "foto de",
    "draw", "generate an image", "create an image", "picture of", "sketch",
)

MAX_OCR_CONTEXT_CHARS = 4000


def is_email_request(message):

    message = message.lower()

    return any(
        k in message
        for k in EMAIL_KEYWORDS
    )


def is_image_request(message: str) -> bool:
    m = message.lower()
    return any(keyword in m for keyword in IMAGE_KEYWORDS)


def get_history_text(session_id: str) -> str:
    history = CONVERSATIONS.get(session_id, [])
    linhas = []
    for msg in history[-6:]:  # últimas 6 mensagens é suficiente de contexto
        quem = "Humano" if msg["role"] == "user" else "Assistente"
        linhas.append(f"{quem}: {msg['content']}")
    return "\n".join(linhas)


def save_message(session_id: str, role: str, content: str):
    CONVERSATIONS.setdefault(session_id, []).append({"role": role, "content": content})


def decode_data_url(data_url: str) -> bytes:
    """Aceita tanto uma data URL completa ('data:image/png;base64,...') como
    apenas a string base64 pura, e devolve sempre os bytes da imagem."""
    if "," in data_url and data_url.strip().startswith("data:"):
        data_url = data_url.split(",", 1)[1]
    return base64.b64decode(data_url)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/pdf-files/<path:filename>")
def download_pdf(filename):
    return send_from_directory(PDF_DIR, filename, as_attachment=True)


@app.route("/imagens/<path:filename>")
def download_imagem(filename):
    return send_from_directory(IMAGENS_DIR, filename, as_attachment=False)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True) or {}
    user_message = (data.get("message") or "").strip()
    images_in = data.get("images") or []
    session_id = data.get("session_id") or str(uuid.uuid4())

    if not user_message and not images_in:
        return jsonify({"error": "Mensagem vazia."}), 400

    if user_message:
        save_message(session_id, "user", user_message)
    if images_in:
        save_message(session_id, "user", f"[{len(images_in)} imagem(ns) anexada(s)]")

    extra_context = ""
    attachment_info = None

    if images_in:
        try:
            raw_images = [decode_data_url(b) for b in images_in]
            resultado = images_to_searchable_pdf(raw_images)
            attachment_info = {
                "pdf_filename": resultado["pdf_filename"],
                "download_url": f"/pdf-files/{resultado['pdf_filename']}",
                "pages": len(raw_images),
            }
            if resultado["extracted_text"]:
                extra_context = (
                    f"\n\n[Texto extraído por OCR dos anexos]:\n"
                    f"{resultado['extracted_text'][:MAX_OCR_CONTEXT_CHARS]}"
                )
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"Não consegui processar os anexos: {exc}"}), 502

        if not user_message:
            return jsonify({
                "session_id": session_id,
                "type": "attachment",
                "attachment": attachment_info,
                "reply": f"PDF criado com {attachment_info['pages']} página(s).",
            })

    history_text = get_history_text(session_id) + extra_context

    logger = CrewLogger()

    if is_image_request(user_message):
        try:
            resultado_imagem = image_tool._run(prompt=user_message)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"Não consegui gerar a imagem: {exc}"}), 502

        save_message(session_id, "assistant", "[Imagem gerada]")
        payload = {
            "session_id": session_id,
            "type": "image",
            "image_base64": resultado_imagem["base64"],
            "download_url": f"/imagens/{resultado_imagem['filename']}",
        }
        if attachment_info:
            payload["attachment"] = attachment_info
        return jsonify(payload)

    resposta = run_crew(
        user_message, history_text, include_email=is_email_request(user_message)
    )
    save_message(session_id, "assistant", resposta)

    payload = {"session_id": session_id, "type": "text", "reply": resposta}
    if attachment_info:
        payload["attachment"] = attachment_info
    return jsonify(payload)


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    data = request.get_json(force=True) or {}
    user_message = (data.get("message") or "").strip()
    images_in = data.get("images") or []
    session_id = data.get("session_id") or str(uuid.uuid4())
    language = data.get("language", "pt")

    if not user_message and not images_in:
        return jsonify({"error": "Mensagem vazia."}), 400

    if user_message:
        save_message(session_id, "user", user_message)
    if images_in:
        save_message(session_id, "user", f"[{len(images_in)} imagem(ns) anexada(s)]")

    q: "queue.Queue" = queue.Queue()

    logger = CrewLogger(session_id)

    def task_callback(task_output):
        agent_role = getattr(task_output, "agent", "Agente")
        output = getattr(task_output, "raw", "")
        logger.agent(agent_role, output)
        label = AGENT_LABELS.get(agent_role, f"{agent_role} a trabalhar...")
        q.put({"type": "progress", "agent": agent_role, "label": label})

    def worker():
        try:
            extra_context = ""

            # 1) Anexos: OCR + PDF pesquisável guardado em PDF/
            if images_in:
                q.put({"type": "attachment_progress", "label": "📎 A processar imagens e a fazer OCR..."})
                raw_images = [decode_data_url(b) for b in images_in]
                resultado = images_to_searchable_pdf(raw_images)

                q.put({
                    "type": "attachment_done",
                    "pdf_filename": resultado["pdf_filename"],
                    "download_url": f"/pdf-files/{resultado['pdf_filename']}",
                    "pages": len(raw_images),
                })

                if resultado["extracted_text"]:
                    extra_context = (
                        f"\n\n[Texto extraído por OCR dos anexos]:\n"
                        f"{resultado['extracted_text'][:MAX_OCR_CONTEXT_CHARS]}"
                    )

                # Só havia imagens, sem mensagem de texto -> terminar aqui.
                if not user_message:
                    q.put({
                        "type": "final",
                        "reply": f"PDF criado com {len(raw_images)} página(s) a partir das imagens anexadas.",
                        "session_id": session_id,
                    })
                    return

            # 3) Pedido de imagem -> ImageTool chamada diretamente (nunca
            #    através do CrewAI/LLM, para não corromper o base64)
            if is_image_request(user_message):
                q.put({"type": "image_progress", "label": "🎨 A gerar a imagem (pode demorar um pouco)..."})
                try:
                    resultado_imagem = image_tool._run(prompt=user_message)
                except Exception as exc:  # noqa: BLE001
                    q.put({"type": "error", "message": f"Não consegui gerar a imagem: {exc}"})
                    return

                save_message(session_id, "assistant", "[Imagem gerada]")
                q.put({
                    "type": "image",
                    "image_base64": resultado_imagem["base64"],
                    "download_url": f"/imagens/{resultado_imagem['filename']}",
                    "session_id": session_id,
                })
                return

            # 4) Pedido normal de texto -> crew de agentes
            history_text = get_history_text(session_id) + extra_context

            logger.user(user_message)

            resposta = run_crew(
                user_message,
                history_text,
                language=language,
                logger=logger,
                task_callback=task_callback,
                include_email=is_email_request(user_message),
            )
            save_message(session_id, "assistant", resposta)
            q.put({"type": "final", "reply": resposta, "session_id": session_id})

            logger.response(resposta)
            logger.finish()

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
    port = int(os.getenv("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=True)