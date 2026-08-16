"""诊断与测试插件 - 验证连接和配置是否正确"""
import nonebot
from nonebot import on_command, on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent, PrivateMessageEvent
from nonebot.params import EventPlainText
import config


# ============================================================
# /ping - 最简单的连通性测试，不检查群号，不检查游戏状态
# ============================================================
ping_cmd = on_command("ping", priority=1, block=True)


@ping_cmd.handle()
async def handle_ping(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    await ping_cmd.finish("pong! Claw Bot is alive.")


# ============================================================
# /debug - 显示当前配置和诊断信息
# ============================================================
debug_cmd = on_command("debug", priority=1, block=True)


@debug_cmd.handle()
async def handle_debug(bot: Bot, event: GroupMessageEvent | PrivateMessageEvent):
    msg = (
        f"=== Claw Bot Debug ===\n"
        f"GAME_GROUP: {config.get_game_group()}\n"
        f"WORK_GROUP: {config.get_work_group()}\n"
        f"BACKEND_GROUP: {config.get_backend_group()}\n"
        f"ADMIN_QQ: {config.get_admin_qqs()}\n"
        f"KDOCS_ENABLED: {config.KDOCS_ENABLED}\n"
        f"DB_PATH: {config.DB_PATH}\n"
        f"event.group_id: {getattr(event, 'group_id', 'N/A')}\n"
        f"event.user_id: {event.user_id}\n"
        f"bot.self_id: {bot.self_id}\n"
    )
    await debug_cmd.finish(msg)


# ============================================================
# 消息日志 - 打印收到的所有群消息（调试用，可删除）
# ============================================================
log_matcher = on_message(priority=99, block=False)


@log_matcher.handle()
async def handle_log(bot: Bot, event: GroupMessageEvent, msg: str = EventPlainText()):
    # 只记录游戏群的消息
    if isinstance(event, GroupMessageEvent):
        gid = event.group_id
        uid = event.user_id
        nonebot.logger.info(
            f"[MSG] group={gid} user={uid} text={msg[:50]!r}"
        )
