from docling.datamodel.base_models import InputFormat, DocumentStream
from docling.datamodel.pipeline_options import LayoutOptions, PdfPipelineOptions
from docling.pipeline.simple_pipeline import SimplePipeline
from docling.document_converter import DocumentConverter, ImageFormatOption, PdfFormatOption
from docling.datamodel.accelerator_options import AcceleratorDevice, AcceleratorOptions
from docling.document_converter import DocumentConverter, PdfFormatOption, WordFormatOption
from docling.backend.pypdfium2_backend import PyPdfiumDocumentBackend
import tempfile
import os
import torch
from io import BytesIO


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
            device=AcceleratorDevice.AUTO
        )
        #ocr_pipeline_options.layout_batch_size = 0.5


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

    def convert_document(self, file_bytes: bytes, filename: str) -> str:
        buf = BytesIO(file_bytes)
        source = DocumentStream(name=filename, stream=buf)
        result = self.converter_scanned.convert(source)
        markdown = result.document.export_to_markdown()
        print("======This is the markdown output======")
        print(markdown)
        print("======================================")
        with open("output.md", "w", encoding = "utf-8") as f:
            f.write(markdown)
        if torch.cuda.is_available():
            torch.cuda.empty_cache()

        return markdown
