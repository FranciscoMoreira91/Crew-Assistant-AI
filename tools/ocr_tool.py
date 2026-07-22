"""
ocr_tool.py
-----------
Recebe imagens anexadas no chat, faz OCR a cada uma e junta tudo num
único PDF pesquisável (imagem + camada de texto invisível), guardado
na pasta PDF/ na raiz do projeto.

Requer o motor Tesseract OCR instalado no sistema (não é só um pacote
Python — ver README.md para instruções no Windows).
"""

import io
import os
from datetime import datetime

import pytesseract
from PIL import Image
from pypdf import PdfReader, PdfWriter

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # raiz do projeto (um nível acima de tools/)
PDF_DIR = os.path.join(BASE_DIR, "PDF")
os.makedirs(PDF_DIR, exist_ok=True)

# No Windows, se o tesseract.exe não estiver no PATH, define o caminho
# completo através da variável de ambiente TESSERACT_CMD (ver .env.example).
_tesseract_cmd = os.getenv("TESSERACT_CMD")
if _tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd


def _ocr_languages() -> str:
    """
    Lê o(s) idioma(s) de OCR a usar (correção issue #5).

    O painel de Definições e o backend (app.py) guardam a escolha do
    utilizador em OCR_LANGUAGE (singular), mas este módulo só lia
    OCR_LANGUAGES (plural, definida no .env.example) — os dois nomes
    nunca coincidiam, por isso mudar o idioma na UI não tinha qualquer
    efeito. Agora dá-se prioridade a OCR_LANGUAGE (o que o utilizador
    escolhe nas Definições) e cai-se em OCR_LANGUAGES como alternativa
    de compatibilidade com instalações mais antigas, mantendo sempre
    "por+eng" como valor por omissão.
    """
    return os.getenv("OCR_LANGUAGE") or os.getenv("OCR_LANGUAGES", "por+eng")


def _ocr_enabled() -> bool:
    """Correção issue #6: o interruptor 'Ativar OCR' das Definições não
    era verificado em lado nenhum antes de correr o OCR. Por omissão o
    OCR está ativo (comportamento igual ao anterior), mas agora
    OCR_ENABLED=false desliga-o de facto."""
    return os.getenv("OCR_ENABLED", "true").strip().lower() not in ("false", "0", "nao", "não", "no")


def images_to_searchable_pdf(images: list[bytes], filename_prefix: str = "anexos") -> dict:
    """
    images: lista de imagens em bytes (jpg/png/etc.)

    Cria uma página de PDF por imagem e junta tudo num único ficheiro PDF
    guardado em PDF/. Se o OCR estiver ativo (OCR_ENABLED, ver
    _ocr_enabled()), cada página fica pesquisável (imagem visível + texto
    OCR invisível por cima); caso contrário, a imagem é apenas incluída
    no PDF sem passar pelo Tesseract (mais rápido, sem texto pesquisável).

    Devolve:
        {
            "pdf_path": caminho absoluto do PDF gerado,
            "pdf_filename": nome do ficheiro,
            "extracted_text": todo o texto OCR concatenado (vazio se o
                               OCR estiver desativado),
        }
    """
    if not images:
        raise ValueError("Nenhuma imagem fornecida para processar.")

    ocr_ativo = _ocr_enabled()
    idiomas = _ocr_languages()

    writer = PdfWriter()
    textos = []

    for img_bytes in images:
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        if ocr_ativo:
            texto = pytesseract.image_to_string(image, lang=idiomas)
            textos.append(texto.strip())

            # Página de PDF com a imagem + camada de texto OCR pesquisável
            pagina_pdf_bytes = pytesseract.image_to_pdf_or_hocr(
                image, extension="pdf", lang=idiomas
            )
            reader = PdfReader(io.BytesIO(pagina_pdf_bytes))
            writer.add_page(reader.pages[0])
        else:
            # OCR desativado: página só com a imagem, sem passar pelo
            # Tesseract nem criar camada de texto pesquisável.
            buffer = io.BytesIO()
            image.save(buffer, format="PDF")
            buffer.seek(0)
            reader = PdfReader(buffer)
            writer.add_page(reader.pages[0])

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    pdf_filename = f"{filename_prefix}_{timestamp}.pdf"
    pdf_path = os.path.join(PDF_DIR, pdf_filename)

    with open(pdf_path, "wb") as f:
        writer.write(f)

    return {
        "pdf_path": pdf_path,
        "pdf_filename": pdf_filename,
        "extracted_text": "\n\n---\n\n".join(t for t in textos if t),
    }
