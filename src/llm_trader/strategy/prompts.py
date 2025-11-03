"""提示词模板管理模块。"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import List, Optional

from llm_trader.data import DatasetKind, DataStoreManager, default_manager


@dataclass
class PromptTemplate:
    """提示词模板数据。"""

    name: str
    content: str
    source: str
    updated_at: Optional[str] = None


class PromptTemplateManager:
    """负责提示词模板的加载、保存与重置。"""

    def __init__(
        self,
        *,
        manager: Optional[DataStoreManager] = None,
        default_dir: Optional[Path] = None,
    ) -> None:
        self._manager = manager or default_manager()
        self._default_dir = Path(default_dir) if default_dir else Path(__file__).resolve().parents[2] / "config" / "prompts"
        config = self._manager.get(DatasetKind.STRATEGY_PROMPTS)
        self._user_dir = self._manager.base_dir / config.relative_dir
        self._user_dir.mkdir(parents=True, exist_ok=True)

    def list_templates(self) -> List[str]:
        """返回可用模板名称列表（默认 + 用户自定义）。"""

        names = {path.stem for path in self._default_dir.glob("*.txt")}
        names.update(path.stem for path in self._user_dir.glob("*.txt"))
        return sorted(names)

    def load_template(self, name: str) -> PromptTemplate:
        """加载指定名称的模板，优先使用用户自定义内容。"""

        user_path = self._user_path(name)
        if user_path.exists():
            return PromptTemplate(
                name=name,
                content=user_path.read_text(encoding="utf-8"),
                source="custom",
                updated_at=self._format_mtime(user_path),
            )
        default_path = self._default_path(name)
        if default_path.exists():
            return PromptTemplate(
                name=name,
                content=default_path.read_text(encoding="utf-8"),
                source="default",
                updated_at=self._format_mtime(default_path),
            )
        raise FileNotFoundError(f"未找到名称为 {name} 的提示词模板")

    def save_template(self, name: str, content: str) -> PromptTemplate:
        """保存模板内容，并返回最新状态。"""

        path = self._user_path(name)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return PromptTemplate(
            name=name,
            content=content,
            source="custom",
            updated_at=self._format_mtime(path),
        )

    def reset_template(self, name: str) -> PromptTemplate:
        """重置模板为默认内容，删除用户自定义文件。"""

        path = self._user_path(name)
        if path.exists():
            path.unlink()
        return self.load_template(name)

    def _default_path(self, name: str) -> Path:
        return self._default_dir / f"{name}.txt"

    def _user_path(self, name: str) -> Path:
        return self._user_dir / f"{name}.txt"

    @staticmethod
    def _format_mtime(path: Path) -> str:
        mtime = datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
        return mtime.isoformat()


__all__ = ["PromptTemplateManager", "PromptTemplate"]
