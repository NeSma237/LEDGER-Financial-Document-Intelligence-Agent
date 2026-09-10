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