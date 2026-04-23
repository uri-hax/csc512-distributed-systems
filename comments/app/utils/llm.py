import json
import ollama
import os
from typing import Any, Dict, List, Optional

from app.core.config import SYSTEM_CODE_PROMPT, SYSTEM_MARKDOWN_PROMPT, JSON_RE

OLLAMA_HOST = "http://127.0.0.1:11434"
OLLAMA_TIMEOUT = 300
MODEL = os.environ.get("LLM_MODEL")

client = ollama.Client(host=OLLAMA_HOST, timeout=OLLAMA_TIMEOUT)

def build_prompt(file_path: str, comments: List[Dict[str, Any]]) -> str:
    parts = [f"File: {file_path}\n"]
    for idx, c in enumerate(comments):
        text = (c.get("text") or "").strip()
        line = c.get("line", "?")
        ctype = c.get("type", "unknown")
        parts.append(f"[{idx}] (line {line}, {ctype}) {text}")
    return "\n".join(parts)

def parse_llm_json(raw: str) -> Optional[Dict[str, Any]]:
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    m = JSON_RE.search(raw)
    if m:
        try:
            return json.loads(m.group(1))
        except json.JSONDecodeError:
            pass

    # Try to find the first { ... } block
    start = raw.find("{")
    end = raw.rfind("}")
    if start != -1 and end != -1 and end > start:
        try:
            return json.loads(raw[start : end + 1])
        except json.JSONDecodeError:
            pass

    return None

def analyze_comments(file_path: str, comments: List[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    if not comments:
        return None

    user_prompt = build_prompt(file_path, comments)
    try:
        response = client.chat(model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_CODE_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": 0.0, "num_predict": 128},
            keep_alive="10m",
        )
    except Exception:
        return None

    raw_text = response.get("message", {}).get("content", "")
    parsed = parse_llm_json(raw_text)

    if parsed is None or "tags" not in parsed:
        return None

    return parsed

def analyze_markdown(file_path: str, text: str) -> Optional[Dict[str, Any]]:
    if not text or not text.strip():
        return None
    
    # Minimum length check to avoid halucinations on empty or near-empty markdown files. 
    if len(text.strip()) < 10:
        return None

    user_prompt = f"File: {file_path}\n\n{text}"
    try:
        response = client.chat(model=MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_MARKDOWN_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            options={"temperature": 0.0, "num_predict": 320},
            keep_alive="10m",
        )
    except Exception:
        return None

    raw_text = response.get("message", {}).get("content", "")
    parsed = parse_llm_json(raw_text)

    if parsed is None:
        return None

    return parsed
