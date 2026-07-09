<p align="center">
    <img src="static/img/logo.png" width="220">
</p>

# Crew Assistant — Chatbot multi-agente com CrewAI

Projeto de exemplo com **vários agentes CrewAI** que colaboram entre si para
responder a uma mensagem, ligados a um **chatbot em HTML/CSS/JS** com design
próprio (tema escuro, com um "relay" visual que mostra qual agente está a
trabalhar em tempo real).

## Como funciona a equipa de agentes

```
Humano
  │
  ▼
🧭 Coordenador de Atendimento   → entende o pedido e faz um plano
  │
  ▼
🔎 Pesquisador                  → reúne informação relevante
  │
  ▼
🛠️ Especialista Técnico         → aprofunda tecnicamente
  │
  ▼
✍️ Redator Final                → escreve a resposta final ao humano
  │
  ▼
Resposta mostrada no chat
```

Cada agente recebe o output dos anteriores como contexto (`context=[...]`
nas `Task` do CrewAI), pelo que o resultado final já incorpora o trabalho de
toda a equipa.

## Estrutura do projeto

```
crew_chatbot/
├── app.py               # Servidor Flask (API, streaming SSE, rotas de texto/imagem/anexos)
├── crew_agents.py        # Definição dos agentes, tarefas e da crew (texto)
├── image_tool.py         # Geração de imagens via AUTOMATIC1111 local
├── ocr_tool.py            # OCR de anexos + junção num PDF pesquisável
├── requirements.txt
├── .env.example           # Copiar para .env e preencher a chave da API
├── PDF/                    # PDFs gerados a partir de imagens anexadas no chat
├── templates/
│   └── index.html         # Página do chat
└── static/
    ├── style.css           # Design (tema navy/indigo + relay animado)
    └── script.js           # Lógica do chat (fetch + streaming + anexos)
```

## Instalação

```bash
cd crew_chatbot
python3 -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env
```

Edita o `.env` e escolhe **um** dos provedores:

- **OpenAI**: define `OPENAI_API_KEY` e `MODEL_NAME=gpt-4o-mini` (ou outro modelo)
- **Anthropic (Claude)**: define `ANTHROPIC_API_KEY` e `MODEL_NAME=claude-sonnet-4-6`

O CrewAI usa o `litellm` por baixo, por isso basta indicar o nome do modelo
correto e a respetiva chave de API — não é preciso alterar código.

## Executar

```bash
python app.py
```

Depois abre o browser em: **http://localhost:5000**

## Notas importantes

- O histórico de conversa é guardado **em memória** (dicionário Python), só
  para efeitos de demonstração. Se reiniciares o servidor, o histórico perde-se.
  Para produção, substitui por uma base de dados (SQLite, Redis, Postgres...).
- O endpoint `/api/chat/stream` usa *Server-Sent Events* para mostrar, em
  tempo real, qual agente está ativo — é isso que anima os pontos no topo
  da página (o "relay").
- Existe também um endpoint simples `/api/chat` (sem streaming) caso
  prefiras integrar noutro frontend sem lidar com SSE.
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

Os ficheiros relevantes são `ocr_tool.py` (OCR + criação do PDF) e as
mesmas rotas de `app.py` usadas para o chat.

## Geração de imagens (opcional)

Se o pedido do humano parecer um pedido de imagem (ex: "desenha um cavalo",
"gera uma imagem de..."), o backend deteta isso automaticamente e, em vez de
acionar a crew de agentes de texto, faz o seguinte:

1. Usa o LLM já configurado (ex: `ollama/gnokit/improve-prompt`) para
   transformar o pedido num bom prompt de Stable Diffusion, em inglês.
2. Envia esse prompt para o **AUTOMATIC1111** local (`SD_API_URL` no `.env`,
   por omissão `http://127.0.0.1:7860`).
3. Devolve a imagem gerada ao chat.

**Pré-requisito:** o AUTOMATIC1111 (stable-diffusion-webui) tem de estar a
correr localmente com a flag `--api` ativa:

```
set COMMANDLINE_ARGS=--api --xformers --medvram
```

Sem isto a correr, os pedidos de texto continuam a funcionar normalmente —
só os pedidos de imagem vão falhar com uma mensagem de erro no chat.

Os ficheiros relevantes são `image_tool.py` (comunicação com a API do
AUTOMATIC1111 e refinamento do prompt) e as rotas em `app.py`.

## Personalizar

- **Agentes**: edita `crew_agents.py` (roles, goals, backstories, número de agentes).
- **Design**: edita `static/style.css` (cores em `:root`, tipografia, animações).
- **Fluxo**: podes mudar `Process.sequential` para `Process.hierarchical`
  em `crew_agents.py` se quiseres um agente "gestor" a delegar dinamicamente
  em vez de um pipeline fixo.
