# SPDX-License-Identifier: GPL-3.0-or-later
"""导入 + 主线关键步骤 演练脚本（写入临时库，不影响 claw.db）

用法：python data/dryrun_import.py
"""
import os, sys, asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
import time
TMP_DB = ROOT / "data" / f"_dryrun_{int(time.time())}.db"
os.environ["DB_PATH"] = str(TMP_DB)
sys.path.insert(0, str(ROOT))

from utils.excel_importer import import_all_from_excel  # noqa: E402
from utils import db as D  # noqa: E402

OK, BAD = "  [OK]", "  [FAIL]"
fails = []


def check(cond, label, extra=""):
    print((OK if cond else BAD) + f" {label}" + (f" -> {extra}" if extra else ""))
    if not cond:
        fails.append(label)


async def main():
    print("=== 1. 导入 sample_game_data.xlsx ===")
    r = await import_all_from_excel(str(ROOT / "data" / "sample_game_data.xlsx"))
    print("  结果:", {k: v for k, v in r.items() if k != "errors"})
    print("  错误:", r["errors"] or "无")
    check(not r["errors"], "导入无错误")
    check(r["玩家"] == 4, "玩家 4 人", r["玩家"])
    check(r["NPC"] == 4, "NPC 4 人", r["NPC"])
    check(r["任务点"] == 1, "任务点 1 个", r["任务点"])
    check(r["普通露水"] == 3, "普通露水 3 张", r["普通露水"])
    check(r["金露水"] == 1, "金露水 1 个", r["金露水"])
    check(r["线索"] == 4, "线索 4 条", r["线索"])

    names = {p["name"] for p in await D.get_all_players()}
    check(names == {"示例姓名", "示例姓名", "示例姓名", "示例姓名"}, "四名玩家全部入库（首行未被吞）", names)

    dbc = await D.get_db()
    c = await dbc.execute("SELECT qq,name,role FROM npcs ORDER BY qq")
    roles = {row["name"]: row["role"] for row in await c.fetchall()}
    check(roles.get("示例姓名") == "task_npc", "示例姓名 = task_npc", roles.get("示例姓名"))
    check(roles.get("示例姓名") == "mobile", "示例姓名 = mobile", roles.get("示例姓名"))
    check(roles.get("示例姓名") == "hunter" and roles.get("示例姓名") == "hunter", "两名猎人 = hunter")

    tp = await D.get_task_point(1)
    check(tp["shield_card_count"] == 2, "任务点1 护盾卡库存 2", tp["shield_card_count"])
    check(tp["static_card_count"] == 1, "任务点1 静止卡库存 1", tp["static_card_count"])
    check(tp["status"] == "启用", "任务点1 状态=启用", tp["status"])

    print("\n=== 2. 步骤2.1 任务点1 完成 线索1 金露水1 护盾卡1 静止卡无 ===")
    res = await D.process_task_point_complete(1, 1, 1, 1, 0)
    print("  ", res)
    check(res["ok"], "任务点完成成功", res["msg"])
    clue1 = await D.get_clue(1)
    check(clue1["status"] == "已发现未收集", "线索1 → 已发现未收集", clue1["status"])
    c = await dbc.execute("SELECT status FROM dews WHERE id=1")
    check((await c.fetchone())["status"] == "已发现未收集", "露水1 → 已发现未收集")
    gs = await D.get_golden_dew_stats()
    check(gs["collected"] == 1, "金露水库存 1（供复活消耗）", gs)

    print("\n=== 3. 步骤3.1 Web端收集露水1 ===")
    ok = await D.collect_dew_from_web(1)
    check(ok, "露水1 收集成功")
    ds = await D.get_dew_stats()
    print("  露水统计:", ds)
    check(ds["collected_value"] == 2, "已收集 2 滴", ds["collected_value"])
    clue1 = await D.get_clue(1)
    check(clue1["status"] == "已收集已发现", "线索1 → 已收集已发现", clue1["status"])

    print("\n=== 4. 步骤7/8 淘汰 ===")
    r1 = await D.eliminate_player(1, "示例姓名", "猎人") if hasattr(D, "eliminate_player") else None
    if r1 is None:
        c = await dbc.execute("UPDATE players SET status='淘汰' WHERE group_num=1 AND name='示例姓名'")
        await dbc.commit()
        print("   (直接置为淘汰用于后续复活验证)")
    else:
        print("  ", r1)

    print("\n=== 5. 步骤11.1 复活示例姓名（消耗金露水）===")
    rv = await D.revive_player(1, "示例姓名")
    print("  ", rv)
    check(rv["ok"], "复活成功", rv["msg"])
    gs = await D.get_golden_dew_stats()
    check(gs["collected"] == 0 and gs["used"] == 1, "金露水已消耗", gs)

    print("\n=== 6. 步骤13.1 任务点1 接收 线索无 露水编号2 ... ===")
    res = await D.process_task_point_receive(1, None, 2, 0, 0, 0)
    print("  ", res)
    check(res["ok"], "接收露水编号2 成功", res["msg"])
    c = await dbc.execute("SELECT id,status FROM dews ORDER BY id")
    print("  露水状态:", [(r["id"], r["status"]) for r in await c.fetchall()])

    print("\n=== 7. 步骤13.2 任务点1 接收 金露水1 护盾卡1 ===")
    res = await D.process_task_point_receive(1, None, 0, 1, 1, 0)
    print("  ", res)
    check(res["ok"], "接收金露水+护盾卡成功", res["msg"])
    gs = await D.get_golden_dew_stats()
    check(gs["collected"] == 1, "金露水重新入库 1", gs)

    print("\n=== 8. 步骤14.1 线索1 已收集（NPC上报，应报异常）===")
    ok = await D.collect_clue(1)
    check(not ok, "线索1 已是终态，重复上报被拒", ok)

    print("\n=== 9. 步骤2.1 重复执行（线索已送出，应失败）===")
    res = await D.process_task_point_complete(1, 1, 0, 0, 0)
    check(not res["ok"], "重复送出线索1 被拒", res["msg"])

    print("\n=== 10. 库存不足检测：护盾卡超发 ===")
    res = await D.process_task_point_complete(1, None, 0, 99, 0)
    check(not res["ok"], "护盾卡超发被拒", res["msg"])

    print("\n" + "=" * 50)
    if fails:
        print(f"演练结束：{len(fails)} 项未通过")
        for f in fails:
            print("  -", f)
    else:
        print("演练结束：全部通过")

    try:
        await dbc.close()
    except Exception:
        pass


asyncio.run(main())
sys.stdout.flush()
os._exit(0)  # aiosqlite 后台线程非 daemon，直接退出避免挂起
