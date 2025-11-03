#!/usr/bin/env python3
"""基础健康检查脚本。"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from llm_trader.config import get_settings
from llm_trader.strategy.prompts import PromptTemplateManager


def _check_status_file(status_path: Path) -> None:
    if not status_path.exists():
        raise RuntimeError(f"状态文件不存在：{status_path}")
    data = json.loads(status_path.read_text(encoding="utf-8"))
    stages = data.get("stages", [])
    for stage in stages:
        if stage.get("status") in {"failed", "blocked"}:
            raise RuntimeError(f"阶段 {stage.get('name')} 状态异常：{stage.get('status')}")


def _check_prompt_template() -> None:
    manager = PromptTemplateManager()
    template = manager.load_template("strategy")
    for placeholder in ("{objective}", "{symbols}", "{indicators}", "{historical_summary}"):
        if placeholder not in template.content:
            raise RuntimeError("策略提示词模板缺少占位符：" + placeholder)


def main() -> int:
    settings = get_settings()
    report_dir = Path(settings.trading.report_output_dir)
    status_path = report_dir / "status.json"
    try:
        _check_status_file(status_path)
        _check_prompt_template()
        return 0
    except Exception as exc:  # pragma: no cover - CLI 输出
        print(f"HEALTHCHECK FAILED: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
