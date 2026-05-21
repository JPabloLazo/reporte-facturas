import logging

logger = logging.getLogger(__name__)


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
