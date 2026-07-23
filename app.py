"""
app.py
------
Servidor Flask que expõe a crew de agentes (crew_agents.py) a um
chatbot frontend em HTML/CSS/JS.

Endpoints:
  GET  /                    -> serve a página do chat
  POST /api/chat             -> resposta simples (sem progresso em tempo real)
  POST /api/chat/stream      -> resposta com progresso em tempo real (SSE):
                                 texto, geração de imagem, ou anexos
                                 (imagens -> OCR + PDF; outros ficheiros ->
                                 extração de texto via tools/attachment_tool.py)
  GET  /pdf-files/<filename> -> download dos PDFs gerados a partir de anexos
"""

import base64
import json
import os
import queue
import threading
import uuid
import traceback

from logger import CrewLogger
from datetime import datetime
from dotenv import load_dotenv, set_key

from flask import Flask, request, jsonify, render_template, Response, stream_with_context, send_from_directory
from flask_cors import CORS

from crew_agents import run_crew
from tools.ocr_tool import images_to_searchable_pdf, PDF_DIR
from tools.image_tool import ImageTool, IMAGENS_DIR
from tools.video_tool import VideoTool, VIDEOS_DIR
from tools.attachment_tool import extract_attachment_text
from tools.calendar_tool import CalendarTool

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ENV_FILE = os.path.join(BASE_DIR, ".env")

image_tool = ImageTool()
video_tool = VideoTool()

app = Flask(__name__)
CORS(app)

# Histórico de conversa em memória, por sessão (uso simples/demo).
# Em produção, substituir por uma base de dados ou cache (ex: Redis).
CONVERSATIONS = {}

# Último aviso de agenda gerado pelo scheduler diário (ver
# verificar_agenda_diaria() e reconfigurar_scheduler_agenda() mais abaixo).
# O frontend consulta isto uma vez ao carregar a página (GET
# /api/agenda/briefing) para mostrar o aviso de "eventos de hoje" sem
# o utilizador ter de perguntar.
AGENDA_BRIEFING = {"gerado_em": None, "texto": None}

AGENT_LABELS = {
    "Coordenador de Atendimento": "🧭 Coordenador a analisar o pedido...",
    "Pesquisador": "🔎 Pesquisador a reunir informação...",
    "Especialista Técnico": "🛠️ Especialista a preparar o conteúdo técnico...",
    "Redator Final": "✍️ Redator a escrever a resposta final...",
    "Assistente de Email": "📧 A verificar o email...",
    "Assistente de Agenda": "📅 A verificar a agenda...",
    "Especialista em Geração de Imagens por Inteligência Artificial": "🎨 A gerar a imagem...",
}

EMAIL_KEYWORDS = (
    "email", "emails", "e-mail", "e-mails", "gmail", "outlook",
    "caixa de correio", "inbox", "mensagens não lidas",
)

IMAGE_KEYWORDS = (
    "gera uma imagem", "gerar uma imagem", "gerar imagem", "cria uma imagem",
    "criar uma imagem", "desenha", "desenhar", "ilustra", "ilustração",
    "faz um desenho", "fazer um desenho", "imagem de", "foto de",
    "draw", "generate an image", "create an image", "picture of", "sketch",
)

CALENDAR_KEYWORDS = (
    "agenda", "calendário", "calendario", "eventos de hoje",
    "compromissos", "reuniões", "reunioes", "reunião", "reuniao",
    "o que tenho hoje", "o que tenho marcado", "tenho algo marcado",
    "convite de calendário", "convite de calendario",
    "calendar", "schedule", "meetings", "appointments", "what do i have today",
)

VIDEO_KEYWORDS = (
    "gera um vídeo", "gera um video", "gerar um vídeo", "gerar um video",
    "cria um vídeo", "cria um video", "criar um vídeo", "criar um video",
    "faz um vídeo", "faz um video", "vídeo de", "video de", "animação de",
    "generate a video", "create a video", "make a video", "video of",
)

