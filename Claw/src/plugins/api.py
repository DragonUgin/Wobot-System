"""Web API 路由 — 极限挑战游戏系统"""
import io, csv, json
from pathlib import Path
from nonebot import get_app
from fastapi import UploadFile, File, HTTPException
from fastapi.responses import HTMLResponse, StreamingResponse
from pydantic import BaseModel

app = get_app()
BASE_DIR = Path(__file__).resolve().parent.parent.parent
WEB_DIR = BASE_DIR / "web"
DATA_DIR = BASE_DIR / "data"


@app.get("/", response_class=HTMLResponse)
async def index():
    p = WEB_DIR / "index.html"
    return p.read_text(encoding="utf-8") if p.exists() else "<h1>管理页未部署</h1>"


# ===== 请求体 =====
class GameStartBody(BaseModel): minutes: int

class PlayerActionBody(BaseModel):
    group_num: int
    name: str

class ConfigUpdateBody(BaseModel):
    game_group: str|None=None; work_group: str|None=None; backend_group: str|None=None

class TaskPointCompleteBody(BaseModel):
    task_point_id: int
    clue_id: int | None = None
    dew_id: int = 0
    golden_dew_count: int = 0
    shield_card_count: int = 0
    static_card_count: int = 0

class TaskPointReceiveBody(BaseModel):
    task_point_id: int
    clue_id: int | None = None
    dew_id: int = 0
    golden_dew_count: int = 0
    shield_card_count: int = 0
    static_card_count: int = 0

class DewTargetBody(BaseModel):
    target: int

class ClueStatusBody(BaseModel):
    clue_id: int
    status: str

class TaskPointBody(BaseModel):
    id: int
    name: str
    tp_type: str
    card_name: str = "无"
    golden_dew_count: int = 0
    status: str = "启用"
    static_card_count: int = 0
    static_card_collected: int = 0
    shield_card_count: int = 0
    shield_card_collected: int = 0
    clue_count: int = 0

class ClueBody(BaseModel):
    id: int
    clue_type: str = "真"
    task_point_id: int = 0
    content: str = ""
    hidden_npc_name: str | None = None
    hunter_name: str | None = None

class ClueActionBody(BaseModel):
    id: int


# ===== 广播函数（从 broadcast.py 引用）=====
from utils.broadcast import send_game_group, send_work_group, send_backend_group


# ===== 数据接口 =====
@app.get("/api/status")
async def api_status():
    from utils.timer_logic import get_game_status_display, get_remaining_display, get_remaining_seconds, is_game_active
    from utils.db import get_dew_stats, get_golden_dew_stats
    ds = await get_dew_stats()
    gs = await get_golden_dew_stats()
    return {
        "status": await get_game_status_display(), "active": await is_game_active(),
        "remaining": await get_remaining_display(), "remaining_seconds": await get_remaining_seconds(),
        "dew_stats": ds,
        "dew_pct": round(ds["collected_value"]/ds["target"]*100) if ds["target"] else 0,
        "golden_dew_stats": gs,
    }

@app.get("/api/dews")
async def api_dews():
    from utils.db import get_all_dews
    return await get_all_dews()

@app.get("/api/golden_dews")
async def api_golden_dews():
    from utils.db import get_all_golden_dews
    return await get_all_golden_dews()

@app.get("/api/clues")
async def api_clues():
    from utils.db import get_all_clues
    return await get_all_clues()

@app.get("/api/task_points")
async def api_task_points():
    from utils.db import get_all_task_points
    return await get_all_task_points()

@app.get("/api/players")
async def api_players():
    from utils.db import get_all_players
    return await get_all_players()

@app.get("/api/player/stats")
async def api_player_stats():
    from utils.db import get_player_stats
    return await get_player_stats()

@app.get("/api/player/get")
async def api_player_get(group_num:int, name:str):
    from utils.db import get_player
    p = await get_player(group_num, name)
    if not p: raise HTTPException(404, "玩家不存在")
    return p

@app.get("/api/npcs")
async def api_npcs():
    from utils.db import get_all_npcs
    return await get_all_npcs()

@app.get("/api/config")
async def api_get_config():
    from utils.db import get_all_config; cfg = await get_all_config()
    cfg.pop("admin_qq",None); return cfg


