from __future__ import annotations

"""模型网关配置加载工具。"""

from typing import Sequence

from sqlmodel import select

from llm_trader.db.models.config import ModelEndpoint
from llm_trader.model_gateway.config import ModelEndpointSettings, ModelGatewaySettings


def build_gateway_settings_from_records(
    records: Sequence[ModelEndpoint],
    *,
    base: ModelGatewaySettings | None = None,
) -> ModelGatewaySettings:
    """将数据库记录转换为 ModelGatewaySettings。"""

    settings = base or _default_settings()
    endpoints = []
    for record in records:
        routing = record.routing or {}
        retry = record.retry_policy or {}
        cost = record.cost_estimate or {}
        endpoints.append(
            ModelEndpointSettings(
                name=record.model_alias,
                base_url=record.endpoint_url,
                api_key=record.auth_secret_ref or None,
                weight=float(routing.get("weight", 1.0) or 1.0),
                timeout=float(retry.get("timeout", 30.0) or 30.0),
                max_retries=int(retry.get("max_retries", 2) or 2),
                enabled=record.enabled,
                prompt_cost_per_1k=float(cost.get("prompt_cost_per_1k", 0.0) or 0.0),
                completion_cost_per_1k=float(cost.get("completion_cost_per_1k", 0.0) or 0.0),
                default_params=record.default_params or {},
                headers=record.metadata or {},
                circuit_breaker=record.circuit_breaker or {},
            )
        )
    if endpoints:
        return ModelGatewaySettings(
            enabled=settings.enabled,
            default_model=settings.default_model,
            audit_enabled=settings.audit_enabled,
            endpoints=endpoints,
        )
    return settings


def load_gateway_settings(session_factory) -> ModelGatewaySettings:
    """从数据库加载模型网关配置，失败时回退到默认配置。"""

    try:
        with session_factory() as session:
            result = session.exec(select(ModelEndpoint)).all()
    except Exception:
        return _default_settings()
    return build_gateway_settings_from_records(result)


def _default_settings() -> ModelGatewaySettings:
    from llm_trader.config import get_settings

    return get_settings().model_gateway


__all__ = ["build_gateway_settings_from_records", "load_gateway_settings"]
