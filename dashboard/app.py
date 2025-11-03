"""Streamlit 仪表盘入口。"""

from __future__ import annotations

import importlib
import math
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


def _render_pipeline_status() -> None:
    """展示自动化流程最新状态。"""

    info = data.load_pipeline_status()
    status_path = info.get("path")
    if not info.get("available"):
        message = info.get("error") or "未检测到自动化流程状态文件"
        if status_path:
            st.info(f"{message}（期望路径：{status_path}）")
        else:
            st.info(message)
        return

    status_data = info.get("data") or {}
    st.subheader("最新自动化状态")
    if status_path:
        st.caption(f"状态文件：{status_path}")

    stages = status_data.get("stages") or []
    col_mode, col_stage = st.columns(2)
    with col_mode:
        st.metric("执行模式", status_data.get("execution_mode", "未知"))
    with col_stage:
        st.metric("阶段数", len(stages))

    warnings = status_data.get("warnings") or []
    for warning in warnings:
        st.warning(warning)

    if stages:
        stage_df = pd.DataFrame(stages)
        if "finished_at" in stage_df.columns:
            stage_df = stage_df.sort_values("finished_at", na_position="last")
        display_cols = [col for col in ["name", "status", "detail", "finished_at"] if col in stage_df.columns]
        st.dataframe(stage_df[display_cols])
        if any(stage.get("status") == "failed" for stage in stages):
            st.error("检测到失败阶段，请检查日志并重新执行自动化流程。")
        elif any(stage.get("status") == "blocked" for stage in stages):
            st.warning("流程被阻断，未执行真实交易。")
    else:
        st.info("尚未记录任何阶段信息。")


def _pagination_controls(prefix: str, total: int, *, default_size: int = 50) -> Tuple[int, int, int, int]:
    """渲染分页控件并返回 offset、page_size、page_index、max_page。"""

    if total <= 0:
        return 0, default_size, 1, 1
    options = [20, 50, 100, 200, 500]
    if default_size not in options:
        options.append(default_size)
    options = sorted(set(options))
    page_size = st.selectbox(
        "每页条数",
        options,
        index=options.index(default_size) if default_size in options else 0,
        key=f"{prefix}-page-size",
    )
    max_page = max(1, math.ceil(total / page_size))
    page_options = [str(index) for index in range(1, max_page + 1)]
    selected = st.selectbox(
        "页码",
        page_options,
        index=0,
        key=f"{prefix}-page-index",
    )
    page_index = int(selected)
    offset = (page_index - 1) * page_size
    return offset, page_size, page_index, max_page


def _format_template_label(identifier: str) -> str:
    if "/" in identifier:
        scenario, name = identifier.split("/", 1)
    else:
        scenario, name = "default", identifier
    return name if scenario == "default" else f"{scenario}/{name}"


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
    total = data.count_orders(strategy_id, session_id)
    if total == 0:
        st.info("暂无订单数据")
        return pd.DataFrame()
    offset, page_size, page_index, max_page = _pagination_controls(
        f"orders-{strategy_id}-{session_id}",
        total,
    )
    records = data.get_orders(strategy_id, session_id, limit=page_size, offset=offset)
    df = pd.DataFrame(records).sort_values("created_at")
    st.dataframe(df)
    st.caption(f"第 {page_index}/{max_page} 页，共 {total} 条订单")
    st.download_button(
        "下载订单 CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"orders_{strategy_id}_{session_id}.csv",
    )
    return df


def _render_trades(strategy_id: str, session_id: str) -> pd.DataFrame:
    total = data.count_trades(strategy_id, session_id)
    if total == 0:
        st.info("暂无成交数据")
        return pd.DataFrame()
    offset, page_size, page_index, max_page = _pagination_controls(
        f"trades-{strategy_id}-{session_id}",
        total,
        default_size=100,
    )
    records = data.get_trades(strategy_id, session_id, limit=page_size, offset=offset)
    df = pd.DataFrame(records).sort_values("timestamp")
    st.dataframe(df)
    st.caption(f"第 {page_index}/{max_page} 页，共 {total} 条成交")
    st.download_button(
        "下载成交 CSV",
        df.to_csv(index=False).encode("utf-8"),
        file_name=f"trades_{strategy_id}_{session_id}.csv",
    )
    return df


