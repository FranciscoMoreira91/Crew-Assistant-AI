"""
image_tool.py
--------------
Comunicação com a API local do AUTOMATIC1111 (Stable Diffusion WebUI)
para gerar imagens a partir de texto (txt2img).

Pressupõe que o WebUI foi iniciado com a flag --api, por exemplo:
    set COMMANDLINE_ARGS=--api --xformers --medvram
"""

import os
import requests
import litellm

SD_API_URL = os.getenv("SD_API_URL", "http://127.0.0.1:7860").rstrip("/")
MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o-mini")


def refine_image_prompt(user_message: str) -> str:
    """
    Usa o LLM já configurado para transformar
    o pedido do humano num bom prompt de Stable Diffusion, em portugês.
    Se falhar por qualquer razão, devolve a mensagem original como fallback.
    """
    instrucao = (
        "Rewrite the following request as a single, detailed Stable Diffusion "
        "image prompt in Portuguese. Only output the prompt itself, nothing else, "
        "no quotes, no explanations.\n\n"
        f"Request: {user_message}"
    )
    kwargs = {
        "model": MODEL_NAME,
        "messages": [{"role": "user", "content": instrucao}],
    }
    if MODEL_NAME.startswith("ollama/") and os.getenv("OLLAMA_API_BASE"):
        kwargs["api_base"] = os.getenv("OLLAMA_API_BASE")

    try:
        response = litellm.completion(**kwargs)
        texto = response.choices[0].message.content.strip()
        return texto if texto else user_message
    except Exception:
        return user_message

DEFAULT_NEGATIVE_PROMPT = (
    "blurry, low quality, distorted, deformed, extra limbs, watermark, text, "
    "bad anatomy, worst quality"
)


def is_stable_diffusion_available() -> bool:
    """Verifica rapidamente se o AUTOMATIC1111 está a correr e acessível."""
    try:
        resp = requests.get(f"{SD_API_URL}/sdapi/v1/sd-models", timeout=3)
        return resp.status_code == 200
    except requests.RequestException:
        return False


def generate_image(
    prompt: str,
    negative_prompt: str = DEFAULT_NEGATIVE_PROMPT,
    steps: int = 25,
    width: int = 512,
    height: int = 512,
) -> str:
    """
    Pede ao AUTOMATIC1111 para gerar uma imagem a partir do prompt.
    Devolve a imagem como string base64 (sem prefixo "data:image/...").
    Lança requests.RequestException se o servidor não estiver acessível.
    """
    payload = {
        "prompt": prompt,
        "negative_prompt": negative_prompt,
        "steps": steps,
        "width": width,
        "height": height,
        "sampler_name": "DPM++ 2M",
        "cfg_scale": 7,
    }
    resp = requests.post(
        f"{SD_API_URL}/sdapi/v1/txt2img", json=payload, timeout=300
    )
    resp.raise_for_status()
    data = resp.json()
    images = data.get("images") or []
    if not images:
        raise RuntimeError("O AUTOMATIC1111 não devolveu nenhuma imagem.")
    return images[0]
