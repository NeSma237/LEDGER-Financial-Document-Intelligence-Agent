"""
docling_adapter.py
==================
Converts raw Docling output into the normalized
document structure used by the retrieval pipeline.
"""

from typing import Dict, Any, List


DEFAULT_SECTION_TITLE = "Document"


# =========================================================
# Table Helpers
# =========================================================

def _table_item_to_rows(
    table_item: Dict[str, Any],
) -> List[List[str]]:

    cells = table_item.get("data", {}).get("table_cells", [])
    num_rows = table_item.get("data", {}).get("num_rows", 0)
    num_cols = table_item.get("data", {}).get("num_cols", 0)

    grid: List[List[str]] = [
        ["" for _ in range(num_cols)]
        for _ in range(num_rows)
    ]

    for cell in cells:
        row_idx = cell.get("start_row_offset_idx", 0)
        col_idx = cell.get("start_col_offset_idx", 0)
        text = cell.get("text", "")

        if (
            0 <= row_idx < num_rows
            and 0 <= col_idx < num_cols
        ):
            grid[row_idx][col_idx] = text

    return [
        row
        for row in grid
        if any(cell.strip() for cell in row)
    ]


# =========================================================
# Reference Helper
# =========================================================

def _resolve_ref(ref: str) -> tuple[str, int]:
    parts = ref.strip("#/").split("/")

    kind = parts[0]
    idx = int(parts[1])

    return kind, idx


# =========================================================
# Body Walker
# =========================================================

def _walk_body(
    node_ref: str,
    raw_docling_dict: Dict[str, Any],
    current_section: List[str],
    document_context: List[str],
    pages_map: Dict[int, List[Dict[str, Any]]],
) -> None:

    kind, idx = _resolve_ref(node_ref)

    # -----------------------------------------------------
    # Groups
    # -----------------------------------------------------

    if kind == "groups":

        groups = raw_docling_dict.get("groups", [])

        if idx >= len(groups):
            return

        group = groups[idx]

        for child in group.get("children", []):
            child_ref = child.get("$ref")

            if child_ref:
                _walk_body(
                    child_ref,
                    raw_docling_dict,
                    current_section,
                    document_context,
                    pages_map,
                )

        return

    # -----------------------------------------------------
    # Text
    # -----------------------------------------------------

    if kind == "texts":

        texts = raw_docling_dict.get("texts", [])

        if idx >= len(texts):
            return

        text_item = texts[idx]

        # Only keep body text.
        if text_item.get("content_layer") != "body":
            return

        # Ignore text that belongs to pictures.
        parent_ref = (
            text_item.get("parent") or {}
        ).get("$ref", "")

        if parent_ref.startswith("#/pictures/"):
            return

        text_content = text_item.get("text", "").strip()

        if not text_content:
            return

        prov = text_item.get("prov", [])

        if not prov:
            return

        page_no = prov[0].get("page_no")

        if page_no is None:
            return

        label = text_item.get("label", "text")

        # -------------------------------------------------
        # Section Header
        # -------------------------------------------------

        if label == "section_header":

            # The first section header is usually
            # the company/document name.
            if not document_context[0]:
                document_context[0] = text_content

            current_section[0] = text_content

            pages_map.setdefault(page_no, []).append({
                "section_title": text_content,
                "content_type": "text",
                "text": text_content,
                "table": None,
                "bounding_box": None,
            })

            return

        # -------------------------------------------------
        # Regular Text
        # -------------------------------------------------

        # IMPORTANT:
        # Every normal body text node is preserved here.
        # This includes footnotes such as:
        #
        # "(a) GitHub has been included ... October 25, 2018"
        #

        pages_map.setdefault(page_no, []).append({
            "section_title": current_section[0],
            "content_type": "text",
            "text": text_content,
            "table": None,
            "bounding_box": None,
        })

        return

    # -----------------------------------------------------
    # Tables
    # -----------------------------------------------------

    if kind == "tables":

        tables = raw_docling_dict.get("tables", [])

        if idx >= len(tables):
            return

        table_item = tables[idx]

        prov = table_item.get("prov", [])

        if not prov:
            return

        page_no = prov[0].get("page_no")

        if page_no is None:
            return

        rows = _table_item_to_rows(table_item)

        if not rows:
            return

        table_section_title = current_section[0]

        if (
            document_context[0]
            and document_context[0] != current_section[0]
        ):
            table_section_title = (
                f"{document_context[0]} — "
                f"{current_section[0]}"
            )

        pages_map.setdefault(page_no, []).append({
            "section_title": table_section_title,
            "content_type": "table",
            "text": None,
            "table": {
                "rows": rows
            },
            "bounding_box": None,
        })

        return

    # -----------------------------------------------------
    # Other content types
    # -----------------------------------------------------

    # Pictures and other unsupported Docling nodes
    # are intentionally ignored because our schema
    # currently supports only text and tables.


# =========================================================
# Main Adapter
# =========================================================

def adapt_docling_output(
    document_id: str,
    raw_docling_dict: Dict[str, Any],
) -> Dict[str, Any]:

    pages_map: Dict[
        int,
        List[Dict[str, Any]]
    ] = {}

    current_section = [DEFAULT_SECTION_TITLE]
    document_context = [""]

    body = raw_docling_dict.get("body", {})
    body_children = body.get("children", [])

    for child in body_children:

        child_ref = child.get("$ref")

        if not child_ref:
            continue

        _walk_body(
            child_ref,
            raw_docling_dict,
            current_section,
            document_context,
            pages_map,
        )

    pages = [
        {
            "page_number": page_no,
            "sections": sections,
        }
        for page_no, sections
        in sorted(pages_map.items())
    ]

    return {
        "document_id": document_id,
        "pages": pages,
    }
