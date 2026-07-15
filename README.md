<p align="center">
    <img src="static/img/logo.png" width="220">
</p>

# Crew Assistant — Chatbot multi-agente com CrewAI

Projeto de exemplo com **vários agentes CrewAI** que colaboram entre si para
responder a uma mensagem, ligados a um **chatbot em HTML/CSS/JS** com design
próprio (tema escuro, com um "relay" visual que mostra qual agente está a
trabalhar em tempo real).

## Como funciona a equipa de agentes

O CrewAI monta um pipeline diferente consoante o tipo de pedido:

**Pedido normal (texto)**

```
Utilizador
     │
     ▼
🧭 Coordenador
     │
     ▼
🔎 Pesquisador
     │
     ▼
🛠️ Especialista
     │
     ▼
✍️ Redator Final
     │
     ▼
Resposta apresentada no chat
```

**Pedido de email** (detetado por palavras-chave em `app.py`, ex: "email",
"fatura", "gmail", "outlook", "anexo", "recibo")

```
Utilizador
     │
     ▼
📧 Assistente de Email  (chama sempre a EmailTool — nunca inventa dados)
     │
     ▼
✍️ Redator Final  (reformula fielmente o resultado real da EmailTool)
     │
     ▼
Resposta apresentada no chat
```

> O Coordenador/Pesquisador/Especialista ficam de fora deste pipeline. Como
> não têm acesso à caixa de correio real, ao "planearem" a resposta
> acabavam por gerar exemplos ilustrativos com números e nomes de ficheiros
> inventados — que a versão final apresentava como se fossem reais. O
> pipeline de email é por isso direto: só o agente com a ferramenta e o
> redator que reformula o texto, sem inventar nada.

**Pedido de imagem** (detetado por palavras-chave em `app.py`, ex:
"desenha", "gera uma imagem", "imagem de")

```
Utilizador
     │
     ▼
app.py chama a ImageTool DIRETAMENTE (sem passar pelo CrewAI/LLM)
     │
     ▼
Imagem gerada, guardada em imagens/ e devolvida ao chat
```

> A geração de imagem não passa por nenhum agente CrewAI. Uma imagem em
> base64 tem tipicamente dezenas ou centenas de milhares de caracteres —
> comprido demais para um LLM conseguir "reproduzir" fielmente na resposta
> final de uma Task sem a truncar ou corromper. Por isso o `app.py` chama a
> `ImageTool` diretamente; o LLM só é usado *dentro* da ferramenta, para
> melhorar o prompt de texto antes de gerar a imagem (isso sim, cabe bem
> numa resposta de LLM).

Cada agente recebe o output dos anteriores como contexto (`context=[...]`
nas `Task` do CrewAI), pelo que o resultado final já incorpora o trabalho de
toda a equipa.

## Instalação

