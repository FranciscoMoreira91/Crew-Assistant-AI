import os
import io
import time
import base64
import litellm

from datetime import datetime
from huggingface_hub import InferenceClient
from typing import Type
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

SD_API_URL = os.getenv("SD_API_URL", "http://127.0.0.1:7860").rstrip("/")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

HF_TOKEN = os.getenv("HF_TOKEN")

IMAGE_MODEL = os.getenv(
    "IMAGE_MODEL",
    "stabilityai/stable-diffusion-3-medium-diffusers"
)

# O provider "hf-inference" (serverless, gratuito) tem estado instável com
# alguns modelos, com erros 500/503 intermitentes já reportados por vários
# utilizadores nos fóruns da Hugging Face. Se isso acontecer com frequência,
# define no .env, por exemplo, IMAGE_PROVIDER=fal-ai (outros providers
# disponíveis para a maioria dos modelos: "replicate", "together", etc. —
# consulta a página do modelo em huggingface.co, botão "Use this model").
IMAGE_PROVIDER = os.getenv("IMAGE_PROVIDER", "hf-inference")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do projeto (um nível acima de tools/)
IMAGENS_DIR = os.path.join(BASE_DIR, "imagens")
os.makedirs(IMAGENS_DIR, exist_ok=True)

client = InferenceClient(
    provider=IMAGE_PROVIDER,
    api_key=HF_TOKEN,
)


DEFAULT_NEGATIVE_PROMPT = (
    "low quality, blurry, bad anatomy, deformed, watermark, text, "
    "extra fingers, cropped, worst quality"
)


class ImageToolInput(BaseModel):

    prompt: str = Field(
        description="Prompt detalhado da imagem."
    )

    negative_prompt: str = Field(
        default=DEFAULT_NEGATIVE_PROMPT,
        description="Prompt negativo."
    )

    width: int = Field(
        default=1024,
        description="Largura da imagem."
    )

    height: int = Field(
        default=1024,
        description="Altura da imagem."
    )

    steps: int = Field(
        default=30,
        description="Número de passos."
    )

    cfg_scale: float = Field(
        default=7,
        description="CFG Scale."
    )


class ImageTool(BaseTool):

    name: str = "ImageTool"

    description: str = (
        """
        Ferramenta responsável pela geração de imagens.

        Recebe um prompt completo e gera uma imagem.

        O prompt fornecido já deve estar totalmente otimizado.

        A ferramenta não melhora prompts nem interpreta pedidos do utilizador.
        """
    )

    args_schema: Type[BaseModel] = ImageToolInput

    def _refine_prompt(self, user_prompt: str):

        current_model = os.getenv("MODEL_NAME", "gpt-4o-mini")

        instruction = f"""
Transform the following request into a professional Stable Diffusion prompt.

Rules:

- Only output the prompt.
- Never explain.
- Never use quotes.
- Extremely detailed.
- Include lighting.
- Include camera.
- Include composition.
- Include artistic style.
- Include quality tags.
- Include colours.
- Include atmosphere.

Request:

{user_prompt}
"""

        kwargs = {
            "model": current_model,
            "messages": [
                {
                    "role": "user",
                    "content": instruction
                }
            ]
        }

        if current_model.startswith("ollama/") and os.getenv("OLLAMA_API_BASE"):
            kwargs["api_base"] = os.getenv("OLLAMA_API_BASE")

        try:

            response = litellm.completion(**kwargs)

            return response.choices[0].message.content.strip()

        except Exception:

            return user_prompt

    # NOTA: esta tool já não é usada através de um Agent do CrewAI (ver
    # app.py — é chamada diretamente para evitar que o base64 passe pelo
    # LLM). Por isso pode devolver um dict em vez de apenas uma string.
    def _run(
        self,
        prompt: str,
        negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
        width = 1024,
        height = 1024,
        steps = 28,
        cfg_scale = 3.5
    ):

        prompt_refinado = self._refine_prompt(prompt)

        # O provider de inferência (ver IMAGE_PROVIDER no .env) por vezes
        # devolve erros 500/503 transitórios — tenta algumas vezes antes
        # de desistir, com uma pequena pausa entre tentativas.
        ultimo_erro = None
        image = None
        for tentativa in range(1, 4):
            try:
                image = client.text_to_image(
                    prompt=prompt_refinado,
                    model=IMAGE_MODEL,
                    width=width,
                    height=height
                )
                break
            except Exception as exc:  # noqa: BLE001
                ultimo_erro = exc
                if tentativa < 3:
                    time.sleep(2 * tentativa)

        if image is None:
            raise RuntimeError(
                f"O provider de imagem ('{IMAGE_PROVIDER}') falhou após 3 "
                f"tentativas. Isto costuma ser uma instabilidade temporária "
                f"do lado do fornecedor — tenta novamente daqui a pouco, ou "
                f"muda IMAGE_PROVIDER no .env (ex: 'fal-ai'). "
                f"Erro original: {ultimo_erro}"
            )

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"imagem_{timestamp}.png"
        filepath = os.path.join(IMAGENS_DIR, filename)
        image.save(filepath, format="PNG")

        buffer = io.BytesIO()

        image.save(buffer, format="PNG")

        return {
            "base64": base64.b64encode(buffer.getvalue()).decode(),
            "filename": filename,
            "path": filepath,
        }