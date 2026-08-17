# SPDX-License-Identifier: GPL-3.0-or-later
"""计时器逻辑 - 管理倒计时、暂停恢复、自适应播报间隔"""
from datetime import datetime, timedelta
from utils.db import get_game_state, set_game_state, set_frenzy_mode


async def start_game(duration_minutes: int) -> bool:
    """开始游戏计时"""
    status = await get_game_state("status")
    if status == "running":
        return False
    await set_game_state("status", "running")
    await set_game_state("duration_minutes", str(duration_minutes))
    await set_game_state("start_time", datetime.now().isoformat())
    await set_game_state("elapsed_seconds", "0")
    await set_game_state("pause_time", "")
    # 重置：清空全局任务免疫 + 关闭狂欢模式 + 重置提示标志
    await set_game_state("global_task_complete_at", "")
    await set_frenzy_mode(False)
    await set_game_state("frenzy_hint_given", "0")
    await set_game_state("victory_announced", "0")
    return True


async def pause_game() -> bool:
    """暂停游戏"""
    status = await get_game_state("status")
    if status != "running":
        return False
    # 记录已经过时间
    elapsed = await _calc_elapsed()
    await set_game_state("elapsed_seconds", str(elapsed))
    await set_game_state("status", "paused")
    await set_game_state("pause_time", datetime.now().isoformat())
    await set_game_state("start_time", "")
    return True


async def resume_game() -> bool:
    """恢复游戏"""
    status = await get_game_state("status")
    if status != "paused":
        return False
    await set_game_state("status", "running")
    await set_game_state("start_time", datetime.now().isoformat())
    # elapsed_seconds 保持不变，继续累积
    return True


async def end_game() -> bool:
    """结束游戏"""
    status = await get_game_state("status")
    if status in ("idle", "ended"):
        return False
    elapsed = await _calc_elapsed()
    await set_game_state("status", "ended")
    await set_game_state("elapsed_seconds", str(elapsed))
    await set_game_state("start_time", "")
    await set_game_state("pause_time", "")
    return True


async def _calc_elapsed() -> int:
    """计算当前已经过的秒数"""
    status = await get_game_state("status")
    base_elapsed = int(await get_game_state("elapsed_seconds") or 0)

    if status == "running":
        start_str = await get_game_state("start_time")
        if start_str:
            start_dt = datetime.fromisoformat(start_str)
            return base_elapsed + int((datetime.now() - start_dt).total_seconds())
    return base_elapsed


async def get_remaining_seconds() -> int:
    """获取剩余秒数"""
    duration = int(await get_game_state("duration_minutes")) * 60
    elapsed = await _calc_elapsed()
    return max(0, duration - elapsed)


async def get_remaining_display() -> str:
    """获取可读的剩余时间"""
    secs = await get_remaining_seconds()
    minutes = secs // 60
    seconds = secs % 60
    return f"{minutes:02d}:{seconds:02d}"


async def get_remaining_ratio() -> float:
    """获取剩余时间比例 0.0~1.0"""
    duration = int(await get_game_state("duration_minutes")) * 60
    if duration == 0:
        return 0.0
    remaining = await get_remaining_seconds()
    return remaining / duration


async def get_broadcast_interval_minutes() -> int:
    """根据剩余时间比例计算播报间隔（分钟）"""
    from config import BROADCAST_SCHEDULE

    ratio = await get_remaining_ratio()
    for threshold, interval in BROADCAST_SCHEDULE:
        if ratio > threshold:
            return interval
    return BROADCAST_SCHEDULE[-1][1]


async def is_game_active() -> bool:
    """游戏是否在进行中"""
    status = await get_game_state("status")
    return status in ("running", "paused")


async def is_game_running() -> bool:
    """游戏是否正在计时（非暂停）"""
    return await get_game_state("status") == "running"


async def get_game_status_display() -> str:
    """获取游戏状态的中文显示"""
    status = await get_game_state("status")
    status_map = {
        "idle": "未开始",
        "running": "进行中",
        "paused": "已暂停",
        "ended": "已结束",
    }
    return status_map.get(status, "未知")
