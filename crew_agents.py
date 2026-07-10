"""
crew_agents.py
--------------
Define os agentes CrewAI, as suas tarefas e o fluxo de colaboração
usado para responder a uma mensagem do utilizador.

Fluxo (sequencial, com passagem de contexto entre tarefas):

    Utilizador
        │
        ▼
  [1] Coordenador   -> entende o pedido, define o plano de resposta
        │
        ▼
  [2] Pesquisador    -> reúne factos/informação relevante
        │
        ▼
  [3] Especialista   -> aprofunda tecnicamente com base na pesquisa
        │
        ▼
  [4] Redator Final  -> junta tudo, escreve a resposta final, clara e simpática
        │
        ▼
     Resposta ao humano
"""

import os
from crewai import Agent, Task, Crew, Process
from dotenv import load_dotenv
from logger import CrewLogger
from datetime import datetime
import time

from contextlib import redirect_stdout
from pathlib import Path

load_dotenv()

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

# Se estiver definida ANTHROPIC_API_KEY, o litellm (usado internamente pelo
# CrewAI) trata do roteamento automaticamente a partir do nome do modelo,
# ex: "claude-sonnet-4-6".


def build_agents():
    coordenador = Agent(
        role="Coordenador de Atendimento",
        goal=(
            "Compreender profundamente o pedido do humano, identificar o que "
            "realmente precisa (mesmo que não o diga de forma explícita) e "
            "definir um plano curto e claro para os restantes agentes seguirem."
        ),
        backstory=(
            "És o primeiro ponto de contacto de uma equipa de assistentes. "
            "Tens muita experiência em perceber a intenção real por trás de "
            "perguntas vagas e em orientar uma equipa multidisciplinar para "
            "dar a melhor resposta possível, sem trabalho desnecessário."
        ),
        allow_delegation=False,
        verbose=True,
        llm=MODEL_NAME,
    )

    pesquisador = Agent(
        role="Pesquisador",
        goal=(
            "Reunir e organizar a informação, factos e contexto necessários "
            "para responder ao pedido do humano com rigor."
        ),
        backstory=(
            "És meticuloso e gostas de confirmar factos antes de os passar "
            "adiante. Trabalhas a partir do plano do Coordenador e entregas "
            "informação estruturada e sem rodeios ao Especialista."
        ),
        allow_delegation=False,
        verbose=True,
        llm=MODEL_NAME,
    )

    especialista = Agent(
        role="Especialista Técnico",
        goal=(
            "Aprofundar a resposta com conhecimento técnico sólido, "
            "explicações corretas e exemplos práticos sempre que fizer sentido."
        ),
        backstory=(
            "És a referência técnica da equipa. Pegas na investigação feita "
            "e transformas isso numa resposta tecnicamente correta, precisa "
            "e sem ambiguidades, sinalizando limitações quando existirem."
        ),
        allow_delegation=False,
        verbose=True,
        llm=MODEL_NAME,
    )

    redator = Agent(
        role="Redator Final",
        goal=(
            "Reescrever o material técnico recebido numa resposta final "
            "clara, simpática, bem estruturada e fácil de ler para o humano, "
            "no mesmo idioma em que o humano escreveu."
        ),
        backstory=(
            "És responsável pela qualidade final da comunicação. Garantes "
            "tom adequado, boa formatação (parágrafos curtos, listas quando "
            "ajudam) e que nada de essencial se perdeu pelo caminho."
        ),
        allow_delegation=False,
        verbose=True,
        llm=MODEL_NAME,
    )

    return coordenador, pesquisador, especialista, redator


def build_tasks(user_message: str, history_text: str, language="pt"):
    coordenador, pesquisador, especialista, redator = build_agents()

    if language == "pt":
        language_instruction = (
            "IMPORTANTE: Todas as respostas e todo o raciocínio devem ser escritos exclusivamente em Português Europeu."
        )
    else:
        language_instruction = (
            "IMPORTANT: All reasoning and all responses must be written exclusively in English."
        )

    contexto_conversa = (
        f"{language_instruction}\n\n"
        f"Histórico recente da conversa (pode estar vazio):\n{history_text}\n\n"
        f"Nova mensagem do humano:\n{user_message}"
    )   

    tarefa_coordenacao = Task(
        description=(
            f"{contexto_conversa}\n\n"
            "Analisa o pedido do humano e produz um plano curto (3-5 pontos) "
            "com o que precisa de ser pesquisado/explicado para responder bem. "
            "Não respondas ainda ao humano, apenas define o plano."
        ),
        expected_output="Um plano curto e objetivo em bullet points.",
        agent=coordenador,
    )

    tarefa_pesquisa = Task(
        description=(
            f"{language_instruction}\n\n"
            "Com base no plano do Coordenador, reúne a informação, factos e "
            "contexto relevantes para o pedido original do humano. "
            "Sê objetivo e organiza a informação por tópicos."
        ),
        expected_output="Informação organizada por tópicos, pronta a ser usada.",
        agent=pesquisador,
        context=[tarefa_coordenacao],
    )

    tarefa_especialista = Task(
        description=(
            f"{language_instruction}\n\n"
            "Usa a informação reunida pelo Pesquisador para construir uma "
            "resposta tecnicamente sólida ao pedido original do humano. "
            "Inclui exemplos práticos quando fizer sentido e sinaliza "
            "claramente qualquer suposição ou limitação."
        ),
        expected_output="Conteúdo técnico completo e correto para o pedido.",
        agent=especialista,
        context=[tarefa_coordenacao, tarefa_pesquisa],
    )

    tarefa_redacao = Task(
        description=(
            f"{language_instruction}\n\n"
            """Pega em todo o trabalho da equipa e escreve a RESPOSTA FINAL
            para o humano.

            A resposta deve ser:
            - clara;
            - bem estruturada;
            - natural;
            - escrita exclusivamente no idioma indicado acima.

            Nunca mudes de idioma.
            Nunca mistures Português e Inglês.
            Não menciones os outros agentes nem o processo interno da equipa.
            Fala diretamente com o humano.
            """
        ),
        expected_output="Resposta final, pronta a mostrar ao humano.",
        agent=redator,
        context=[tarefa_coordenacao, tarefa_pesquisa, tarefa_especialista],
    )

    return [tarefa_coordenacao, tarefa_pesquisa, tarefa_especialista, tarefa_redacao]


def run_crew(user_message: str, history_text: str = "", language="pt", logger=None, task_callback=None):
    """
    Executa a crew de forma síncrona e devolve a resposta final (string).
    `task_callback`, se fornecido, é chamado pelo CrewAI após cada tarefa
    concluída, permitindo emitir progresso em tempo real (ex: via SSE).
    """

    if logger is None:
        logger = CrewLogger()
    
    tasks = build_tasks(
        user_message=user_message,
        history_text=history_text,
        language=language
    )

    crew = Crew(
        agents=[t.agent for t in tasks],
        tasks=tasks,
        process=Process.sequential,
        verbose=True,
        task_callback=task_callback,
    )

    try:
        resultado = crew.kickoff()
    except Exception as e:
        import traceback

        traceback.print_exc()

        raise

    return str(resultado)
