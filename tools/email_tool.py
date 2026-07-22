"""
tools/email_tool.py
--------------------
Ferramenta CrewAI para ligar a uma caixa de correio (Gmail ou Outlook) via
IMAP, procurar emails por palavra-chave no assunto (ex: "Fatura"), contar
quantos foram encontrados/não lidos, e opcionalmente descarregar os anexos,
juntando tudo num único PDF.

Variáveis de ambiente necessárias (.env):
    EMAIL_HOST      ex: imap.gmail.com ou outlook.office365.com
    EMAIL_PORT      ex: 993
    EMAIL_USERNAME  o teu email
    EMAIL_PASSWORD  password DE APLICAÇÃO (ver nota abaixo)
    EMAIL_FOLDER    pasta a pesquisar, por omissão INBOX

⚠️ IMPORTANTE (segurança):
    - Com verificação em 2 passos ativa (recomendado), o Gmail e o Outlook
      não aceitam a password normal de login para IMAP — é preciso gerar
      uma "password de aplicação" própria:
        Gmail:   https://myaccount.google.com/apppasswords
        Outlook: https://account.live.com/proofs/AppPassword
    - Nunca commits o ficheiro .env para o git.
"""

import os
import io
import email
import imaplib
import time
from email.header import decode_header
from datetime import datetime
from typing import Type, List, Tuple

from typing import Optional, Literal
from pydantic import BaseModel, Field
from crewai.tools import BaseTool
from PIL import Image
from pypdf import PdfReader, PdfWriter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PDF_DIR = os.path.join(BASE_DIR, "PDF")
os.makedirs(PDF_DIR, exist_ok=True)

# Cache simples do token de acesso Outlook/Microsoft 365 em memória do
# processo, para não pedir um token novo a cada operação de email
# (correção issue #3 — ver get_access_token() mais abaixo).
_ms_token_cache = {"access_token": None, "expires_at": 0}

# Scope IMAP necessário para autenticar via XOAUTH2 no Outlook/M365.
_MS_IMAP_SCOPE = ["https://outlook.office365.com/IMAP.AccessAsUser.All"]


def get_access_token() -> str:
    """
    Obtém um token de acesso OAuth2 (Bearer) para autenticar via IMAP
    XOAUTH2 numa caixa de correio Outlook/Microsoft 365.

    Esta função não existia (era chamada em _connect() mas nunca tinha
    sido definida nem importada), o que fazia qualquer ligação a uma
    conta Outlook falhar sempre com "NameError: name 'get_access_token'
    is not defined". Está agora implementada com base na biblioteca
    `msal`, usando o fluxo "Resource Owner Password Credentials" (ROPC),
    a forma mais simples de obter um token sem interação do utilizador
    num servidor.

    Requer, no .env:
        MS_CLIENT_ID      ID da aplicação registada no Azure AD /
                           Microsoft Entra (App registrations).
        MS_TENANT_ID       ID do tenant, ou "common" para contas pessoais
                           e organizacionais em simultâneo (por omissão).
        EMAIL_USERNAME e EMAIL_PASSWORD (já existentes) — usados como
                           credenciais do ROPC.

    Nota: o ROPC não funciona em contas com MFA ativa nem em muitos
    tenants empresariais mais restritos (é uma limitação da própria
    Microsoft, não desta aplicação); nesses casos é necessário migrar
    para um fluxo interativo (device code / autorização), fora do
    âmbito desta correção pontual.
    """
    now = time.time()
    if _ms_token_cache["access_token"] and _ms_token_cache["expires_at"] > now + 30:
        return _ms_token_cache["access_token"]

    try:
        import msal
    except ImportError as exc:
        raise RuntimeError(
            "A integração com Outlook/Microsoft 365 requer a biblioteca "
            "'msal' (adiciona 'msal' ao requirements.txt e corre "
            "'pip install msal')."
        ) from exc

    client_id = os.getenv("MS_CLIENT_ID")
    tenant_id = os.getenv("MS_TENANT_ID", "common")
    username = os.getenv("EMAIL_USERNAME")
    password = os.getenv("EMAIL_PASSWORD")

    if not client_id:
        raise RuntimeError(
            "MS_CLIENT_ID não está configurado no .env. Para ligar a uma "
            "conta Outlook/Microsoft 365 é preciso registar uma aplicação "
            "em https://entra.microsoft.com (App registrations) com a "
            "permissão delegada 'IMAP.AccessAsUser.All', e colocar o "
            "respetivo ID da aplicação em MS_CLIENT_ID no .env."
        )
    if not username or not password:
        raise RuntimeError(
            "EMAIL_USERNAME/EMAIL_PASSWORD não configurados — necessários "
            "para autenticar a conta Outlook/Microsoft 365."
        )

    app = msal.PublicClientApplication(
        client_id,
        authority=f"https://login.microsoftonline.com/{tenant_id}",
    )

    resultado = app.acquire_token_by_username_password(
        username=username,
        password=password,
        scopes=_MS_IMAP_SCOPE,
    )

    if "access_token" not in resultado:
        erro = resultado.get("error_description") or resultado.get("error") or "erro desconhecido"
        raise RuntimeError(
            f"Não foi possível autenticar no Outlook/Microsoft 365: {erro}. "
            f"Se a conta tiver verificação em dois passos (MFA) ativa, este "
            f"método de autenticação (ROPC) não é suportado pela Microsoft "
            f"— é necessário um fluxo interativo, que esta versão ainda não "
            f"implementa."
        )

    _ms_token_cache["access_token"] = resultado["access_token"]
    _ms_token_cache["expires_at"] = now + int(resultado.get("expires_in", 3600))

    return resultado["access_token"]