CONFIG_KEYS = {
    "LLM_PROVIDER",
    "MODEL_NAME",

    "IMAGE_PROVIDER",
    "IMAGE_MODEL",

    "VIDEO_PROVIDER",
    "VIDEO_MODEL",

    "OCR_ENABLED",
    "OCR_LANGUAGE",

    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_USERNAME",
    "EMAIL_PASSWORD",

    # Necessários apenas para contas Outlook/Microsoft 365 (ver correção
    # issue #3 em tools/email_tool.py::get_access_token)
    "MS_CLIENT_ID",
    "MS_TENANT_ID",

    "SMTP_HOST",
    "SMTP_PORT",
    "SMTP_USERNAME",
    "SMTP_PASSWORD",

    "OPENAI_API_KEY",
    "ANTHROPIC_API_KEY",
    "HF_TOKEN",
    "FAL_KEY",

    "AGENDA_AVISO_ATIVO",
    "AGENDA_AVISO_HORA",
}

MAX_OCR_CONTEXT_CHARS = 4000


def is_email_request(message):

    message = message.lower()

    return any(
        k in message
        for k in EMAIL_KEYWORDS
    )


def is_calendar_request(message: str) -> bool:
    m = message.lower()
    return any(keyword in m for keyword in CALENDAR_KEYWORDS)


def is_image_request(message: str) -> bool:
    m = message.lower()
    return any(keyword in m for keyword in IMAGE_KEYWORDS)


def is_video_request(message: str) -> bool:
    m = message.lower()
    return any(keyword in m for keyword in VIDEO_KEYWORDS)


def verificar_agenda_diaria():
    """
    Corre em segundo plano (ver reconfigurar_scheduler_agenda()), uma vez por
    dia, à hora configurada em AGENDA_AVISO_HORA. Chama a CalendarTool
    diretamente (sem passar pela crew completa de agentes — não há
    utilizador à espera de resposta em tempo real, e poupa chamadas ao LLM)
    e guarda o resultado em AGENDA_BRIEFING para o frontend consultar.

    Tenta também mostrar uma notificação nativa do sistema (Windows), se a
    biblioteca opcional 'win10toast' estiver instalada — mas nunca falha
    por causa disso: a app continua a funcionar sem notificações de
    secretária, o frontend fica na mesma com o aviso disponível via
    GET /api/agenda/briefing.
    """
    try:
        texto = CalendarTool()._run(operation="hoje")
    except Exception as exc:  # noqa: BLE001
        texto = f"Não consegui verificar a agenda de hoje. Detalhe: {exc}"

    AGENDA_BRIEFING["texto"] = texto
    AGENDA_BRIEFING["gerado_em"] = datetime.now().isoformat()

    # Mostra o aviso na consola tal como o Assistente de Agenda o "diria"
    # no chat — não só um log técnico, mas o próprio texto, com a mesma
    # etiqueta usada nos avisos de progresso do chat (ver AGENT_LABELS).
    print(f"\n📅 Assistente de Agenda: {texto}\n")

    try:
        from win10toast import ToastNotifier  # opcional, só existe no Windows
        ToastNotifier().show_toast(
            "Crew Assistant AI — Agenda de hoje",
            texto[:250],
            duration=10,
            threaded=True,
        )
    except Exception:
        # Sem 'win10toast' instalado, ou fora do Windows: não é um erro,
        # apenas não há notificação de secretária. O aviso continua
        # disponível para o frontend via /api/agenda/briefing.
        pass


_AGENDA_SCHEDULER = None
# Instância única do BackgroundScheduler, criada uma só vez (na primeira
# chamada a reconfigurar_scheduler_agenda()) e reutilizada durante toda a
# vida do processo. Guardá-la aqui — em vez de a criar e "esquecer" dentro
# da função, como acontecia antes — é o que permite reconfigurar o aviso
# diário (ativar/desativar, mudar a hora) a partir das Definições sem
# reiniciar a app: mexe-se sempre na mesma instância já a correr.


