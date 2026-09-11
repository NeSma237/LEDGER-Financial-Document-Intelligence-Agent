import json
import logging
import os

import httpx
from dotenv import load_dotenv

from observability import observation


load_dotenv()
logger = logging.getLogger("agent-service.llm")
LLM_TIMEOUT_SECONDS = float(os.getenv("LLM_TIMEOUT_SECONDS", "45"))


def call_llm(prompt: str) -> dict:
    with observation("groq-generation", {"prompt": prompt}) as span:
        model = os.getenv("LLM_MODEL", "openai/gpt-oss-120b")
        api_key = os.getenv("GROQ_API_KEY")

        if not api_key:
            return {
                "answer_type": "insufficient_evidence",
                "evidence": [],
                "params": {"reason": "GROQ_API_KEY is missing"},
                "needs_calculation": False,
                "formula_to_calculate": None,
            }

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": model,
            "messages": [
                {
                    "role": "system",
                    "content": "You are a financial analyst. Always respond with valid JSON only. No markdown, no explanation.",
                },
                {"role": "user", "content": prompt},
            ],
            "temperature": 0,
            "max_tokens": 1000,
            "response_format": {"type": "json_object"},
        }

        try:
            response = httpx.post(
                "https://api.groq.com/openai/v1/chat/completions",
                headers=headers,
                json=payload,
                timeout=LLM_TIMEOUT_SECONDS,
            )
            logger.info("Groq completion returned HTTP %s", response.status_code)
            response.raise_for_status()
            data = response.json()
            usage = data.get("usage") or {}
            usage_payload = {
                "llm_calls": 1,
                "input_tokens": usage.get("prompt_tokens", 0),
                "output_tokens": usage.get("completion_tokens", 0),
                "tokens": usage.get("total_tokens", 0),
            }

            if "choices" not in data:
                return {
                    "answer_type": "insufficient_evidence",
                    "evidence": [],
                    "params": {"reason": "Groq response does not contain 'choices'", "response": data},
                    "needs_calculation": False,
                    "formula_to_calculate": None,
                    "_usage": usage_payload,
                }

            raw = data["choices"][0]["message"]["content"]
            try:
                parsed = json.loads(raw)
            except json.JSONDecodeError:
                return {
                    "answer_type": "insufficient_evidence",
                    "evidence": [],
                    "params": {"reason": "LLM returned invalid JSON", "raw_response": raw},
                    "needs_calculation": False,
                    "formula_to_calculate": None,
                    "_usage": usage_payload,
                }

            parsed["_usage"] = usage_payload
            if span is not None:
                span.update(output={"answer_type": parsed.get("answer_type"), "usage": usage_payload})
            return parsed
        except httpx.HTTPStatusError as exc:
            return {
                "answer_type": "insufficient_evidence",
                "evidence": [],
                "params": {
                    "reason": "Groq API returned an HTTP error",
                    "status_code": exc.response.status_code,
                    "response": exc.response.text,
                },
                "needs_calculation": False,
                "formula_to_calculate": None,
                "_usage": {"llm_calls": 1, "input_tokens": 0, "output_tokens": 0, "tokens": 0},
            }
        except Exception as exc:
            return {
                "answer_type": "insufficient_evidence",
                "evidence": [],
                "params": {"reason": f"LLM request failed: {exc}"},
                "needs_calculation": False,
                "formula_to_calculate": None,
                "_usage": {"llm_calls": 1, "input_tokens": 0, "output_tokens": 0, "tokens": 0},
            }
