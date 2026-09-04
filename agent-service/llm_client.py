import httpx
import os
import json
from dotenv import load_dotenv

load_dotenv()


def call_llm(prompt: str) -> dict:
    model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        return {
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {"reason": "GROQ_API_KEY is missing"},
            "needs_calculation": False,
            "formula_to_calculate": None
        }

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }

    payload = {
        "model": model,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a financial analyst. "
                    "Always respond with valid JSON only. "
                    "No markdown, no explanation."
                )
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
        "temperature": 0,
        "max_tokens": 1000,
        "response_format": {
            "type": "json_object"
        }
    }

    try:
        r = httpx.post(
            "https://api.groq.com/openai/v1/chat/completions",
            headers=headers,
            json=payload,
            timeout=30
        )

        print("=== GROQ RESPONSE ===")
        print("Status:", r.status_code)
        print("Body:", r.text)
        print("=====================")

        r.raise_for_status()

        data = r.json()

        if "choices" not in data:
            return {
                "answer_type": "insufficient_evidence",
                "evidence": [],
                "params": {
                    "reason": "Groq response does not contain 'choices'",
                    "response": data
                },
                "needs_calculation": False,
                "formula_to_calculate": None
            }

        raw = data["choices"][0]["message"]["content"]

        try:
            return json.loads(raw)

        except json.JSONDecodeError:
            return {
                "answer_type": "insufficient_evidence",
                "evidence": [],
                "params": {
                    "reason": "LLM returned invalid JSON",
                    "raw_response": raw
                },
                "needs_calculation": False,
                "formula_to_calculate": None
            }

    except httpx.HTTPStatusError as e:
        return {
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {
                "reason": "Groq API returned an HTTP error",
                "status_code": e.response.status_code,
                "response": e.response.text
            },
            "needs_calculation": False,
            "formula_to_calculate": None
        }

    except Exception as e:
        return {
            "answer_type": "insufficient_evidence",
            "evidence": [],
            "params": {
                "reason": f"LLM request failed: {str(e)}"
            },
            "needs_calculation": False,
            "formula_to_calculate": None
        }