def reconfigurar_scheduler_agenda():
    """
    (Re)configura o job do aviso diário de agenda a partir dos valores
    ATUAIS de AGENDA_AVISO_ATIVO / AGENDA_AVISO_HORA em os.environ.

    Chamada tanto no arranque da app como sempre que o utilizador guarda
    as Definições (ver /update-config) — por isso ativar/desativar o
    aviso, ou mudar a hora, tem efeito imediato, sem reiniciar a app:
      - se ativo=false -> remove o job, se existir (para de avisar já,
        sem ser preciso desligar a app).
      - se ativo=true  -> cria/atualiza o job com a hora atual
        (replace_existing=True substitui a hora antiga em vez de
        duplicar jobs).

    Usa APScheduler (BackgroundScheduler) — corre numa thread própria,
    sem bloquear o Flask nem exigir infraestrutura extra (cron, Celery,
    etc.), adequado ao uso local/desktop desta app.
    """
    global _AGENDA_SCHEDULER

    ativo = os.getenv("AGENDA_AVISO_ATIVO", "false").strip().lower() in ("true", "1", "sim", "yes")

    try:
        from apscheduler.schedulers.background import BackgroundScheduler
    except ImportError:
        if ativo:
            print(
                "[Agenda] AGENDA_AVISO_ATIVO=true mas a biblioteca 'apscheduler' "
                "não está instalada. Adiciona 'apscheduler' ao requirements.txt "
                "e corre 'pip install apscheduler'."
            )
        return

    if _AGENDA_SCHEDULER is None:
        _AGENDA_SCHEDULER = BackgroundScheduler(daemon=True)
        _AGENDA_SCHEDULER.start()

    if not ativo:
        if _AGENDA_SCHEDULER.get_job("agenda_diaria"):
            _AGENDA_SCHEDULER.remove_job("agenda_diaria")
            print("[Agenda] Aviso diário de agenda desativado.")
        return

    hora_texto = os.getenv("AGENDA_AVISO_HORA", "08:00").strip()
    try:
        hora, minuto = (int(p) for p in hora_texto.split(":"))
    except ValueError:
        print(f"[Agenda] AGENDA_AVISO_HORA inválida ('{hora_texto}'), a usar 08:00.")
        hora, minuto = 8, 0

    _AGENDA_SCHEDULER.add_job(
        verificar_agenda_diaria,
        trigger="cron",
        hour=hora,
        minute=minuto,
        id="agenda_diaria",
        replace_existing=True,
    )
    print(f"[Agenda] Aviso diário de agenda ativo às {hora:02d}:{minuto:02d}.")


def get_history_text(session_id: str) -> str:
    history = CONVERSATIONS.get(session_id, [])
    linhas = []
    for msg in history[-6:]:  # últimas 6 mensagens é suficiente de contexto
        quem = "Humano" if msg["role"] == "user" else "Assistente"
        linhas.append(f"{quem}: {msg['content']}")
    return "\n".join(linhas)


def build_reply_context(reply_to: str) -> str:
    """
    Se o humano respondeu diretamente a uma mensagem anterior do
    assistente (via botão de "responder" no chat), devolve um bloco de
    contexto explícito para os agentes saberem exatamente a que ponto se
    referem — para responderem de imediato e de forma focada, sem terem
    de adivinhar a partir do histórico geral.
    """
    if not reply_to:
        return ""
    return (
        "\n\n[O humano está a responder DIRETAMENTE a esta mensagem tua "
        "anterior — a tua resposta deve focar-se especificamente neste "
        "ponto, sem rodeios]:\n"
        f"{reply_to}"
    )


def save_message(session_id: str, role: str, content: str):
    CONVERSATIONS.setdefault(session_id, []).append({"role": role, "content": content})


