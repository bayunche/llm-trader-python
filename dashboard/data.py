"""仪表盘数据访问封装。"""

from __future__ import annotations

import json
import os
from functools import lru_cache
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple

from llm_trader.api.utils import (
    load_llm_logs,
    load_trading_equity,
    load_trading_orders,
    load_trading_trades,
)
from llm_trader.data import DatasetKind, default_manager
from llm_trader.config import get_settings
from llm_trader.strategy import PromptTemplateManager, StrategyRepository, StrategyVersion


def _repository(base_dir: Optional[Path] = None) -> StrategyRepository:
    return StrategyRepository(base_dir=base_dir)


def _resolve_status_path(status_path: Optional[Path | str] = None) -> Path:
    if status_path is not None:
        return Path(status_path)
    env_path = os.getenv("LLM_TRADER_PIPELINE_STATUS")
    if env_path:
        return Path(env_path)
    base_dir = Path(os.getenv("REPORT_OUTPUT_DIR", "reports"))
    filename = os.getenv("PIPELINE_STATUS_FILENAME", "status.json")
    return base_dir / filename


def load_pipeline_status(status_path: Optional[Path | str] = None) -> Dict[str, object]:
    """读取自动化流程状态文件，供仪表盘展示。"""

    path = _resolve_status_path(status_path)
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {"available": False, "path": str(path), "error": "状态文件不存在"}
    except OSError as exc:
        return {"available": False, "path": str(path), "error": f"无法读取状态文件：{exc}"}
    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        return {"available": False, "path": str(path), "error": f"状态文件格式错误：{exc}"}
    return {"available": True, "path": str(path), "data": data}


def _slice_records(records: Sequence[Dict[str, object]], offset: int, limit: Optional[int]) -> List[Dict[str, object]]:
    """根据偏移量与分页大小切片记录。"""

    if offset < 0:
        offset = 0
    end = None if limit is None else offset + max(limit, 0)
    sliced = records[offset:end] if end is not None else records[offset:]
    return [dict(item) for item in sliced]


@lru_cache(maxsize=128)
def _cached_orders(strategy_id: str, session_id: str) -> Tuple[Dict[str, object], ...]:
    """缓存订单记录，减少重复读取。"""

    return tuple(load_trading_orders(strategy_id=strategy_id, session_id=session_id, limit=None))


@lru_cache(maxsize=128)
def _cached_trades(strategy_id: str, session_id: str) -> Tuple[Dict[str, object], ...]:
    """缓存成交流水。"""

    return tuple(load_trading_trades(strategy_id=strategy_id, session_id=session_id, limit=None))


@lru_cache(maxsize=128)
def _cached_equity(strategy_id: str, session_id: str) -> Tuple[Dict[str, object], ...]:
    """缓存资金曲线。"""

    return tuple(load_trading_equity(strategy_id=strategy_id, session_id=session_id, limit=None))


@lru_cache(maxsize=128)
def _cached_llm_logs(strategy_id: str, session_id: str) -> Tuple[Dict[str, object], ...]:
    """缓存 LLM 日志。"""

    return tuple(load_llm_logs(strategy_id=strategy_id, session_id=session_id, limit=None))


def count_orders(strategy_id: str, session_id: str) -> int:
    """返回订单总数。"""

    return len(_cached_orders(strategy_id, session_id))


def get_orders(strategy_id: str, session_id: str, limit: Optional[int] = None, offset: int = 0) -> List[dict]:
    """获取订单流水，支持分页。"""

    records = _cached_orders(strategy_id, session_id)
    return _slice_records(records, offset, limit)


def count_trades(strategy_id: str, session_id: str) -> int:
    """返回成交流水总数。"""

    return len(_cached_trades(strategy_id, session_id))


def get_trades(strategy_id: str, session_id: str, limit: Optional[int] = None, offset: int = 0) -> List[dict]:
    """获取成交流水，支持分页。"""

    records = _cached_trades(strategy_id, session_id)
    return _slice_records(records, offset, limit)


def get_equity_curve(strategy_id: str, session_id: str, limit: Optional[int] = None, offset: int = 0) -> List[dict]:
    """获取资金曲线与仓位快照，支持分页。"""

    records = _cached_equity(strategy_id, session_id)
    return _slice_records(records, offset, limit)


def get_llm_logs(strategy_id: str, session_id: str, limit: Optional[int] = None, offset: int = 0) -> List[dict]:
    """获取大模型策略日志，支持分页。"""

    records = _cached_llm_logs(strategy_id, session_id)
    return _slice_records(records, offset, limit)


def count_equity_points(strategy_id: str, session_id: str) -> int:
    """返回资金曲线记录数。"""

    return len(_cached_equity(strategy_id, session_id))


def count_llm_logs(strategy_id: str, session_id: str) -> int:
    """返回 LLM 日志条数。"""

    return len(_cached_llm_logs(strategy_id, session_id))


def _prompt_manager() -> PromptTemplateManager:
    """延迟初始化模板管理器，便于切换数据目录。"""

    global _PROMPT_MANAGER
    if _PROMPT_MANAGER is None:
        _PROMPT_MANAGER = PromptTemplateManager()
    return _PROMPT_MANAGER


