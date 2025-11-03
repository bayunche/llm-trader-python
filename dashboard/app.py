"""Streamlit 仪表盘入口。"""

from __future__ import annotations

import importlib
import os
import sys
from pathlib import Path
from typing import List, Tuple

import altair as alt
import pandas as pd
import streamlit as st

if __package__ is None or __package__ == "":
    current_dir = Path(__file__).resolve().parent
    project_root = current_dir.parent
    src_dir = project_root / "src"
    if str(src_dir) not in sys.path:
        sys.path.insert(0, str(src_dir))
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))
    data = importlib.import_module("dashboard.data")
else:
    from . import data  # type: ignore[no-redef]
from llm_trader.strategy.llm_generator import LLMStrategyContext, LLMStrategyGenerator


def _render_equity_multi(pairs: List[Tuple[str, str]]) -> None:
    records: List[pd.DataFrame] = []
    for strategy_id, session_id in pairs:
        raw = data.get_equity_curve(strategy_id, session_id)
        if not raw:
            continue
        df = pd.DataFrame(raw)
        df["timestamp"] = pd.to_datetime(df["timestamp"])
        df["series"] = f"{strategy_id}/{session_id}"
        records.append(df)
    if not records:
        st.info("所选策略暂无资金曲线数据")
        return
    combined = pd.concat(records, ignore_index=True)
    chart = (
        alt.Chart(combined)
        .mark_line()
        .encode(
            x="timestamp:T",
            y="equity:Q",
            color="series:N",
            tooltip=["series:N", "timestamp:T", "equity:Q", "cash:Q"],
        )
        .interactive()
    )
    st.subheader("资金曲线对比")
    st.altair_chart(chart, use_container_width=True)

    latest = combined.sort_values("timestamp").groupby("series").tail(1)
    st.dataframe(latest[["series", "timestamp", "cash", "equity"]])
    csv = combined.to_csv(index=False).encode("utf-8")
    st.download_button("下载资金曲线 CSV", csv, file_name="equity_curve.csv")


def _render_orders(strategy_id: str, session_id: str) -> pd.DataFrame:
    records = data.get_orders(strategy_id, session_id)
    if not records:
        st.info("暂无订单数据")
        return pd.DataFrame()
    df = pd.DataFrame(records).sort_values("created_at")
    st.dataframe(df)
    st.download_button(
        "下载订单 CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"orders_{strategy_id}_{session_id}.csv",
    )
    return df


def _render_trades(strategy_id: str, session_id: str) -> pd.DataFrame:
    records = data.get_trades(strategy_id, session_id)
    if not records:
        st.info("暂无成交数据")
        return pd.DataFrame()
    df = pd.DataFrame(records).sort_values("timestamp")
    st.dataframe(df)
    st.download_button(
        "下载成交 CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"trades_{strategy_id}_{session_id}.csv",
    )
    return df


def _render_llm_logs(strategy_id: str, session_id: str) -> List[dict]:
    st.subheader("LLM 策略日志")
    records = data.get_llm_logs(strategy_id, session_id, limit=50)
    if not records:
        st.info("暂无日志数据")
        return []
    for record in records:
        st.markdown(f"**时间**：{record.get('timestamp')}")
        st.markdown(f"**策略目标**：{record.get('objective', '')}")
        if record.get("suggestion_description"):
            st.markdown(f"**策略说明**：{record['suggestion_description']}")
        with st.expander("Prompt"):
            st.code(record.get("prompt", ""), language="markdown")
        with st.expander("Response"):
            st.code(record.get("response", ""), language="json")
        st.markdown("---")
    return records


def _render_llm_assistant(strategy_id: str, session_id: str, logs: List[dict]) -> None:
    st.subheader("LLM 辅助诊断")
    question = st.text_area(
        "自然语言提问（例如：'解释当前策略风险点'）",
        key=f"assistant-{strategy_id}-{session_id}",
    )
    if st.button("生成回答", key=f"assistant-btn-{strategy_id}-{session_id}"):
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            st.warning("请先设置 OPENAI_API_KEY 环境变量")
            return
        last_log = logs[-1] if logs else {}
        context = LLMStrategyContext(
            objective=last_log.get("objective", question or "策略诊断"),
            symbols=last_log.get("symbols", []),
            indicators=last_log.get("indicators", []),
            historical_summary=last_log.get("quotes_summary", question or ""),
        )
        try:
            generator = LLMStrategyGenerator(api_key=api_key)
            suggestion = generator.generate(context)
            st.success(suggestion.description)
        except Exception as exc:  # pragma: no cover - 网络/凭据异常
            st.error(f"调用大模型失败：{exc}")


def _render_version_panel(strategy_ids: List[str]) -> None:
    st.sidebar.markdown("### 策略版本概览")
    for strategy_id in strategy_ids:
        versions = data.list_strategy_versions(strategy_id)
        if not versions:
            continue
        df = pd.DataFrame(
            [
                {
                    "version_id": v.version_id,
                    "run_id": v.run_id,
                    "created_at": v.created_at,
                    **(v.metrics or {}),
                }
                for v in versions
            ]
        )
        st.sidebar.markdown(f"**{strategy_id}**")
        st.sidebar.dataframe(df)


def main() -> None:
    st.set_page_config(page_title="LLM Trader Dashboard", layout="wide")
    st.title("LLM Trader 交易仪表盘")

    available_pairs = data.list_strategy_sessions()
    if not available_pairs:
        st.info("暂无交易数据，请先运行自动交易循环。")
        return

    options = [f"{item['strategy_id']}/{item['session_id']}" for item in available_pairs]
    mapping = {label: (item["strategy_id"], item["session_id"]) for label, item in zip(options, available_pairs)}

    with st.sidebar:
        st.caption("默认读取本地 data_store，请先运行交易循环生成数据。")
        selected_labels = st.multiselect("选择策略/会话", options, default=options[:1])

    if not selected_labels:
        st.warning("请选择至少一个策略/会话组合")
        return

    selected_pairs = [mapping[label] for label in selected_labels]
    strategy_ids = sorted({strategy for strategy, _ in selected_pairs})
    _render_version_panel(strategy_ids)

    _render_equity_multi(selected_pairs)

    tabs = st.tabs([f"{strategy}/{session}" for strategy, session in selected_pairs])
    for tab, (strategy, session) in zip(tabs, selected_pairs):
        with tab:
            st.markdown("### 策略详情")
            logs = _render_llm_logs(strategy, session)
            _render_llm_assistant(strategy, session, logs)
            st.markdown("### 订单流水")
            _render_orders(strategy, session)
            st.markdown("### 成交流水")
            _render_trades(strategy, session)


if __name__ == "__main__":
    main()