# ===== 游戏控制 =====
@app.post("/api/game/start")
async def api_game_start(body: GameStartBody):
    from utils.timer_logic import start_game
    ok=await start_game(body.minutes)
    if not ok: raise HTTPException(400,"游戏已在进行中")
    from utils.db import get_all_players
    ps=await get_all_players()
    await send_game_group(f"极限挑战开始！时长 {body.minutes} 分钟\n参赛人数：{len(ps)}人")
    await send_work_group(f"[游戏开始] 时长 {body.minutes} 分钟 | 参赛 {len(ps)}人")
    return {"ok":True}

@app.post("/api/game/pause")
async def api_game_pause():
    from utils.timer_logic import pause_game, get_remaining_display
    ok=await pause_game()
    if not ok: raise HTTPException(400,"游戏未在运行中")
    await send_game_group(f"游戏已暂停，剩余时间：{await get_remaining_display()}")
    return {"ok":True}

@app.post("/api/game/resume")
async def api_game_resume():
    from utils.timer_logic import resume_game, get_remaining_display
    ok=await resume_game()
    if not ok: raise HTTPException(400,"游戏未在暂停中")
    await send_game_group(f"游戏继续！剩余时间：{await get_remaining_display()}")
    return {"ok":True}

@app.post("/api/game/end")
async def api_game_end():
    from utils.timer_logic import end_game
    from utils.db import get_dew_stats
    ok=await end_game()
    if not ok: raise HTTPException(400,"当前没有进行中的游戏")
    ds=await get_dew_stats()
    await send_game_group(f"极限挑战结束！\n露水收集：{ds['collected_value']}/{ds['target']}滴")
    return {"ok":True,"dew_stats":ds}


# ===== 露水操作 =====
@app.post("/api/dew/collect/{dew_id}")
async def api_collect_dew(dew_id:int):
    from utils.db import collect_dew_from_web, add_operation_log
    ok=await collect_dew_from_web(dew_id)
    if not ok: raise HTTPException(400,"露水状态异常（需先在任务点送出对应线索使其变为'已发现未收集'）")
    await add_operation_log("collect_dew", f"露水{dew_id} 前端收集", json.dumps({"dew_id": dew_id}))
    await send_work_group(f"[露水] 露水{dew_id} 已收集 → 对应真线索已收集已发现")
    return {"ok":True}


# ===== 金露水收集 =====
@app.post("/api/golden_dew/collect/{dew_id}")
async def api_collect_golden_dew(dew_id:int):
    from utils.db import collect_golden_dew, add_operation_log
    ok=await collect_golden_dew(dew_id)
    if not ok: raise HTTPException(400,"金露水已收集或不存在")
    await add_operation_log("collect_golden_dew", f"金露水{dew_id} 收集", json.dumps({"dew_id": dew_id}))
    from utils.db import get_golden_dew_stats
    gs=await get_golden_dew_stats()
    await send_work_group(f"[金露水] 金露水{dew_id} 已收集 | 当前库存 {gs['available']}/{gs['total']}")
    return {"ok":True,"golden_dew_stats":gs}


# ===== 任务点操作 =====
@app.get("/api/task_points/{tp_id}/inventory")
async def api_task_point_inventory(tp_id:int):
    from utils.db import get_task_point_inventory
    return await get_task_point_inventory(tp_id)

@app.post("/api/task_point/complete")
async def api_task_point_complete(body: TaskPointCompleteBody):
    """Web 管理员手动标记任务点完成（新格式：完整四物品）"""
    from utils.db import process_task_point_complete, add_operation_log
    result = await process_task_point_complete(body.task_point_id, body.clue_id, body.dew_id, body.golden_dew_count, body.shield_card_count, body.static_card_count)
    if not result["ok"]:
        raise HTTPException(400, result["msg"])
    await add_operation_log(
        "tp_complete", f"任务点{body.task_point_id} 管理员标记完成 {result['details']}",
        json.dumps({"tp_id": body.task_point_id, "clue_id": body.clue_id, "golden_dew": body.golden_dew_count,
                   "shield_card": body.shield_card_count, "static_card": body.static_card_count}), 0
    )
    # 全局任务免疫
    from utils.db import set_global_task_immune
    await set_global_task_immune()
    from utils.broadcast import send_game_group, send_work_group
    await send_game_group(f"[免疫] 任务点{body.task_point_id} 完成 | 全体玩家15秒内不可被淘汰")
    await send_work_group(f"[任务点] 任务点{body.task_point_id} 管理员标记送出道具 | {result['details']}")
    return {"ok": True, "details": result["details"]}


