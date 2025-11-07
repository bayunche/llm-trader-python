from __future__ import annotations

"""模型网关核心服务，实现 OpenAI 兼容转发与调用审计。"""

import json
import logging
import random
import time
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional

import httpx
from llm_trader.db.models import LLMCallAudit
from llm_trader.db.models.enums import ModelRole
from llm_trader.db.session import create_session_factory
from llm_trader.model_gateway.config import ModelEndpointSettings, ModelGatewaySettings
from llm_trader.model_gateway.loader import load_gateway_settings
LOGGER = logging.getLogger("llm_trader.model_gateway")


@dataclass
class EndpointStats:
    success_count: int = 0
    failure_count: int = 0
    consecutive_failures: int = 0
    opened_until: Optional[float] = None
    last_error: Optional[str] = None


@dataclass
class GatewayResponse:
    """封装网关返回结果，便于上层访问原始 JSON。"""

    payload: Dict[str, object]
    endpoint: ModelEndpointSettings
    latency_ms: int


class ModelGateway:
    """模型网关，兼容 OpenAI Chat Completions 接口。"""

    def __init__(
        self,
        *,
        settings: Optional[ModelGatewaySettings] = None,
        session_factory=None,
        client: Optional[httpx.Client] = None,
    ) -> None:
        if session_factory is None:
            session_factory = create_session_factory()
        self._session_factory = session_factory
        if settings is None:
            resolved_settings = load_gateway_settings(self._session_factory)
        else:
            resolved_settings = settings
        self._settings = resolved_settings
        self._stats: Dict[str, EndpointStats] = {endpoint.name: EndpointStats() for endpoint in resolved_settings.endpoints}
        timeout = self._max_timeout(resolved_settings)
        self._client = client or httpx.Client(timeout=timeout or 30.0)

    @property
    def settings(self) -> ModelGatewaySettings:
        return self._settings

    def close(self) -> None:
        try:
            self._client.close()
        except Exception:  # pragma: no cover - 关闭异常不影响主流程
            LOGGER.debug("关闭模型网关 http 客户端失败", exc_info=True)

    def chat_completions(
        self,
        payload: Dict[str, object],
        *,
        model: Optional[str] = None,
        role: ModelRole = ModelRole.ACTOR,
        decision_id: Optional[str] = None,
    ) -> GatewayResponse:
        if not self._settings.enabled:
            raise RuntimeError("模型网关已禁用")

        endpoints = [endpoint for endpoint in self._settings.enabled_endpoints() if self._is_endpoint_available(endpoint)]
        if not endpoints:
            endpoints = list(self._settings.enabled_endpoints())
        if not endpoints:
            raise RuntimeError("模型网关没有可用端点")

        request_model = model or payload.get("model") or self._settings.default_model
        request_body = dict(payload)
        request_body["model"] = request_model
        attempts = self._weighted_attempts(endpoints)
        last_exception: Optional[Exception] = None
        for endpoint in attempts:
            if not self._is_endpoint_available(endpoint):
                continue
            start = time.perf_counter()
            try:
                response_json = self._invoke_endpoint(endpoint, request_body)
                latency_ms = int((time.perf_counter() - start) * 1000)
                self._record_success(endpoint)
                self._record_audit(
                    endpoint=endpoint,
                    payload=request_body,
                    response=response_json,
                    role=role,
                    decision_id=decision_id,
                    latency_ms=latency_ms,
                )
                return GatewayResponse(payload=response_json, endpoint=endpoint, latency_ms=latency_ms)
            except Exception as exc:  # pragma: no cover - 失败时尝试其它端点
                LOGGER.warning(
                    "模型端点调用失败，将尝试下一个端点",
                    extra={"endpoint": endpoint.name, "error": str(exc)},
                )
                self._record_failure(endpoint, exc)
                last_exception = exc
        assert last_exception is not None
        raise last_exception

    def __del__(self) -> None:  # pragma: no cover - 析构时关闭客户端
        try:
            self.close()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------
    def _invoke_endpoint(self, endpoint: ModelEndpointSettings, request_body: Dict[str, object]) -> Dict[str, object]:
        url = f"{endpoint.base_url.rstrip('/')}/v1/chat/completions"
        headers = {"Content-Type": "application/json"}
        headers.update({k: str(v) for k, v in endpoint.headers.items()})
        if endpoint.metadata:
            extra_headers = endpoint.metadata.get("headers")
            if isinstance(extra_headers, dict):
                headers.update({k: str(v) for k, v in extra_headers.items()})
        if endpoint.api_key:
            headers["Authorization"] = f"Bearer {endpoint.api_key}"
        payload = dict(endpoint.default_params)
        if endpoint.metadata:
            extra_params = endpoint.metadata.get("default_params")
            if isinstance(extra_params, dict):
                payload.update(extra_params)
        payload.update(request_body)
        response = self._client.post(url, json=payload, headers=headers, timeout=endpoint.timeout)
        response.raise_for_status()
        return response.json()

    def _weighted_attempts(self, endpoints: Iterable[ModelEndpointSettings]) -> List[ModelEndpointSettings]:
        weighted: List[ModelEndpointSettings] = []
        for endpoint in endpoints:
            repeat = max(1, int(endpoint.weight))
            weighted.extend([endpoint] * repeat)
        random.shuffle(weighted)
        # fallback 保证覆盖所有端点
        seen = []
        for endpoint in weighted:
            if endpoint not in seen:
                seen.append(endpoint)
        for endpoint in endpoints:
            if endpoint not in seen:
                seen.append(endpoint)
        return seen

    def update_settings(self, settings: ModelGatewaySettings) -> None:
        """刷新网关配置，并在必要时更新 HTTP 客户端超时时间。"""

        self._settings = settings
        names = {endpoint.name for endpoint in settings.endpoints}
        self._stats = {name: self._stats.get(name, EndpointStats()) for name in names}
        timeout = self._max_timeout(settings)
        try:
            self._client.timeout = timeout or 30.0
        except Exception:  # pragma: no cover - httpx 旧版本不支持动态修改
            self._client = httpx.Client(timeout=timeout or 30.0)

    def metrics_snapshot(self) -> List[Dict[str, Any]]:
        now = time.time()
        snapshot: List[Dict[str, Any]] = []
        for endpoint in self._settings.endpoints:
            stats = self._stats.setdefault(endpoint.name, EndpointStats())
            available = self._is_endpoint_available(endpoint)
            opened_until = stats.opened_until
            opened_until_dt = (
                datetime.fromtimestamp(opened_until, tz=timezone.utc)
                if opened_until and opened_until > now
                else None
            )
            snapshot.append(
                {
                    "endpoint": endpoint.name,
                    "enabled": endpoint.enabled,
                    "available": available,
                    "success_count": stats.success_count,
                    "failure_count": stats.failure_count,
                    "consecutive_failures": stats.consecutive_failures,
                    "opened_until": opened_until_dt,
                    "last_error": stats.last_error,
                }
            )
        return snapshot

    def _record_audit(
        self,
        *,
        endpoint: ModelEndpointSettings,
        payload: Dict[str, object],
        response: Dict[str, object],
        role: ModelRole,
        decision_id: Optional[str],
        latency_ms: int,
    ) -> None:
        if not self._settings.audit_enabled:
            return
        usage = response.get("usage", {}) if isinstance(response, dict) else {}
        prompt_tokens = int(usage.get("prompt_tokens", 0) or 0)
        completion_tokens = int(usage.get("completion_tokens", 0) or 0)
        total_cost = self._estimate_cost(endpoint, prompt_tokens, completion_tokens)
        messages = payload.get("messages", [])
        try:
            serialised_messages = json.dumps(messages, ensure_ascii=False, sort_keys=True)
        except (TypeError, ValueError):
            serialised_messages = json.dumps(str(messages), ensure_ascii=False)
        prompt_hash = uuid.uuid5(uuid.NAMESPACE_OID, serialised_messages).hex
        trace_id = uuid.uuid4().hex
        with self._session_factory() as session:
            audit = LLMCallAudit(
                trace_id=trace_id,
                decision_id=decision_id,
                role=role,
                provider=endpoint.name,
                model=str(payload.get("model", self._settings.default_model)),
                prompt_hash=prompt_hash,
                tokens_prompt=prompt_tokens,
                tokens_completion=completion_tokens,
                latency_ms=latency_ms,
                cost=total_cost,
                created_at=datetime.now(tz=timezone.utc),
            )
            session.add(audit)

    def _estimate_cost(
        self,
        endpoint: ModelEndpointSettings,
        prompt_tokens: int,
        completion_tokens: int,
    ) -> float:
        prompt_cost = endpoint.prompt_cost_per_1k * prompt_tokens / 1000.0
        completion_cost = endpoint.completion_cost_per_1k * completion_tokens / 1000.0
        return round(prompt_cost + completion_cost, 6)

    def _max_timeout(self, settings: ModelGatewaySettings) -> Optional[float]:
        if not settings.endpoints:
            return None
        return max(endpoint.timeout for endpoint in settings.endpoints)

    def _is_endpoint_available(self, endpoint: ModelEndpointSettings) -> bool:
        if not endpoint.enabled:
            return False
        stats = self._stats.setdefault(endpoint.name, EndpointStats())
        opened_until = stats.opened_until
        if opened_until is None:
            return True
        now = time.time()
        if opened_until <= now:
            stats.opened_until = None
            stats.consecutive_failures = 0
            return True
        return False

    def _record_success(self, endpoint: ModelEndpointSettings) -> None:
        stats = self._stats.setdefault(endpoint.name, EndpointStats())
        stats.success_count += 1
        stats.consecutive_failures = 0
        stats.opened_until = None
        stats.last_error = None

    def _record_failure(self, endpoint: ModelEndpointSettings, exc: Exception) -> None:
        stats = self._stats.setdefault(endpoint.name, EndpointStats())
        stats.failure_count += 1
        stats.consecutive_failures += 1
        stats.last_error = str(exc)
        breaker = endpoint.circuit_breaker or {}
        if endpoint.metadata:
            metadata_breaker = endpoint.metadata.get("circuit_breaker")
            if isinstance(metadata_breaker, dict):
                breaker = {**breaker, **metadata_breaker}
        threshold = int(breaker.get("failure_threshold", 3) or 3)
        recovery = float(breaker.get("recovery_seconds", 60) or 60.0)
        if stats.consecutive_failures >= threshold:
            stats.opened_until = time.time() + recovery
            LOGGER.warning(
                "模型端点熔断", extra={"endpoint": endpoint.name, "recovery_seconds": recovery}
            )


__all__ = ["ModelGateway", "GatewayResponse"]
