from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions, TableFormerMode,RapidOcrOptions
from docling.document_converter import DocumentConverter,PdfFormatOption,ImageFormatOption
import json
from pathlib import Path

def process_file(input_path, id=None):
    file_path = Path(input_path)

    ocr_options = RapidOcrOptions(force_full_page_ocr=True)

    # Enable OCR
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = True
    pipeline_options.ocr_options = ocr_options
    pipeline_options.do_table_structure = True

    # Use ACCURATE mode for TableFormer if default structure recovery misses cells
    pipeline_options.table_structure_options.mode = TableFormerMode.ACCURATE

    # Converter
    converter = DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(pipeline_options=pipeline_options),
            InputFormat.IMAGE: ImageFormatOption(pipeline_options=pipeline_options)
        }
    )

    # Process PDF/img
    result = converter.convert(file_path)
    document = result.document
    
    return {
    "document_id": id or file_path.stem,
    "markdown_content": document.export_to_markdown(),
    "raw_docling_dict": document.export_to_dict()
}


