"""
Chunking Logic
==============
    chunk_id, document_id, page, section, content_type, text
"""
from typing import List, Dict, Any

MAX_CHARS_PER_TEXT_CHUNK = 800  # approx. 1-2 paragraphs, or ~150 words, or ~800 characters. This is a good size for semantic search embeddings.


def table_to_text(table_rows: List[List[str]]) -> str:

    lines = []
    for row in table_rows:
        if len(row) >= 2:
            lines.append(f"{row[0]}: {row[1]}")
        else:
            lines.append(" | ".join(row))
    return " | ".join(lines)


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
        for section_idx, section in enumerate(page.get("sections", [])):
            section_title = section.get("section_title") or f"section_{section_idx}"
            content_type = section["content_type"]

            if content_type == "table" and section.get("table"):
                # the table is treated as a single chunk, but we convert it to text for embedding purposes
                raw_text = table_to_text(section["table"]["rows"])
                text = with_section_context(section_title, raw_text)
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
                # the text can be split if it's long, but each part will inherit the same section metadata
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