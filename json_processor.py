import json
from pathlib import Path

file_paths = ["C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\4d41ea7a63b2d9b5cc3cb24ca6c7e9ac.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\0cf6769516cf2a245aaed5fcf2bd9c21.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\0ba33bc0610e557810de948f4248719e.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\0e2b9dbc14940f49d225762ca8970f03.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\1ab00922b8ffb4c7d4ae5dea80f45637.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\1ac0f01d143b3789807888da03560a51.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\1b54b462b06a8786c7b0b63587f93122.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\1bc7c4c0b8933692dec5dbad014984d5.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\1c5aaf3f3c28e0d325567ae8c3f7b230.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\01cbb28d73f2117a2bf155814a46806c.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\1dcc49e0d122ddd39f5df46093f57e4d.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\1df5c844392a7823c038c5b8f0cec73d.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\1f5c09a7575587beff235fac23ebb8df.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\1f796e0f4ee185b27fd21159bc6a1924.json",
              "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\2b9d89e7dacd3fe91ff1114d740c3353.json"]              
processed_documents = []

for path in file_paths:  
    file_path = Path(path)

    with open(file_path, 'r') as f:
        data = json.load(f)

# pages(list if more than one) -> blocks(list of blocks) -> words(dict of word_list) -> word_list

    for page_idx, page in enumerate(data.get("pages") or []):
            blocks_text = [
                block.get("text", "")
                for block in (page.get("blocks") or [])
                if block.get("text")
            ]

            # Append each page entry to your main list
            processed_documents.append({
                "document_id": file_path.stem,  # Uses the file name without .json
                "page": page_idx,
                "section": "Default",
                "content": "\n".join(blocks_text),
                "content_type": "text"
                # "score": 1
            })

print(len(processed_documents))
test_json = json.dumps(processed_documents, indent=2)
with open("test_json.json", "w") as f:
     f.write(test_json)
# print(test_json)



# use this when you want a single file for single test
def signle_file_json_maker(path):
    list = [] # the other code works on a list
    file_path = Path(path)
    with open(file_path, 'r') as f:
        data = json.load(f)

    blocks_text = [
    block.get("text", "")
    for page in (data.get("pages") or [])
    for block in (page.get("blocks") or [])
    if block.get("text")
    ]

    # Construct the Python dictionary
    dict_data = {
        "document_id": file_path.stem,
        "page": 0,
        "section": "Default",
        "content": "\n".join(blocks_text),  # Joining by newline keeps text blocks separated
        "score": 1
    }
    list.append(dict_data)

    # Convert dictionary to a formatted JSON string
    test_json_single_file = json.dumps(list, indent=2)
    with open("test_json_single_file.json", "w") as f:
        f.write(test_json_single_file) 

single_file_path = "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev\\4d41ea7a63b2d9b5cc3cb24ca6c7e9ac.json"
# signle_file_json_maker(single_file_path)

# run this for bulk processing with your path
def bulk_processor(path):
    docs_dir = Path(path)

    output_dir = docs_dir.parent.parent / "processed_json_docs_whole"
    output_dir.mkdir(parents=True, exist_ok=True)

    for file_path in docs_dir.glob("*.json"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        file_pages = []

        for page_idx, page in enumerate(data.get("pages") or []):
            blocks_text = [
                block.get("text", "")
                for block in (page.get("blocks") or [])
                if block.get("text")
            ]

            # Suffix document_id with page index so it is unique per chunk
            chunk_id = f"{file_path.stem}_p{page_idx}"

            file_pages.append({
                "document_id": chunk_id,  # Now identical to id
                "page": page_idx,
                "section": "Default",
                "content": "\n".join(blocks_text),
                "content_type": "text"
            })

        out_file_path = output_dir / f"{file_path.stem}.json"
        with open(out_file_path, "w", encoding="utf-8") as f:
            json.dump(file_pages, f, indent=2)

bulk_processor_path = "C:\\Users\\Lenovo\\Desktop\\MIA\\doc_intel\\tatdqa_docs_dev\\dev"
# bulk_processor(bulk_processor_path)



# =============================================================================================== for docling


def transform_docling_to_target(docling_json_path: dict, score: float = 1.0) -> list[dict]:
    with open(docling_json_path, "r", encoding="utf-8") as f:
        docling_data = json.load(f)

    doc_id = docling_data.get("document_id", "")
    
    # 1. Extract main text content
    content = docling_data.get("markdown_content")
    
    if not content and "raw_docling_dict" in docling_data:
        # Fallback: aggregate text items if markdown_content is missing
        texts = docling_data["raw_docling_dict"].get("texts", [])
        content = " ".join(t.get("text", "") for t in texts if t.get("text"))
    
    # 2. Extract page number (0-indexed default)
    page = 0
    raw_dict = docling_data.get("raw_docling_dict", {})
    texts = raw_dict.get("texts", [])
    
    if texts and "prov" in texts[0] and texts[0]["prov"]:
        # Docling page numbers are usually 1-based; convert to 0-based
        raw_page = texts[0]["prov"][0].get("page_no", 1)
        page = max(0, raw_page - 1)

    result = [
            {
                "document_id": doc_id,
                "page": page,
                "section": "Default",
                "content": content or "",
                "score": score
            }
        ]
    
    json_docling_test = json.dumps(result, indent=2)
    with open("json_docling_test.json", "w") as f:
        f.write(json_docling_test) 


# uncomment to run the single docling function
docling_json_path = r"C:\Users\Lenovo\Desktop\MIA\Ledger\document_processor\JSON_data_duplicates\cced1c9e0cece04d1cd72d197d650906.json"
result = transform_docling_to_target(docling_json_path, score=4)


from pathlib import Path
import json

def bulk_docling_processor(path):
    docs_dir = Path(path)
    
    # Target directory for transformed JSON files
    output_dir = docs_dir.parent.parent.parent / "doc_intel" / "docling_processed_json"
    output_dir.mkdir(parents=True, exist_ok=True)

    for file_path in docs_dir.glob("*.json"):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)

        # Fallback to filename if document_id key is missing/empty
        doc_id = data.get("document_id") or file_path.stem
            
        # 1. Extract main text content
        content = data.get("markdown_content")
        
        raw_dict = data.get("raw_docling_dict", {})
        texts = raw_dict.get("texts", [])

        if not content:
            # Fallback: aggregate text items if markdown_content is missing
            content = " ".join(t.get("text", "") for t in texts if t.get("text"))
        
        # 2. Extract page number safely from the first item with valid provenance
        page = 0
        for item in texts:
            prov = item.get("prov", [])
            if prov and isinstance(prov, list) and "page_no" in prov[0]:
                raw_page = prov[0].get("page_no", 1)
                page = max(0, raw_page - 1)
                break
    
        result = [
            {
                "document_id": doc_id,
                "page": page,
                "section": "Default",
                "content": content or "",
                "content_type": "text"
            }
        ]
        
        # Save each input file to its own output file inside output_dir
        output_file_path = output_dir / f"{file_path.stem}.json"
        with open(output_file_path, "w", encoding="utf-8") as f:
            json.dump(result, f, indent=2, ensure_ascii=False)

docling_set_json_path = r"C:\Users\Lenovo\Desktop\MIA\Ledger\document_processor\JSON_data"
# bulk_docling_processor(docling_json_path)