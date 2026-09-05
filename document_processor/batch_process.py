from pathlib import Path
import requests
import subprocess
import sys
import time
import json

# Paths

BASE_DIR = Path(__file__).resolve().parent

INPUT_FOLDER = BASE_DIR / "input_data"
OUTPUT_FOLDER = BASE_DIR / "JSON_data"

API_URL = "http://127.0.0.1:8000/process"
HEALTH_URL = "http://127.0.0.1:8000/docs"

OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

# Start API

def start_api():
    print("\nStarting FastAPI...")

    server = subprocess.Popen([
        sys.executable,
        str(BASE_DIR / "doc_processor_api.py")
    ])

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

# Get PDFs

pdf_files = list(INPUT_FOLDER.glob("*.pdf"))

print(f"Found {len(pdf_files)} PDF files.\n")

# Process files

for i, pdf_path in enumerate(pdf_files, start=1):

    output_path = OUTPUT_FOLDER / f"{pdf_path.stem}.json"

    # Already processed
    if output_path.exists():
        print(f"[{i}/{len(pdf_files)}] Skipping: {pdf_path.name}")
        continue

    print(f"[{i}/{len(pdf_files)}] Processing: {pdf_path.name}")

    success = False

    # Try the file up to 3 times
    for attempt in range(1, 4):

        try:

            # Check if API is alive
            requests.get(HEALTH_URL, timeout=2)

            with open(pdf_path, "rb") as file:

                response = requests.post(
                    API_URL,
                    files={
                        "file": (
                            pdf_path.name,
                            file,
                            "application/pdf"
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
        print(f" Failed permanently: {pdf_path.name}\n")

print("Batch processing finished.")

server.terminate()