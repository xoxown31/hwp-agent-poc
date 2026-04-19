"""
SFT data pipeline.
hwpx → parsed JSON → (prompt, JSON) pairs via LLM

Output format (JSONL):
{"prompt": "...", "response": [...paragraphs...]}
"""

import json
import os
import ollama
from hwpx import HwpxDocument

_STYLE_ID_TO_NAME = {
    0: "바탕글", 1: "본문",
    2: "개요 1", 3: "개요 2", 4: "개요 3",
    5: "개요 4", 6: "개요 5",
}

PROMPT_GEN_SYSTEM = """You are given a Korean public document content as JSON.
Write a concise Korean user request (1-2 sentences) that would naturally produce this document.
Output ONLY the request string, no explanation."""


def hwpx_to_json(path: str, max_paragraphs: int = 60) -> list[dict]:
    """Parse hwpx → list of paragraph/table dicts."""
    doc = HwpxDocument.open(path)
    items = []

    for sec in doc.oxml.sections:
        for p in sec.paragraphs:
            tbls = p.tables
            if tbls:
                t = tbls[0]
                rows = []
                seen = set()
                for ri in range(t.row_count):
                    row = []
                    for ci in range(t.column_count):
                        cell = t.cell(ri, ci)
                        addr = (ri, ci)
                        if cell and addr not in seen:
                            paras = list(cell.paragraphs) if hasattr(cell, "paragraphs") else []
                            text = paras[0].text.strip() if paras else ""
                            row.append(text)
                            seen.add(addr)
                    if row:
                        rows.append(row)

                # 중복 행 제거 (병합 셀 artifact)
                deduped = []
                for row in rows:
                    if not deduped or row != deduped[-1]:
                        deduped.append(row)

                if deduped:
                    items.append({"type": "table", "rows": deduped})
            else:
                text = p.text.strip()
                style_name = _STYLE_ID_TO_NAME.get(p.style_id_ref, "바탕글")
                items.append({"type": "text", "text": text, "style": style_name})

            if len(items) >= max_paragraphs:
                return items

    return items


def generate_prompt(doc_json: list[dict], model: str = "gemma4:e2b") -> str:
    """LLM으로 문서 JSON → 사용자 요청 프롬프트 생성."""
    doc_preview = json.dumps(doc_json[:20], ensure_ascii=False)
    response = ollama.chat(
        model=model,
        messages=[
            {"role": "system", "content": PROMPT_GEN_SYSTEM},
            {"role": "user", "content": doc_preview},
        ],
    )
    return response["message"]["content"].strip()


def process_file(hwpx_path: str, model: str = "gemma4:e2b") -> dict | None:
    """단일 hwpx → SFT 데이터 1건."""
    try:
        doc_json = hwpx_to_json(hwpx_path)
        if not doc_json:
            return None
        prompt = generate_prompt(doc_json, model)
        return {"prompt": prompt, "response": doc_json, "source": os.path.basename(hwpx_path)}
    except Exception as e:
        print(f"  error: {hwpx_path}: {e}")
        return None


def run_pipeline(samples_dir: str, output_path: str, model: str = "gemma4:e2b"):
    files = [f for f in os.listdir(samples_dir) if f.endswith(".hwpx")]
    print(f"Processing {len(files)} files...")

    results = []
    for fname in files:
        path = os.path.join(samples_dir, fname)
        print(f"  {fname}...")
        item = process_file(path, model)
        if item:
            results.append(item)
            print(f"    prompt: {item['prompt'][:60]}...")

    with open(output_path, "w", encoding="utf-8") as f:
        for item in results:
            f.write(json.dumps(item, ensure_ascii=False) + "\n")

    print(f"\nSaved {len(results)} pairs → {output_path}")


if __name__ == "__main__":
    samples_dir = os.path.join(os.path.dirname(__file__), "..", "data", "samples")
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(output_dir, exist_ok=True)

    run_pipeline(samples_dir, os.path.join(output_dir, "sft_data.jsonl"))
