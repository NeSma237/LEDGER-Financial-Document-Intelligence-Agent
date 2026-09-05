"""
Adapter module for converting IBM Docling document representation into the
retrieval-api IndexRequest pages format.
"""
from typing import Dict, Any, List, Optional

DEFAULT_SECTION_TITLE = "Document"


def _table_item_to_rows(table_item: Dict[str, Any]) -> List[List[str]]:
    cells = table_item.get("data", {}).get("table_cells", [])
    num_rows = table_item.get("data", {}).get("num_rows", 0)
    num_cols = table_item.get("data", {}).get("num_cols", 0)

    grid: List[List[str]] = [["" for _ in range(num_cols)] for _ in range(num_rows)]

    for cell in cells:
        row_idx = cell.get("start_row_offset_idx", 0)
        col_idx = cell.get("start_col_offset_idx", 0)
        text = cell.get("text", "")
        if 0 <= row_idx < num_rows and 0 <= col_idx < num_cols:
            grid[row_idx][col_idx] = text

    return [row for row in grid if any(cell.strip() for cell in row)]


def _resolve_ref(ref: str) -> tuple[str, int]:
    parts = ref.strip("#/").split("/")
    kind = parts[0]
    idx = int(parts[1])
    return kind, idx


def _walk_body(
    node_ref: str,
    raw_docling_dict: Dict[str, Any],
    current_section: List[str],
    pages_map: Dict[int, List[Dict[str, Any]]],
) -> None:
    try:
        kind, idx = _resolve_ref(node_ref)
    except Exception:
        return

    if kind == "groups":
        groups = raw_docling_dict.get("groups", [])
        if idx < len(groups):
            group = groups[idx]
            for child in group.get("children", []):
                ref = child.get("$ref")
                if ref:
                    _walk_body(ref, raw_docling_dict, current_section, pages_map)
        return

    if kind == "texts":
        texts = raw_docling_dict.get("texts", [])
        if idx >= len(texts):
            return
        text_item = texts[idx]

        if text_item.get("content_layer") != "body":
            return
        parent_ref = (text_item.get("parent") or {}).get("$ref", "")
        if parent_ref.startswith("#/pictures/"):
            return

        prov = text_item.get("prov", [])
        if not prov:
            return
        page_no = prov[0].get("page_no", 1)

        text_content = text_item.get("text", "")
        if not text_content.strip():
            return

        label = text_item.get("label", "text")

        if label == "section_header":
            current_section[0] = text_content
            pages_map.setdefault(page_no, []).append({
                "section_title": text_content,
                "content_type": "text",
                "text": text_content,
                "table": None,
                "bounding_box": None,
            })
            return

        pages_map.setdefault(page_no, []).append({
            "section_title": current_section[0],
            "content_type": "text",
            "text": text_content,
            "table": None,
            "bounding_box": None,
        })
        return

    if kind == "tables":
        tables = raw_docling_dict.get("tables", [])
        if idx >= len(tables):
            return
        table_item = tables[idx]
        prov = table_item.get("prov", [])
        if not prov:
            return
        page_no = prov[0].get("page_no", 1)

        rows = _table_item_to_rows(table_item)
        if not rows:
            return

        pages_map.setdefault(page_no, []).append({
            "section_title": current_section[0],
            "content_type": "table",
            "text": None,
            "table": {"rows": rows},
            "bounding_box": None,
        })
        return


def adapt_docling_output(document_id: str, raw_docling_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    Transforms raw Docling dict export into retrieval-api IndexRequest format:
    {"document_id": document_id, "pages": [{"page_number": int, "sections": [...]}]}
    """
    if not isinstance(raw_docling_dict, dict):
        return {"document_id": document_id, "pages": []}

    # If it already contains formatted pages, return directly
    if "pages" in raw_docling_dict and isinstance(raw_docling_dict["pages"], list) and raw_docling_dict["pages"]:
        return {
            "document_id": document_id,
            "pages": raw_docling_dict["pages"]
        }

    pages_map: Dict[int, List[Dict[str, Any]]] = {}
    current_section = [DEFAULT_SECTION_TITLE]

    body_children = raw_docling_dict.get("body", {}).get("children", [])
    for child in body_children:
        ref = child.get("$ref")
        if ref:
            _walk_body(ref, raw_docling_dict, current_section, pages_map)

    pages = [
        {"page_number": page_no, "sections": sections}
        for page_no, sections in sorted(pages_map.items())
    ]

    return {
        "document_id": document_id,
        "pages": pages,
    }
