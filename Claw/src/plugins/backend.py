"""管理指令插件 — 管理员在任意群均可发管理指令

指令列表：
  /开始 N    — 开始游戏 N 分钟
  /暂停      — 暂停计时
  /继续      — 恢复计时
  /结束      — 结束游戏
  /状态      — 查看当前战况
  /播报 内容 — 自定义播报到所有群
  /大盘      — 查看总览数据
"""
from nonebot import on_command
from nonebot.adapters.onebot.v11 import Bot, GroupMessageEvent
import config
from utils.broadcast import send_game_group, send_all_groups, send_work_group, send_backend_group
from utils.timer_logic import (
    start_game, pause_game, resume_game, end_game,
    get_game_status_display, get_remaining_display, get_remaining_seconds, is_game_active,
)
from utils.db import get_dew_stats, get_golden_dew_stats, get_player_stats, get_all_clues, get_dew_target, get_recent_operations, delete_operation_log, get_db, set_frenzy_mode, get_frenzy_mode, reveal_all_clues, add_operation_log


def _is_backend_admin(event: GroupMessageEvent) -> bool:
    """检查是否是管理员（任意群均可发指令）"""
    return event.user_id in config.get_admin_qqs()


# ============================================================
# /开始 N — 开始游戏
# ============================================================
start_cmd = on_command("开始", priority=1, block=True)


@start_cmd.handle()
async def handle_start(bot: Bot, event: GroupMessageEvent):
    if not _is_backend_admin(event):
        return
    # 解析分钟数
    args = event.get_plaintext().strip().split()
    minutes = 90
    if len(args) >= 2:
        try:
            minutes = int(args[1])
        except ValueError:
            await start_cmd.finish("用法：/开始 <分钟数>")
            return
    ok = await start_game(minutes)
    if not ok:
        await start_cmd.finish("游戏已在进行中，无法重复开始")
        return
    await send_game_group(f"极限挑战开始！\n时长 {minutes} 分钟\n参赛人数：见 Web 管理页")
    await start_cmd.finish(f"游戏已开始，时长 {minutes} 分钟，已广播到游戏群")


# ============================================================
# /暂停 — 暂停计时
# ============================================================
pause_cmd = on_command("暂停", priority=1, block=True)


@pause_cmd.handle()
async def handle_pause(bot: Bot, event: GroupMessageEvent):
    if not _is_backend_admin(event):
        return
    ok = await pause_game()
    if not ok:
        await pause_cmd.finish("游戏未在运行中")
        return
    remaining = await get_remaining_display()
    await send_game_group(f"游戏已暂停\n剩余时间：{remaining}")
    await pause_cmd.finish(f"已暂停，剩余 {remaining}")


# ============================================================
# /继续 — 恢复计时
# ============================================================
resume_cmd = on_command("继续", priority=1, block=True)


@resume_cmd.handle()
async def handle_resume(bot: Bot, event: GroupMessageEvent):
    if not _is_backend_admin(event):
        return
    ok = await resume_game()
    if not ok:
        await resume_cmd.finish("游戏未在暂停中")
        return
    remaining = await get_remaining_display()
    await send_game_group(f"游戏继续！\n剩余时间：{remaining}")
    await resume_cmd.finish(f"已继续，剩余 {remaining}")


# ============================================================
# /结束 — 结束游戏
# ============================================================
end_cmd = on_command("结束", priority=1, block=True)


@end_cmd.handle()
async def handle_end(bot: Bot, event: GroupMessageEvent):
    if not _is_backend_admin(event):
        return
    ok = await end_game()
    if not ok:
        await end_cmd.finish("当前没有进行中的游戏")
        return
    ds = await get_dew_stats()
    await send_game_group(f"极限挑战结束！\n露水收集：{ds['collected_value']}/{ds['target']}滴")
    await end_cmd.finish(f"已结束，最终露水 {ds['collected_value']}/{ds['target']}滴")


# ============================================================
# /状态 — 查看战况
# ============================================================
status_cmd = on_command("状态", priority=1, block=True)


