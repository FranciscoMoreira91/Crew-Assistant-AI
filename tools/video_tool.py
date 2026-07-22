"""
video_tool.py
-------------
Geração de vídeos curtos a partir de texto, usando o Hugging Face Inference API[](https://huggingface.co/docs/huggingface_hub/en/package_reference/inference_client).

Modelo por omissão: Lightricks/LTX-Video (ou outro modelo suportado via Inference Providers).
Autenticação: define HF_TOKEN no .env (token com permissões de Inference).
A biblioteca `huggingface_hub` lê esta variável automaticamente.

NOTA: tal como a ImageTool, esta tool NÃO é chamada através de um Agent do
CrewAI — é chamada diretamente pelo app.py.
"""

import os
import time
from datetime import datetime
from typing import Type

import requests
from huggingface_hub import InferenceClient
from pydantic import BaseModel, Field
from crewai.tools import BaseTool

MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do projeto
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
        """Mantido igual ao original."""
        current_model = os.getenv("MODEL_NAME", "gpt-4o-mini")
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
        # (código de litellm mantido igual)
        import litellm

        kwargs = {
            "model": current_model,
            "messages": [{"role": "user", "content": instruction}],
        }
        if current_model.startswith("ollama/") and os.getenv("OLLAMA_API_BASE"):
            kwargs["api_base"] = os.getenv("OLLAMA_API_BASE")
        try:
            response = litellm.completion(**kwargs)
            texto = response.choices[0].message.content.strip()
            return texto if texto else user_prompt
        except Exception:
            return user_prompt

    def _run(self, prompt: str):
        hf_token = os.getenv("HF_TOKEN")
        video_model = os.getenv("VIDEO_MODEL", "Lightricks/LTX-Video-0.9.8-13B-distilled")  # ou "tencent/HunyuanVideo", etc.

        if not hf_token:
            raise RuntimeError(
                "HF_TOKEN não está definido no .env. Gera um token em "
                "https://huggingface.co/settings/tokens (com permissão Inference)."
            )

        client = InferenceClient(token=hf_token)

        prompt_refinado = self._refine_prompt(prompt)

        # Geração de vídeo pode demorar bastante
        ultimo_erro = None
        output = None
        for tentativa in range(1, 4):
            try:
                # text_to_video retorna bytes do vídeo (geralmente MP4)
                output = client.text_to_video(
                    prompt_refinado,
                    model=video_model,
                    # Parâmetros opcionais comuns:
                    # num_frames=16,          # número de frames
                    # num_inference_steps=20, # qualidade vs velocidade
                    # guidance_scale=7.5,
                    # seed=42,
                )
                break
            except Exception as exc:
                ultimo_erro = exc
                if tentativa < 3:
                    time.sleep(5 * tentativa)  # espera mais generosa

        if output is None:
            raise RuntimeError(
                f"Hugging Face Inference ('{video_model}') falhou após 3 tentativas. "
                f"Verifica créditos/saldo em https://huggingface.co/settings/billing "
                f"ou tenta novamente mais tarde. Erro: {ultimo_erro}"
            )

        # output já deve ser bytes do vídeo
        if isinstance(output, (bytes, bytearray)):
            video_bytes = bytes(output)
        else:
            # fallback caso retorne outro formato
            video_bytes = output

        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"video_{timestamp}.mp4"
        filepath = os.path.join(VIDEOS_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(video_bytes)

        return {
            "filename": filename,
            "path": filepath,
        }