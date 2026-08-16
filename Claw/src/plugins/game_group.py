"""游戏群消息插件 — 玩家查询状态（淘汰统一由猎人在工作群执行）

指令格式：
  查询状态
"""
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import EventPlainText
import config
from utils.db import (
    get_dew_stats, get_player_stats,
)
from utils.timer_logic import is_game_active, is_game_running, get_remaining_display



game_matcher = on_message(priority=10, block=False)


@game_matcher.handle()
async def handle_game_group_msg(
    bot: Bot, event: GroupMessageEvent, msg: str = EventPlainText()
):
    # 仅游戏群
    gid = config.get_game_group()
    if gid == 0 or event.group_id != gid:
        return

    if not await is_game_running():
        return

    text = msg.strip()

    # ===== 查询状态 =====
    if text == "查询状态":
        ds = await get_dew_stats()
        stats = await get_player_stats()
        remaining = await get_remaining_display()

        # 存活率计算
        total = stats.get("total", 0)
        alive = stats.get("存活", 0)
        rate = round(alive / total * 100) if total else 0

        msg = (
            f"=== 游戏状态 ===\n"
            f"倒计时：{remaining}\n"
            f"{'-' * 15}\n"
            f"存活：{alive}人\n"
            f"淘汰：{stats.get('淘汰', 0)}人\n"
            f"复活：{stats.get('复活', 0)}人\n"
            f"总人数：{total}人\n"
            f"存活率：{rate}%"
        )
        await bot.send(event, msg)
        return
