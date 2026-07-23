# Nova funcionalidade: Assistente de Agenda

## O que faz

1. **No chat**: podes perguntar "o que tenho na agenda hoje?", "tenho reuniões esta semana?", etc. Um novo agente (**Assistente de Agenda**) responde com os eventos reais, lidos a partir dos convites de calendário (`.ics`) que já chegam à tua caixa de correio — a mesma conta configurada para o Assistente de Email.
2. **Aviso diário automático**: se ativares `AGENDA_AVISO_ATIVO=true` no `.env`, a app verifica a agenda todos os dias à hora definida em `AGENDA_AVISO_HORA` (por omissão `08:00`) e guarda um aviso com os eventos de hoje — sem precisares de perguntar. Se tiveres a biblioteca opcional `win10toast` instalada, também aparece uma notificação nativa do Windows.

## Como funciona por dentro

- **Nova tool**: `tools/calendar_tool.py` (`CalendarTool`) — liga-se à caixa de correio via IMAP (reaproveitando `connect_mailbox()`, extraída do `email_tool.py`), percorre os emails recentes à procura de anexos/partes `text/calendar` ou `.ics`, e usa a biblioteca `icalendar` para extrair título, data/hora e local de cada evento (`VEVENT`). Ignora eventos cancelados (`STATUS:CANCELLED`) e remove duplicados (o mesmo convite chega muitas vezes duas vezes: original + atualização).
- **Novo agente**: `Assistente de Agenda`, em `crew_agents.py`, com um pipeline curto e dedicado (Assistente de Agenda → Redator), na mesma lógica anti-alucinação já usada para o email: nunca inventa eventos, e se a ferramenta falhar, o erro real é mostrado ao utilizador.
- **Deteção automática no chat**: `app.py` ganhou `CALENDAR_KEYWORDS` / `is_calendar_request()`, tal como já existia para email/imagem/vídeo.
- **Scheduler diário**: `app.py` usa `APScheduler` (`BackgroundScheduler`) para correr `verificar_agenda_diaria()` uma vez por dia, guardando o resultado em memória e imprimindo-o na consola (`📅 Assistente de Agenda: ...`). O endpoint `GET /api/agenda/briefing` devolve esse resultado, e o frontend (`script.js`) chama-o ao carregar a página e depois a cada 60 segundos (`mostrarAvisoAgendaDiario()` + `setInterval`), mostrando o aviso como mensagem do assistente no chat assim que é gerado — mesmo que a app já estivesse aberta antes da hora configurada. Guarda o `gerado_em` do último aviso já mostrado em `localStorage`, para não repetir o mesmo aviso.
- **Configuração visual**: a aba **📅 Agenda**, nas Definições da app, permite ativar/desativar o aviso diário e escolher a hora, sem tocar no `.env` manualmente. Reutiliza sempre o Servidor/Utilizador/Password já definidos na aba Email.
- **Aplicação sem reiniciar**: `app.py` guarda uma única instância do `BackgroundScheduler` (`reconfigurar_scheduler_agenda()`), reutilizada em vez de recriada. Sempre que as Definições são guardadas com alterações à Agenda, `/update-config` chama esta função de novo — ativar/desativar o aviso ou mudar a hora tem efeito imediato, sem reiniciar a app.

## Como ativar

Pela app: Definições → aba **📅 Agenda** → ativa "Aviso diário automático" e escolhe a hora → Guardar Alterações. Fica ativo de imediato.

Alternativa, direto no `.env`:
```
AGENDA_AVISO_ATIVO=true
AGENDA_AVISO_HORA=08:00
```
Não precisa de mais nenhuma configuração — reutiliza `EMAIL_HOST` / `EMAIL_USERNAME` / `EMAIL_PASSWORD` / `EMAIL_FOLDER` já existentes.

Novas dependências (já adicionadas ao `requirements.txt`): `icalendar`, `apscheduler`, e opcionalmente `win10toast` (Windows, notificações de secretária).

## Limitações conhecidas

- Só deteta eventos que chegam como convite por email (`.ics`). Eventos criados diretamente no Google Calendar/Outlook Calendar sem convite por email (ex: criados manualmente por ti, sem participantes) não aparecem — isso exigiria uma integração OAuth adicional com a API de Calendar (Google Calendar API ou Microsoft Graph), fora do âmbito desta versão.
- A janela de pesquisa por defeito cobre os últimos 200 emails da caixa de entrada (`max_emails_pesquisados`); em caixas muito cheias, um convite antigo pode não ser encontrado.
- O aviso diário fica guardado em memória (perde-se se reiniciares a app antes do utilizador o consultar) — para produção a sério, isto devia ir para um ficheiro/BD, tal como já é referido para o histórico de conversa.
