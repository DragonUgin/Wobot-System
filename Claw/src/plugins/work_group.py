"""工作群消息插件 — 处理 NPC/猎人的上报

指令格式：
  1组XXX被XXX淘汰               —— 猎人淘汰玩家（姓名匹配 + 冷却检测 + 免疫检测）
  猎人Y被使用静止卡              —— 仅触发 180s 冷却
  猎人Y被使用静止卡 获得线索N    —— 猎人把线索N送出给玩家（消耗其持有，置已发现未收集）
  猎人Y被使用静止卡 获得露水M    —— 指令格式保留但露水送出已砍掉（系统忽略，仅告警；露水只能经接收/存入或网页端编辑）
  猎人Y被使用护盾卡              —— 仅确认使用（护盾卡不再支持获得线索；静止卡也只能获线索，露水送出已砍）
  任务点N 完成 线索X 露水Y 金露水Z 护盾卡Z 静止卡Z   —— 任务点完成（送出道具，无=无）
  任务点N 接收 线索X 露水Y 金露水Z 护盾卡Z 静止卡Z   —— 任务点接收（入库道具，无=无）
"""
import re, json
from nonebot import on_message
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
from nonebot.params import EventPlainText
import config
from utils.db import (
    hunter_give_clue, add_task_point_inventory,
    add_operation_log, incr_task_point_card_collected,
    eliminate_player, get_player, set_global_task_immune, is_global_task_immune,
    record_elimination_location,
    process_task_point_complete, process_task_point_receive,
)
from utils.timer_logic import is_game_active, is_game_running
from utils.cooldown import (
    check_static_card_cooldown, set_static_card_cooldown,
    check_capture_cooldown, set_capture_cooldown,
    check_shield_card_cooldown, set_shield_card_cooldown,
)
from utils.broadcast import send_game_group, send_backend_group

# （"线索N 已收集"独立指令已移除，线索改由功能卡/任务点触发）

# "猎人Y被使用静止卡 [获得线索N] [获得露水M]"（线索/露水各自独立子句，可同条出现，猎人送出=消耗其持有）
STATIC_CARD_PATTERN = re.compile(r"^猎人(.+?)被使用静止卡(?:\s+(.*))?$")

# "猎人Y被使用护盾卡"（护盾卡不再支持 获得线索；只有静止卡可获线索/露水）
SHIELD_CARD_PATTERN = re.compile(r"^猎人(.+?)被使用护盾卡$")

# "X组XXX被XXX淘汰"（工作群，猎人淘汰玩家，姓名匹配）
CAPTURE_PATTERN = re.compile(r"^(\d+)组(.+?)被(.+?)淘汰$")

# "X组XXX被XXX在...淘汰 召唤机动人员"（玩家携带道具，需机动护送）
CAPTURE_WITH_ITEMS = re.compile(r"^(\d+)组(.+?)被(.+?)在(.+)淘汰\s+召唤机动人员$")

# 任务点完成/接收指令的新格式：
#   任务点N 完成 线索X 露水Y 金露水Z 护盾卡Z 静止卡Z
#   任务点N 接收 线索X 露水Y 金露水Z 护盾卡Z 静止卡Z
# X=线索编号或"无"，Y=露水编号或"无"，Z=数量或"无"
_TP_ITEM = r"(?:无|(\d+))"
TP_COMPLETE = re.compile(
    rf"^任务点(\d+)\s*完成\s*线索{_TP_ITEM}\s*露水{_TP_ITEM}\s*金露水{_TP_ITEM}\s*护盾卡{_TP_ITEM}\s*静止卡{_TP_ITEM}$"
)
TP_RECEIVE = re.compile(
    rf"^任务点(\d+)\s*接收\s*线索{_TP_ITEM}\s*露水{_TP_ITEM}\s*金露水{_TP_ITEM}\s*护盾卡{_TP_ITEM}\s*静止卡{_TP_ITEM}$"
)


work_matcher = on_message(priority=10, block=False)


