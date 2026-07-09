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

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PDF_DIR = os.path.join(BASE_DIR, "PDF")
os.makedirs(PDF_DIR, exist_ok=True)

# No Windows, se o tesseract.exe não estiver no PATH, define o caminho
# completo através da variável de ambiente TESSERACT_CMD (ver .env.example).
_tesseract_cmd = os.getenv("TESSERACT_CMD")
if _tesseract_cmd:
    pytesseract.pytesseract.tesseract_cmd = _tesseract_cmd

OCR_LANGUAGES = os.getenv("OCR_LANGUAGES", "por+eng")


def images_to_searchable_pdf(images: list[bytes], filename_prefix: str = "anexos") -> dict:
    """
    images: lista de imagens em bytes (jpg/png/etc.)

    Faz OCR a cada imagem, cria uma página de PDF pesquisável por imagem
    (imagem visível + texto OCR invisível por cima) e junta tudo num único
    ficheiro PDF guardado em PDF/.

    Devolve:
        {
            "pdf_path": caminho absoluto do PDF gerado,
            "pdf_filename": nome do ficheiro,
            "extracted_text": todo o texto OCR concatenado,
        }
    """
    if not images:
        raise ValueError("Nenhuma imagem fornecida para processar.")

    writer = PdfWriter()
    textos = []

    for img_bytes in images:
        image = Image.open(io.BytesIO(img_bytes)).convert("RGB")

        texto = pytesseract.image_to_string(image, lang=OCR_LANGUAGES)
        textos.append(texto.strip())

        # Página de PDF com a imagem + camada de texto OCR pesquisável
        pagina_pdf_bytes = pytesseract.image_to_pdf_or_hocr(
            image, extension="pdf", lang=OCR_LANGUAGES
        )
        reader = PdfReader(io.BytesIO(pagina_pdf_bytes))
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
