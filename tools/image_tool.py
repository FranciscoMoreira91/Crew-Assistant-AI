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

# NOTA (correção issue #1): IMAGE_PROVIDER, IMAGE_MODEL e HF_TOKEN deixaram
# de ser lidos apenas uma vez à importação do módulo. Antes, uma alteração
# feita no painel de Definições (que só atualiza os.environ/.env) nunca
# chegava a este módulo, porque as constantes globais e o InferenceClient
# já tinham sido criados com os valores do arranque — o utilizador podia
# mudar o token/provider à vontade que a app continuava a usar sempre o
# valor antigo até reiniciar o processo. Agora estes valores são lidos de
# novo em cada chamada a _run(), tal como já acontecia com o token do
# Replicate em video_tool.py.

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do projeto (um nível acima de tools/)
IMAGENS_DIR = os.path.join(BASE_DIR, "imagens")
os.makedirs(IMAGENS_DIR, exist_ok=True)


def _current_image_config():
    """Lê a configuração de imagem diretamente do ambiente, a cada chamada,
    para que alterações feitas no painel de Definições (ou no .env) tenham
    efeito imediato, sem ser preciso reiniciar a app."""
    provider = os.getenv("IMAGE_PROVIDER", "hf-inference")
    model = os.getenv("IMAGE_MODEL", "stabilityai/stable-diffusion-3-medium-diffusers")
    token = os.getenv("HF_TOKEN")
    return provider, model, token


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

        # Lê a configuração atual (issue #1) e cria o cliente na hora, para
        # refletir qualquer mudança feita nas Definições sem reiniciar a app.
        image_provider, image_model, hf_token = _current_image_config()
        client = InferenceClient(provider=image_provider, api_key=hf_token)

        # O provider de inferência (ver IMAGE_PROVIDER no .env) por vezes
        # devolve erros 500/503 transitórios — tenta algumas vezes antes
        # de desistir, com uma pequena pausa entre tentativas.
        ultimo_erro = None
        image = None
        for tentativa in range(1, 4):
            try:
                # issue #7: negative_prompt/steps/cfg_scale eram aceites
                # pela função mas nunca chegavam a ser enviados à API.
                image = client.text_to_image(
                    prompt=prompt_refinado,
                    negative_prompt=negative_prompt or None,
                    model=image_model,
                    width=width,
                    height=height,
                    num_inference_steps=steps,
                    guidance_scale=cfg_scale,
                )
                break
            except Exception as exc:  # noqa: BLE001
                ultimo_erro = exc
                if tentativa < 3:
                    time.sleep(2 * tentativa)

        if image is None:
            raise RuntimeError(
                f"O provider de imagem ('{image_provider}') falhou após 3 "
                f"tentativas. Isto costuma ser uma instabilidade temporária "
                f"do lado do fornecedor — tenta novamente daqui a pouco, ou "
                f"muda IMAGE_PROVIDER no .env ou nas Definições (ex: 'fal-ai'). "
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
            "prompt": prompt,
        }