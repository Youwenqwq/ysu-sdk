"""服务端渲染 HTML 表格的最小抽取器（标准库 ``html.parser``，零依赖）。

劳动教育系统是 ASP.NET MVC 服务端渲染，数据直接嵌在页面的 ``<table>``
里；导出端点是旧版 OLE2 ``.xls`` 不便解析，故以 HTML 表格为准。

设计要点：

- 只收集**顶层** ``<table>``——主表单元格里嵌套了详情小表
  （如「劳动时长 4 学生 …」），嵌套表内容一律忽略，防止污染主表文本；
- 活动名单元格内可能有 ``<span class="m-badge">`` 徽标（如「教师选择」），
  单独收集到 badges，不混进名称；
- 单元格文本压缩空白。
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from html.parser import HTMLParser

_WS_RE = re.compile(r"\s+")


@dataclass
class TableData:
    """一张顶层表格的抽取结果。"""

    headers: list[str] = field(default_factory=list)
    rows: list[list[str]] = field(default_factory=list)
    # 与 rows 对齐：每行各单元格内的徽标文本（多数单元格为空列表）
    badges: list[list[list[str]]] = field(default_factory=list)


class _TableExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.tables: list[TableData] = []
        self._table_depth = 0
        self._cur: TableData | None = None
        self._in_header = False
        self._cur_row: list[str] | None = None
        self._cur_badges: list[list[str]] | None = None
        self._cell_text: list[str] | None = None
        self._cell_badges: list[str] | None = None
        self._in_badge = False

    # ── 标签进入 ──────────────────────────────────────────────────────── #

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "table":
            self._table_depth += 1
            if self._table_depth == 1:
                self._cur = TableData()
            return
        if self._table_depth != 1 or self._cur is None:
            return
        if tag == "tr":
            self._cur_row = []
            self._cur_badges = []
        elif tag in ("th", "td"):
            self._cell_text = []
            self._cell_badges = []
            self._in_header = tag == "th"
        elif tag == "span" and self._cell_text is not None:
            cls = dict(attrs).get("class") or ""
            if "m-badge" in cls:
                self._in_badge = True

    # ── 文本 ──────────────────────────────────────────────────────────── #

    def handle_data(self, data: str) -> None:
        if self._table_depth != 1 or self._cell_text is None:
            return
        if self._in_badge:
            assert self._cell_badges is not None
            self._cell_badges.append(data)
        else:
            self._cell_text.append(data)

    # ── 标签退出 ──────────────────────────────────────────────────────── #

    def handle_endtag(self, tag: str) -> None:
        if tag == "table":
            if self._table_depth == 1 and self._cur is not None:
                self.tables.append(self._cur)
                self._cur = None
            self._table_depth = max(0, self._table_depth - 1)
            return
        if self._table_depth != 1 or self._cur is None:
            return
        if tag == "span":
            self._in_badge = False
        elif tag in ("th", "td") and self._cell_text is not None:
            text = _WS_RE.sub(" ", "".join(self._cell_text)).strip()
            badges = [
                _WS_RE.sub(" ", b).strip() for b in (self._cell_badges or [])
            ]
            badges = [b for b in badges if b]
            # 有的单元格整体就是一个徽标（如审核状态），此时以徽标文本为准
            if not text and badges:
                text = " ".join(badges)
            if self._in_header:
                self._cur.headers.append(text)
            elif self._cur_row is not None:
                self._cur_row.append(text)
                assert self._cur_badges is not None
                self._cur_badges.append(badges)
            self._cell_text = None
            self._cell_badges = None
        elif tag == "tr" and self._cur_row is not None:
            if any(self._cur_row):
                self._cur.rows.append(self._cur_row)
                self._cur.badges.append(self._cur_badges or [])
            self._cur_row = None
            self._cur_badges = None


def parse_tables(html: str) -> list[TableData]:
    """抽取页面中的全部顶层表格。"""
    parser = _TableExtractor()
    parser.feed(html)
    parser.close()
    return parser.tables