def decode_data_url(data_url: str) -> bytes:
    """Aceita tanto uma data URL completa ('data:image/png;base64,...') como
    apenas a string base64 pura, e devolve sempre os bytes do ficheiro."""
    if "," in data_url and data_url.strip().startswith("data:"):
        data_url = data_url.split(",", 1)[1]
    return base64.b64decode(data_url)


def split_attachments(attachments_in):
    """
    Separa os anexos recebidos do frontend em imagens (processadas por OCR
    -> PDF pesquisável) e outros ficheiros (documentos, folhas de cálculo,
    apresentações, código, comprimidos, áudio, vídeo, etc.).

    Aceita tanto o formato antigo (string com a data URL, só imagens) como
    o formato atual {name, dataUrl, mime} enviado desde a v2.0.0.

    Devolve (lista de data URLs de imagem, lista de ficheiros não-imagem
    como {"name", "mime", "raw"}).
    """
    image_urls = []
    other_files = []
    for item in attachments_in:
        if isinstance(item, str):
            # formato antigo: sempre tratado como imagem
            image_urls.append(item)
            continue
        if not isinstance(item, dict):
            continue

        name = item.get("name") or "ficheiro"
        mime = (item.get("mime") or "").lower()
        data_url = item.get("dataUrl") or ""

        if mime.startswith("image/") or data_url.startswith("data:image/"):
            image_urls.append(data_url)
        else:
            try:
                raw = decode_data_url(data_url)
            except Exception:  # noqa: BLE001
                raw = b""
            other_files.append({"name": name, "mime": mime, "raw": raw})

    return image_urls, other_files


def build_other_files_context(other_files: list) -> str:
    """Extrai o conteúdo possível de cada ficheiro não-imagem anexado e
    devolve um bloco de texto pronto a juntar ao contexto do LLM, para que
    este consiga responder a perguntas sobre qualquer tipo de ficheiro."""
    if not other_files:
        return ""

    blocos = []
    for f in other_files:
        texto = extract_attachment_text(f["name"], f["mime"], f["raw"])
        if texto:
            blocos.append(f"[Ficheiro anexado: {f['name']}]\n{texto}")
        else:
            blocos.append(
                f"[Ficheiro anexado: {f['name']} — conteúdo não pôde ser "
                f"lido automaticamente (tipo não suportado nesta versão, "
                f"ex.: áudio/vídeo/binário). Está disponível apenas o nome "
                f"do ficheiro.]"
            )

    return "\n\n[Ficheiros anexados pelo utilizador]:\n" + "\n\n".join(blocos)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/pdf-files/<path:filename>")
def download_pdf(filename):
    return send_from_directory(PDF_DIR, filename, as_attachment=True)


@app.route("/imagens/<path:filename>")
def download_imagem(filename):
    return send_from_directory(IMAGENS_DIR, filename, as_attachment=False)


@app.route("/videos/<path:filename>")
def download_video(filename):
    return send_from_directory(VIDEOS_DIR, filename, as_attachment=False)

@app.route("/api/config/model", methods=["POST"])
def update_model():
    """
    Endpoint não usado pelo frontend atual (que usa sempre /update-config
    para tudo, incluindo o MODEL_NAME), mas mantido para compatibilidade
    com eventuais integrações externas que já o chamem diretamente.

    Correção issue #11: gravava sempre no caminho relativo ".env", em
    vez do ENV_FILE absoluto usado no resto da app — se o processo Flask
    fosse arrancado a partir de outra pasta de trabalho, esta rota podia
    criar/editar um .env diferente do que a app efetivamente lê, e a
    alteração parecia "não ter efeito".
    """
    data = request.get_json(force=True)
    new_model = data.get("model_name")

    if not new_model:
        return jsonify({"error": "Nome do modelo não fornecido"}), 400

    # 1. Atualiza a variável no ambiente do processo atual
    os.environ["MODEL_NAME"] = new_model

    # 2. Persiste a alteração no ficheiro .env correto (caminho absoluto)
    set_key(ENV_FILE, "MODEL_NAME", new_model)

    return jsonify({"message": f"Modelo alterado com sucesso para: {new_model}"})

