"""
docling_adapter.py
=====================

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
    current_section: List[str],  #a mutable list to hold the current section title
    pages_map: Dict[int, List[Dict[str, Any]]],
) -> None:

    kind, idx = _resolve_ref(node_ref)

    if kind == "groups":
        group = raw_docling_dict.get("groups", [])[idx]
        for child in group.get("children", []):
            _walk_body(child["$ref"], raw_docling_dict, current_section, pages_map)
        return

    if kind == "texts":
        text_item = raw_docling_dict.get("texts", [])[idx]

        #ignore any text that is not part of the body content (like headers, footers, etc.)
        if text_item.get("content_layer") != "body":
            return
        parent_ref = (text_item.get("parent") or {}).get("$ref", "")
        if parent_ref.startswith("#/pictures/"):
            return

        prov = text_item.get("prov", [])
        if not prov:
            return
        page_no = prov[0]["page_no"]

        text_content = text_item.get("text", "")
        if not text_content.strip():
            return

        label = text_item.get("label", "text")

        if label == "section_header":
            # this is a new section header, so we update the current_section
            current_section[0] = text_content
            pages_map.setdefault(page_no, []).append({
                "section_title": text_content,
                "content_type": "text",
                "text": text_content,
                "table": None,
                "bounding_box": None,
            })
            return

        # in any other case, we treat it as a regular text chunk, and we inherit the current section title
        pages_map.setdefault(page_no, []).append({
            "section_title": current_section[0],
            "content_type": "text",
            "text": text_content,
            "table": None,
            "bounding_box": None,
        })
        return

    if kind == "tables":
        table_item = raw_docling_dict.get("tables", [])[idx]
        prov = table_item.get("prov", [])
        if not prov:
            return
        page_no = prov[0]["page_no"]

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

    # ignore any other kinds (like pictures, etc.) that don't have a direct representation in our schema
    # schema only supports text and tables, so we skip other content types for now.


def adapt_docling_output(document_id: str, raw_docling_dict: Dict[str, Any]) -> Dict[str, Any]:

    pages_map: Dict[int, List[Dict[str, Any]]] = {}
    current_section = [DEFAULT_SECTION_TITLE]  # return a mutable list to hold the current section title

    body_children = raw_docling_dict.get("body", {}).get("children", [])
    for child in body_children:
        _walk_body(child["$ref"], raw_docling_dict, current_section, pages_map)

    pages = [
        {"page_number": page_no, "sections": sections}
        for page_no, sections in sorted(pages_map.items())
    ]

    return {
        "document_id": document_id,
        "pages": pages,
    }