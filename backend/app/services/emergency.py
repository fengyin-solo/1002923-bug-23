"""应急演练业务规则：状态流转、字段校验与筛选口径都收在这里。"""
from __future__ import annotations

from typing import Any

from app.store import store

MODULE = "emergency"
REQUIRED_FIELDS = ["演练编号", "演练主题", "演练类型"]
LIST_FIELDS = ["演练编号", "演练主题", "演练类型", "参与单位", "演练日期", "演练评估", "改进措施"]
STATUS_ORDER = ["待组织", "已组织", "已完成", "已复盘"]
ACTION_RULES = {"组织演练": "已组织", "完成演练": "已完成", "复盘总结": "已复盘"}
NEGATIVE_ACTIONS = []
# 复盘总结之后改进措施才算落实闭环，此前一律视为待办
REVIEWED_STATUS = STATUS_ORDER[-1]
CODE_PREFIX = "EMER"


class EmergencyService:
    def list_entries(
        self,
        *,
        keyword: str | None = None,
        status: str | None = None,
        page: int = 1,
        size: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        rows = store.rows(MODULE)
        if keyword:
            rows = [row for row in rows if keyword in str(row.get("演练编号", ""))]
        if status:
            rows = [row for row in rows if row.get("status") == status]
        total = len(rows)
        start = max(page - 1, 0) * size
        return rows[start:start + size], total

    def get_entry(self, entry_id: int) -> dict[str, Any] | None:
        return store.find(MODULE, entry_id)

    def create_entry(self, values: dict[str, Any]) -> tuple[dict[str, Any] | None, list[str]]:
        values = dict(values)
        if not str(values.get("演练编号") or "").strip():
            values["演练编号"] = self._next_code()
        missing = [field for field in REQUIRED_FIELDS if not str(values.get(field) or "").strip()]
        if missing:
            return None, missing
        rows = store.rows(MODULE)
        entry: dict[str, Any] = {"id": max((int(row.get("id", 0)) for row in rows), default=0) + 1}
        for field in LIST_FIELDS:
            value = values.get(field)
            if value is not None and str(value).strip() != "":
                entry[field] = value
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

    def matrix(self) -> dict[str, Any]:
        """按 参与单位 × 演练主题 把演练记录铺成概览矩阵。

        与列表接口读的是 store 里同一份数据，次数、待办的口径两边一致；
        没有演练的组合不出现在 cells 里，由前端标成「暂无」。
        """
        rows = store.rows(MODULE)
        units: list[str] = []
        themes: list[str] = []
        cells: dict[tuple[str, str], dict[str, Any]] = {}
        for row in rows:
            unit = str(row.get("参与单位") or "").strip() or "未填写单位"
            theme = str(row.get("演练主题") or "").strip() or "未填写主题"
            if unit not in units:
                units.append(unit)
            if theme not in themes:
                themes.append(theme)
            cell = cells.setdefault(
                (unit, theme),
                {"unit": unit, "theme": theme, "count": 0, "todo": 0, "entries": []},
            )
            cell["count"] += 1
            if self.improvement_pending(row):
                cell["todo"] += 1
            cell["entries"].append(self._summary(row))
        for cell in cells.values():
            cell["entries"].sort(key=lambda item: int(item.get("id", 0)))
        return {
            "units": sorted(units),
            "themes": sorted(themes),
            "cells": [cells[key] for key in sorted(cells)],
            "total": len(rows),
        }

    @staticmethod
    def improvement_pending(row: dict[str, Any]) -> bool:
        """改进措施已提出但演练还没复盘闭环，视为改进待落实。"""
        return bool(str(row.get("改进措施") or "").strip()) and row.get("status") != REVIEWED_STATUS

    @staticmethod
    def _summary(row: dict[str, Any]) -> dict[str, Any]:
        summary = {field: row.get(field) for field in LIST_FIELDS}
        summary["id"] = row.get("id")
        summary["演练状态"] = row.get("status")
        summary["改进待落实"] = EmergencyService.improvement_pending(row)
        return summary

    @staticmethod
    def _next_code() -> str:
        serial = 0
        for row in store.rows(MODULE):
            code = str(row.get("演练编号") or "")
            prefix, _, tail = code.partition("-")
            if prefix != CODE_PREFIX or not tail.isdigit():
                continue
            serial = max(serial, int(tail))
        return f"{CODE_PREFIX}-{serial + 1:04d}"
