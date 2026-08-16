"""冷却机制 — 抓捕冷却 + 静止卡冷却 + 护盾卡冷却（数据库持久化）

冷却类型：
  capture     — 猎人抓捕冷却，默认20秒（狂欢模式40秒）
  static_card — 猎人被使用静止卡后的冷却，默认180秒（3分钟）
  shield_card — 猎人被使用护盾卡后的冷却，默认20秒

冷却结束播报由 timer.py 轮询处理，Bot 重启后冷却不丢失。
"""
from utils.db import add_cooldown as _add, check_cooldown as _check

# 冷却配置
CAPTURE_COOLDOWN_SECONDS = 20
FRENZY_CAPTURE_COOLDOWN_SECONDS = 40
STATIC_CARD_COOLDOWN_SECONDS = 180
SHIELD_CARD_COOLDOWN_SECONDS = 20


async def check_capture_cooldown(hunter_qq: int) -> tuple[bool, int]:
    """检查猎人抓捕是否在冷却中。返回 (can_capture, remaining_seconds)"""
    return await _check("capture", str(hunter_qq))


async def set_capture_cooldown(hunter_qq: int, hunter_name: str = "", seconds: int = None):
    """设置猎人抓捕冷却。seconds=None 时根据狂欢模式自动选 20 或 40"""
    if seconds is None:
        from utils.db import get_frenzy_mode
        frenzy = await get_frenzy_mode()
        seconds = FRENZY_CAPTURE_COOLDOWN_SECONDS if frenzy else CAPTURE_COOLDOWN_SECONDS
    await _add("capture", str(hunter_qq), hunter_name, seconds)


async def check_static_card_cooldown(hunter_name: str) -> tuple[bool, int]:
    """检查猎人静止卡是否在冷却中"""
    return await _check("static_card", hunter_name)


async def set_static_card_cooldown(hunter_name: str, seconds: int = STATIC_CARD_COOLDOWN_SECONDS):
    """设置猎人静止卡冷却"""
    await _add("static_card", hunter_name, hunter_name, seconds)


async def check_shield_card_cooldown(hunter_name: str) -> tuple[bool, int]:
    """检查猎人护盾卡是否在冷却中"""
    return await _check("shield_card", hunter_name)


async def set_shield_card_cooldown(hunter_name: str, seconds: int = SHIELD_CARD_COOLDOWN_SECONDS):
    """设置猎人护盾卡冷却"""
    await _add("shield_card", hunter_name, hunter_name, seconds)
