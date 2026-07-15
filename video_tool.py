"""
video_tool.py
-------------
Geração de vídeos curtos a partir de texto, usando o Replicate
(https://replicate.com) — não depende da Hugging Face.

Modelo por omissão: minimax/video-01 (também conhecido como "Hailuo"),
um modelo texto-para-vídeo bem documentado no Replicate, que gera vídeos
de ~6 segundos a 720p/25fps a partir de um prompt em texto.

Autenticação: define REPLICATE_API_TOKEN no .env
(gera um token em https://replicate.com/account/api-tokens). A biblioteca
`replicate` lê esta variável de ambiente automaticamente.

NOTA: tal como a ImageTool, esta tool NÃO é chamada através de um Agent do
CrewAI — é chamada diretamente pelo app.py. Um vídeo é ainda maior que uma
imagem, por isso faz ainda menos sentido tentar fazê-lo "passar" pela
resposta de texto de um LLM.
"""

import os
import time
import litellm
import replicate
import requests

from datetime import datetime
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")
REPLICATE_API_TOKEN = os.getenv("REPLICATE_API_TOKEN")

VIDEO_MODEL = os.getenv("VIDEO_MODEL", "minimax/video-01")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
VIDEOS_DIR = os.path.join(BASE_DIR, "videos")
os.makedirs(VIDEOS_DIR, exist_ok=True)


class VideoToolInput(BaseModel):
    prompt: str = Field(description="Prompt detalhado do vídeo a gerar.")


class VideoTool(BaseTool):
    name: str = "VideoTool"

    description: str = (
        """
        Ferramenta responsável pela geração de vídeos curtos a partir de texto.

        Recebe um prompt completo e gera um vídeo.

        O prompt fornecido já deve estar totalmente otimizado.

        A ferramenta não melhora prompts nem interpreta pedidos do utilizador.
        """
    )

    args_schema: Type[BaseModel] = VideoToolInput

    def _refine_prompt(self, user_prompt: str) -> str:
        instruction = f"""
Transform the following request into a detailed text-to-video prompt.

Rules:

- Only output the prompt.
- Never explain.
- Never use quotes.
- Describe the subject, the scene, the motion/action taking place, camera
  movement, lighting and atmosphere.
- Keep it concise (2-4 sentences) — video prompts work best shorter and
  more literal than image prompts.

Request:

{user_prompt}
"""
        kwargs = {
            "model": MODEL_NAME,
            "messages": [{"role": "user", "content": instruction}],
        }
        if MODEL_NAME.startswith("ollama/") and os.getenv("OLLAMA_API_BASE"):
            kwargs["api_base"] = os.getenv("OLLAMA_API_BASE")

        try:
            response = litellm.completion(**kwargs)
            texto = response.choices[0].message.content.strip()
            return texto if texto else user_prompt
        except Exception:
            return user_prompt

    def _extract_video_bytes(self, output) -> bytes:
        """
        O `replicate.run(...)` pode devolver, consoante o modelo e a versão
        da biblioteca: uma lista de resultados, um objeto FileOutput
        (com .read() ou .url()), ou diretamente uma URL em string. Esta
        função normaliza tudo isso para bytes do vídeo.
        """
        if isinstance(output, list):
            if not output:
                raise RuntimeError("O Replicate não devolveu nenhum resultado.")
            output = output[0]

        # Objeto tipo ficheiro (FileOutput das versões mais recentes do SDK)
        if hasattr(output, "read"):
            return output.read()

        # Já são bytes
        if isinstance(output, (bytes, bytearray)):
            return bytes(output)

        # URL (string, ou objeto com método .url())
        url = output.url() if callable(getattr(output, "url", None)) else str(output)
        resp = requests.get(url, timeout=180)
        resp.raise_for_status()
        return resp.content

    def _run(self, prompt: str):
        if not REPLICATE_API_TOKEN:
            raise RuntimeError(
                "REPLICATE_API_TOKEN não está definido no .env. Gera um "
                "token em https://replicate.com/account/api-tokens."
            )

        prompt_refinado = self._refine_prompt(prompt)

        # A geração de vídeo demora bastante e por vezes falha de forma
        # transitória (fila cheia, timeout do modelo) — vale a pena repetir
        # algumas vezes antes de desistir.
        ultimo_erro = None
        output = None
        for tentativa in range(1, 4):
            try:
                output = replicate.run(
                    VIDEO_MODEL,
                    input={
                        "prompt": prompt_refinado,
                        "prompt_optimizer": True,
                    },
                )
                break
            except Exception as exc:  # noqa: BLE001
                ultimo_erro = exc
                if tentativa < 3:
                    time.sleep(3 * tentativa)

        if output is None:
            raise RuntimeError(
                f"O Replicate ('{VIDEO_MODEL}') falhou após 3 tentativas. "
                f"Confirma o teu saldo/créditos em "
                f"https://replicate.com/account/billing, ou tenta "
                f"novamente daqui a pouco. Erro original: {ultimo_erro}"
            )

        video_bytes = self._extract_video_bytes(output)

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_{timestamp}.mp4"
        filepath = os.path.join(VIDEOS_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(video_bytes)

        return {
            "filename": filename,
            "path": filepath,
        }