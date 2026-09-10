from chunking import chunk_document, table_to_text


def test_table_text_keeps_fiscal_year_attached_to_value():
    text = table_to_text([
        ["Metric", "FY2022", "FY2023"],
        ["Revenue", "$100M", "$125M"],
    ])

    assert "2=FY2022" in text
    assert "3=FY2023" in text
    assert "FY2022 = $100M" in text
    assert "FY2023 = $125M" in text


def test_table_chunking_creates_one_chunk_per_data_row():
    chunks = chunk_document("doc_1", [{
        "page_number": 7,
        "sections": [{
            "section_title": "Income Statement",
            "content_type": "table",
            "table": {
                "rows": [
                    ["Metric", "FY2022", "FY2023"],
                    ["Revenue", "$100M", "$125M"],
                    ["Net income", "$10M", "$15M"],
                ]
            },
        }],
    }])

    assert len(chunks) == 2
    assert chunks[0]["chunk_id"].endswith("_table_r0")
    assert "FY2023 = $125M" in chunks[0]["text"]
    assert "FY2023 = $15M" in chunks[1]["text"]