@status_cmd.handle()
async def handle_status(bot: Bot, event: GroupMessageEvent):
    if not _is_backend_admin(event):
        return
    status = await get_game_status_display()
    remaining = await get_remaining_display()
    active = await is_game_active()
    ds = await get_dew_stats()
    gs = await get_golden_dew_stats()
    stats = await get_player_stats()

    msg = (
        f"=== 当前战况 ===\n"
        f"状态：{status}\n"
        f"剩余时间：{remaining}\n"
        f"{'-' * 20}\n"
        f"露水：{ds['collected_value']}/{ds['target']}滴\n"
        f"金露水：库存 {gs['available']} | 已用 {gs['used']} | 总 {gs['total']}\n"
        f"{'-' * 20}\n"
        f"玩家：存活 {stats.get('存活', 0)} | 淘汰 {stats.get('淘汰', 0)} | 复活 {stats.get('复活', 0)} | 总 {stats.get('total', 0)}"
    )
    await status_cmd.finish(msg)


# ============================================================
# /播报 内容 — 自定义播报
# ============================================================
broadcast_cmd = on_command("播报", priority=1, block=True)


@broadcast_cmd.handle()
async def handle_broadcast(bot: Bot, event: GroupMessageEvent):
    if not _is_backend_admin(event):
        return
    text = event.get_plaintext().strip()
    # 去掉 /播报 前缀
    parts = text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        await broadcast_cmd.finish("用法：/播报 <要播报的内容>")
        return
    content = parts[1].strip()
    await send_all_groups(f"[管理员播报]\n{content}")
    await broadcast_cmd.finish(f"已播报到所有群：\n{content}")


# ============================================================
# /大盘 — 总览数据
# ============================================================
dashboard_cmd = on_command("大盘", priority=1, block=True)


@dashboard_cmd.handle()
async def handle_dashboard(bot: Bot, event: GroupMessageEvent):
    if not _is_backend_admin(event):
        return
    status = await get_game_status_display()
    remaining = await get_remaining_display()
    ds = await get_dew_stats()
    gs = await get_golden_dew_stats()
    stats = await get_player_stats()
    clues = await get_all_clues()

    # 线索统计
    clue_discovered = sum(1 for c in clues if c.get("status") == "已收集已发现")
    clue_undiscovered = sum(1 for c in clues if c.get("status") == "已收集未发现")
    clue_uncollected = sum(1 for c in clues if c.get("status") == "未收集")

    dew_pct = round(ds["collected_value"] / ds["target"] * 100) if ds["target"] else 0

    msg = (
        f"{'=' * 30}\n"
        f"  乌波 // 极限挑战 大盘数据\n"
        f"{'=' * 30}\n"
        f"游戏状态：{status}\n"
        f"倒计时：{remaining}\n"
        f"{'─' * 30}\n"
        f"露水进度：{ds['collected_value']}/{ds['target']}滴 ({dew_pct}%)\n"
        f"金露水：库存 {gs['available']} | 已用 {gs['used']} | 总 {gs['total']}\n"
        f"{'─' * 30}\n"
        f"玩家：存活 {stats.get('存活', 0)} | 淘汰 {stats.get('淘汰', 0)} | 复活 {stats.get('复活', 0)} | 总 {stats.get('total', 0)}\n"
        f"{'─' * 30}\n"
        f"线索：已发现 {clue_discovered} | 未发现 {clue_undiscovered} | 未收集 {clue_uncollected} | 总 {len(clues)}\n"
        f"{'─' * 30}\n"
    )

    # 分组数据
    groups = stats.get("groups", [])
    if groups:
        msg += "分组统计：\n"
        for g in groups:
            total_g = g["alive"] + g["dead"] + g["revived"]
            rate = round(g["alive"] / total_g * 100) if total_g else 0
            msg += f"  第{g['group_num']}组：存活{g['alive']} 淘汰{g['dead']} 复活{g['revived']} 存活率{rate}%\n"

    await dashboard_cmd.finish(msg)


async def _undo_one(op: dict, data: dict) -> str | None:
    """撤销单条操作，成功返回描述字符串，失败返回 None"""
    from utils.db import undo_operation
    return await undo_operation(op, data)


# ============================================================
# /撤销 [N] — 撤销最近N次操作
# /撤销 #N  — 撤销指定序号的操作（配合 /撤销记录 使用）
# ============================================================
undo_cmd = on_command("撤销", priority=1, block=True)