@app.route("/update-config", methods=["POST"])
def update_config():

    try:

        data = request.get_json(force=True)

        if not data:
            return jsonify({
                "status": "error",
                "message": "Nenhum dado recebido."
            }), 400

        # Validação simples
        if "EMAIL_PORT" in data:
            int(data["EMAIL_PORT"])

        if "SMTP_PORT" in data:
            int(data["SMTP_PORT"])

        # Guarda todas as configurações
        for key, value in data.items():

            if key not in CONFIG_KEYS:
                continue

            if value is None:
                value = ""

            value = str(value)

            os.environ[key] = value

            set_key(
                ENV_FILE,
                key,
                value
            )

        # Recarrega o .env
        load_dotenv(
            dotenv_path=ENV_FILE,
            override=True
        )

        # Se as Definições mudaram algo da Agenda (ativar/desativar o
        # aviso diário, ou a hora), aplica de imediato ao scheduler já em
        # execução — sem isto, a alteração só teria efeito depois de
        # reiniciar a app.
        if "AGENDA_AVISO_ATIVO" in data or "AGENDA_AVISO_HORA" in data:
            reconfigurar_scheduler_agenda()

        return jsonify({
            "status": "success",
            "message": "Configurações guardadas com sucesso."
        })

    except Exception as e:

        traceback.print_exc()

        return jsonify({
            "status": "error",
            "message": str(e)
        }), 500
    
    
@app.route("/api/config", methods=["GET"])
def get_config():

    return jsonify({

        "LLM_PROVIDER": os.getenv("LLM_PROVIDER", ""),
        "MODEL_NAME": os.getenv("MODEL_NAME", ""),

        "IMAGE_PROVIDER": os.getenv("IMAGE_PROVIDER", ""),
        "IMAGE_MODEL": os.getenv("IMAGE_MODEL", ""),

        "VIDEO_PROVIDER": os.getenv("VIDEO_PROVIDER", ""),
        "VIDEO_MODEL": os.getenv("VIDEO_MODEL", ""),

        "OCR_ENABLED": os.getenv("OCR_ENABLED", ""),
        "OCR_LANGUAGE": os.getenv("OCR_LANGUAGE", ""),

        "EMAIL_HOST": os.getenv("EMAIL_HOST", ""),
        "EMAIL_PORT": os.getenv("EMAIL_PORT", ""),
        "EMAIL_USERNAME": os.getenv("EMAIL_USERNAME", ""),
        "EMAIL_PASSWORD": os.getenv("EMAIL_PASSWORD", ""),

        "MS_CLIENT_ID": os.getenv("MS_CLIENT_ID", ""),
        "MS_TENANT_ID": os.getenv("MS_TENANT_ID", ""),

        "SMTP_HOST": os.getenv("SMTP_HOST", ""),
        "SMTP_PORT": os.getenv("SMTP_PORT", ""),
        "SMTP_USERNAME": os.getenv("SMTP_USERNAME", ""),
        "SMTP_PASSWORD": os.getenv("SMTP_PASSWORD", ""),

        "OPENAI_API_KEY": os.getenv("OPENAI_API_KEY", ""),
        "ANTHROPIC_API_KEY": os.getenv("ANTHROPIC_API_KEY", ""),
        "HF_TOKEN": os.getenv("HF_TOKEN", ""),
        "FAL_KEY": os.getenv("FAL_KEY", ""),
        "REPLICATE_API_TOKEN": os.getenv("REPLICATE_API_TOKEN", ""),

        "AGENDA_AVISO_ATIVO": os.getenv("AGENDA_AVISO_ATIVO", "false"),
        "AGENDA_AVISO_HORA": os.getenv("AGENDA_AVISO_HORA", "08:00"),

    })