@work_matcher.handle()
async def handle_work_group_msg(
    bot: Bot, event: GroupMessageEvent, msg: str = EventPlainText()
):
    # 仅工作群
    gid = config.get_work_group()
    if gid == 0 or event.group_id != gid:
        return

    if not await is_game_running():
        return

    text = msg.strip()

    # ===== 猎人淘汰玩家（带道具护送）=====
    # 先匹配带道具格式：1组张三被李四在学校淘汰 召唤机动人员
    m_items = CAPTURE_WITH_ITEMS.match(text)
    if m_items:
        group_num = int(m_items.group(1))
        player_name = m_items.group(2).strip()
        hunter_name = m_items.group(3).strip()
        location = m_items.group(4).strip()

        # ① 猎人名单已砍掉（线下口头约定），冷却key用发送者真实QQ
        hunter_qq = event.user_id

        # ② 姓名匹配玩家
        player = await get_player(group_num, player_name)
        if not player:
            await bot.send(event, f"淘汰失败：未找到 {group_num}组{player_name}，请确认组号和姓名")
            return

        # ③ 玩家状态检查
        if player["status"] not in ("存活", "复活"):
            await bot.send(event, f"淘汰失败：{group_num}组{player_name} 当前状态为{player['status']}，无法淘汰")
            return

        # ④ 全局任务免疫检查
        immune, rem = await is_global_task_immune()
        if immune:
            await bot.send(event, f"淘汰失败：全局任务免疫中，{rem}秒内不可淘汰任何玩家")
            return

        # ⑤ 猎人冷却检查
        can_capture, cd_rem = await check_capture_cooldown(hunter_qq)
        if not can_capture:
            await bot.send(event, f"淘汰失败：猎人{hunter_name} 处于冷却中，请等待 {cd_rem} 秒")
            return

        # ⑥ 执行淘汰 + 记录地点
        ok = await eliminate_player(group_num, player_name, source="hunter_capture")
        if not ok:
            await bot.send(event, f"淘汰失败：{group_num}组{player_name} 状态异常")
            return
        await record_elimination_location(group_num, player_name, location)

        # ⑦ 设置冷却
        await set_capture_cooldown(hunter_qq, hunter_name)
        await send_game_group(f"[冷却] 猎人{hunter_name} 淘汰冷却开始")

        # ⑧ 记录操作日志
        await add_operation_log(
            "eliminate", f"{group_num}组{player_name} 在{location}被{hunter_name}淘汰 召唤机动人员",
            json.dumps({"group_num": group_num, "name": player_name, "hunter_qq": hunter_qq, "location": location}), hunter_qq
        )

        # ⑨ 三群播报
        await send_game_group(f"[淘汰] {group_num}组{player_name} 被猎人{hunter_name}淘汰")
        await bot.send(event, f"[淘汰] {group_num}组{player_name} 被{hunter_name}淘汰 | 来源：猎人")
        await send_backend_group(f"{group_num}组{player_name}被{hunter_name}在{location}淘汰 召唤机动人员")
        return

    # ===== 猎人淘汰玩家（无道具） =====
    m = CAPTURE_PATTERN.match(text)
    if m:
        group_num = int(m.group(1))
        player_name = m.group(2).strip()
        hunter_name = m.group(3).strip()

        # ① 猎人名单已砍掉（线下口头约定），冷却key用发送者真实QQ
        hunter_qq = event.user_id

        # ② 姓名匹配玩家
        player = await get_player(group_num, player_name)
        if not player:
            await bot.send(event, f"淘汰失败：未找到 {group_num}组{player_name}，请确认组号和姓名")
            return

        # ③ 玩家状态检查
        if player["status"] not in ("存活", "复活"):
            await bot.send(event, f"淘汰失败：{group_num}组{player_name} 当前状态为{player['status']}，无法淘汰")
            return

        # ④ 全局任务免疫检查
        immune, rem = await is_global_task_immune()
        if immune:
            await bot.send(event, f"淘汰失败：全局任务免疫中，{rem}秒内不可淘汰任何玩家")
            return

        # ⑤ 猎人冷却检查
        can_capture, cd_rem = await check_capture_cooldown(hunter_qq)
        if not can_capture:
            await bot.send(event, f"淘汰失败：猎人{hunter_name} 处于冷却中，请等待 {cd_rem} 秒")
            return

        # ⑥ 执行淘汰
        ok = await eliminate_player(group_num, player_name, source="hunter_capture")
        if not ok:
            await bot.send(event, f"淘汰失败：{group_num}组{player_name} 状态异常")
            return

        # ⑦ 设置冷却
        await set_capture_cooldown(hunter_qq, hunter_name)
        await send_game_group(f"[冷却] 猎人{hunter_name} 淘汰冷却开始")

        # ⑧ 记录操作日志
        await add_operation_log(
            "eliminate", f"{group_num}组{player_name} 被{hunter_name}淘汰",
            json.dumps({"group_num": group_num, "name": player_name, "hunter_qq": hunter_qq}), hunter_qq
        )

        # ⑨ 双群播报
        await send_game_group(f"[淘汰] {group_num}组{player_name} 被猎人{hunter_name}淘汰")
        await bot.send(event, f"[淘汰] {group_num}组{player_name} 被{hunter_name}淘汰 | 来源：猎人")
        return

    # ===== 静止卡（猎人送出线索/露水给玩家，唯一能让玩家获线索+露水的卡）=====
    m = STATIC_CARD_PATTERN.match(text)
    if m:
        hunter_name = m.group(1).strip()
        rest = (m.group(2) or "").strip()
        clue_ids = [int(x) for x in re.findall(r"获得线索(\d+)", rest)]
        dew_ids  = [int(x) for x in re.findall(r"获得露水(\d+)", rest)]

        # 冷却（无论是否带子句都冷却）
        can_use, remaining = await check_static_card_cooldown(hunter_name)
        if not can_use:
            await bot.send(event, f"猎人{hunter_name} 静止卡冷却中，请等待 {remaining} 秒")
            return

        warns = []
        for cid in clue_ids:
            r = await hunter_give_clue(hunter_name, cid)
            if not r["ok"]:
                warns.append(f"线索{cid}：{r['msg']}")
        # 露水送出功能已砍掉：猎人静止卡不再送出露水（指令格式仍支持"获得露水X"，但本指令忽略该项，仅提示）。
        # 露水仅可由任务点/猎人"接收/存入"经网页端编辑。
        for did in dew_ids:
            warns.append(f"露水{did}：送出功能已停用（露水仅可由任务点/猎人接收入库）")

        await set_static_card_cooldown(hunter_name)
        parts = []
        if clue_ids: parts.append(f"线索{'/'.join(map(str, clue_ids))} → 已发现未收集")
        detail = ("，" + "，".join(parts)) if parts else ""
        await bot.send(event, f"[功能卡] {hunter_name}被使用静止卡{detail}\n静止卡冷却：3分钟")
        for w in warns:
            await bot.send(event, f"[警告] {w}")
        if clue_ids or dew_ids:
            await add_operation_log(
                "static_card_give",
                f"{hunter_name}被使用静止卡送出 线索{clue_ids} 露水{dew_ids}",
                json.dumps({"hunter": hunter_name, "clues": clue_ids, "dews": dew_ids}),
                event.user_id
            )
        return

    # ===== 护盾卡 =====
    m = SHIELD_CARD_PATTERN.match(text)
    if m:
        hunter_name = m.group(1).strip()
        # 检查护盾卡冷却
        can_use, rem = await check_shield_card_cooldown(hunter_name)
        if not can_use:
            await bot.send(event, f"猎人{hunter_name} 护盾卡冷却中，请等待 {rem} 秒")
            return
        await set_shield_card_cooldown(hunter_name)
        await bot.send(
            event,
            f"[功能卡] {hunter_name}被使用护盾卡\n护盾卡冷却：20秒"
        )
        return

    # 线索收集独立指令已移除：线索统一由 静止卡/护盾卡/任务点 触发

    # ===== 任务点完成（送出道具） =====
    m = TP_COMPLETE.match(text)
    if m:
        tp_id = int(m.group(1))
        clue_id = int(m.group(2)) if m.group(2) else None
        dew_id = int(m.group(3)) if m.group(3) else 0
        golden_dew = int(m.group(4)) if m.group(4) else 0
        shield_card = int(m.group(5)) if m.group(5) else 0
        static_card = int(m.group(6)) if m.group(6) else 0

        result = await process_task_point_complete(tp_id, clue_id, dew_id, golden_dew, shield_card, static_card)
        if result["ok"]:
            # 全局任务免疫：全体玩家15秒内不可被淘汰
            await set_global_task_immune()
            await send_game_group(f"[免疫] 任务点{tp_id} 完成 | 全体玩家15秒内不可被淘汰")
            await send_game_group(f"[任务点] 任务点{tp_id} 完成 {result['details']}")
            await add_operation_log(
                "tp_complete", f"任务点{tp_id} 完成 {result['details']}",
                json.dumps({"tp_id": tp_id, "clue_id": clue_id, "golden_dew": golden_dew,
                           "shield_card": shield_card, "static_card": static_card}),
                event.user_id
            )
            await bot.send(
                event,
                f"[任务点] {result['msg']}\n{result['details']}\n免疫保护：全体玩家15秒内不可被淘汰"
            )
        else:
            await bot.send(event, f"[失败] {result['msg']}")
        return

    # ===== 任务点接收（入库道具） =====
    m = TP_RECEIVE.match(text)
    if m:
        tp_id = int(m.group(1))
        clue_id = int(m.group(2)) if m.group(2) else None
        dew_id = int(m.group(3)) if m.group(3) else 0
        golden_dew = int(m.group(4)) if m.group(4) else 0
        shield_card = int(m.group(5)) if m.group(5) else 0
        static_card = int(m.group(6)) if m.group(6) else 0

        result = await process_task_point_receive(tp_id, clue_id, dew_id, golden_dew, shield_card, static_card)
        if result["ok"]:
            await add_operation_log(
                "tp_receive", f"任务点{tp_id} 接收 {result['details']}",
                json.dumps({"tp_id": tp_id, "clue_id": clue_id, "dew_id": dew_id, "golden_dew": golden_dew,
                           "shield_card": shield_card, "static_card": static_card}),
                event.user_id
            )
            await send_game_group(f"[任务点] 任务点{tp_id} 接收 {result['details']}")
            await bot.send(
                event,
                f"[任务点] {result['msg']}\n{result['details']}"
            )
        else:
            await bot.send(event, f"[失败] {result['msg']}")
        return
