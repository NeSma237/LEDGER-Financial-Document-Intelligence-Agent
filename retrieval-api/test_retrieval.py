"""
test_retrieval.py
"""
import requests
from sample_data import ALL_DOCUMENTS, TEST_QUERIES

BASE_URL = "http://localhost:8001"


def print_results(title, results):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print(f"{'=' * 60}")
    if not results:
        print("  ⚠️ no results found.")
        return
    for i, r in enumerate(results, 1):
        print(f"\n  [{i}] document: {r['document_id']} | page: {r['page']} | section: {r.get('section')}")
        print(f"      score: {r['score']:.4f}")
        print(f"      content: {r['content'][:120]}...")


def main():
    # make sure the server is running
    try:
        health = requests.get(f"{BASE_URL}/health", timeout=5)
        print(f"✅ the server is running: {health.json()}")
    except requests.exceptions.ConnectionError:
        print("❌ the server is not running! please start it first: uvicorn main:app --reload --port 8000")
        return

    # 1. index the sample documents
    print("\n📥 indexing the sample documents...")
    for doc in ALL_DOCUMENTS:
        resp = requests.post(f"{BASE_URL}/index", json=doc)
        if resp.status_code == 200:
            data = resp.json()
            print(f"   ✅ {data['document_id']}: successfully indexed {data['chunks_indexed']} chunk")
        else:
            print(f"   ❌ Failed to index {doc['document_id']}: {resp.status_code} — {resp.text}")

    # 2. test /search_documents
    query = TEST_QUERIES["search_documents"]
    resp = requests.post(f"{BASE_URL}/search_documents", json={"query": query, "top_k": 5})
    print_results(f"/search_documents — the query: '{query}'", resp.json().get("results", []))

    # 3. test /search_tables
    query = TEST_QUERIES["search_tables"]
    resp = requests.post(f"{BASE_URL}/search_tables", json={"query": query, "top_k": 5})
    print_results(f"/search_tables — the query: '{query}'", resp.json().get("results", []))

    # 4. test /filter_documents
    payload = TEST_QUERIES["filter_documents"]
    resp = requests.post(f"{BASE_URL}/filter_documents", json=payload)
    print_results(f"/filter_documents — {payload}", resp.json().get("results", []))

    print(f"\n{'=' * 60}")
    print("  ✅ All tests completed.")
    print(f"{'=' * 60}\n")


if __name__ == "__main__":
    main()