IMAGE_EXTENSIONS = (".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".webp")
PDF_EXTENSION = ".pdf"


def _decode(value: str) -> str:
    """Descodifica cabeçalhos de email (Subject/From) que podem vir
    codificados em MIME (ex: =?UTF-8?B?...?=)."""
    if not value:
        return ""
    partes = decode_header(value)
    resultado = ""
    for texto, enc in partes:
        if isinstance(texto, bytes):
            resultado += texto.decode(enc or "utf-8", errors="ignore")
        else:
            resultado += texto
    return resultado


class EmailToolInput(BaseModel):
    operation: Literal[
        "list",
        "search",
        "read",
        "report",
        "download"
    ] = Field(
        default="search",
        description=(
            "Operação a executar.\n"
            "list -> lista emails.\n"
            "search -> procura emails.\n"
            "read -> lê emails completos.\n"
            "report -> gera relatório.\n"
            "download -> descarrega anexos."
        ),
    )

    unread_only: bool = Field(
        default=False,
        description="Se True procura apenas emails não lidos.",
    )

    subject_keyword: Optional[str] = Field(
        default=None,
        description="Texto a procurar no assunto.",
    )

    body_keyword: Optional[str] = Field(
        default=None,
        description="Texto a procurar no corpo do email.",
    )

    sender: Optional[str] = Field(
        default=None,
        description="Remetente do email (FROM).",
    )

    has_attachment: bool = Field(
        default=False,
        description="Se True devolve apenas emails com anexos.",
    )

    download_attachments: bool = Field(
        default=False,
        description="Descarrega os anexos encontrados.",
    )

    merge_attachments: bool = Field(
        default=False,
        description="Junta todos os anexos PDF/imagens num único PDF.",
    )

    mark_as_read: bool = Field(
        default=False,
        description="Marca os emails encontrados como lidos.",
    )

    max_results: int = Field(
        default=20,
        ge=1,
        le=100,
        description="Número máximo de emails a devolver.",
    )

class EmailTool(BaseTool):
    name: str = "EmailTool"
    description: str = (
        "Liga-se à caixa de correio (IMAP, configurada em .env) e procura "
        "emails por palavra-chave no assunto (ex: 'Fatura'). Devolve quantos "
        "foram encontrados, uma lista com remetente/assunto/data, e "
        "opcionalmente descarrega os anexos, juntando-os num único ficheiro "
        "PDF guardado na pasta PDF/."
    )
    args_schema: Type[BaseModel] = EmailToolInput

    # ------------------------------------------------------------------ #
    # Ligação IMAP
    # ------------------------------------------------------------------ #
    def _connect(self) -> imaplib.IMAP4_SSL:
        host = os.getenv("EMAIL_HOST")
        port = int(os.getenv("EMAIL_PORT", 993))
        username = os.getenv("EMAIL_USERNAME")
        password = os.getenv("EMAIL_PASSWORD")
        folder = os.getenv("EMAIL_FOLDER", "INBOX")

        if not host or not username:
            raise RuntimeError("EMAIL_HOST ou EMAIL_USERNAME não configurados.")

        mail = imaplib.IMAP4_SSL(host, port)

        # Outlook / Microsoft 365
        if "office365" in host or "outlook" in host:

            token = get_access_token()

            auth_string = (
                f"user={username}\x01"
                f"auth=Bearer {token}\x01\x01"
            )

            mail.authenticate(
                "XOAUTH2",
                lambda _: auth_string.encode()
            )

        # Gmail e outros servidores IMAP
        else:

            if not password:
                raise RuntimeError("EMAIL_PASSWORD não configurada.")

            mail.login(username, password)

        mail.select(folder)

        return mail

    # ------------------------------------------------------------------ #
    # Execução principal (chamada pelo agente CrewAI)
    # ------------------------------------------------------------------ #
    def _run(
        self,
        operation: str = "search",
        unread_only: bool = False,
        subject_keyword: str | None = None,
        body_keyword: str | None = None,
        sender: str | None = None,
        has_attachment: bool = False,
        download_attachments: bool = False,
        merge_attachments: bool = False,
        mark_as_read: bool = False,
        max_results: int = 20,
    ) -> str:
        try:
            mail = self._connect()
        except Exception as exc:  # noqa: BLE001
            return f"Não consegui aceder ao email. Detalhe: {exc}"

        try:
            criteria = []

            if unread_only:
                criteria.append("UNSEEN")

            if subject_keyword:
                criteria.append(f'SUBJECT "{subject_keyword}"')

            if sender:
                criteria.append(f'FROM "{sender}"')

            if body_keyword:
                criteria.append(f'TEXT "{body_keyword}"')

            if not criteria:
                criteria.append("ALL")

            criterio = "(" + " ".join(criteria) + ")"
            status, data = mail.search(None, criterio)

            if status != "OK":
                mail.logout()
                return "Não consegui aceder ao email."

            ids = data[0].split()
            ids = ids[-max_results:]  # limita a quantidade processada por chamada

            if not ids:
                mail.logout()
                estado = " não lidos" if unread_only else ""
                return (
                    f"Não encontrei nenhum email{estado} com o assunto "
                    f"'{subject_keyword}'."
                )

            encontrados = []
            anexos: List[Tuple[str, bytes]] = []

            for eid in ids:
                status, msg_data = mail.fetch(eid, "(RFC822)")
                if status != "OK":
                    continue

                msg = email.message_from_bytes(msg_data[0][1])
                assunto = _decode(msg.get("Subject", ""))
                remetente = _decode(msg.get("From", ""))
                data_email = msg.get("Date", "")

                tem_anexo = False

                if download_attachments:
                    for parte in msg.walk():
                        if parte.get_content_disposition() != "attachment":
                            continue
                        nome_ficheiro = parte.get_filename()
                        if not nome_ficheiro:
                            continue
                        nome_ficheiro = _decode(nome_ficheiro)
                        conteudo = parte.get_payload(decode=True)
                        if not conteudo:
                            continue
                        tem_anexo = True
                        anexos.append((nome_ficheiro, conteudo))

                encontrados.append(
                    {
                        "assunto": assunto,
                        "remetente": remetente,
                        "data": data_email,
                        "tem_anexo": tem_anexo,
                    }
                )

                if mark_as_read:
                    mail.store(eid, "+FLAGS", "\\Seen")

            mail.logout()

        except Exception as exc:  # noqa: BLE001
            return f"Não consegui aceder ao email. Detalhe: {exc}"

        return self._build_response(
            subject_keyword, unread_only, encontrados, anexos, download_attachments
        )

    # ------------------------------------------------------------------ #
    # Construção da resposta em texto
    # ------------------------------------------------------------------ #
    def _build_response(
        self,
        subject_keyword: str,
        unread_only: bool,
        encontrados: list,
        anexos: List[Tuple[str, bytes]],
        download_attachments: bool,
    ) -> str:
        estado = " não lidos" if unread_only else ""
        linhas = [
            f"Encontrei {len(encontrados)} email(ns){estado} com o assunto "
            f"'{subject_keyword}'."
        ]

        for i, e in enumerate(encontrados, 1):
            anexo_txt = " [tem anexo]" if e["tem_anexo"] else ""
            linhas.append(
                f"{i}. De: {e['remetente']} | Assunto: {e['assunto']} | "
                f"Data: {e['data']}{anexo_txt}"
            )

        if download_attachments and anexos:
            try:
                pdf_filename = self._merge_attachments_to_pdf(anexos)
                linhas.append(
                    f"\nJuntei {len(anexos)} anexo(s) num único PDF: {pdf_filename} "
                    f"(pasta PDF/)."
                )
            except Exception as exc:  # noqa: BLE001
                linhas.append(f"\nNão consegui juntar os anexos num PDF. Detalhe: {exc}")
        elif download_attachments:
            linhas.append("\nNenhum dos emails encontrados tinha anexos.")

        return "\n".join(linhas)

    # ------------------------------------------------------------------ #
    # Junta PDFs e imagens (convertidas em página PDF) num único ficheiro
    # ------------------------------------------------------------------ #
    def _merge_attachments_to_pdf(self, anexos: List[Tuple[str, bytes]]) -> str:
        writer = PdfWriter()
        paginas_adicionadas = 0

        for nome, conteudo in anexos:
            extensao = os.path.splitext(nome)[1].lower()

            try:
                if extensao == PDF_EXTENSION:
                    reader = PdfReader(io.BytesIO(conteudo))
                    for pagina in reader.pages:
                        writer.add_page(pagina)
                        paginas_adicionadas += 1

                elif extensao in IMAGE_EXTENSIONS:
                    imagem = Image.open(io.BytesIO(conteudo)).convert("RGB")
                    buffer = io.BytesIO()
                    imagem.save(buffer, format="PDF")
                    buffer.seek(0)
                    reader = PdfReader(buffer)
                    for pagina in reader.pages:
                        writer.add_page(pagina)
                        paginas_adicionadas += 1
                # outros tipos (.docx, .xlsx, etc.) são ignorados por agora
            except Exception:
                # não deixa um anexo corrompido estragar o PDF final inteiro
                continue

        if paginas_adicionadas == 0:
            raise RuntimeError(
                "Nenhum anexo era um PDF ou imagem válidos, nada foi juntado."
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        pdf_filename = f"faturas_email_{timestamp}.pdf"
        pdf_path = os.path.join(PDF_DIR, pdf_filename)

        with open(pdf_path, "wb") as f:
            writer.write(f)

        return pdf_filename