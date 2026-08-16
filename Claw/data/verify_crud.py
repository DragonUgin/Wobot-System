"""验证五个实体的前端 CRUD 后端逻辑（露水/金露水/玩家/线索/任务点）。

去名单化后调整：
  - NPC 名单已砍，移除 NPC CRUD + 任务点NPC关联测试
  - 任务点 CRUD 改用 add_task_point_full / update_task_point / delete_task_point（不带 NPC 参数）
  - 线索补验 hidden_npc_name 文本名字（去名单化核心改动）

隔离到临时库，不碰正式数据。"""
import os, sys, asyncio, time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TMP_DB = ROOT / "data" / f"_crud_{int(time.time())}.db"
if TMP_DB.exists():
    TMP_DB.unlink()
os.environ["DB_PATH"] = str(TMP_DB)
sys.path.insert(0, str(ROOT))

from utils import db as db

def log(*a):
    print(*a, flush=True)

async def main():
    log("=== 前端 CRUD 后端逻辑验证（去名单化版）===")
    await db.get_db()

    # 1. 露水 CRUD
    log("1) 露水 CRUD ...")
    before = len(await db.get_all_dews())
    await db.add_dew_web(901, 4, "未收集")
    await db.update_dew(901, 6, "已收集")
    d = next(x for x in await db.get_all_dews() if x["id"] == 901)
    assert d["dew_value"] == 6 and d["status"] == "已收集", d
    await db.delete_dew(901)
    assert len(await db.get_all_dews()) == before
    log("   ok")

    # 2. 金露水 CRUD（依赖任务点）
    log("2) 金露水 CRUD ...")
    await db.add_task_point_full(801, "测试任务点", "solo", "无", 0)
    before = len(await db.get_all_golden_dews())
    await db.add_golden_dew_web(801, 801)
    await db.update_golden_dew(801, 801)
    g = next(x for x in await db.get_all_golden_dews() if x["id"] == 801)
    assert g["task_point_id"] == 801, g
    await db.delete_golden_dew(801)
    assert len(await db.get_all_golden_dews()) == before
    log("   ok")

    # 3. 玩家 CRUD
    log("3) 玩家 CRUD ...")
    before = len(await db.get_all_players())
    await db.add_player_web(2, "测试玩家甲", "备注")
    p = await db.get_player(2, "测试玩家甲")
    assert p, "无新玩家"
    await db.update_player(p["id"], 2, "测试玩家乙", "改备注")
    p2 = await db.get_player_by_id(p["id"])
    assert p2["name"] == "测试玩家乙", p2
    await db.delete_player(p["id"])
    assert len(await db.get_all_players()) == before
    log("   ok")

    # 4. 线索 CRUD + 藏匿NPC用文本名字（去名单化核心）
    log("4) 线索 CRUD + 文本藏匿名 ...")
    before = len(await db.get_all_clues())
    await db.add_clue(901, "真", 801, "测试线索内容", "示例姓名")
    c = await db.get_clue(901)
    assert c and c["hidden_npc_name"] == "示例姓名", c
    await db.update_clue(901, "假", 801, "改后内容", "张三")
    c = await db.get_clue(901)
    assert c["hidden_npc_name"] == "张三" and c["clue_type"] == "假", c
    await db.delete_clue(901)
    assert len(await db.get_all_clues()) == before
    log("   ok")

    # 5. 任务点 CRUD（不关联 NPC 名单）
    log("5) 任务点 CRUD（无NPC名单）...")
    before = len(await db.get_all_task_points())
    await db.add_task_point_full(802, "NPC任务点", "solo", "护盾卡", 1)
    tp = next(x for x in await db.get_all_task_points() if x["id"] == 802)
    assert "npc_qqs" not in tp, "任务点不应返回 npc_qqs"
    await db.update_task_point(802, "NPC任务点改", "team_vs", "无", 0)
    tp = await db.get_task_point(802)
    assert tp["name"] == "NPC任务点改", tp
    r = await db.delete_task_point(802)
    assert r["ok"], r
    assert len(await db.get_all_task_points()) == before
    log("   ok")

    log("全部 CRUD 验证通过 ✅")
    try:
        TMP_DB.unlink()
    except Exception:
        pass

asyncio.run(asyncio.wait_for(main(), timeout=40))