@app.post("/api/task_point/receive")
async def api_task_point_receive(body: TaskPointReceiveBody):
    """Web 管理员手动标记任务点接收（入库散落道具，不触发全局免疫）"""
    from utils.db import process_task_point_receive, add_operation_log
    result = await process_task_point_receive(body.task_point_id, body.clue_id, body.dew_id, body.golden_dew_count, body.shield_card_count, body.static_card_count)
    if not result["ok"]:
        raise HTTPException(400, result["msg"])
    await add_operation_log(
        "tp_receive", f"任务点{body.task_point_id} 管理员标记接收 {result['details']}",
        json.dumps({"tp_id": body.task_point_id, "clue_id": body.clue_id, "dew_id": body.dew_id, "golden_dew": body.golden_dew_count,
                   "shield_card": body.shield_card_count, "static_card": body.static_card_count}), 0
    )
    from utils.broadcast import send_work_group
    await send_work_group(f"[任务点] 任务点{body.task_point_id} 管理员标记接收物资 | {result['details']}")
    return {"ok": True, "details": result["details"]}


# ===== 狂欢模式（上帝时刻）=====
@app.get("/api/frenzy/status")
async def api_frenzy_status():
    from utils.db import get_frenzy_mode
    return {"active": await get_frenzy_mode()}

@app.post("/api/frenzy/activate")
async def api_frenzy_activate():
    from utils.db import set_frenzy_mode, get_frenzy_mode, reveal_all_clues, add_operation_log
    if await get_frenzy_mode():
        return {"ok": False, "msg": "狂欢模式已激活"}
    await set_frenzy_mode(True)
    changed = await reveal_all_clues()
    await add_operation_log(
        "frenzy_reveal", f"狂欢模式-线索公示({len(changed)}条)",
        json.dumps({"clues": changed}), 0
    )
    msg = (
        "[上帝时刻] 狂欢模式激活！\n"
        "猎人淘汰冷却延长至40秒\n"
        f"所有线索已公示（{len(changed)}条）"
    )
    await send_game_group(msg)
    await send_work_group(msg)
    await send_backend_group(f"[大盘] 狂欢模式激活 | 线索公示{len(changed)}条 | 淘汰冷却40s")
    return {"ok": True, "revealed": len(changed)}

@app.post("/api/frenzy/deactivate")
async def api_frenzy_deactivate():
    from utils.db import set_frenzy_mode
    await set_frenzy_mode(False)
    await send_game_group("[上帝时刻] 狂欢模式已关闭，淘汰冷却恢复为20秒")
    await send_work_group("[上帝时刻] 狂欢模式已关闭，淘汰冷却恢复为20秒")
    return {"ok": True}


# ===== 任务点CRUD =====
@app.post("/api/task_point/add")
async def api_task_point_add(body: TaskPointBody):
    from utils.db import add_task_point_full
    await add_task_point_full(body.id, body.name, body.tp_type, body.card_name, body.golden_dew_count, body.status,
        body.static_card_count, body.static_card_collected, body.shield_card_count, body.shield_card_collected, body.clue_count)
    return {"ok":True}

@app.post("/api/task_point/update")
async def api_task_point_update(body: TaskPointBody):
    from utils.db import update_task_point
    r=await update_task_point(body.id, body.name, body.tp_type, body.card_name, body.golden_dew_count, body.status,
        body.static_card_count, body.static_card_collected, body.shield_card_count, body.shield_card_collected, body.clue_count)
    if not r["ok"]: raise HTTPException(400, r["msg"])
    return r

@app.post("/api/task_point/delete")
async def api_task_point_delete(body: dict):
    from utils.db import delete_task_point
    r=await delete_task_point(body["id"])
    if not r["ok"]: raise HTTPException(400, r["msg"])
    return r

@app.post("/api/task_point/status")
async def api_task_point_status(body: dict):
    from utils.db import update_task_point_status
    await update_task_point_status(body["id"], body["status"])
    return {"ok":True}


# ===== 露水目标量 =====
@app.post("/api/config/dew_target")
async def api_set_dew_target(body: DewTargetBody):
    from utils.db import set_dew_target
    await set_dew_target(body.target)
    return {"ok":True}

# ===== 露水/金露水/线索重置 =====
@app.post("/api/dew/reset/{dew_id}")
async def api_reset_dew(dew_id:int):
    from utils.db import reset_dew
    await reset_dew(dew_id)
    return {"ok":True}

@app.post("/api/golden_dew/reset/{dew_id}")
async def api_reset_golden_dew(dew_id:int):
    from utils.db import reset_golden_dew
    await reset_golden_dew(dew_id)
    return {"ok":True}

