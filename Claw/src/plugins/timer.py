# SPDX-License-Identifier: GPL-3.0-or-later
"""计时器和自适应播报调度插件"""
import asyncio
from datetime import datetime
from nonebot import get_bot, get_driver
from nonebot.adapters.onebot.v11 import Bot
import config
from utils.db import get_dew_stats, get_golden_dew_stats, get_player_stats, get_dew_target, get_expired_cooldowns, remove_cooldown
from utils.broadcast import send_game_group, send_work_group, send_backend_group
from utils.timer_logic import (
    end_game,
    get_remaining_seconds,
    get_remaining_display,
    get_remaining_ratio,
    get_broadcast_interval_minutes,
    is_game_running,
)

# 定时播报任务句柄
_broadcast_task: asyncio.Task | None = None


async def _broadcast_loop():
    """自适应播报主循环"""
    last_interval = 0
    last_broadcast_time: datetime | None = None

    while True:
        try:
            if not await is_game_running():
                await asyncio.sleep(5)
                continue

            now = datetime.now()
            remaining = await get_remaining_seconds()

            # 游戏时间到
            if remaining <= 0:
                ds = await get_dew_stats()
                gs = await get_golden_dew_stats()
                stats = await get_player_stats()
                await send_game_group(
                    f"极限挑战时间到！\n"
                    f"金露水：库存{gs['available']} 已用{gs['used']}\n"
                    f"玩家：存活{stats.get('存活',0)} 淘汰{stats.get('淘汰',0)} 复活{stats.get('复活',0)}"
                )
                await send_work_group(f"[游戏结束] 露水 {ds['collected_value']}/{ds['target']}滴 | 金露水 库存{gs['available']}/已用{gs['used']}")
                await send_backend_group(f"[大盘] 游戏结束 | 露水{ds['collected_value']}/{ds['target']}滴 | 存活{stats.get('存活',0)} 淘汰{stats.get('淘汰',0)} 复活{stats.get('复活',0)}")
                await end_game()
                break

            # 最后30分钟提示可开狂欢模式
            if remaining <= 30 * 60:
                from utils.db import get_frenzy_mode, get_game_state, set_game_state
                if not await get_frenzy_mode() and await get_game_state("frenzy_hint_given") != "1":
                    await set_game_state("frenzy_hint_given", "1")
                    await send_game_group("[提示] 游戏进入最后30分钟")
                    await send_work_group("[提示] 最后30分钟，可开启狂欢模式")

            # 检查露水滴数达标（胜利判定）
            ds = await get_dew_stats()
            from utils.db import get_game_state as _gs_check, set_game_state as _set_gs
            vic = await _gs_check("victory_announced")
            if ds['collected_value'] >= ds['target'] and vic != "1":
                await _set_gs("victory_announced", "1")
                # 游戏群不播报达标预告（保留工作群/后台群）
                await send_work_group(f"[达标] 露水收集达标！{ds['collected_value']}/{ds['target']}滴")
                await send_backend_group(f"[大盘] 露水达标！{ds['collected_value']}/{ds['target']}滴")

            # 计算当前播报间隔
            interval = await get_broadcast_interval_minutes()
            interval_seconds = interval * 60

            # 首次播报 或 到达播报时间 或 间隔缩短了
            should_broadcast = (
                last_broadcast_time is None
                or (now - last_broadcast_time).total_seconds() >= interval_seconds
                or (interval < last_interval and last_interval > 0)
            )

            if should_broadcast:
                ds = await get_dew_stats()
                gs = await get_golden_dew_stats()
                stats = await get_player_stats()
                remaining_display = await get_remaining_display()
                ratio = await get_remaining_ratio()
                next_interval = await get_broadcast_interval_minutes()

                # 游戏群播报（不含露水实时数量，玩家不得知晓进度）
                game_msg = (
                    f"倒计时：{remaining_display}\n"
                    f"下次播报：{next_interval}分钟后"
                )
                # 工作群播报（含露水进度，NPC/猎人可见）
                work_msg = (
                    f"倒计时：{remaining_display}\n"
                    f"露水收集：{ds['collected_value']}/{ds['target']}滴\n"
                    f"下次播报：{next_interval}分钟后"
                )

                if ratio <= 0.05:
                    game_msg = "最后冲刺！\n" + game_msg
                    work_msg = "最后冲刺！\n" + work_msg
                elif ratio <= 0.20:
                    game_msg = "比赛进入白热化阶段！\n" + game_msg
                    work_msg = "比赛进入白热化阶段！\n" + work_msg

                await send_game_group(game_msg)
                await send_work_group(work_msg)

                # 后台群大盘（每次播报时同步）
                dew_pct = round(ds["collected_value"]/ds["target"]*100) if ds["target"] else 0
                await send_backend_group(
                    f"[大盘] 倒计时{remaining_display} | 露水{ds['collected_value']}/{ds['target']}滴({dew_pct}%) | "
                    f"金露水库存{gs['available']} | "
                    f"存活{stats.get('存活',0)} 淘汰{stats.get('淘汰',0)} 复活{stats.get('复活',0)}"
                )

                last_broadcast_time = now
                last_interval = interval

            # 检查过期冷却并播报
            expired = await get_expired_cooldowns()
            for c in expired:
                name = c['hunter_name'] or c['hunter_key']
                type_names = {"capture":"淘汰冷却","static_card":"静止卡","shield_card":"护盾卡"}
                t = type_names.get(c["cooldown_type"], c["cooldown_type"])
                await send_game_group(f"[冷却] 猎人{name} {t}冷却已结束")
                await remove_cooldown(c["id"])

            await asyncio.sleep(10)  # 每10秒检查一次

        except Exception as e:
            import traceback
            err_detail = f"[播报] 循环异常: {e}\n{traceback.format_exc()}"
            print(err_detail)
            # 写异常日志到 data 目录
            try:
                from pathlib import Path
                log_dir = Path(__file__).resolve().parent.parent / "data"
                log_dir.mkdir(parents=True, exist_ok=True)
                with open(log_dir / "broadcast_errors.log", "a", encoding="utf-8") as f:
                    from datetime import datetime
                    f.write(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {err_detail}\n")
            except:
                pass
            await asyncio.sleep(15)


def start_broadcast_loop():
    """启动播报循环"""
    global _broadcast_task
    if _broadcast_task is None or _broadcast_task.done():
        _broadcast_task = asyncio.create_task(_broadcast_loop())


# NoneBot 启动后自动开始播报循环
driver = get_driver()


@driver.on_startup
async def _on_startup():
    start_broadcast_loop()
