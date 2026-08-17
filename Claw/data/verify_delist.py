# SPDX-License-Identifier: GPL-3.0-or-later
"""去名单化端到端验证：导入 sample_game_data.xlsx 到临时库，确认：
1. 任务点不再写 task_point_npcs 关联表
2. 线索 hidden_npc_name 是文本名字（非QQ）
3. add_clue/update_clue 接受文本名字
4. 导入无错误
"""
import asyncio, os, sys, json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
os.environ["DB_PATH"] = str(ROOT / "data" / f"_verify_delist_{os.getpid()}.db")
sys.path.insert(0, str(ROOT))

from utils.db import get_db, get_all_task_points, get_all_clues, add_clue, update_clue, add_task_point
from utils.excel_importer import import_all_from_excel

XLSX = ROOT / "data" / "sample_game_data.xlsx"

async def main():
    print("=" * 50)
    print("去名单化端到端验证")
    print("=" * 50)
    await get_db()  # 触发建库+迁移
    fails = []

    # 1. 导入
    r = await import_all_from_excel(str(XLSX))
    print(f"[导入] 玩家{r['玩家']} NPC{r['NPC']} 任务点{r['任务点']} 露水{r['普通露水']} 金露水{r['金露水']} 线索{r['线索']}")
    print(f"[导入] errors: {r['errors']}")
    if r['errors']:
        fails.append(f"导入有错误: {r['errors']}")
    if r['玩家'] != 4 or r['任务点'] != 1 or r['线索'] != 4 or r['普通露水'] != 3:
        fails.append(f"导入数量不符: {r}")

    db = await get_db()

    # 2. 任务点不再写 task_point_npcs
    c = await db.execute("SELECT COUNT(*) as cnt FROM task_point_npcs")
    cnt = (await c.fetchone())["cnt"]
    print(f"[任务点NPC关联] task_point_npcs 表行数 = {cnt} (预期 0)")
    if cnt != 0:
        fails.append(f"task_point_npcs 应为空，实际 {cnt}")

    # 3. 任务点列表不返回 npc_qqs
    tps = await get_all_task_points()
    tp1 = tps[0] if tps else {}
    print(f"[任务点] tp1={tp1.get('name')} npc_qqs字段={'npc_qqs' in tp1} (预期 False/不存在)")
    if "npc_qqs" in tp1:
        fails.append("get_all_task_points 仍返回 npc_qqs 字段")

    # 4. 线索 hidden_npc_name 是文本名字
    clues = await get_all_clues()
    for cl in clues:
        hn = cl.get("hidden_npc_name")
        print(f"[线索{cl['id']}] hidden_npc_name = {hn!r} (预期 '示例姓名')")
        if hn != "示例姓名":
            fails.append(f"线索{cl['id']} hidden_npc_name 应为'示例姓名'，实际 {hn!r}")

    # 5. add_clue 接受文本名字
    await add_clue(999, "真", 1, "测试线索", "张三")
    c = await db.execute("SELECT hidden_npc_name FROM clues WHERE id=999")
    row = await c.fetchone()
    print(f"[新增线索999] hidden_npc_name = {row['hidden_npc_name']!r} (预期 '张三')")
    if not row or row["hidden_npc_name"] != "张三":
        fails.append("add_clue 未正确写入文本 hidden_npc_name")

    # 6. update_clue 接受文本名字
    await update_clue(999, "假", 1, "改后", "李四")
    c = await db.execute("SELECT hidden_npc_name FROM clues WHERE id=999")
    row = await c.fetchone()
    print(f"[更新线索999] hidden_npc_name = {row['hidden_npc_name']!r} (预期 '李四')")
    if not row or row["hidden_npc_name"] != "李四":
        fails.append("update_clue 未正确更新文本 hidden_npc_name")

    # 7. add_task_point 不写 task_point_npcs
    await add_task_point(888, "测试任务点", "solo", "无", 0, 0, 0)
    c = await db.execute("SELECT COUNT(*) as cnt FROM task_point_npcs WHERE task_point_id=888")
    cnt2 = (await c.fetchone())["cnt"]
    print(f"[新增任务点888] task_point_npcs 关联数 = {cnt2} (预期 0)")
    if cnt2 != 0:
        fails.append(f"add_task_point 不应写 task_point_npcs，实际写了 {cnt2} 条")

    print("=" * 50)
    if fails:
        print(f"验证结束：{len(fails)} 项未通过")
        for f in fails:
            print("  -", f)
    else:
        print("验证结束：全部通过 ✅")

    # 清理临时库
    try:
        del os.environ["DB_PATH"]
    except: pass

asyncio.run(main())
