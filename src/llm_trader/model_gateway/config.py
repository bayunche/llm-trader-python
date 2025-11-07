from __future__ import annotations

"""模型网关配置数据结构。"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class ModelEndpointSettings:
    """单个模型端点配置。"""

    name: str
    base_url: str
    api_key: Optional[str] = None
    weight: float = 1.0
    timeout: float = 30.0
    max_retries: int = 2
    enabled: bool = True
    prompt_cost_per_1k: float = 0.0
    completion_cost_per_1k: float = 0.0
    default_params: Dict[str, Any] = field(default_factory=dict)
    headers: Dict[str, Any] = field(default_factory=dict)
    circuit_breaker: Dict[str, Any] = field(default_factory=dict)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.weight <= 0:
            raise ValueError("weight 必须大于 0")
        if self.timeout <= 0:
            raise ValueError("timeout 必须大于 0")
        if self.max_retries < 0:
            raise ValueError("max_retries 不能为负数")


@dataclass
class ModelGatewaySettings:
    """模型网关整体配置。"""

    enabled: bool = True
    default_model: str = "gpt-4.1-mini"
    audit_enabled: bool = True
    endpoints: List[ModelEndpointSettings] = field(default_factory=list)

    def enabled_endpoints(self) -> List[ModelEndpointSettings]:
        return [endpoint for endpoint in self.endpoints if endpoint.enabled]


__all__ = ["ModelGatewaySettings", "ModelEndpointSettings"]
