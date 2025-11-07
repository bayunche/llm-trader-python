"""模型网关端点配置管理 API。"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, HttpUrl
from sqlmodel import select

from llm_trader.api.schemas import (
    ModelEndpointItem,
    ModelEndpointListResponse,
    ModelEndpointResponse,
    ModelEndpointMetricsResponse,
)
from llm_trader.api.security import require_api_key
from llm_trader.db.models.config import ModelEndpoint
from llm_trader.db.session import session_scope
from llm_trader.model_gateway import ModelEndpointSettings, ModelGateway, ModelGatewaySettings
from llm_trader.model_gateway.loader import build_gateway_settings_from_records


router = APIRouter(prefix="/config/models", tags=["config"], dependencies=[Depends(require_api_key)])
gateway: Optional[ModelGateway] = None


class ModelEndpointUpsertRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    model_alias: str = Field(..., min_length=1)
    provider: str = Field(..., min_length=1)
    endpoint_url: HttpUrl
    auth_type: str = Field(default="api_key")
    auth_secret_ref: str = Field(..., min_length=1)
    weight: float = Field(default=1.0, gt=0)
    timeout: float = Field(default=30.0, gt=0)
    max_retries: int = Field(default=2, ge=0)
    enabled: bool = True
    default_params: Dict[str, Any] = Field(default_factory=dict)
    headers: Dict[str, Any] = Field(default_factory=dict)
    circuit_breaker: Dict[str, Any] = Field(default_factory=dict)
    prompt_cost_per_1k: float = Field(default=0.0, ge=0.0)
    completion_cost_per_1k: float = Field(default=0.0, ge=0.0)


def _utcnow() -> datetime:
    return datetime.now(tz=timezone.utc)


def _record_to_payload(record: ModelEndpoint) -> ModelEndpointItem:
    routing = record.routing or {}
    retry = record.retry_policy or {}
    cost = record.cost_estimate or {}
    return ModelEndpointItem(
        model_alias=record.model_alias,
        provider=record.provider,
        endpoint_url=record.endpoint_url,
        auth_type=record.auth_type,
        auth_secret_ref=record.auth_secret_ref,
        weight=float(routing.get("weight", 1.0) or 1.0),
        timeout=float(retry.get("timeout", 30.0) or 30.0),
        max_retries=int(retry.get("max_retries", 2) or 2),
        enabled=record.enabled,
        default_params=record.default_params or {},
        headers=record.metadata or {},
        circuit_breaker=record.circuit_breaker or {},
        prompt_cost_per_1k=float(cost.get("prompt_cost_per_1k", 0.0) or 0.0),
        completion_cost_per_1k=float(cost.get("completion_cost_per_1k", 0.0) or 0.0),
        created_at=record.created_at,
        updated_at=record.updated_at,
    )


def _refresh_gateway_from_db() -> None:
    with session_scope() as session:
        records = session.exec(select(ModelEndpoint)).all()
    _get_gateway().update_settings(build_gateway_settings_from_records(records))


@router.get("", response_model=ModelEndpointListResponse)
async def list_model_endpoints() -> ModelEndpointListResponse:
    with session_scope() as session:
        records = session.exec(select(ModelEndpoint)).all()
    payload = [_record_to_payload(record) for record in records]
    return ModelEndpointListResponse(code="OK", message="success", data=payload)


@router.put("", response_model=ModelEndpointResponse)
async def upsert_model_endpoint(request: ModelEndpointUpsertRequest) -> ModelEndpointResponse:
    now = _utcnow()
    with session_scope() as session:
        record = session.get(ModelEndpoint, request.model_alias)
        if record is None:
            record = ModelEndpoint(
                model_alias=request.model_alias,
                provider=request.provider,
                endpoint_url=str(request.endpoint_url),
                auth_type=request.auth_type,
                auth_secret_ref=request.auth_secret_ref,
                default_params=request.default_params,
                retry_policy={"timeout": request.timeout, "max_retries": request.max_retries},
                routing={"weight": request.weight},
                circuit_breaker=request.circuit_breaker,
                cost_estimate={
                    "prompt_cost_per_1k": request.prompt_cost_per_1k,
                    "completion_cost_per_1k": request.completion_cost_per_1k,
                },
                enabled=request.enabled,
                metadata=request.headers,
                created_at=now,
                updated_at=now,
            )
            session.add(record)
        else:
            record.provider = request.provider
            record.endpoint_url = str(request.endpoint_url)
            record.auth_type = request.auth_type
            record.auth_secret_ref = request.auth_secret_ref
            record.default_params = request.default_params
            record.retry_policy = {"timeout": request.timeout, "max_retries": request.max_retries}
            record.routing = {"weight": request.weight}
            record.circuit_breaker = request.circuit_breaker
            record.cost_estimate = {
                "prompt_cost_per_1k": request.prompt_cost_per_1k,
                "completion_cost_per_1k": request.completion_cost_per_1k,
            }
            record.enabled = request.enabled
            record.metadata = request.headers
            record.updated_at = now
        session.flush()
        payload = _record_to_payload(record)
    _refresh_gateway_from_db()
    return ModelEndpointResponse(code="OK", message="success", data=payload)


@router.get("/metrics", response_model=ModelEndpointMetricsResponse)
async def model_gateway_metrics() -> ModelEndpointMetricsResponse:
    metrics = _get_gateway().metrics_snapshot()
    return ModelEndpointMetricsResponse(code="OK", message="success", data=metrics)

def _get_gateway() -> ModelGateway:
    """延迟创建模型网关，避免模块导入阶段即连接数据库。"""

    global gateway
    if gateway is None:
        gateway = ModelGateway()
    return gateway
