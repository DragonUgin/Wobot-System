"""私聊播报插件 — 管理员私聊机器人发内容，自动转发到所有群

用法：
  管理员私聊机器人发送任意内容 → 转发到游戏群+工作群+后台群
  发送 /播报 <内容> 也行（兼容指令格式）
"""
from nonebot import on_message, on_command
from nonebot.adapters.onebot.v11 import Bot, PrivateMessageEvent
from nonebot.params import EventPlainText
import config
from utils.broadcast import send_all_groups

# 私聊消息匹配器（优先级低，不拦截其他匹配器）
private_msg_matcher = on_message(priority=50, block=False)


@private_msg_matcher.handle()
async def handle_private_broadcast(
    bot: Bot, event: PrivateMessageEvent, msg: str = EventPlainText()
):
    # 仅处理私聊
    if not isinstance(event, PrivateMessageEvent):
        return

    # 仅管理员可使用
    if event.user_id not in config.get_admin_qqs():
        return

    text = msg.strip()
    if not text:
        return

    # 兼容 /播报 内容 格式
    if text.startswith("/播报 ") or text.startswith("/播报\u3000"):
        text = text[3:].strip()
    elif text == "/播报":
        await bot.send(event, "请输入要播报的内容：/播报 <内容>")
        return

    # 转发到所有群
    broadcast_msg = f"[管理员播报]\n{text}"
    await send_all_groups(broadcast_msg)
    await bot.send(event, f"已播报到所有群：\n{text}")
