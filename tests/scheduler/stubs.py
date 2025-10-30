"""调度测试桩。"""

EVENTS = []


def record_job(**kwargs) -> None:
    EVENTS.append(kwargs)