@app.route("/api/agenda/briefing", methods=["GET"])
def agenda_briefing():
    """
    Devolve o último aviso de agenda gerado pelo scheduler diário (ver
    verificar_agenda_diaria()). O frontend chama isto uma vez ao carregar
    a página para mostrar o aviso de eventos de hoje sem o utilizador ter
    de perguntar. Se o scheduler ainda não tiver corrido (ou estiver
    desativado), devolve texto=null.
    """
    return jsonify(AGENDA_BRIEFING)


@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True) or {}
    user_message = (data.get("message") or "").strip()
    attachments_in = data.get("attachments") or data.get("images") or []
    session_id = data.get("session_id") or str(uuid.uuid4())
    reply_to = (data.get("reply_to") or "").strip()

    image_urls, other_files = split_attachments(attachments_in)

    if not user_message and not image_urls and not other_files:
        return jsonify({"error": "Mensagem vazia."}), 400

    if user_message:
        save_message(session_id, "user", user_message)
    if image_urls or other_files:
        total = len(image_urls) + len(other_files)
        save_message(session_id, "user", f"[{total} anexo(s) enviado(s)]")

    extra_context = ""
    attachment_info = None

    if image_urls:
        try:
            raw_images = [decode_data_url(b) for b in image_urls]
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

    if other_files:
        extra_context += build_other_files_context(other_files)

    if (image_urls or other_files) and not user_message:
        resumo_partes = []
        if attachment_info:
            resumo_partes.append(f"PDF criado com {attachment_info['pages']} página(s).")
        if other_files:
            resumo_partes.append(
                f"{len(other_files)} outro(s) ficheiro(s) recebido(s) e analisado(s)."
            )
        return jsonify({
            "session_id": session_id,
            "type": "attachment",
            "attachment": attachment_info,
            "reply": " ".join(resumo_partes),
        })

    history_text = get_history_text(session_id) + extra_context + build_reply_context(reply_to)

    # Correção issue #13: o CrewLogger era criado aqui mesmo quando o
    # pedido acabava por ser de vídeo/imagem (que não usam este logger),
    # criando um ficheiro de log praticamente vazio a cada pedido. Passa
    # a ser criado só quando é mesmo necessário (pedido de texto, mais
    # abaixo), e é efetivamente utilizado em vez de descartado.

    if is_video_request(user_message):
        try:
            resultado_video = video_tool._run(prompt=user_message)
        except Exception as exc:  # noqa: BLE001
            return jsonify({"error": f"Não consegui gerar o vídeo: {exc}"}), 502

        save_message(session_id, "assistant", "[Vídeo gerado]")
        payload = {
            "session_id": session_id,
            "type": "video",
            "video_url": f"/videos/{resultado_video['filename']}",
        }
        if attachment_info:
            payload["attachment"] = attachment_info
        return jsonify(payload)

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
            "prompt_used": resultado_imagem.get("prompt", user_message),
        }
        if attachment_info:
            payload["attachment"] = attachment_info
        return jsonify(payload)

    logger = CrewLogger(session_id)
    logger.user(user_message)

    _pedido_email = is_email_request(user_message) and not (image_urls or other_files)
    _pedido_agenda = is_calendar_request(user_message) and not (image_urls or other_files)

    resposta = run_crew(
        user_message,
        history_text,
        logger=logger,
        include_email=_pedido_email,
        include_calendar=_pedido_agenda and not _pedido_email,
    )
    save_message(session_id, "assistant", resposta)

    logger.response(resposta)
    logger.finish()

    payload = {"session_id": session_id, "type": "text", "reply": resposta}
    if attachment_info:
        payload["attachment"] = attachment_info
    return jsonify(payload)


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    data = request.get_json(force=True) or {}
    user_message = (data.get("message") or "").strip()
    attachments_in = data.get("attachments") or data.get("images") or []
    session_id = data.get("session_id") or str(uuid.uuid4())
    language = data.get("language", "pt")
    reply_to = (data.get("reply_to") or "").strip()

    image_urls, other_files = split_attachments(attachments_in)

    if not user_message and not image_urls and not other_files:
        return jsonify({"error": "Mensagem vazia."}), 400

    if user_message:
        save_message(session_id, "user", user_message)
    if image_urls or other_files:
        total = len(image_urls) + len(other_files)
        save_message(session_id, "user", f"[{total} anexo(s) enviado(s)]")

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

            # 1) Anexos: imagens -> OCR + PDF pesquisável guardado em PDF/
            if image_urls:
                q.put({"type": "attachment_progress", "label": "📎 A processar imagens e a fazer OCR..."})
                raw_images = [decode_data_url(b) for b in image_urls]
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

            # 2) Outros ficheiros anexados (documentos, folhas de cálculo,
            #    apresentações, código-fonte, comprimidos, áudio, vídeo...):
            #    extrai o conteúdo possível para dar contexto ao LLM.
            if other_files:
                q.put({"type": "attachment_progress", "label": "📎 A analisar os ficheiros anexados..."})
                extra_context += build_other_files_context(other_files)

            if (image_urls or other_files) and not user_message:
                total = len(image_urls) + len(other_files)
                q.put({
                    "type": "final",
                    "reply": f"{total} anexo(s) recebido(s) e analisado(s).",
                    "session_id": session_id,
                })
                return

            # 3) Pedido de vídeo -> VideoTool chamada diretamente (mesmo
            #    motivo da imagem: um vídeo é maior ainda, não pode passar
            #    pelo LLM)
            if is_video_request(user_message):
                q.put({"type": "video_progress", "label": "🎥 A gerar o vídeo (pode demorar vários minutos)..."})
                try:
                    resultado_video = video_tool._run(prompt=user_message)
                except Exception as exc:  # noqa: BLE001
                    q.put({"type": "error", "message": f"Não consegui gerar o vídeo: {exc}"})
                    return

                save_message(session_id, "assistant", "[Vídeo gerado]")
                q.put({
                    "type": "video",
                    "video_url": f"/videos/{resultado_video['filename']}",
                    "session_id": session_id,
                })
                return

            # 4) Pedido de imagem -> ImageTool chamada diretamente (nunca
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
                    "prompt_used": resultado_imagem.get("prompt", user_message),
                    "session_id": session_id,
                })
                return

            # 5) Pedido normal de texto -> crew de agentes
            history_text = get_history_text(session_id) + extra_context + build_reply_context(reply_to)

            logger.user(user_message)

            _pedido_email = is_email_request(user_message) and not (image_urls or other_files)
            _pedido_agenda = is_calendar_request(user_message) and not (image_urls or other_files)

            resposta = run_crew(
                user_message,
                history_text,
                language=language,
                logger=logger,
                task_callback=task_callback,
                include_email=_pedido_email,
                include_calendar=_pedido_agenda and not _pedido_email,
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
    # Correção issue #4: a app corria sempre com debug=True e exposta em
    # 0.0.0.0 (qualquer dispositivo na rede local), o que ativa o
    # debugger interativo do Werkzeug — um risco de execução de código
    # arbitrário se alguém na mesma rede conseguir acionar um erro não
    # tratado. Por omissão, corre agora em modo produção (debug=False) e
    # só acessível a partir do próprio computador (127.0.0.1). Para
    # ativar deliberadamente o modo de desenvolvimento/rede local,
    # define FLASK_DEBUG=true e/ou FLASK_HOST=0.0.0.0 no .env.
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "false").strip().lower() in ("true", "1", "sim", "yes")
    host = os.getenv("FLASK_HOST", "127.0.0.1")

    # Em modo debug o Werkzeug reinicia o processo num sub-processo próprio
    # (reloader); sem esta verificação, o scheduler arrancaria em duplicado
    # (uma vez no processo pai, outra no filho).
    if not debug or os.environ.get("WERKZEUG_RUN_MAIN") == "true":
        reconfigurar_scheduler_agenda()

    app.run(host=host, port=port, debug=debug)