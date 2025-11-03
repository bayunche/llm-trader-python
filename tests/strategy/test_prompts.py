"""提示词模板管理器测试。"""

from __future__ import annotations

from pathlib import Path

import pytest

from llm_trader.strategy import PromptTemplateManager
from llm_trader.data import default_manager


def _build_manager(tmp_path: Path) -> PromptTemplateManager:
    base_dir = tmp_path / "data_store"
    manager = default_manager(base_dir=base_dir)
    default_dir = tmp_path / "defaults"
    default_dir.mkdir()
    (default_dir / "strategy.txt").write_text("默认：{objective}", encoding="utf-8")
    return PromptTemplateManager(manager=manager, default_dir=default_dir)


def test_load_template_falls_back_to_default(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    template = manager.load_template("strategy")
    assert template.content == "默认：{objective}"
    assert template.source == "default"


def test_save_and_load_custom_template(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    manager.save_template("strategy", "自定义：{objective}")
    template = manager.load_template("strategy")
    assert template.content == "自定义：{objective}"
    assert template.source == "custom"


def test_reset_template(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    manager.save_template("strategy", "自定义：{objective}")
    template = manager.reset_template("strategy")
    assert template.content == "默认：{objective}"
    assert template.source == "default"


def test_list_templates_includes_custom(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    manager.save_template("custom", "内容")
    names = manager.list_templates()
    assert "strategy" in names
    assert "custom" in names


def test_load_template_missing(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    with pytest.raises(FileNotFoundError):
        manager.load_template("unknown")


def test_template_versions_and_restore(tmp_path: Path) -> None:
    manager = _build_manager(tmp_path)
    manager.save_template("strategy", "版本1")
    manager.save_template("strategy", "版本2")
    versions = manager.list_versions("strategy")
    assert len(versions) >= 2
    first_version = versions[-1]["version_id"]
    manager.restore_version("strategy", first_version)
    template = manager.load_template("strategy")
    assert template.content == "版本1"
