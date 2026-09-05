from pathlib import Path
import re
import mimetypes
import requests
import subprocess
import sys
import time
import json

# Paths

BASE_DIR = Path(__file__).resolve().parent

INPUT_FOLDER = BASE_DIR / "input_data_new"
OUTPUT_FOLDER = BASE_DIR / "JSON_data"

API_URL = "http://127.0.0.1:8000/process"
HEALTH_URL = "http://127.0.0.1:8000/docs"

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# Start API

def start_api():
    print("\nStarting FastAPI...")

    server = subprocess.Popen(
    [sys.executable, "-m", "document_processor.doc_processor_api"],
    cwd=BASE_DIR.parent
     )

    # Wait until API is actually ready
    for _ in range(30):
        try:
            requests.get(HEALTH_URL, timeout=1)
            print("API is ready.\n")
            return server

        except requests.RequestException:
            time.sleep(1)

    print("API failed to start.")
    server.terminate()
    return None


# Start API
server = start_api()

if server is None:
    print("Could not start API. Exiting.")
    sys.exit(1)


pdf_files = list(INPUT_FOLDER.rglob("*.pdf"))
pdf_stems = {p.stem for p in pdf_files}

image_extensions = ["*.png", "*.jpg", "*.jpeg"]
image_files = []
for ext in image_extensions:
    image_files.extend(INPUT_FOLDER.rglob(ext))

standalone_images = []
for img in image_files:
    base_id = re.sub(r"_\d+$", "", img.stem)  
    if base_id not in pdf_stems:
        standalone_images.append(img)

files_to_process = pdf_files + standalone_images

print(
    f"Found {len(pdf_files)} PDF files and {len(standalone_images)} "
    f"standalone image files (images with a matching PDF were skipped as duplicates).\n"
)

# Process files

for i, file_path in enumerate(files_to_process, start=1):

    output_path = OUTPUT_FOLDER / f"{file_path.stem}.json"

    # Already processed
    if output_path.exists():
        print(f"[{i}/{len(files_to_process)}] Skipping: {file_path.name}")
        continue

    print(f"[{i}/{len(files_to_process)}] Processing: {file_path.name}")

    success = False

    # نحدد الـ mime type الصح حسب امتداد الملف نفسه (PDF أو صورة)
    mime_type, _ = mimetypes.guess_type(file_path.name)
    if mime_type is None:
        mime_type = "application/octet-stream"

    # Try the file up to 3 times
    for attempt in range(1, 4):

        try:

            # Check if API is alive
            requests.get(HEALTH_URL, timeout=2)

            with open(file_path, "rb") as file:

                response = requests.post(
                    API_URL,
                    files={
                        "file": (
                            file_path.name,
                            file,
                            mime_type
                        )
                    },
                    timeout=600
                )

            response.raise_for_status()

            result = response.json()

            # Save JSON
            with open(
                output_path,
                "w",
                encoding="utf-8"
            ) as json_file:

                json.dump(
                    result,
                    json_file,
                    ensure_ascii=False,
                    indent=2
                )

            print(f"  Saved: {output_path.name}\n")

            success = True
            break

        except requests.RequestException as e:

            print(
                f"   API connection failed "
                f"(attempt {attempt}/3)"
            )

            # Stop old server if it crashed
            if server.poll() is not None:
                print("   API stopped. Restarting...")

            else:
                server.terminate()
                time.sleep(2)

            # Restart API
            server = start_api()

            if server is None:
                print("   Could not restart API.")
                time.sleep(5)

    if not success:
        print(f" Failed permanently: {file_path.name}\n")

print("Batch processing finished.")

server.terminate()