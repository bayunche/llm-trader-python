"""数据质量与校验工具。"""

from __future__ import annotations

from typing import Any, Dict, Iterable, List, Sequence

from llm_trader.common import ValidationError, get_logger


_LOGGER = get_logger("data.quality")


Record = Dict[str, Any]


def ensure_columns(records: Sequence[Record], required: Sequence[str]) -> None:
    """确保所有记录包含必要字段。"""

    for record in records:
        missing = [col for col in required if col not in record]
        if missing:
            raise ValidationError(f"数据缺少必要字段：{missing}")


def drop_duplicates(records: Sequence[Record], subset: Iterable[str]) -> List[Record]:
    """基于指定字段去重，保留最后一条记录。"""

    subset = list(subset)
    seen: Dict[tuple, tuple] = {}
    for index, record in enumerate(records):
        key = tuple(record.get(col) for col in subset)
        seen[key] = (index, record)
    ordered = sorted(seen.values(), key=lambda item: item[0])
    result = [record for _, record in ordered]
    if len(result) < len(records):
        _LOGGER.warning("发现重复记录，已自动去重", extra={"before": len(records), "after": len(result)})
    return result


def drop_na(records: Sequence[Record], subset: Iterable[str]) -> List[Record]:
    """移除关键字段为空的记录。"""

    subset = list(subset)
    filtered = [record for record in records if all(record.get(col) is not None for col in subset)]
    if len(filtered) < len(records):
        _LOGGER.warning(
            "发现关键字段缺失，已删除空值记录",
            extra={"before": len(records), "after": len(filtered)},
        )
    return filtered


def assert_sorted(records: Sequence[Record], column: str) -> None:
    """断言记录按指定字段非递减排序。"""

    values = [record.get(column) for record in records]
    if values != sorted(values):
        raise ValidationError(f"字段 {column} 必须按升序排列")


def sort_records(records: Sequence[Record], column: str) -> List[Record]:
    """返回按指定字段排序后的新列表。"""

    return sorted(records, key=lambda record: record.get(column))


__all__ = ["ensure_columns", "drop_duplicates", "drop_na", "assert_sorted", "sort_records"]
