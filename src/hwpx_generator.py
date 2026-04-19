"""
HWPX document generator using python-hwpx.
Input: list of paragraph/table dicts (LLM output)
Output: .hwpx file
"""

# python-hwpx bug: uses stdlib ET.SubElement on lxml elements → smart-patch
import xml.etree.ElementTree as _ET
from lxml import etree as _LET
_orig_subelement = _ET.SubElement
def _smart_subelement(parent, tag, attrib={}, **extra):  # noqa: B006
    if isinstance(parent, _LET._Element):
        return _LET.SubElement(parent, tag, attrib or {}, **extra)
    return _orig_subelement(parent, tag, attrib, **extra)
_ET.SubElement = _smart_subelement  # type: ignore[assignment]

from hwpx import HwpxDocument

_HH = "{http://www.hancom.co.kr/hwpml/2011/head}"
_HC = "{http://www.hancom.co.kr/hwpml/2011/core}"

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

PAGE_WIDTH = 42520   # HWPUNIT (A4 본문 너비)
CELL_HEIGHT = 2400   # 기본 셀 높이


def _col_widths(col_cnt: int, col_widths: list[int] | None) -> list[int]:
    if col_widths and len(col_widths) == col_cnt:
        total = sum(col_widths)
        ws = [int(PAGE_WIDTH * w / total) for w in col_widths]
        ws[-1] = PAGE_WIDTH - sum(ws[:-1])
        return ws
    if col_cnt == 1:
        return [PAGE_WIDTH]
    if col_cnt == 2:
        w0 = int(PAGE_WIDTH * 0.28)
        return [w0, PAGE_WIDTH - w0]
    # 3칸 이상: 첫 칸 좁게
    w0 = int(PAGE_WIDTH * 0.18)
    rest = (PAGE_WIDTH - w0) // (col_cnt - 1)
    ws = [w0] + [rest] * (col_cnt - 1)
    ws[-1] = PAGE_WIDTH - sum(ws[:-1])
    return ws


def _patch_header(doc: HwpxDocument) -> tuple[str, str]:
    """
    헤더에 2개 항목 추가:
    - 가운데 정렬 paraPr (개요1용 CENTER align)
    - 회색 배경 borderFill (테이블 헤더 셀용)
    반환: (center_para_pr_id, gray_border_fill_id)
    """
    header = doc._root._headers[0]
    el = header._element

    # ── 1. 개요 1 paraPr (id=2) align → CENTER ───────────────────────
    for pp in el.findall(f".//{_HH}paraPr"):
        if pp.get("id") == "2":
            align = pp.find(f"{_HH}align")
            if align is not None:
                align.set("horizontal", "CENTER")
            break

    # ── 2. 회색 배경 borderFill 추가 ────────────────────────────────
    bf_list = el.find(f".//{_HH}borderFills")
    existing_ids = [int(bf.get("id", 0)) for bf in bf_list.findall(f"{_HH}borderFill")]
    new_id = str(max(existing_ids) + 1)

    # 기존 기본 borderFill(id=2) 복사 후 fill 변경
    base_bf = bf_list.find(f"{_HH}borderFill[@id='2']")
    if base_bf is None:
        base_bf = bf_list.find(f"{_HH}borderFill")
    import copy
    gray_bf = copy.deepcopy(base_bf)
    gray_bf.set("id", new_id)

    # 기존 fillBrush 제거 후 회색으로 교체
    for fb in gray_bf.findall(f"{_HC}fillBrush"):
        gray_bf.remove(fb)
    fill = _LET.SubElement(gray_bf, f"{_HC}fillBrush")
    _LET.SubElement(fill, f"{_HC}winBrush", {
        "faceColor": "#D9D9D9",
        "hatchColor": "#999999",
        "alpha": "0",
    })
    bf_list.append(gray_bf)

    # itemCnt 갱신
    bf_list.set("itemCnt", str(len(bf_list.findall(f"{_HH}borderFill"))))
    header.mark_dirty()

    return "2", new_id


def _set_cell_border_fill(cell, border_fill_id: str) -> None:
    """셀 element의 borderFillIDRef 직접 변경."""
    cell.element.set("borderFillIDRef", border_fill_id)


def build_hwpx(paragraphs: list[dict], output_path: str):
    """
    paragraphs: list of dicts
      - {"type": "text", "text": "...", "style": "본문"}
      - {"type": "table", "rows": [...], "col_widths": [30, 50, 20], "header_rows": 1}
    """
    doc = HwpxDocument.new()

    # 여백 조정: 공문서 표준 (상35 하30 좌35 우30 mm)
    section = doc.sections[0]
    section.properties.set_page_margins(left=3500, right=3000, top=3500, bottom=3000, header=1500, footer=1500)

    # 헤더 패치: 개요1 가운데정렬, 회색 borderFill 추가
    _, gray_bf_id = _patch_header(doc)

    for item in paragraphs:
        if item["type"] == "text":
            text = item.get("text", "")
            style_name = item.get("style", "바탕글")
            bold = item.get("bold", False)

            if style_name == "개요 1":
                p = doc.add_paragraph("", style_id_ref=2, para_pr_id_ref=2)
                p.add_run(text, bold=True)
            elif bold:
                p = doc.add_paragraph("")
                p.style_id_ref = STYLE_MAP.get(style_name, 0)
                p.add_run(text, bold=True)
            else:
                p = doc.add_paragraph(text)
                p.style_id_ref = STYLE_MAP.get(style_name, 0)

        elif item["type"] == "table":
            rows = item.get("rows", [])
            if not rows:
                continue

            row_cnt = len(rows)
            col_cnt = max(len(r) for r in rows)
            header_rows = item.get("header_rows", 1)
            widths = _col_widths(col_cnt, item.get("col_widths"))

            tbl = doc.add_table(rows=row_cnt, cols=col_cnt, width=PAGE_WIDTH)

            for ri, row in enumerate(rows):
                is_header = ri < header_rows
                for ci, text in enumerate(row):
                    cell = tbl.cell(ri, ci)
                    if cell is None:
                        continue
                    cell.set_size(widths[ci] if ci < len(widths) else widths[-1], CELL_HEIGHT)

                    if is_header:
                        _set_cell_border_fill(cell, gray_bf_id)

                    paras = list(cell.paragraphs)
                    if paras:
                        p = paras[0]
                        p.clear_text()
                        if is_header:
                            p.add_run(text, bold=True)
                        else:
                            p.add_run(text)
                    else:
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
        ], "col_widths": [20, 60, 20]},
        {"type": "text", "text": ""},
        {"type": "text", "text": "붙임: 없음.", "style": "본문"},
    ]

    build_hwpx(paragraphs, os.path.join(output_dir, "output_test.hwpx"))
