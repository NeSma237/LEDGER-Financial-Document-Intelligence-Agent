"""
Chunking Logic
==============
    chunk_id, document_id, page, section, content_type, text
"""
import re
from typing import List, Dict, Any, Sequence

MAX_CHARS_PER_TEXT_CHUNK = 800  # approx. 1-2 paragraphs, or ~150 words, or ~800 characters. This is a good size for semantic search embeddings.


YEAR_PATTERN = re.compile(r"\b(?:fy\s*)?(?:19|20)\d{2}\b", re.IGNORECASE)
HEADER_WORDS = re.compile(
    r"\b(?:year|period|fiscal|quarter|months?|ended|date)\b",
    re.IGNORECASE,
)


def _clean_row(row: Sequence[Any]) -> List[str]:
    return [str(cell).strip() for cell in row]


def _is_header_row(row: Sequence[str]) -> bool:
    text = " ".join(row)
    return bool(YEAR_PATTERN.search(text) or HEADER_WORDS.search(text))


def _table_header_rows(table_rows: List[List[str]]) -> int:
    """Return the number of leading rows that describe table columns.

    Financial tables commonly use one row for labels and a second row for
    fiscal years. Keeping both rows with every data row prevents values from
    becoming detached from their year during retrieval.
    """
    if not table_rows:
        return 0

    header_count = 1
    while (
        header_count < len(table_rows)
        and _is_header_row(table_rows[header_count])
    ):
        header_count += 1
    return header_count


def _column_headers(header_rows: List[List[str]], width: int) -> List[str]:
    headers: List[str] = []
    for column_idx in range(width):
        parts: List[str] = []
        for row in header_rows:
            value = row[column_idx] if column_idx < len(row) else ""
            if value and value not in parts:
                parts.append(value)
        headers.append(" / ".join(parts) or f"Column {column_idx + 1}")
    return headers


def _table_row_to_text(
    row: List[str],
    headers: List[str],
    header_context: str,
) -> str:
    label = row[0] if row else ""
    values = []
    for column_idx, value in enumerate(row[1:], start=1):
        if not value:
            continue
        column = headers[column_idx] if column_idx < len(headers) else f"Column {column_idx + 1}"
        values.append(f"{column} = {value}")

    row_text = label
    if values:
        row_text = f"{label}: " + "; ".join(values)
    return f"{header_context}. Row: {row_text}" if header_context else row_text


def table_to_text(table_rows: List[List[str]]) -> str:
    """Serialize a table while preserving the relationship between headers and values."""
    normalized = [_clean_row(row) for row in table_rows if row and any(str(cell).strip() for cell in row)]
    if not normalized:
        return ""

    header_count = _table_header_rows(normalized)
    header_rows = normalized[:header_count]
    width = max(len(row) for row in normalized)
    headers = _column_headers(header_rows, width)
    header_context = "Table columns: " + "; ".join(
        f"{idx + 1}={header}" for idx, header in enumerate(headers)
    )

    data_rows = normalized[header_count:] or normalized
    return " | ".join(
        _table_row_to_text(row, headers, header_context)
        for row in data_rows
    )


def with_section_context(section_title: str, piece: str) -> str:

    if not section_title or piece.strip() == section_title.strip():
        return piece
    return f"{section_title} — {piece}"


def split_long_text(text: str, max_chars: int = MAX_CHARS_PER_TEXT_CHUNK) -> List[str]:

    if len(text) <= max_chars:
        return [text]

    sentences = text.replace("\n", " ").split(". ")
    chunks: List[str] = []
    current = ""
    for sentence in sentences:
        candidate = f"{current}. {sentence}" if current else sentence
        if len(candidate) > max_chars and current:
            chunks.append(current.strip())
            current = sentence
        else:
            current = candidate
    if current:
        chunks.append(current.strip())
    return chunks if chunks else [text]


def chunk_document(document_id: str, pages: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    chunks: List[Dict[str, Any]] = []

    for page in pages:
        page_number = page["page_number"]

        # Keep useful page-level context such as the company name.
        page_context = ""

        for section_idx, section in enumerate(page.get("sections", [])):
            section_title = section.get("section_title") or f"section_{section_idx}"
            content_type = section["content_type"]

            # Capture short text sections that can identify the document/company.
            if content_type == "text" and section.get("text"):
                section_text = section["text"].strip()

                if (
                    section_idx == 0
                    and section_text
                    and len(section_text) <= 200
                ):
                    page_context = section_text

            if content_type == "table" and section.get("table"):
                rows = [
                    _clean_row(row)
                    for row in section["table"]["rows"]
                    if row and any(str(cell).strip() for cell in row)
                ]

                if not rows:
                    continue

                table_text = table_to_text(rows)

                # Add the page/company context to the table chunk.
                if page_context and not section_title.startswith(page_context):
                    text = f"{page_context} — {with_section_context(section_title, table_text)}"
                else:
                    text = with_section_context(section_title, table_text)
                chunk_id = f"{document_id}_p{page_number}_s{section_idx}_table"

                chunks.append({
                    "chunk_id": chunk_id,
                    "document_id": document_id,
                    "page": page_number,
                    "section": section_title,
                    "content_type": "table",
                    "text": text,
                })

            elif content_type == "text" and section.get("text"):
                # The text can be split if it's long,
                # but each part will inherit the same section metadata.
                pieces = split_long_text(section["text"])

                for piece_idx, piece in enumerate(pieces):
                    text = with_section_context(section_title, piece)

                    chunk_id = f"{document_id}_p{page_number}_s{section_idx}_t{piece_idx}"

                    chunks.append({
                        "chunk_id": chunk_id,
                        "document_id": document_id,
                        "page": page_number,
                        "section": section_title,
                        "content_type": "text",
                        "text": text,
                    })

    return chunks