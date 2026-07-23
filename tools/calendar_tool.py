"""
tools/calendar_tool.py
-----------------------
Ferramenta CrewAI para verificar a agenda do utilizador e avisar sobre os
eventos do dia (ou dos próximos dias).

Como funciona:
    Convites de reunião (Google Calendar, Outlook/Teams, Zoom, etc.) chegam
    quase sempre por email como uma parte MIME "text/calendar" (ficheiro
    .ics) — incluindo quando o utilizador já aceitou o convite, porque o
    convite original permanece na caixa de correio. Esta ferramenta liga-se
    à MESMA caixa de correio já configurada para o EmailTool (via IMAP,
    reutilizando `connect_mailbox()`), procura esses convites dentro de uma
    janela de datas, e devolve os eventos encontrados, ordenados por data.

    Não faz scraping direto do Google Calendar / Outlook Calendar (isso
    exigiria uma integração OAuth adicional com scopes de Calendar, fora do
    âmbito desta versão) — lê antes os convites que já chegam à caixa de
    correio, o que cobre a grande maioria dos casos de uso reais.

Variáveis de ambiente (reutiliza as mesmas do EmailTool, não precisa de
configuração adicional):
    EMAIL_HOST, EMAIL_PORT, EMAIL_USERNAME, EMAIL_PASSWORD, EMAIL_FOLDER

Dependência nova (ver requirements.txt):
    icalendar
"""

import email as email_lib
from datetime import datetime, timedelta, date
from typing import List, Literal

from pydantic import BaseModel, Field
from crewai.tools import BaseTool

from tools.email_tool import connect_mailbox

try:
    from icalendar import Calendar
    _ICAL_DISPONIVEL = True
except ImportError:  # a dependência pode ainda não estar instalada
    _ICAL_DISPONIVEL = False


class CalendarToolInput(BaseModel):
    operation: Literal["hoje", "semana", "proximos_dias"] = Field(
        default="hoje",
        description=(
            "hoje -> eventos de hoje.\n"
            "semana -> eventos dos próximos 7 dias.\n"
            "proximos_dias -> eventos dos próximos `dias` dias "
            "(usar em conjunto com o campo 'dias')."
        ),
    )
    dias: int = Field(
        default=7,
        ge=1,
        le=60,
        description="Número de dias a considerar, usado apenas com operation='proximos_dias'.",
    )
    max_emails_pesquisados: int = Field(
        default=200,
        ge=10,
        le=1000,
        description="Quantidade de emails recentes a inspecionar à procura de convites de calendário.",
    )


