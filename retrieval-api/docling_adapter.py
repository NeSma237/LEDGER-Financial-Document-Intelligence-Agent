"""
docling_adapter.py
=====================
بتحول الـ DoclingDocument (اللي doc-processor-api بيرجعه عن طريق
`raw_docling_dict`) لنفس الشكل بالظبط اللي schemas.py بتاعتنا
(IndexRequest) متوقعاه: document_id + pages[] + sections[].

ليه محتاجينها؟
---------------
doc-processor-api عند زميلنا بيستخدم مكتبة Docling، وبيرجع شكل مختلف
تمامًا (markdown_content + raw_docling_dict) عن الـ schema المتفق
عليه في docs/api-contracts.md. بدل ما نطلب منه يغيّر كوده (وقت
مش موجود قبل الديدلاين)، بنعمل "طبقة تحويل" هنا في retrieval-api
بس، فمفيش حاجة تتغير في doc-processor-api.

طريقة الاستخدام
-----------------
1. لما توصل النتيجة من doc-processor-api (JSON فيه raw_docling_dict)
2. نستدعي adapt_docling_output(document_id, raw_docling_dict)
3. اللي بيرجع بقى نفس شكل IndexRequest بالظبط، وتقدري تبعتيه على
   طول لـ chunk_document()
"""
from typing import Dict, Any, List


def _table_item_to_rows(table_item: Dict[str, Any]) -> List[List[str]]:
    """
    بتحول جدول واحد من raw_docling_dict لشكل rows بسيط
    (ليستة من ليستات نصوص)، باستخدام table_cells مباشرة
    (كل خلية فيها text + start_row_offset_idx + start_col_offset_idx).
    """
    cells = table_item.get("data", {}).get("table_cells", [])
    num_rows = table_item.get("data", {}).get("num_rows", 0)
    num_cols = table_item.get("data", {}).get("num_cols", 0)

    # نبني grid فاضي الأول
    grid: List[List[str]] = [["" for _ in range(num_cols)] for _ in range(num_rows)]

    for cell in cells:
        row_idx = cell.get("start_row_offset_idx", 0)
        col_idx = cell.get("start_col_offset_idx", 0)
        text = cell.get("text", "")
        if 0 <= row_idx < num_rows and 0 <= col_idx < num_cols:
            grid[row_idx][col_idx] = text

    # نشيل أي صفوف فاضية تمامًا (ممكن تحصل مع بعض الجداول المعقدة)
    return [row for row in grid if any(cell.strip() for cell in row)]


def adapt_docling_output(document_id: str, raw_docling_dict: Dict[str, Any]) -> Dict[str, Any]:
    """
    بتاخد raw_docling_dict كامل، وترجع IndexRequest-shaped dict:
        { "document_id": ..., "pages": [ { "page_number": ..., "sections": [...] } ] }

    بتلف على texts[] و tables[] مع بعض، وبتحدد كل عنصر ينتمي لأنهي
    صفحة عن طريق prov[0]["page_no"].
    """
    pages_map: Dict[int, List[Dict[str, Any]]] = {}

    # 1. النصوص (كل عنصر في texts[] بيبقى section من نوع "text")
    for text_item in raw_docling_dict.get("texts", []):
        # نتجاهل أي حاجة "furniture" — دي رأس/تذييل الصفحة، أرقام الصفحات،
        # أو نصوص متكررة (زي اللوجو) مش جزء حقيقي من محتوى المستند
        if text_item.get("content_layer") != "body":
            continue

        # نتجاهل أي نص جوّه صورة/لوجو (parent بيشاور على #/pictures/...)
        parent = text_item.get("parent") or {}
        parent_ref = parent.get("$ref", "")
        if parent_ref.startswith("#/pictures/"):
            continue

        prov = text_item.get("prov", [])
        if not prov:
            continue  # عنصر من غير رقم صفحة، نتجاهله
        page_no = prov[0]["page_no"]

        section_title = text_item.get("label", "text").replace("_", " ").title()
        text_content = text_item.get("text", "")
        if not text_content.strip():
            continue

        pages_map.setdefault(page_no, []).append({
            "section_title": section_title,
            "content_type": "text",
            "text": text_content,
            "table": None,
            "bounding_box": None,
        })

    # 2. الجداول (كل عنصر في tables[] بيبقى section من نوع "table")
    for table_item in raw_docling_dict.get("tables", []):
        prov = table_item.get("prov", [])
        if not prov:
            continue
        page_no = prov[0]["page_no"]

        rows = _table_item_to_rows(table_item)
        if not rows:
            continue

        pages_map.setdefault(page_no, []).append({
            "section_title": "Table",
            "content_type": "table",
            "text": None,
            "table": {"rows": rows},
            "bounding_box": None,
        })

    # 3. نبني ليستة pages[] مرتبة برقم الصفحة
    pages = [
        {"page_number": page_no, "sections": sections}
        for page_no, sections in sorted(pages_map.items())
    ]

    return {
        "document_id": document_id,
        "pages": pages,
    }