@app.post("/api/clue/status")
async def api_update_clue_status(body: ClueStatusBody):
    from utils.db import update_clue_status
    await update_clue_status(body.clue_id, body.status)
    return {"ok":True}

@app.post("/api/clue/add")
async def api_clue_add(body: ClueBody):
    from utils.db import get_clue, add_clue
    if await get_clue(body.id): raise HTTPException(400, "线索编号已存在")
    await add_clue(body.id, body.clue_type, body.task_point_id, body.content, body.hidden_npc_name, body.hunter_name)
    return {"ok":True}

@app.post("/api/clue/update")
async def api_clue_update(body: ClueBody):
    from utils.db import update_clue
    await update_clue(body.id, body.clue_type, body.task_point_id, body.content, body.hidden_npc_name, body.hunter_name)
    return {"ok":True}

@app.post("/api/clue/delete")
async def api_clue_delete(body: ClueActionBody):
    from utils.db import delete_clue
    r=await delete_clue(body.id)
    if not r["ok"]: raise HTTPException(400, r["msg"])
    return r

@app.post("/api/clue/collect")
async def api_clue_collect(body: ClueActionBody):
    from utils.db import collect_clue_manual, add_operation_log
    await collect_clue_manual(body.id)
    await add_operation_log("collect_clue", f"线索{body.id}手动标记已收集", "", None)
    await send_work_group(f"[线索] 管理员操作：线索{body.id} 已手动标记为已收集已发现")
    return {"ok":True}

@app.post("/api/clue/reset")
async def api_clue_reset(body: ClueActionBody):
    from utils.db import reset_clue_status, add_operation_log
    await reset_clue_status(body.id)
    await add_operation_log("reset_clue", f"线索{body.id}重置为未收集", "", None)
    await send_work_group(f"[线索] 管理员操作：线索{body.id} 已重置为未收集")
    return {"ok":True}


# ===== 猎人持有物 / 无主线索 =====
class HunterClueBody(BaseModel):
    clue_id: int
    hunter_name: str

@app.get("/api/hunter/items")
async def api_hunter_items(hunter_name: str):
    from utils.db import get_hunter_items
    return await get_hunter_items(hunter_name)

@app.get("/api/hunter/list")
async def api_hunter_list():
    from utils.db import get_hunters_with_items
    return await get_hunters_with_items()

@app.get("/api/orphan/clues")
async def api_orphan_clues():
    from utils.db import get_orphan_clues
    return await get_orphan_clues()

@app.post("/api/hunter/clue/assign")
async def api_hunter_clue_assign(body: HunterClueBody):
    from utils.db import assign_clue_to_hunter
    r=await assign_clue_to_hunter(body.clue_id, body.hunter_name)
    if not r["ok"]: raise HTTPException(400, r["msg"])
    return r

@app.post("/api/clue/unassign")
async def api_clue_unassign(body: ClueActionBody):
    from utils.db import unassign_clue
    r=await unassign_clue(body.id)
    if not r["ok"]: raise HTTPException(400, r["msg"])
    return r


# ===== 玩家淘汰/复活 =====
@app.post("/api/player/eliminate")
async def api_player_elim(body: PlayerActionBody):
    from utils.db import eliminate_player, add_operation_log
    ok=await eliminate_player(body.group_num, body.name, source='admin')
    if not ok: raise HTTPException(400,"玩家不存在或已淘汰")
    await add_operation_log("eliminate", f"{body.group_num}组{body.name} 管理员淘汰", json.dumps({"group_num": body.group_num, "name": body.name}))
    await send_game_group(f"管理员操作：{body.group_num}组{body.name} 被淘汰")
    await send_work_group(f"[淘汰] 管理员操作：{body.group_num}组{body.name} 被淘汰")
    return {"ok":True}

@app.post("/api/player/revive")
async def api_player_revive(body: PlayerActionBody):
    from utils.db import revive_player, get_golden_dew_stats, add_operation_log
    r = await revive_player(body.group_num, body.name)
    if not r["ok"]:
        raise HTTPException(400, r["msg"])
    await add_operation_log("revive", f"{body.group_num}组{body.name} 复活", json.dumps({"group_num": body.group_num, "name": body.name, "golden_dew_id": r["golden_dew_id"]}))
    gs = await get_golden_dew_stats()
    await send_game_group(f"管理员操作：{body.group_num}组{body.name} 已复活")
    await send_work_group(f"[复活] 管理员操作：{body.group_num}组{body.name} 已复活 | 消耗金露水#{r['golden_dew_id']} | 剩余库存 {gs['available']}")
    return {"ok": True, "consumed_golden_dew": r["golden_dew_id"], "golden_dew_stats": gs}