class CalendarTool(BaseTool):
    name: str = "CalendarTool"
    description: str = (
        "Verifica a agenda do utilizador a partir de convites de calendário "
        "(.ics) recebidos por email (Google Calendar, Outlook/Teams, Zoom, "
        "etc.) e devolve os eventos de hoje, da semana, ou dos próximos N "
        "dias, com título, data/hora e local."
    )
    args_schema: type[BaseModel] = CalendarToolInput

    # ------------------------------------------------------------------ #
    # Execução principal (chamada pelo agente CrewAI)
    # ------------------------------------------------------------------ #
    def _run(
        self,
        operation: str = "hoje",
        dias: int = 7,
        max_emails_pesquisados: int = 200,
    ) -> str:
        if not _ICAL_DISPONIVEL:
            return (
                "A funcionalidade de agenda requer a biblioteca 'icalendar' "
                "(adiciona 'icalendar' ao requirements.txt e corre "
                "'pip install icalendar')."
            )

        try:
            mail = connect_mailbox()
        except Exception as exc:  # noqa: BLE001
            return f"Não consegui aceder ao email para verificar a agenda. Detalhe: {exc}"

        hoje = date.today()
        if operation == "hoje":
            data_limite = hoje
        elif operation == "semana":
            data_limite = hoje + timedelta(days=7)
        else:
            data_limite = hoje + timedelta(days=dias)

        eventos: List[dict] = []

        try:
            status, data = mail.search(None, "ALL")
            if status != "OK":
                mail.logout()
                return "Não consegui pesquisar a caixa de correio à procura de convites."

            ids = data[0].split()
            ids = ids[-max_emails_pesquisados:]  # só os mais recentes, por performance

            for eid in ids:
                status, msg_data = mail.fetch(eid, "(RFC822)")
                if status != "OK":
                    continue

                msg = email_lib.message_from_bytes(msg_data[0][1])

                for parte in msg.walk():
                    nome_ficheiro = (parte.get_filename() or "").lower()
                    e_convite = (
                        parte.get_content_type() == "text/calendar"
                        or nome_ficheiro.endswith(".ics")
                    )
                    if not e_convite:
                        continue

                    conteudo = parte.get_payload(decode=True)
                    if not conteudo:
                        continue

                    eventos.extend(
                        self._extrair_eventos(conteudo, hoje, data_limite)
                    )

            mail.logout()

        except Exception as exc:  # noqa: BLE001
            return f"Não consegui verificar a agenda. Detalhe: {exc}"

        return self._build_response(operation, eventos, hoje, data_limite)

    # ------------------------------------------------------------------ #
    # Extrai VEVENTs de um ficheiro .ics dentro da janela [hoje, limite]
    # ------------------------------------------------------------------ #
    def _extrair_eventos(self, conteudo_ics: bytes, hoje: date, data_limite: date) -> List[dict]:
        eventos = []
        try:
            cal = Calendar.from_ical(conteudo_ics)
        except Exception:
            return eventos

        for componente in cal.walk():
            if componente.name != "VEVENT":
                continue

            dtstart = componente.get("dtstart")
            if dtstart is None:
                continue
            inicio = dtstart.dt

            # Eventos de dia inteiro vêm como `date`; eventos com hora
            # vêm como `datetime` (por vezes com timezone).
            data_evento = inicio.date() if isinstance(inicio, datetime) else inicio

            if not (hoje <= data_evento <= data_limite):
                continue

            # Convites cancelados não devem ser apresentados como eventos ativos.
            status = str(componente.get("status", "")).upper()
            if status == "CANCELLED":
                continue

            eventos.append(
                {
                    "titulo": str(componente.get("summary", "(sem título)")),
                    "inicio": inicio,
                    "local": str(componente.get("location", "")) or None,
                }
            )

        return eventos

    # ------------------------------------------------------------------ #
    # Construção da resposta em texto
    # ------------------------------------------------------------------ #
    def _build_response(self, operation: str, eventos: List[dict], hoje: date, data_limite: date) -> str:
        # Remove duplicados: o mesmo convite pode chegar mais de uma vez
        # (convite original + atualização), usamos (título, início) como chave.
        vistos = set()
        unicos = []
        for e in eventos:
            chave = (e["titulo"], str(e["inicio"]))
            if chave in vistos:
                continue
            vistos.add(chave)
            unicos.append(e)

        unicos.sort(key=lambda e: str(e["inicio"]))

        if not unicos:
            if operation == "hoje":
                return "Não encontrei nenhum evento marcado para hoje."
            return (
                f"Não encontrei nenhum evento marcado entre "
                f"{hoje.strftime('%d/%m/%Y')} e {data_limite.strftime('%d/%m/%Y')}."
            )

        linhas = [f"Encontrei {len(unicos)} evento(s):"]
        for i, e in enumerate(unicos, 1):
            inicio = e["inicio"]
            if isinstance(inicio, datetime):
                quando = inicio.strftime("%d/%m/%Y %H:%M")
            else:
                quando = inicio.strftime("%d/%m/%Y") + " (dia inteiro)"
            local_txt = f" | Local: {e['local']}" if e["local"] else ""
            linhas.append(f"{i}. {e['titulo']} — {quando}{local_txt}")

        return "\n".join(linhas)
