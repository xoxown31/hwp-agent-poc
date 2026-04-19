"""
HWPX document generator using python-hwpx.
Input: list of paragraph/table dicts (LLM output)
Output: .hwpx file
"""

from hwpx import HwpxDocument

STYLE_MAP = {
    "바탕글": 0,
    "본문": 1,
    "개요 1": 2,
    "개요 2": 3,
    "개요 3": 4,
    "개요 4": 5,
    "개요 5": 6,
    "캡션": 22,
}


def build_hwpx(paragraphs: list[dict], output_path: str):
    """
    paragraphs: list of dicts
      - {"type": "text", "text": "...", "style": "본문"}
      - {"type": "table", "rows": [["col1", "col2"], ["v1", "v2"]]}
    """
    doc = HwpxDocument.new()

    for item in paragraphs:
        if item["type"] == "text":
            p = doc.add_paragraph(item.get("text", ""))
            style_name = item.get("style", "바탕글")
            p.style_id_ref = STYLE_MAP.get(style_name, 0)

        elif item["type"] == "table":
            rows = item.get("rows", [])
            if not rows:
                continue
            row_cnt = len(rows)
            col_cnt = max(len(r) for r in rows)
            tbl = doc.add_table(rows=row_cnt, cols=col_cnt)
            for ri, row in enumerate(rows):
                for ci, text in enumerate(row):
                    tbl.set_cell_text(ri, ci, text)

    doc.save_to_path(output_path)
    print(f"saved: {output_path}")


if __name__ == "__main__":
    import os
    output_dir = os.path.join(os.path.dirname(__file__), "..", "output")
    os.makedirs(output_dir, exist_ok=True)

    paragraphs = [
        {"type": "text", "text": "업무 협조 요청", "style": "개요 1"},
        {"type": "text", "text": ""},
        {"type": "text", "text": "아래와 같이 업무 협조를 요청드리오니 검토 후 회신하여 주시기 바랍니다.", "style": "본문"},
        {"type": "text", "text": ""},
        {"type": "table", "rows": [
            ["항목", "내용", "비고"],
            ["요청 부서", "기획조정실", ""],
            ["요청 일자", "2026. 4. 19.", ""],
            ["요청 사항", "예산 집행 현황 제출", "5월 1일까지"],
        ]},
        {"type": "text", "text": ""},
        {"type": "text", "text": "붙임: 없음.", "style": "본문"},
    ]

    build_hwpx(paragraphs, os.path.join(output_dir, "output_test.hwpx"))
