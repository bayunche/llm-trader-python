"""提示词模板管理模块。"""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from llm_trader.data import DatasetKind, DataStoreManager, default_manager

DEFAULT_SCENARIO = "default"


@dataclass
class PromptTemplate:
    """提示词模板数据。"""

    name: str
    scenario: str
    content: str
    source: str
    version_id: Optional[str] = None
    updated_at: Optional[str] = None
    history: List[Dict[str, str]] = field(default_factory=list)


@dataclass(frozen=True)
class PromptTemplateKey:
    """模板索引，用于标识场景与名称。"""

    scenario: str
    name: str

    def identifier(self) -> str:
        if self.scenario == DEFAULT_SCENARIO:
            return self.name
        return f"{self.scenario}/{self.name}"


class PromptTemplateManager:
    """负责提示词模板的加载、保存与重置。"""

    def __init__(
        self,
        *,
        manager: Optional[DataStoreManager] = None,
        default_dir: Optional[Path] = None,
    ) -> None:
        self._manager = manager or default_manager()
        if default_dir:
            self._default_dir = Path(default_dir)
        else:
            # 默认模板位于项目根目录下的 config/prompts
            self._default_dir = Path(__file__).resolve().parents[3] / "config" / "prompts"
        config = self._manager.get(DatasetKind.STRATEGY_PROMPTS)
        self._user_dir = self._manager.base_dir / config.relative_dir
        self._user_dir.mkdir(parents=True, exist_ok=True)

    # 对外接口 -----------------------------------------------------------------

    def list_templates(self) -> List[str]:
        """返回可用模板名称列表（默认 + 用户自定义）。"""

        keys = {key.identifier() for key in self._collect_default_templates()}
        keys.update(key.identifier() for key in self._collect_user_templates())
        return sorted(keys)

    def load_template(self, name: str, *, scenario: Optional[str] = None) -> PromptTemplate:
        """加载指定名称的模板，优先使用用户自定义内容。"""

        scenario, template_name = self._normalize_input(name, scenario)
        user_path = self._current_path(scenario, template_name)
        legacy_path = self._legacy_path(template_name) if scenario == DEFAULT_SCENARIO else None
        history = self._list_versions(scenario, template_name)

        if user_path.exists():
            return PromptTemplate(
                name=template_name,
                scenario=scenario,
                content=user_path.read_text(encoding="utf-8"),
                source="custom",
                version_id=history[0]["version_id"] if history else self._format_mtime(user_path),
                updated_at=self._format_mtime(user_path),
                history=history,
            )
        if legacy_path and legacy_path.exists():
            return PromptTemplate(
                name=template_name,
                scenario=scenario,
                content=legacy_path.read_text(encoding="utf-8"),
                source="custom",
                version_id=self._format_mtime(legacy_path),
                updated_at=self._format_mtime(legacy_path),
                history=history,
            )

        default_path = self._default_path(scenario, template_name)
        if default_path.exists():
            return PromptTemplate(
                name=template_name,
                scenario=scenario,
                content=default_path.read_text(encoding="utf-8"),
                source="default",
                version_id="default",
                updated_at=self._format_mtime(default_path),
                history=history,
            )
        raise FileNotFoundError(f"未找到名称为 {template_name} 的提示词模板（场景：{scenario}）")

    def save_template(self, name: str, content: str, *, scenario: Optional[str] = None) -> PromptTemplate:
        """保存模板内容，并返回最新状态。"""

        scenario, template_name = self._normalize_input(name, scenario)
        current_path = self._current_path(scenario, template_name)
        current_path.parent.mkdir(parents=True, exist_ok=True)

        # 内容未变化则不写入新版本
        if current_path.exists() and current_path.read_text(encoding="utf-8") == content:
            return self.load_template(template_name, scenario=scenario)

        timestamp = datetime.utcnow().strftime("%Y%m%d%H%M%S%f")
        current_path.write_text(content, encoding="utf-8")
        versions_dir = self._versions_dir(scenario, template_name)
        versions_dir.mkdir(parents=True, exist_ok=True)
        version_path = versions_dir / f"{timestamp}.txt"
        version_path.write_text(content, encoding="utf-8")
        return self.load_template(template_name, scenario=scenario)

    def reset_template(self, name: str, *, scenario: Optional[str] = None) -> PromptTemplate:
        """重置模板为默认内容。"""

        scenario, template_name = self._normalize_input(name, scenario)
        user_dir = self._current_path(scenario, template_name).parent
        if user_dir.exists():
            shutil.rmtree(user_dir)
        legacy_path = self._legacy_path(template_name)
        if scenario == DEFAULT_SCENARIO and legacy_path.exists():
            legacy_path.unlink()
        return self.load_template(template_name, scenario=scenario)

    def list_versions(self, name: str, *, scenario: Optional[str] = None) -> List[Dict[str, str]]:
        """列出模板的历史版本。"""

        scenario, template_name = self._normalize_input(name, scenario)
        return self._list_versions(scenario, template_name)

    def restore_version(
        self,
        name: str,
        version_id: str,
        *,
        scenario: Optional[str] = None,
    ) -> PromptTemplate:
        """根据版本号恢复模板。"""

        scenario, template_name = self._normalize_input(name, scenario)
        version_path = self._versions_dir(scenario, template_name) / f"{version_id}.txt"
        if not version_path.exists():
            raise FileNotFoundError(f"未找到模板 {template_name} 的版本 {version_id}")
        content = version_path.read_text(encoding="utf-8")
        return self.save_template(template_name, content, scenario=scenario)

    # 内部工具方法 -------------------------------------------------------------

    def _collect_default_templates(self) -> List[PromptTemplateKey]:
        keys: List[PromptTemplateKey] = []
        if not self._default_dir.exists():
            return keys
        # 顶层默认模板
        for file_path in self._default_dir.glob("*.txt"):
            keys.append(PromptTemplateKey(DEFAULT_SCENARIO, file_path.stem))
        # 子目录场景模板
        for scenario_dir in self._default_dir.iterdir():
            if scenario_dir.is_dir():
                for file_path in scenario_dir.glob("*.txt"):
                    keys.append(PromptTemplateKey(scenario_dir.name, file_path.stem))
        return keys

    def _collect_user_templates(self) -> List[PromptTemplateKey]:
        keys: List[PromptTemplateKey] = []
        if not self._user_dir.exists():
            return keys
        for scenario_dir in self._user_dir.iterdir():
            if scenario_dir.is_dir():
                for template_dir in scenario_dir.iterdir():
                    if template_dir.is_dir():
                        keys.append(PromptTemplateKey(scenario_dir.name, template_dir.name))
        # 兼容旧版本的平铺结构
        for file_path in self._user_dir.glob("*.txt"):
            keys.append(PromptTemplateKey(DEFAULT_SCENARIO, file_path.stem))
        return keys

    def _normalize_input(self, name: str, scenario: Optional[str]) -> Tuple[str, str]:
        if "/" in name:
            scenario_part, name_part = name.split("/", 1)
            scenario = scenario_part or DEFAULT_SCENARIO
            name = name_part
        scenario = self._sanitize_token(scenario or DEFAULT_SCENARIO)
        name = self._sanitize_token(name)
        return scenario, name

    @staticmethod
    def _sanitize_token(value: str) -> str:
        token = value.strip()
        if not token:
            raise ValueError("模板名称或场景不能为空")
        if any(sep in token for sep in ("/", "\\", "..")):
            raise ValueError("模板名称或场景不能包含路径符号")
        return token

    def _default_path(self, scenario: str, name: str) -> Path:
        if scenario == DEFAULT_SCENARIO:
            candidate = self._default_dir / f"{name}.txt"
            if candidate.exists():
                return candidate
        # 目录结构 <scenario>/<name>.txt
        candidate = self._default_dir / scenario / f"{name}.txt"
        if candidate.exists():
            return candidate
        # 兼容旧版本命名 <scenario>__<name>.txt
        legacy = self._default_dir / f"{scenario}__{name}.txt"
        return legacy

    def _current_path(self, scenario: str, name: str) -> Path:
        return self._user_dir / scenario / name / "current.txt"

    def _versions_dir(self, scenario: str, name: str) -> Path:
        return self._user_dir / scenario / name / "versions"

    def _legacy_path(self, name: str) -> Path:
        return self._user_dir / f"{name}.txt"

    def _list_versions(self, scenario: str, name: str) -> List[Dict[str, str]]:
        versions_dir = self._versions_dir(scenario, name)
        if not versions_dir.exists():
            return []
        items: List[Dict[str, str]] = []
        for file_path in sorted(versions_dir.glob("*.txt"), reverse=True):
            version_id = file_path.stem
            items.append(
                {
                    "version_id": version_id,
                    "updated_at": self._format_mtime(file_path),
                    "path": str(file_path),
                }
            )
        return items

    @staticmethod
    def _format_mtime(path: Path) -> str:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return mtime.isoformat()


__all__ = ["PromptTemplateManager", "PromptTemplate", "PromptTemplateKey"]
