# SPDX-License-Identifier: GPL-3.0-or-later
"""统一广播函数 — 三群消息发送

群类型：
  game_group    — 游戏群（玩家交流、低频播报）
  work_group    — 工作群（NPC/猎人上报、高频播报）
  backend_group — 后台群（管理员操作、大盘数据）

用法：
  from utils.broadcast import send_game_group, send_work_group, send_backend_group, send_all_groups
  await send_game_group("消息")
"""
from nonebot import get_bot
from nonebot.adapters.onebot.v11 import Bot
import config


async def _safe_send(bot: Bot, group_id: int, message: str, tag: str = ""):
    """安全发送群消息，失败只打印不抛异常"""
    try:
        if group_id and group_id > 0:
            await bot.send_group_msg(group_id=group_id, message=message)
    except Exception as e:
        label = tag or f"群{group_id}"
        print(f"[广播] 发送到{label}失败: {e}")


async def send_game_group(message: str):
    """发送到游戏群"""
    try:
        bot: Bot = get_bot()  # type: ignore
        await _safe_send(bot, config.get_game_group(), message, "游戏群")
    except Exception as e:
        print(f"[广播] 获取Bot失败: {e}")


async def send_work_group(message: str):
    """发送到工作群"""
    try:
        bot: Bot = get_bot()  # type: ignore
        await _safe_send(bot, config.get_work_group(), message, "工作群")
    except Exception as e:
        print(f"[广播] 获取Bot失败: {e}")


async def send_backend_group(message: str):
    """发送到后台群"""
    try:
        bot: Bot = get_bot()  # type: ignore
        await _safe_send(bot, config.get_backend_group(), message, "后台群")
    except Exception as e:
        print(f"[广播] 获取Bot失败: {e}")


async def send_all_groups(message: str):
    """发送到所有配置的群（自定义播报用）"""
    try:
        bot: Bot = get_bot()  # type: ignore
        await _safe_send(bot, config.get_game_group(), message, "游戏群")
        await _safe_send(bot, config.get_work_group(), message, "工作群")
        await _safe_send(bot, config.get_backend_group(), message, "后台群")
    except Exception as e:
        print(f"[广播] 获取Bot失败: {e}")