@undo_cmd.handle()
async def handle_undo(bot: Bot, event: GroupMessageEvent):
    if not _is_backend_admin(event):
        return
    import json
    text = event.get_plaintext().strip()
    parts = text.split()

    # 按序号撤销：/撤销 #N
    if len(parts) >= 2 and parts[1].startswith("#"):
        idx_str = parts[1][1:]
        try:
            idx = int(idx_str)
        except ValueError:
            await undo_cmd.finish("用法：/撤销 #序号（如 /撤销 #3）。先用 /撤销记录 查看可撤销的操作列表")
            return
        if idx < 1 or idx > 10:
            await undo_cmd.finish("序号需在 1~10 之间")
            return
        ops_all = await get_recent_operations(10)
        if idx > len(ops_all):
            await undo_cmd.finish(f"没有第 {idx} 条操作（共 {len(ops_all)} 条可撤销）")
            return
        op = ops_all[idx - 1]
        desc = op["target_desc"]
        try:
            data = json.loads(op["undo_data"]) if op["undo_data"] else {}
        except:
            data = {}
        result = await _undo_one(op, data)
        if result:
            await undo_cmd.finish(result)
        else:
            await undo_cmd.finish("撤销失败：不支持的操作类型")
        return

    # 按数量撤销：/撤销 或 /撤销 N
    n = int(parts[1]) if len(parts) >= 2 else 1
    if n > 10:
        n = 10

    ops = await get_recent_operations(n)
    if not ops:
        await undo_cmd.finish("没有可撤销的操作")
        return

    results = []
    for op in ops:
        desc = op["target_desc"]
        try:
            data = json.loads(op["undo_data"]) if op["undo_data"] else {}
        except:
            data = {}
        r = await _undo_one(op, data)
        if r:
            results.append(r)

    if results:
        await undo_cmd.finish("\n".join(results))
    else:
        await undo_cmd.finish("没有可撤销的操作")


# ============================================================
# /撤销记录 — 查看最近可撤销的操作（带序号，配合 /撤销 #N 使用）
# ============================================================
undo_list_cmd = on_command("撤销记录", priority=1, block=True)


@undo_list_cmd.handle()
async def handle_undo_list(bot: Bot, event: GroupMessageEvent):
    if not _is_backend_admin(event):
        return

    ops = await get_recent_operations(10)
    if not ops:
        await undo_list_cmd.finish("没有可撤销的操作")
        return

    lines = ["最近可撤销的操作："]
    for i, op in enumerate(ops, 1):
        desc = op["target_desc"]
        ts = op.get("created_at", "")
        # 只取时间部分（HH:MM:SS）
        try:
            ts = ts.split(" ")[1] if " " in ts else ts
        except:
            pass
        lines.append(f"[{i}] {desc}  ({ts})")

    lines.append("回复 /撤销 #序号 撤销指定条目（如 /撤销 #3）")
    await undo_list_cmd.finish("\n".join(lines))


# ============================================================
# /狂欢 — 激活狂欢模式（上帝时刻）
# /狂欢 关闭 — 关闭狂欢模式
# ============================================================
frenzy_cmd = on_command("狂欢", priority=1, block=True)


@frenzy_cmd.handle()
async def handle_frenzy(bot: Bot, event: GroupMessageEvent):
    if not _is_backend_admin(event):
        return

    import json as _json
    args = event.get_plaintext().strip().split()
    turn_off = len(args) >= 2 and args[1] == "关闭"

    if turn_off:
        await set_frenzy_mode(False)
        await send_game_group("[上帝时刻] 狂欢模式已关闭，淘汰冷却恢复为20秒")
        await send_work_group("[上帝时刻] 狂欢模式已关闭，淘汰冷却恢复为20秒")
        await frenzy_cmd.finish("狂欢模式已关闭")
        return

    # 激活狂欢模式
    if await get_frenzy_mode():
        await frenzy_cmd.finish("狂欢模式已激活，无需重复激活")
        return

    await set_frenzy_mode(True)
    # 批量改线索状态为已发现（可撤销）
    changed = await reveal_all_clues()
    await add_operation_log(
        "frenzy_reveal", f"狂欢模式-线索公示({len(changed)}条)",
        _json.dumps({"clues": changed}), event.user_id
    )
    msg = (
        "[上帝时刻] 狂欢模式激活！\n"
        "猎人淘汰冷却延长至40秒\n"
        f"所有线索已公示（{len(changed)}条）"
    )
    await send_game_group(msg)
    await send_work_group(msg)
    await send_backend_group(f"[大盘] 狂欢模式激活 | 线索公示{len(changed)}条 | 淘汰冷却40s")
    await frenzy_cmd.finish(f"狂欢模式已激活，线索公示{len(changed)}条，淘汰冷却40秒")
