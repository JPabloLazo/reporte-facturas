import logging
import os

logger = logging.getLogger(__name__)


IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}


class MarkitdownExtractor:
    @staticmethod
    def convert_to_markdown(file_path: str) -> str:
        try:
            from markitdown import MarkItDown
            md = MarkItDown()
            result = md.convert(file_path)
            return result.text_content
        except Exception:
            logger.warning("Markitdown falló al procesar %s", file_path, exc_info=True)
            return ""

    @staticmethod
    def convert_with_fallback(file_path: str) -> tuple[str, str]:
        ext = os.path.splitext(file_path)[1].lower()
        if ext in IMAGE_EXTENSIONS:
            return ("", "vision")
        if ext == ".pdf":
            texto = MarkitdownExtractor.convert_to_markdown(file_path)
            if len(texto) >= 50:
                return (texto, "markitdown")
            return ("", "vision_fallback")
        texto = MarkitdownExtractor.convert_to_markdown(file_path)
        return (texto, "markitdown")
