from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption
import tempfile
import os
import torch

class DoclingService:
    def __init__(self):
        pipeline_options = PdfPipelineOptions()
        pipeline_options.accelerator_options.device = "cuda"
        self.converter = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
                InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options),
            }
        )

    def convert_document(self, file_bytes: bytes, filename: str) -> str:
        ext = os.path.splitext(filename)[1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tmp:
            tmp.write(file_bytes)
            tmp_path = tmp.name

        try:
            result = self.converter.convert(tmp_path)
            text = result.document.export_to_markdown()
            return text
        finally:
            os.unlink(tmp_path)