def _parse_template_identifier(identifier: str) -> Tuple[str, str]:
    """解析模板标识，返回 (scenario, name)。"""

    if "/" in identifier:
        scenario, name = identifier.split("/", 1)
        return scenario or "default", name
    return "default", identifier


def list_prompt_templates() -> List[str]:
    """列出可编辑的提示词模板名称。"""

    return _prompt_manager().list_templates()


def load_prompt_template(name: str) -> Dict[str, object]:
    """加载指定模板，返回内容与元信息。"""

    scenario, template_name = _parse_template_identifier(name)
    template = _prompt_manager().load_template(template_name, scenario=scenario)
    return {
        "name": template_name,
        "scenario": template.scenario,
        "content": template.content,
        "source": template.source,
        "updated_at": template.updated_at,
        "version_id": template.version_id,
        "history": template.history,
    }


def save_prompt_template(name: str, content: str) -> Dict[str, object]:
    """保存模板内容并返回最新状态。"""

    scenario, template_name = _parse_template_identifier(name)
    template = _prompt_manager().save_template(template_name, content, scenario=scenario)
    return {
        "name": template_name,
        "scenario": template.scenario,
        "content": template.content,
        "source": template.source,
        "updated_at": template.updated_at,
        "version_id": template.version_id,
        "history": template.history,
    }


def reset_prompt_template(name: str) -> Dict[str, object]:
    """重置模板为默认内容。"""

    scenario, template_name = _parse_template_identifier(name)
    template = _prompt_manager().reset_template(template_name, scenario=scenario)
    return {
        "name": template_name,
        "scenario": template.scenario,
        "content": template.content,
        "source": template.source,
        "updated_at": template.updated_at,
        "version_id": template.version_id,
        "history": template.history,
    }


def list_strategy_versions(strategy_id: str) -> List[StrategyVersion]:
    """列出策略版本信息。"""

    repo = _repository()
    return repo.list_versions(strategy_id)


def list_strategy_ids() -> List[str]:
    """获取所有存在版本或交易数据的策略 ID。"""

    repo = _repository()
    versions = repo.list_versions()
    strategy_ids = {version.strategy_id for version in versions}
    # 补充仅存在交易数据的策略
    manager = default_manager()
    orders_config = manager.get(DatasetKind.TRADING_ORDERS)
    base = manager.base_dir / orders_config.relative_dir
    if base.exists():
        for session_dir in base.glob("session=*"):
            for strategy_dir in session_dir.glob("strategy=*"):
                strategy_ids.add(strategy_dir.name.split("=", 1)[1])
    return sorted(strategy_ids)


def list_strategy_sessions() -> List[Dict[str, str]]:
    """获取策略与会话映射列表。"""

    manager = default_manager()
    orders_config = manager.get(DatasetKind.TRADING_ORDERS)
    base = manager.base_dir / orders_config.relative_dir
    results: List[Dict[str, str]] = []
    if not base.exists():
        return results
    for session_dir in sorted(base.glob("session=*")):
        session_id = session_dir.name.split("=", 1)[1]
        for strategy_dir in sorted(session_dir.glob("strategy=*")):
            strategy_id = strategy_dir.name.split("=", 1)[1]
            results.append({"strategy_id": strategy_id, "session_id": session_id})
    return results


def invalidate_cache() -> None:
    """清除数据访问相关缓存。"""

    _cached_orders.cache_clear()
    _cached_trades.cache_clear()
    _cached_equity.cache_clear()
    _cached_llm_logs.cache_clear()
    global _PROMPT_MANAGER
    _PROMPT_MANAGER = None
    get_settings.cache_clear()


def list_prompt_template_versions(name: str) -> List[Dict[str, str]]:
    """列出指定模板的历史版本。"""

    scenario, template_name = _parse_template_identifier(name)
    return _prompt_manager().list_versions(template_name, scenario=scenario)


def restore_prompt_template_version(name: str, version_id: str) -> Dict[str, object]:
    """恢复模板到指定版本并返回最新状态。"""

    scenario, template_name = _parse_template_identifier(name)
    template = _prompt_manager().restore_version(template_name, version_id, scenario=scenario)
    return {
        "name": template_name,
        "scenario": template.scenario,
        "content": template.content,
        "source": template.source,
        "updated_at": template.updated_at,
        "version_id": template.version_id,
        "history": template.history,
    }


__all__ = [
    "get_orders",
    "get_trades",
    "get_equity_curve",
    "get_llm_logs",
    "count_orders",
    "count_trades",
    "count_equity_points",
    "count_llm_logs",
    "list_strategy_versions",
    "list_strategy_ids",
    "list_strategy_sessions",
    "load_pipeline_status",
    "list_prompt_templates",
    "load_prompt_template",
    "save_prompt_template",
    "reset_prompt_template",
    "list_prompt_template_versions",
    "restore_prompt_template_version",
    "invalidate_cache",
]
_PROMPT_MANAGER: Optional[PromptTemplateManager] = None