def _render_llm_logs(strategy_id: str, session_id: str) -> List[dict]:
    st.subheader("LLM 策略日志")
    total_logs = data.count_llm_logs(strategy_id, session_id)
    if total_logs == 0:
        st.info("暂无日志数据")
        return []
    limit_candidates = [value for value in (20, 50, 100, 200) if value < total_logs]
    limit_candidates.append(total_logs)
    default_value = 50 if 50 in limit_candidates else limit_candidates[0]
    selected_value = st.selectbox(
        "显示日志条数",
        limit_candidates,
        index=limit_candidates.index(default_value),
        format_func=lambda value: "全部" if value == total_logs else f"{value} 条",
        key=f"logs-limit-{strategy_id}-{session_id}",
    )
    if selected_value == total_logs:
        offset = 0
        limit = None
    else:
        limit = selected_value
        offset = max(total_logs - limit, 0)
    records = data.get_llm_logs(strategy_id, session_id, limit=limit, offset=offset)
    st.caption(f"最近展示 {len(records)} 条，共 {total_logs} 条日志")
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

    _render_pipeline_status()
    prompt_tab, trading_tab = st.tabs(["提示词管理", "交易数据"])

    with prompt_tab:
        st.subheader("策略提示词模板")
        templates = data.list_prompt_templates()
        if not templates:
            st.info("未发现任何提示词模板。")
        else:
            labels = {_format_template_label(item): item for item in templates}
            selected_label = st.selectbox("选择模板", list(labels.keys()), index=0)
            selected_template = labels[selected_label]
            template_info = data.load_prompt_template(selected_template)
            source = template_info.get("source", "default")
            updated_at = template_info.get("updated_at", "")
            scenario = template_info.get("scenario", "default")
            version_id = template_info.get("version_id", "")
            st.caption(
                f"场景：{scenario} | 来源：{source} | 当前版本：{version_id or '未知'} | 最近更新时间：{updated_at or '未知'}"
            )
            content = st.text_area(
                "模板内容（使用 {objective}、{symbols}、{indicators}、{historical_summary} 占位符）",
                value=template_info.get("content", ""),
                height=260,
                key=f"template-editor-{selected_template}",
            )
            history = template_info.get("history") or []
            if history:
                history_df = pd.DataFrame(history)[["version_id", "updated_at"]]
                st.dataframe(history_df, use_container_width=True)
                selected_version = st.selectbox(
                    "选择历史版本",
                    [item["version_id"] for item in history],
                    key=f"version-select-{selected_template}",
                )
                if st.button("恢复到所选版本", key=f"restore-{selected_template}"):
                    restored = data.restore_prompt_template_version(selected_template, selected_version)
                    st.success(f"已恢复到版本 {selected_version}")
                    st.experimental_rerun()
            col_save, col_reset = st.columns([2, 1])
            with col_save:
                if st.button("保存修改", key=f"save-{selected_template}"):
                    try:
                        result = data.save_prompt_template(selected_template, content)
                        st.success(f"模板已保存（更新时间：{result.get('updated_at')})")
                    except Exception as exc:
                        st.error(f"保存失败：{exc}")
            with col_reset:
                if st.button("重置为默认", key=f"reset-{selected_template}"):
                    try:
                        result = data.reset_prompt_template(selected_template)
                        st.success("已重置为默认模板")
                        st.experimental_rerun()
                    except Exception as exc:
                        st.error(f"重置失败：{exc}")
            st.info("保存后新模板将在下一次交易循环中生效。")

    with trading_tab:
        available_pairs = data.list_strategy_sessions()
        if not available_pairs:
            st.info("暂无交易数据，请先运行自动交易循环。")
            return

        options = [f"{item['strategy_id']}/{item['session_id']}" for item in available_pairs]
        mapping = {label: (item["strategy_id"], item["session_id"]) for label, item in zip(options, available_pairs)}

        with st.sidebar:
            st.caption("默认读取本地 data_store，请先运行交易循环生成数据。")
            if st.button("刷新数据缓存", key="refresh-cache"):
                data.invalidate_cache()
                st.experimental_rerun()
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