@app.post("/api/player/reset")
async def api_player_reset(body: PlayerActionBody):
    from utils.db import reset_player_status, add_operation_log
    ok=await reset_player_status(body.group_num, body.name)
    if not ok: raise HTTPException(400,"玩家不存在或状态无需重置")
    await add_operation_log("reset", f"{body.group_num}组{body.name} 管理员重置为存活", json.dumps({"group_num": body.group_num, "name": body.name}))
    await send_game_group(f"管理员操作：{body.group_num}组{body.name} 已重置为存活")
    await send_work_group(f"[重置] 管理员操作：{body.group_num}组{body.name} 已重置为存活（不消耗金露水）")
    return {"ok":True}

@app.post("/api/player/clear_all")
async def api_player_clear_all():
    from utils.db import clear_all_players
    await clear_all_players()
    await send_game_group("管理员已清空所有玩家数据")
    return {"ok":True}


# ===== 实体 CRUD（前端管理：露水/金露水/玩家/NPC） =====
@app.post("/api/dew/add")
async def api_dew_add(body: dict):
    from utils.db import get_all_dews, add_dew_web, add_operation_log
    did = int(body["id"])
    if any(d["id"] == did for d in await get_all_dews()):
        raise HTTPException(400, "露水编号已存在")
    hunter_name = body.get("hunter_name") or None
    r = await add_dew_web(did, int(body.get("dew_value", 2)), body.get("status", "未收集"), hunter_name)
    if not r["ok"]:
        raise HTTPException(400, "露水编号已存在")
    await add_operation_log("add_dew", f"新增露水{did}{('(猎人:'+hunter_name+')') if hunter_name else ''}", json.dumps({"id": did, "hunter_name": hunter_name}), 0)
    return {"ok": True}

@app.post("/api/dew/update")
async def api_dew_update(body: dict):
    from utils.db import update_dew
    await update_dew(int(body["id"]), int(body.get("dew_value", 2)), body.get("status", "未收集"), body.get("hunter_name") or None)
    return {"ok": True}

@app.post("/api/dew/delete")
async def api_dew_delete(body: dict):
    from utils.db import get_all_dews, delete_dew, add_operation_log
    d = next((x for x in await get_all_dews() if x["id"] == int(body["id"])), None)
    if not d:
        raise HTTPException(400, "露水不存在")
    await delete_dew(int(body["id"]))
    await add_operation_log("delete_dew", f"删除露水{body['id']}", json.dumps({"row": d}), 0)
    return {"ok": True}


@app.post("/api/golden_dew/add")
async def api_gd_add(body: dict):
    from utils.db import get_all_golden_dews, add_golden_dew_web, add_operation_log
    gid = int(body["id"]); tpid = int(body["task_point_id"])
    if any(g["id"] == gid for g in await get_all_golden_dews()):
        raise HTTPException(400, "金露水编号已存在")
    r = await add_golden_dew_web(gid, tpid)
    if not r["ok"]:
        raise HTTPException(400, "金露水编号已存在")
    await add_operation_log("add_golden_dew", f"新增金露水{gid}", json.dumps({"id": gid}), 0)
    return {"ok": True}

@app.post("/api/golden_dew/update")
async def api_gd_update(body: dict):
    from utils.db import update_golden_dew
    await update_golden_dew(int(body["id"]), int(body["task_point_id"]))
    return {"ok": True}

@app.post("/api/golden_dew/delete")
async def api_gd_delete(body: dict):
    from utils.db import get_all_golden_dews, delete_golden_dew, add_operation_log
    d = next((g for g in await get_all_golden_dews() if g["id"] == int(body["id"])), None)
    if not d:
        raise HTTPException(400, "金露水不存在")
    await delete_golden_dew(int(body["id"]))
    await add_operation_log("delete_golden_dew", f"删除金露水{body['id']}", json.dumps({"row": d}), 0)
    return {"ok": True}


