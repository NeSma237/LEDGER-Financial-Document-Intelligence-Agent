from typing import List, Dict, Any

MAX_CHARS_PER_TEXT_CHUNK = 800


def table_to_text(table_rows: List[List[str]]) -> str:
    lines = []
    for row in table_rows:
        if len(row) >= 2:
            lines.append(f"{row[0]}: {row[1]}")
        else:
            lines.append(" | ".join(row))
    return " | ".join(lines)

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
                text = table_to_text(section["table"]["rows"])
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
                pieces = split_long_text(section["text"])
                for piece_idx, piece in enumerate(pieces):
                    chunk_id = f"{document_id}_p{page_number}_s{section_idx}_t{piece_idx}"
                    chunks.append({
                        "chunk_id": chunk_id,
                        "document_id": document_id,
                        "page": page_number,
                        "section": section_title,
                        "content_type": "text",
                        "text": piece,
                    })

    return chunks