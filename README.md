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
├── app.py              # Servidor Flask (API + streaming SSE de progresso)
├── crew_agents.py       # Definição dos agentes, tarefas e da crew
├── requirements.txt
├── .env.example         # Copiar para .env e preencher a chave da API
├── templates/
│   └── index.html       # Página do chat
└── static/
    ├── style.css         # Design (tema navy/indigo + relay animado)
    └── script.js         # Lógica do chat (fetch + streaming)
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

## Personalizar

- **Agentes**: edita `crew_agents.py` (roles, goals, backstories, número de agentes).
- **Design**: edita `static/style.css` (cores em `:root`, tipografia, animações).
- **Fluxo**: podes mudar `Process.sequential` para `Process.hierarchical`
  em `crew_agents.py` se quiseres um agente "gestor" a delegar dinamicamente
  em vez de um pipeline fixo.