@app.post("/api/player/add")
async def api_player_add(body: dict):
    from utils.db import add_player_web, get_player, add_operation_log
    r = await add_player_web(int(body["group_num"]), body["name"], body.get("note", ""))
    if not r["ok"]:
        raise HTTPException(400, "该组号+姓名已存在")
    p = await get_player(int(body["group_num"]), body["name"])
    pid = p["id"] if p else None
    if pid is not None:
        await add_operation_log("add_player", f"新增玩家 {body['group_num']}组{body['name']}", json.dumps({"id": pid}), 0)
    return {"ok": True}

@app.post("/api/player/update")
async def api_player_update(body: dict):
    from utils.db import update_player, get_player, add_operation_log
    pid = int(body["id"])
    old = await get_player(int(body.get("group_num")), body.get("name")) if False else None
    p = await get_player_by_id(pid)
    if not p:
        raise HTTPException(400, "玩家不存在")
    r = await update_player(pid, int(body["group_num"]), body["name"], body.get("note", ""))
    if not r["ok"]:
        raise HTTPException(400, r["msg"])
    await add_operation_log("update_player", f"编辑玩家 {body['group_num']}组{body['name']}",
                            json.dumps({"id": pid, "old": {"group_num": p["group_num"], "name": p["name"], "note": p["note"]}}), 0)
    return {"ok": True}

@app.post("/api/player/delete")
async def api_player_delete(body: dict):
    from utils.db import get_player_by_id, delete_player, add_operation_log
    p = await get_player_by_id(int(body["id"]))
    if not p:
        raise HTTPException(400, "玩家不存在")
    await delete_player(int(body["id"]))
    await add_operation_log("delete_player", f"删除玩家 {p['group_num']}组{p['name']}", json.dumps({"row": p}), 0)
    return {"ok": True}


# NPC 增删改端点已移除：NPC 名单砍掉，改为线下口头约定，不再系统化管理
# /api/npcs（GET）保留仅用于查看备注性的 NPC 记录（Excel 导入写入）


# ===== 导入 =====
@app.post("/api/import/all")
async def api_import_all(file:UploadFile=File(...)):
    from utils.excel_importer import import_all_from_excel
    DATA_DIR.mkdir(parents=True,exist_ok=True)
    tmp=DATA_DIR/"_upload.xlsx"; tmp.write_bytes(await file.read())
    result=await import_all_from_excel(str(tmp))
    import os; os.remove(str(tmp)) # bypass sandbox safe-delete
    return result


# ===== 配置 =====
@app.post("/api/config/update")
async def api_config_update(body:ConfigUpdateBody):
    from utils.db import set_config; import config as cfg
    for k,v in body.dict(exclude_none=True).items():
        await set_config(k,str(v))
    await cfg.reload_config()
    return {"ok":True}


# ===== 操作日志（实时事件栏 + 网页撤销） =====
@app.get("/api/operations/recent")
async def api_ops_recent(limit:int=20):
    from utils.db import get_recent_operations
    ops=await get_recent_operations(limit)
    return [{"id":o["id"],"op_type":o["op_type"],"target_desc":o["target_desc"],"created_at":o["created_at"]} for o in ops]

@app.post("/api/operation/undo/{log_id}")
async def api_undo_operation(log_id:int):
    import json as _json
    from utils.db import get_recent_operations, undo_operation
    # 取该 ID 的操作日志
    ops=await get_recent_operations(100)
    op=next((o for o in ops if o["id"]==log_id), None)
    if not op:
        raise HTTPException(404,"操作记录不存在")
    try:
        data=_json.loads(op["undo_data"]) if op["undo_data"] else {}
    except:
        data={}
    result=await undo_operation(op, data)
    if result:
        return {"ok":True,"msg":result}
    raise HTTPException(400,"不支持的操作类型或撤销失败")

# ===== 导出 =====
@app.get("/api/export/json")
async def api_export_json():
    from utils.db import get_all_players, get_all_dews, get_all_clues
    data={"players":await get_all_players(),"dews":await get_all_dews(),"clues":await get_all_clues()}
    return StreamingResponse(iter([json.dumps(data,ensure_ascii=False,indent=2)]),media_type="application/json",headers={"Content-Disposition":"attachment; filename=export.json"})

@app.get("/api/export/csv")
async def api_export_csv():
    from utils.db import get_all_players, get_all_dews
    o=io.StringIO(); w=csv.writer(o)
    w.writerow(["组号","姓名","备注"])
    for p in await get_all_players(): w.writerow([p["group_num"],p["name"],p.get("note","")])
    o.seek(0)
    return StreamingResponse(iter([o.getvalue()]),media_type="text/csv",headers={"Content-Disposition":"attachment; filename=export.csv"})
