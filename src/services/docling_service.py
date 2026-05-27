from docling.document_converter import DocumentConverter
import tempfile
import os

class DoclingService:
    def __init__(self):
        self.converter = DocumentConverter()

    def convert_document(self, file_bytes: bytes, filename: str) -> str:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            result = self.converter.convert(tmp_path)
            text = result.document.export_to_markdown()
            return text
        finally:
            os.unlink(tmp_path)