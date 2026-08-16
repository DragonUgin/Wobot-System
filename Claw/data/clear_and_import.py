"""清空正式库 claw.db 现有游戏数据 + 导入 sample_game_data.xlsx 一条龙。
保留 system_config（三群号/admin_qq 等配置）与 schema_version。
"""
import os, sys, asyncio
from pathlib import Path

ROOT = Path(r"D:/58系统/Claw")
os.environ["DB_PATH"] = str(ROOT / "data" / "claw.db")
sys.path.insert(0, str(ROOT))

from utils import db as D
from utils.excel_importer import import_all_from_excel

TABLES = ["players", "npcs", "task_points", "clues", "dews", "golden_dews"]


async def main():
    dbc = await D.get_db()

    print("=== 0. 清空前 ===")
    for t in TABLES:
        n = (await (await dbc.execute(f"SELECT COUNT(*) FROM {t}")).fetchone())[0]
        print(f"  {t} = {n}")

    print("\n=== 1. 清空现有游戏数据（clear_all_players）===")
    await D.clear_all_players()
    for t in TABLES:
        n = (await (await dbc.execute(f"SELECT COUNT(*) FROM {t}")).fetchone())[0]
        print(f"  {t} = {n}  (应全为 0)")

    print("\n=== 2. 导入 sample_game_data.xlsx ===")
    r = await import_all_from_excel(str(ROOT / "data" / "sample_game_data.xlsx"))
    print("  结果:", {k: v for k, v in r.items() if k != "errors"})
    print("  错误:", r["errors"] or "无")
    if r["errors"]:
        print("  !! 存在导入错误，已中断后续验证")
        await dbc.close()
        return

    print("\n=== 3. 导入后核对 ===")
    for t in TABLES:
        n = (await (await dbc.execute(f"SELECT COUNT(*) FROM {t}")).fetchone())[0]
        print(f"  {t} = {n}")
    tp = await D.get_task_point(1)
    print("  任务点1:", {k: tp[k] for k in ["name", "status", "shield_card_count", "static_card_count", "golden_dew_count"]})
    names = {p["name"] for p in await D.get_all_players()}
    print("  玩家名单:", names)

    print("\n=== 一条龙完成 ===")
    await dbc.close()


asyncio.run(main())
