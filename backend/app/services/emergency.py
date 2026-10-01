"""应急演练业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "emergency"
REQUIRED_FIELDS = ["演练主题", "演练类型"]
ENTRY_FIELDS = ["演练编号", "演练主题", "演练类型", "参与单位", "演练日期", "演练评估", "改进措施"]
STATUS_ORDER = ["待组织", "已组织", "已完成", "已复盘"]
ACTION_RULES = {"组织演练": "已组织", "完成演练": "已完成", "复盘总结": "已复盘"}
NEGATIVE_ACTIONS = []
CODE_PREFIX = "EMER"


class EmergencyService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        unit: str | None = None,
        theme: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("演练编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        if unit:
            rows = [row for row in rows if str(row.get("参与单位") or "").strip() == unit]
        if theme:
            rows = [row for row in rows if str(row.get("演练主题") or "").strip() == theme]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def matrix(self) -> dict[str, Any]:
        """按参与单位 × 演练主题聚合演练次数，与列表共用同一份记录，口径一致。"""
        rows = store.rows(MODULE)
        units = sorted({str(row.get("参与单位") or "").strip() for row in rows} - {""})
        themes = sorted({str(row.get("演练主题") or "").strip() for row in rows} - {""})
        cells: list[dict[str, Any]] = []
        for unit in units:
            for theme in themes:
                matched = [
                    row for row in rows
                    if str(row.get("参与单位") or "").strip() == unit
                    and str(row.get("演练主题") or "").strip() == theme
                ]
                if not matched:
                    continue
                cells.append({
                    "unit": unit,
                    "theme": theme,
                    "count": len(matched),
                    "todo": sum(1 for row in matched if self._measure_pending(row)),
                })
        return {"units": units, "themes": themes, "cells": cells}

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in ENTRY_FIELDS:
            entry[field] = values.get(field)
        if not str(entry.get("演练编号") or "").strip():
            entry["演练编号"] = self._next_code(rows)
        entry["status"] = STATUS_ORDER[0]
        entry["演练状态"] = STATUS_ORDER[0]
        entry["pending"] = True
        entry["abnormal"] = False
        rows.append(entry)
        return entry, []

    def run_action(self, entry_id: int, action: str) -> tuple[dict[str, Any] | None, str]:
        entry = store.find(MODULE, entry_id)
        if entry is None:
            return None, f"演练记录 {entry_id} 不存在或已归档"
        if action not in ACTION_RULES:
            return None, f"动作「{action}」不属于应急演练可执行范围"
        target = ACTION_RULES[action]
        if target not in STATUS_ORDER:
            return None, f"目标状态「{target}」不在允许的状态序列里"
        entry["status"] = target
        entry["演练状态"] = target
        entry["pending"] = target != STATUS_ORDER[-1]
        entry["abnormal"] = action in NEGATIVE_ACTIONS
        return entry, f"演练记录已{action}"

    @staticmethod
    def _measure_pending(row: dict[str, Any]) -> bool:
        """改进措施已提出但演练尚未复盘闭环，视为待落实。"""
        return bool(str(row.get("改进措施") or "").strip()) and row.get("status") != STATUS_ORDER[-1]

    @staticmethod
    def _next_code(rows: list[dict[str, Any]]) -> str:
        seq = 0
        for row in rows:
            code = str(row.get("演练编号") or "")
            if not code.startswith(f"{CODE_PREFIX}-"):
                continue
            try:
                seq = max(seq, int(code.rsplit("-", 1)[-1]))
            except ValueError:
                continue
        return f"{CODE_PREFIX}-{seq + 1:04d}"
