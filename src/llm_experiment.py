"""
LLM → JSON → HWPX pipeline experiment.
"""

import json
import os
import ollama
from hwpx_generator import build_hwpx

_OUTPUT_DIR = os.path.join(os.path.dirname(__file__), "..", "output")
os.makedirs(_OUTPUT_DIR, exist_ok=True)

SYSTEM_PROMPT = """You are a Korean public document formatter.
Given a document request, output a JSON array of paragraph objects.

Rules:
- Each object has "type": "text" or "table"
- For "text": {"type": "text", "text": "...", "style": "<style>"}
- For "table": {"type": "table", "rows": [["col1", "col2"], ["val1", "val2"]]}
- Available styles: 바탕글, 본문, 개요 1, 개요 2, 개요 3
- Use Korean, follow Korean government document (공문서) style
- Output ONLY the JSON array, no explanation

Example output:
[
  {"type": "text", "text": "업무 협조 요청", "style": "개요 1"},
  {"type": "text", "text": ""},
  {"type": "text", "text": "아래와 같이 업무 협조를 요청드립니다.", "style": "본문"},
  {"type": "table", "rows": [["항목", "내용"], ["요청 사항", "예산 현황 제출"]]}
]"""


def generate_document(prompt: str, model: str = "exaone3.5:7.8b") -> list[dict]:
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
    )
    raw = response["message"]["content"].strip()

    if "```" in raw:
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    return json.loads(raw.strip())


if __name__ == "__main__":
    prompt = "출장 복명서를 작성해줘. 출장자: 홍길동, 기간: 2026.4.14~4.16, 목적: 업무 협의, 장소: 서울청사"

    print(f"Prompt: {prompt}\n")
    paragraphs = generate_document(prompt)
    print("Generated JSON:")
    print(json.dumps(paragraphs, ensure_ascii=False, indent=2))

    out = os.path.join(_OUTPUT_DIR, "output_llm.hwpx")
    build_hwpx(paragraphs, out)
