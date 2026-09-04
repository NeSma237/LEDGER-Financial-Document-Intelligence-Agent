"""
sample_data.py
================
"""

DOCUMENT_1 = {
    "document_id": "doc_017",
    "pages": [
        {
            "page_number": 1,
            "sections": [
                {
                    "section_title": "Income Statement",
                    "content_type": "table",
                    "text": None,
                    "table": {
                        "rows": [
                            ["Revenue", "$142.5M"],
                            ["Operating Income", "$38.2M"],
                            ["Net Income", "$29.1M"],
                        ]
                    },
                    "bounding_box": None,
                },
                {
                    "section_title": "Management Discussion",
                    "content_type": "text",
                    "text": (
                        "The company reported strong revenue growth in fiscal year 2020, "
                        "driven primarily by increased demand in the logistics segment. "
                        "Operating income rose by 13.4% compared to the previous year, "
                        "reflecting improved cost efficiency across all business units."
                    ),
                    "table": None,
                    "bounding_box": None,
                },
            ],
        },
        {
            "page_number": 2,
            "sections": [
                {
                    "section_title": "Operating Expenses",
                    "content_type": "table",
                    "text": None,
                    "table": {
                        "rows": [
                            ["Marketing", "$12.3M"],
                            ["R&D", "$18.7M"],
                            ["Logistics", "$9.4M"],
                        ]
                    },
                    "bounding_box": None,
                },
            ],
        },
    ],
}

DOCUMENT_2 = {
    "document_id": "doc_022",
    "pages": [
        {
            "page_number": 1,
            "sections": [
                {
                    "section_title": "Inventory Summary",
                    "content_type": "table",
                    "text": None,
                    "table": {
                        "rows": [
                            ["Finished Goods", "$21.6M"],
                            ["Raw Materials", "$8.9M"],
                            ["Work In Progress", "$4.2M"],
                        ]
                    },
                    "bounding_box": None,
                },
                {
                    "section_title": "Notes",
                    "content_type": "text",
                    "text": (
                        "Finished goods balance increased slightly in 2019 due to "
                        "seasonal stocking ahead of the fourth quarter. The company "
                        "does not expect material write-downs in the coming period."
                    ),
                    "table": None,
                    "bounding_box": None,
                },
            ],
        },
    ],
}

ALL_DOCUMENTS = [DOCUMENT_1, DOCUMENT_2]

# sample queries for testing the retrieval endpoints
TEST_QUERIES = {
    "search_documents": "What was the operating income in 2020?",
    "search_tables": "finished goods balance 2019",
    "filter_documents": {"document_id": "doc_017", "page": 2},
}
