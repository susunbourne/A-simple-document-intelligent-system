from docling.datamodel.base_models import InputFormat, DocumentStream
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.document_converter import DocumentConverter, PdfFormatOption
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.document_converter import WordFormatOption
import logging
import torch
from io import BytesIO

from src.core.logging import log_event, privacy_safe_file_id


logger = logging.getLogger(__name__)


class DoclingService:
    def __init__(self):
        # pdf_pipeline_options = PdfPipelineOptions()
        # pdf_pipeline_options.do_ocr = False
        # pdf_pipeline_options.do_table_structure = True
        # pdf_pipeline_options.accelerator_options = AcceleratorOptions(
        #     device=AcceleratorDevice.AUTO,
        # )

        ocr_pipeline_options = PdfPipelineOptions()
        ocr_pipeline_options.queue_max_size = 1
        ocr_pipeline_options.do_ocr = False
        ocr_pipeline_options.do_table_structure = True
        ocr_pipeline_options.accelerator_options = AcceleratorOptions(
            device=AcceleratorDevice.AUTO,
            num_threads=1
        )
        #ocr_pipeline_options.layout_batch_size = 1


        # self.converter_digital = DocumentConverter(
        #     format_options={
        #         InputFormat.PDF: PdfFormatOption(
        #             pipeline_options=pdf_pipeline_options,
        #             backend=PyPdfiumDocumentBackend
        #         ),
        #         InputFormat.DOCX: WordFormatOption(
        #             pipeline_cls=SimplePipeline
        #         ),
        #     }
        # )
        self.converter_scanned = DocumentConverter(
            format_options={
                InputFormat.PDF: PdfFormatOption(
                    pipeline_options=ocr_pipeline_options
                ),
                InputFormat.DOCX: WordFormatOption(
                    pipeline_cls=SimplePipeline
                )
            }
        )

    def convert_document(self, file_bytes: bytes, filename: str, request_id: str | None = None) -> str:
        buf = BytesIO(file_bytes)
        source = DocumentStream(name=filename, stream=buf)
        result = self.converter_scanned.convert(source)
        markdown = result.document.export_to_markdown()
        log_event(
            logger,
            "document_parsed",
            request_id=request_id,
            file_id=privacy_safe_file_id(filename),
            extracted_chars=len(markdown),
        )
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return markdown
