from pathlib import Path
import tempfile

from fastapi import FastAPI, UploadFile, File
import uvicorn

from document_processor.processor import process_file

app = FastAPI(title="Document Processor API")


@app.post("/process")
async def process_document(file: UploadFile = File(...)):

    suffix = Path(file.filename).suffix

    with tempfile.NamedTemporaryFile(
        delete=False,
        suffix=suffix
    ) as temp:
        temp.write(await file.read())
        temp_path = temp.name

    try:
        return process_file(
            temp_path,
            id=Path(file.filename).stem
        )

    finally:
        Path(temp_path).unlink(missing_ok=True)

if __name__ == "__main__":
    uvicorn.run(app, host="127.0.0.1", port=8000)