```bash
cd crew_chatbot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edita o `.env` e escolhe **um** dos provedores de LLM:

- **OpenAI**: define `OPENAI_API_KEY` e `MODEL_NAME=gpt-4o-mini` (ou outro modelo)
- **Anthropic (Claude)**: define `ANTHROPIC_API_KEY` e `MODEL_NAME=claude-sonnet-4-6`
- **Ollama (local)**: define `MODEL_NAME=ollama/qwen2.5` (ou outro modelo Ollama
  com bom suporte de *function calling* — ver nota abaixo)

O CrewAI usa o `litellm` por baixo, por isso basta indicar o nome do modelo
correto e a respetiva chave de API — não é preciso alterar código.

> **Nota sobre modelos locais (Ollama) e *function calling*:** os agentes
> de Email e de Coordenação dependem de o LLM conseguir chamar ferramentas
> corretamente. Modelos como `mistral` puro têm suporte inconsistente disto
> no Ollama e podem "inventar" texto a fingir que usaram uma ferramenta em
> vez de a chamarem de verdade. `qwen2.5` e `llama3.1` costumam ser bem mais
> fiáveis neste aspeto.

Para a funcionalidade de **email** (ver secção própria abaixo), define
também:
```
EMAIL_HOST=imap.gmail.com
EMAIL_PORT=993
EMAIL_USERNAME=oteuemail@gmail.com
EMAIL_PASSWORD=<password de aplicação — nunca a password normal de login>
EMAIL_FOLDER=INBOX
```

Para a funcionalidade de **geração de imagens** (ver secção própria
abaixo), define também:
```
HF_TOKEN=<o teu token da Hugging Face>
IMAGE_MODEL=black-forest-labs/FLUX.1-schnell
IMAGE_PROVIDER=hf-inference
```

Para a funcionalidade de **geração de vídeos** (ver secção própria
abaixo), define também (usa o mesmo `HF_TOKEN` de cima):
```
VIDEO_MODEL=Wan-AI/Wan2.2-TI2V-5B
VIDEO_PROVIDER=fal-ai
```

## Executar

```bash
python app.py
```

Depois abre o browser em: **http://localhost:5000**

## Outras Funcionalidades

🌍 Internacionalização (PT/EN)

Foi implementado um sistema completo de internacionalização (i18n), permitindo alterar dinamicamente o idioma da interface e das respostas dos agentes.

- Funcionalidades
- Seleção de idioma através de um menu suspenso.
- Suporte para:
  - 🇵🇹 Português
  - 🇬🇧 English
- Alteração imediata dos textos da interface sem recarregar a página.
- Tradução dos textos estáticos da aplicação.
- O idioma escolhido é enviado para o backend, garantindo que toda a equipa de agentes responde exclusivamente no idioma selecionado.

## 🇵🇹🇬🇧 Seletor de idioma com bandeiras

- O seletor de idioma foi melhorado para incluir bandeiras, tornando a escolha mais intuitiva.

- Inclui:

- Bandeira do idioma atualmente selecionado.
- Alteração automática da bandeira quando o idioma muda.
- Ícones SVG leves e adaptados ao design da aplicação.
🌙 Tema Claro / Escuro

💬 Nova Conversa

- Foi criado um botão Nova Conversa para iniciar rapidamente uma nova sessão.

- Ao iniciar uma nova conversa:

- é criado um novo identificador de sessão;
- o histórico atual deixa de ser utilizado;
- a área do chat é limpa;
- os agentes começam uma conversa completamente nova.

📜 Histórico de Conversas

- O projeto foi preparado para apresentar o histórico das conversas anteriores.

- Cada conversa pode ser apresentada numa lista lateral, permitindo ao utilizador alternar facilmente entre diferentes sessões.

📄 Sistema de Logs

- Foi iniciado um sistema de registo da execução dos agentes.

- Os logs incluem informação como:

    - data;
    - hora;
    - pergunta do utilizador;
    - execução dos agentes;
    - resposta final.

Este sistema facilita a depuração, auditoria e análise do comportamento da Crew.

## Notas importantes

- O histórico de conversa é guardado **em memória** (dicionário Python), só
  para efeitos de demonstração. Se reiniciares o servidor, o histórico perde-se.
  Para produção, substitui por uma base de dados (SQLite, Redis, Postgres...).
- O endpoint `/api/chat/stream` usa *Server-Sent Events* para mostrar, em
  tempo real, qual agente está ativo — é isso que anima os pontos no topo
  da página (o "relay").
- Existe também um endpoint simples `/api/chat` (sem streaming) caso
  prefiras integrar noutro frontend sem lidar com SSE.
- Pastas geradas automaticamente na raiz do projeto (criadas sozinhas na
  primeira execução, não precisas de as criar à mão):
  - `PDF/` — PDFs pesquisáveis criados a partir de anexos de imagem (OCR) e
    faturas descarregadas por email.
  - `imagens/` — imagens geradas pela `ImageTool`.
  - `videos/` — vídeos gerados pela `VideoTool`.
  - `logs/` — um ficheiro de log por conversa, com o detalhe de cada agente.
- **Segurança:** o `.env` contém credenciais reais (password de email,
  token da Hugging Face, chaves de API). Nunca o commits para o git —
  confirma que está no `.gitignore`. Se alguma password ou token ficar
  exposto por engano (ex: partilhado num chat, print, ou commit), troca-o
  imediatamente.
- Podes adicionar ferramentas reais aos agentes (pesquisa na web, leitura de
  ficheiros, etc.) usando `crewai-tools`, por exemplo:

  ```python
  from crewai_tools import SerperDevTool
  pesquisador = Agent(..., tools=[SerperDevTool()])
  ```

## Anexos: OCR + junção em PDF

No chat, junto ao campo de texto, existe um botão de clip (📎) que permite
anexar uma ou mais imagens (fotos de documentos, recibos, páginas de livros,
etc.). Ao enviar:

1. O backend faz **OCR** a cada imagem (com Tesseract, via `pytesseract`).
2. Junta todas as imagens num **único PDF pesquisável** (cada imagem numa
   página, com o texto OCR embutido como camada invisível — dá para
   selecionar/pesquisar texto no PDF final).
3. Guarda o PDF na pasta **`PDF/`** na raiz do projeto, com o nome
   `anexos_AAAAMMDD_HHMMSS.pdf`.
4. Se também escreveste uma mensagem de texto junto com as imagens (ex:
   "resume este documento"), o texto extraído por OCR é passado como
   contexto extra à equipa de agentes, para que a resposta final já tenha
   em conta o conteúdo das imagens.

**Pré-requisito: o motor Tesseract OCR** (não é só um pacote Python, é
software à parte):

- Windows: descarrega o instalador em
  https://github.com/UB-Mannheim/tesseract/wiki (escolhe a versão de 64-bit).
  Durante a instalação, na secção de "Additional language data", marca
  também **Portuguese** (para OCR em português).
- Depois de instalado, se o comando `tesseract` não for reconhecido no
  PowerShell, define no `.env` o caminho completo do executável:
  ```
  TESSERACT_CMD=C:\Program Files\Tesseract-OCR\tesseract.exe
  ```

Os ficheiros relevantes são `tools/ocr_tool.py` (OCR + criação do PDF) e as
mesmas rotas de `app.py` usadas para o chat.

## Ler emails (Gmail / Outlook)

No chat, pedidos que mencionem palavras como "email", "fatura", "gmail",
"outlook", "anexo" ou "recibo" ativam o **Assistente de Email**, que usa a
`EmailTool` (`tools/email_tool.py`) para ligar à caixa de correio por IMAP.

Exemplos de pedidos que funcionam:
- "verifica no meu email todos os emails não lidos com o assunto Fatura, diz quantos foram"
- "lê os emails da caixa de entrada que contenham faturas, se tiverem alguma fatura em anexo junta num documento PDF"

O que a `EmailTool` faz:
1. Liga por IMAP com as credenciais do `.env`.
2. Procura emails por palavra-chave no assunto (`subject_keyword`, por
   omissão `"Fatura"`), com opção de filtrar só os não lidos
   (`unread_only`).
3. Devolve a contagem real e uma lista com remetente/assunto/data/se tem
   anexo.
4. Se pedido, descarrega os anexos de todos os emails encontrados e
   junta-os **num único PDF**, guardado em `PDF/faturas_email_AAAAMMDD_HHMMSS.pdf`
   (PDFs são fundidos diretamente; imagens são convertidas em página PDF).

**Importante — a EmailTool nunca inventa dados.** Se a ligação falhar, é
devolvido o erro real, nunca um resultado fictício. Por desenho, o pipeline
de email (ver diagrama acima) é curto (só o Assistente de Email + Redator)
precisamente para nenhum outro agente "imaginar" exemplos que pudessem ser
confundidos com dados reais.

### Gmail (suportado)

Com verificação em 2 passos ativa (recomendado), o Gmail **não aceita** a
password normal de login para IMAP — é preciso gerar uma **password de
aplicação**:

1. Vai a https://myaccount.google.com/apppasswords
2. Cria uma password de aplicação (16 caracteres)
3. No `.env`:
   ```
   EMAIL_HOST=imap.gmail.com
   EMAIL_PORT=993
   EMAIL_USERNAME=oteuemail@gmail.com
   EMAIL_PASSWORD=<password de aplicação, sem espaços>
   ```
4. Confirma que o IMAP está ativo em Gmail → Definições → **Ver todas as
   definições** → separador **"Encaminhamento e POP/IMAP"** (em muitas
   contas o IMAP já vem ativado por omissão e essa opção nem aparece — é
   normal).

Testa a ligação isoladamente, sem passar pelo chatbot:
```bash
python -u test_email_tool.py
```

### Outlook / Hotmail (contas pessoais) — ⚠️ requer OAuth2

Desde ~outubro de 2024, a Microsoft **bloqueia por completo** o login IMAP
com password (mesmo password de aplicação) em contas pessoais
Outlook.com/Hotmail — só aceita OAuth2. Não há password nenhuma que resolva
isto com login simples.

> **Estado atual:** existe um módulo `outlook_auth.py` já preparado com o
> essencial do fluxo OAuth2 via MSAL (Device Code Flow), mas a integração
> com a `EmailTool` (autenticação IMAP via `XOAUTH2`) ainda **não está
> ligada** — é trabalho pendente. Para já, usa Gmail. Se precisares mesmo
> de Outlook, os passos em falta são:
> 1. Registar uma app no [Azure Portal](https://portal.azure.com) (App
>    registrations), tipo de conta "Personal Microsoft accounts only",
>    com "Allow public client flows" ativado.
> 2. Adicionar a permissão delegada `IMAP.AccessAsUser.All` (API "Office
>    365 Exchange Online").
> 3. Copiar o "Application (client) ID" para `MS_CLIENT_ID` no `.env`.
> 4. Instalar `msal` (`pip install msal`) e criar um script
>    `outlook_auth_setup.py` que corre uma vez para autenticar
>    interativamente (Device Code Flow) e guardar o token em cache.
> 5. Alterar `EmailTool._connect()` para, quando `EMAIL_PROVIDER=outlook`,
>    obter o `access_token` via `outlook_auth.get_access_token()` e fazer
>    `mail.authenticate("XOAUTH2", ...)` em vez de `mail.login(...)`.

## Geração de vídeos

No chat, pedidos com palavras como "gera um vídeo", "cria um vídeo" ou
"vídeo de" ativam a geração de vídeo — pelo mesmo princípio da imagem (ver
acima), a `VideoTool` (`tools/video_tool.py`) é chamada **diretamente** pelo
`app.py`, nunca através de um Agent do CrewAI (um vídeo é ainda maior que
uma imagem em base64, por isso faz ainda menos sentido tentar fazê-lo
"passar" pela resposta de um LLM).

1. O LLM refina o prompt do humano (mais conciso do que para imagem — os
   modelos de vídeo funcionam melhor com descrições diretas de 2-4 frases:
   sujeito, cena, movimento/ação, câmara, iluminação).
2. Esse prompt é enviado à Hugging Face (modelo `VIDEO_MODEL`, por omissão
   `Wan-AI/Wan2.2-TI2V-5B`, via provider `VIDEO_PROVIDER`, por omissão
   `fal-ai` — os mesmos recomendados na documentação oficial da HF para
   texto-para-vídeo).
3. O ficheiro `.mp4` é guardado em `videos/video_AAAAMMDD_HHMMSS.mp4` na
   raiz do projeto (pasta criada automaticamente) e é servido ao chat via
   `/videos/<filename>` — ao contrário da imagem, o vídeo **não** é
   enviado em base64 (seria demasiado grande para uma resposta JSON), o
   `<video>` no chat aponta diretamente para essa URL.

**Pré-requisito:** o mesmo `HF_TOKEN` já usado para imagens.

**⚠️ Consome muitos mais créditos/tempo do que a geração de imagem.** É
fácil esgotar a quota gratuita da Hugging Face rapidamente — ver a nota de
gestão de créditos na secção de imagens acima; aplica-se aqui com ainda
mais força. A geração pode demorar vários minutos.

## Geração de imagens

No chat, pedidos com palavras como "desenha", "gera uma imagem", "cria uma
imagem" ou "imagem de" ativam a geração de imagens.

**Importante: a geração de imagem não passa pelo CrewAI/LLM como resposta
final.** Uma imagem em base64 tem tipicamente dezenas ou centenas de
milhares de caracteres — longa demais para um LLM (sobretudo modelos locais)
conseguir reproduzir sem truncar ou corromper, o que resultava em imagens
partidas. Por isso o `app.py` chama a `ImageTool` (`tools/image_tool.py`)
**diretamente**:

1. O LLM configurado (`MODEL_NAME`) é usado só para refinar o pedido do
   humano num prompt de Stable Diffusion detalhado (função
   `_refine_prompt`) — isto sim, cabe perfeitamente numa resposta de texto.
2. Esse prompt é enviado à API de inferência da Hugging Face (modelo
   `IMAGE_MODEL`, por omissão `black-forest-labs/FLUX.1-schnell`).
3. A imagem é guardada em `imagens/imagem_AAAAMMDD_HHMMSS.png` na raiz do
   projeto (a pasta é criada automaticamente se não existir) e devolvida ao
   chat em base64, com um link de download (`/imagens/<filename>`).

**Pré-requisito:** um token da Hugging Face em `HF_TOKEN` no `.env`
(gera um em https://huggingface.co/settings/tokens).

**Gestão de créditos e providers:** a Hugging Face dá uma quota mensal
gratuita de créditos para os *Inference Providers*, partilhada entre todos
os providers (`hf-inference`, `fal-ai`, etc.) — não é por modelo. Erros
comuns:
- `500`/`503` intermitente → normalmente instabilidade temporária do
  provider (`IMAGE_TOOL` já tenta 3 vezes automaticamente antes de
  desistir). Podes trocar de provider no `.env`:
  ```
  IMAGE_PROVIDER=fal-ai
  ```
- `402 Payment Required` / "depleted your monthly included credits" →
  esgotaste a quota gratuita da conta (isto é ao nível da conta HF, não do
  modelo — trocar de modelo ou provider não resolve). Opções: esperar pelo
  reset mensal, comprar créditos pré-pagos, ou assinar o plano PRO (20x
  mais quota incluída). Ver https://huggingface.co/settings/billing.

Os ficheiros relevantes são `tools/image_tool.py` (refinamento do prompt +
chamada à API da Hugging Face + gravação em disco) e as rotas em `app.py`.

## Personalizar

- **Agentes**: edita `crew_agents.py` (roles, goals, backstories, número de agentes).
- **Design**: edita `static/style.css` (cores em `:root`, tipografia, animações).
- **Fluxo**: podes mudar `Process.sequential` para `Process.hierarchical`
  em `crew_agents.py` se quiseres um agente "gestor" a delegar dinamicamente
  em vez de um pipeline fixo.
- **Deteção de email/imagem**: as palavras-chave usadas para decidir se um
  pedido é sobre email (`EMAIL_KEYWORDS`) ou imagem (`IMAGE_KEYWORDS`) estão
  no topo do `app.py`.