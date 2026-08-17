# SPDX-License-Identifier: GPL-3.0-or-later
"""SQLite 数据库层 — 极限挑战游戏系统"""
import aiosqlite
from datetime import datetime
from pathlib import Path
from config import DB_PATH

_SCHEMA = """
-- 玩家表
CREATE TABLE IF NOT EXISTS players (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    group_num INTEGER NOT NULL,
    name      TEXT NOT NULL,
    status    TEXT DEFAULT '存活',
    source    TEXT,
    eliminated_at TEXT,
    revived_at TEXT,
    note      TEXT,
    created_at TEXT DEFAULT (datetime('now', 'localtime')),
    UNIQUE(group_num, name)
);

-- NPC/猎人/机动人员表
CREATE TABLE IF NOT EXISTS npcs (
    qq         INTEGER PRIMARY KEY,
    name       TEXT,
    role       TEXT NOT NULL DEFAULT 'hunter',  -- task_npc / hunter / mobile
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 任务点表
CREATE TABLE IF NOT EXISTS task_points (
    id               INTEGER PRIMARY KEY,
    name             TEXT NOT NULL,
    tp_type          TEXT NOT NULL DEFAULT 'solo',  -- team_vs / team_coop / solo
    card_name        TEXT DEFAULT '',                 -- 静止卡 / 护盾卡 / 无
    npc_qq           INTEGER,
    golden_dew_count INTEGER DEFAULT 0,
    static_card_count    INTEGER DEFAULT 0,   -- 静止卡总数
    static_card_collected INTEGER DEFAULT 0,  -- 静止卡已收集
    shield_card_count    INTEGER DEFAULT 0,   -- 护盾卡总数
    shield_card_collected INTEGER DEFAULT 0,  -- 护盾卡已收集
    clue_count           INTEGER DEFAULT 0,   -- 线索数量
    status           TEXT DEFAULT '未开启',
    FOREIGN KEY (npc_qq) REFERENCES npcs(qq)
);

-- 任务点-NPC 多对多关系表
CREATE TABLE IF NOT EXISTS task_point_npcs (
    task_point_id INTEGER NOT NULL,
    npc_qq        INTEGER NOT NULL,
    created_at    TEXT DEFAULT (datetime('now','localtime')),
    PRIMARY KEY (task_point_id, npc_qq),
    FOREIGN KEY (task_point_id) REFERENCES task_points(id),
    FOREIGN KEY (npc_qq) REFERENCES npcs(qq)
);

-- 普通露水表
CREATE TABLE IF NOT EXISTS dews (
    id           INTEGER PRIMARY KEY,
    status       TEXT DEFAULT '未收集',
    collected_at TEXT,
    dew_value    INTEGER DEFAULT 2,   -- 每张露水卡的滴数
    hunter_name  TEXT                -- 猎人持有露水归属（直接归属，不靠线索id配对；NULL=任务点池 / 有值=猎人池）
);

-- 金露水表
CREATE TABLE IF NOT EXISTS golden_dews (
    id            INTEGER PRIMARY KEY,
    task_point_id INTEGER NOT NULL,
    status        TEXT DEFAULT '未收集',
    collected_at  TEXT,
    FOREIGN KEY (task_point_id) REFERENCES task_points(id)
);

-- 线索表
CREATE TABLE IF NOT EXISTS clues (
    id             INTEGER PRIMARY KEY,
    clue_type      TEXT NOT NULL DEFAULT '真',   -- 真 / 假
    task_point_id  INTEGER NOT NULL,
    content        TEXT DEFAULT '',
    hidden_npc_qq  INTEGER,                       -- 旧字段，保留兼容；新数据用 hidden_npc_name
    hidden_npc_name TEXT,                          -- 藏匿NPC姓名（纯文本，不关联QQ，线下口头约定）
    hunter_name    TEXT,                           -- 猎人持有线索/露水归属（纯名字字符串，不关联QQ，去名单化）
    status         TEXT DEFAULT '未收集',         -- 未收集 / 已收集未发现 / 已收集已发现
    collected_at   TEXT,
    discovered_at  TEXT,
    FOREIGN KEY (task_point_id) REFERENCES task_points(id)
);

-- 游戏状态表
CREATE TABLE IF NOT EXISTS game_state (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO game_state (key, value) VALUES
    ('status', 'idle'), ('start_time', ''),
    ('duration_minutes', '90'), ('elapsed_seconds', '0'), ('pause_time', ''),
    ('dew_target', '0');

-- 系统配置表
CREATE TABLE IF NOT EXISTS system_config (
    key   TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
INSERT OR IGNORE INTO system_config (key, value) VALUES
    ('game_group', ''), ('work_group', ''), ('backend_group', ''), ('admin_qq', '');

-- 任务点物资/完成记录表
CREATE TABLE IF NOT EXISTS task_point_inventory (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_point_id INTEGER NOT NULL,
    source      TEXT NOT NULL,  -- 'complete'（任务完成获得） / 'receive'（接收物资）
    item_type   TEXT NOT NULL,  -- 线索 / 功能卡 / 露水 / 金露水
    item_id     INTEGER,
    created_at  TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (task_point_id) REFERENCES task_points(id)
);

-- 操作日志表（用于撤销）
CREATE TABLE IF NOT EXISTS operation_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    op_type TEXT NOT NULL,
    target_desc TEXT,
    undo_data TEXT,
    operator_qq INTEGER,
    created_at TEXT DEFAULT (datetime('now', 'localtime'))
);

-- 冷却持久化表
CREATE TABLE IF NOT EXISTS cooldowns (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cooldown_type TEXT NOT NULL,   -- 'capture' / 'static_card'
    hunter_key TEXT NOT NULL,      -- 猎人QQ号(抓捕) 或 猎人名字(静止卡)
    hunter_name TEXT DEFAULT '',
    expire_at TEXT NOT NULL,
    broadcast INTEGER DEFAULT 1
);

-- 数据库 schema 版本号（迁移管理）
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);
INSERT OR IGNORE INTO schema_version (version) VALUES (0);
"""

_db: aiosqlite.Connection | None = None

# 当前最新的 schema 版本号（每次加列/加表后 +1）
CURRENT_SCHEMA_VERSION = 6


async def _add_column_if_missing(db: aiosqlite.Connection, table: str, column: str, ddl: str):
    """幂等加列：全新库由 _SCHEMA 建表时已带该列，旧库才真正 ALTER。

    不能只靠 schema_version 判断——全新库的 version 也是 0，会重复 ALTER 报
    "duplicate column name" 并中断后续所有迁移。
    """
    cur = await db.execute(f"PRAGMA table_info({table})")
    cols = {r[1] for r in await cur.fetchall()}
    if column in cols:
        return
    await db.execute(f"ALTER TABLE {table} ADD COLUMN {column} {ddl}")


async def _migrate(db: aiosqlite.Connection):
    """按版本号顺序执行数据库迁移，只跑未执行的版本（每步均幂等）"""
    # 规整 schema_version：仅保留最大版本那一行，删除其余，
    # 避免 _SCHEMA 的 INSERT OR IGNORE 在重启后重复插入 0 造成多行、后续 UPDATE 主键冲突
    await db.execute("DELETE FROM schema_version WHERE version < (SELECT MAX(version) FROM schema_version)")
    cur = await db.execute("SELECT MAX(version) FROM schema_version")
    row = await cur.fetchone()
    db_ver = row[0] if row and row[0] is not None else 0

    if db_ver < 1:
        # v0→v1: task_points 加 status 列
        await _add_column_if_missing(db, "task_points", "status", "TEXT DEFAULT '启用'")

    if db_ver < 2:
        # v1→v2: task_points 加卡片/线索计数列
        for col in ["static_card_count", "static_card_collected",
                     "shield_card_count", "shield_card_collected", "clue_count"]:
            await _add_column_if_missing(db, "task_points", col, "INTEGER DEFAULT 0")

    if db_ver < 3:
        # v2→v3: dews 加 dew_value 列
        await _add_column_if_missing(db, "dews", "dew_value", "INTEGER DEFAULT 2")

    if db_ver < 4:
        # v3→v4: clues 加 hidden_npc_name 列（藏匿NPC改为纯文本名字，不再关联QQ）
        await _add_column_if_missing(db, "clues", "hidden_npc_name", "TEXT")
        # 旧数据回填：按 hidden_npc_qq 反查 npcs.name 填入 hidden_npc_name
        await db.execute(
            "UPDATE clues SET hidden_npc_name=(SELECT name FROM npcs WHERE npcs.qq=clues.hidden_npc_qq) "
            "WHERE hidden_npc_name IS NULL AND hidden_npc_qq IS NOT NULL"
        )

    if db_ver < 5:
        # v4→v5: clues 加 hunter_name 列（猎人持有线索/露水，靠名字字符串标识，不引入QQ名单）
        # 线索归属三态：task_point_id!=0 → 任务点；hunter_name NOT NULL → 猎人；两者皆空(0+NULL) → 无主
        await _add_column_if_missing(db, "clues", "hunter_name", "TEXT")

    if db_ver < 6:
        # v5→v6: dews 加 hunter_name 列（猎人持有露水，直接归属，与线索解耦）
        # 总露水池分为两半：hunter_name IS NULL → 任务点池；hunter_name NOT NULL → 猎人池（新建独立记录，不取全局池已有id）
        await _add_column_if_missing(db, "dews", "hunter_name", "TEXT")

    # 仅更新最大版本那一行，避免多行触发 UNIQUE 冲突
    await db.execute(
        "UPDATE schema_version SET version=? WHERE version=(SELECT MAX(version) FROM schema_version)",
        (CURRENT_SCHEMA_VERSION,),
    )
    await db.commit()


async def get_db() -> aiosqlite.Connection:
    global _db
    if _db is None:
        DB_PATH.parent.mkdir(parents=True, exist_ok=True)
        conn = await aiosqlite.connect(str(DB_PATH))
        conn.row_factory = aiosqlite.Row
        try:
            await conn.executescript(_SCHEMA)
            await _migrate(conn)
        except Exception:
            # 初始化失败必须暴露出来，否则会被调用方的 try/except 吞掉，
            # 表现为"莫名其妙只丢了第一条数据"
            await conn.close()
            raise
        _db = conn
    return _db

# ===== 玩家 =====
async def init_players(plist):
    added = 0; db = await get_db()
    for g, n in plist:
        try:
            await db.execute("INSERT INTO players(group_num,name)VALUES(?,?)", (g, n))
            added += 1
        except aiosqlite.IntegrityError:
            pass
    await db.commit(); return added


async def get_all_players():
    db=await get_db(); c=await db.execute("SELECT * FROM players ORDER BY group_num,name")
    return [dict(r) for r in await c.fetchall()]

async def get_player(group_num:int, name:str):
    db=await get_db()
    c=await db.execute("SELECT * FROM players WHERE group_num=? AND name=?", (group_num, name))
    r=await c.fetchone(); return dict(r) if r else None

async def get_player_by_id(pid:int):
    db=await get_db()
    c=await db.execute("SELECT * FROM players WHERE id=?", (pid,))
    r=await c.fetchone(); return dict(r) if r else None

async def eliminate_player(group_num:int, name:str, source:str='admin', note:str=''):
    """手动淘汰玩家 — 支持「存活」和「复活」两种状态被淘汰"""
    db=await get_db()
    now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c=await db.execute(
        "UPDATE players SET status='淘汰',source=?,eliminated_at=? WHERE group_num=? AND name=? AND (status='存活' OR status='复活')",
        (source,now,group_num,name)
    )
    await db.commit(); return c.rowcount>0

async def record_elimination_location(group_num: int, name: str, location: str):
    """记录淘汰地点到玩家 note 字段"""
    db = await get_db()
    await db.execute("UPDATE players SET note=? WHERE group_num=? AND name=?", (location, group_num, name))
    await db.commit()

async def revive_player(group_num:int, name:str)->dict:
    """复活玩家 — 消耗1个已收集的金露水（库存自动减一）

    返回 {"ok":bool,"msg":str,"golden_dew_id":int|None}
    金露水状态流转：未收集 → 已收集 → 已使用
    """
    db=await get_db()
    # 1. 校验玩家
    p=await get_player(group_num, name)
    if not p:
        return {"ok":False,"msg":"玩家不存在","golden_dew_id":None}
    if p["status"]!="淘汰":
        return {"ok":False,"msg":f"玩家当前状态为{p['status']}，无法复活","golden_dew_id":None}
    # 2. 取一个最早收集的金露水（FIFO）
    c=await db.execute(
        "SELECT id FROM golden_dews WHERE status='已收集' ORDER BY collected_at ASC, id ASC LIMIT 1"
    )
    row=await c.fetchone()
    if not row:
        return {"ok":False,"msg":"金露水库存不足，无法复活","golden_dew_id":None}
    gid=row["id"]
    # 3. 消耗金露水（标记为已使用）
    await db.execute(
        "UPDATE golden_dews SET status='已使用' WHERE id=? AND status='已收集'",
        (gid,)
    )
    # 4. 更新玩家状态
    now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c=await db.execute(
        "UPDATE players SET status='复活',revived_at=? WHERE group_num=? AND name=? AND status='淘汰'",
        (now,group_num,name)
    )
    if c.rowcount==0:
        # 玩家状态更新失败，回滚金露水
        await db.execute("UPDATE golden_dews SET status='已收集' WHERE id=?",(gid,))
        await db.commit()
        return {"ok":False,"msg":"玩家状态更新失败，已回滚金露水","golden_dew_id":None}
    await db.commit()
    return {"ok":True,"msg":"复活成功","golden_dew_id":gid}

async def reset_player_status(group_num:int, name:str)->bool:
    """重置玩家为「存活」（免费撤销淘汰/复活，不消耗金露水）"""
    db=await get_db()
    c=await db.execute(
        "UPDATE players SET status='存活',eliminated_at=NULL,revived_at=NULL,source=?,note='' WHERE group_num=? AND name=? AND status IN ('淘汰','复活')",
        ('admin',group_num,name)
    )
    await db.commit()
    return c.rowcount>0

async def get_player_stats():
    """获取玩家状态统计"""
    db=await get_db()
    stats={}
    for s in ('存活','淘汰','复活'):
        c=await db.execute("SELECT COUNT(*) as cnt FROM players WHERE status=?",(s,))
        stats[s]=(await c.fetchone())["cnt"]
    c=await db.execute("""SELECT group_num,
        SUM(CASE WHEN status='存活' THEN 1 ELSE 0 END) as alive,
        SUM(CASE WHEN status='淘汰' THEN 1 ELSE 0 END) as dead,
        SUM(CASE WHEN status='复活' THEN 1 ELSE 0 END) as revived
        FROM players GROUP BY group_num ORDER BY group_num""")
    stats['groups']=[dict(r) for r in await c.fetchall()]
    stats['total']=sum(stats[s] for s in ('存活','淘汰','复活'))
    return stats

async def clear_all_players():
    db=await get_db()
    await db.execute("DELETE FROM players")
    await db.execute("DELETE FROM dews")
    await db.execute("DELETE FROM golden_dews")
    await db.execute("DELETE FROM clues")
    await db.execute("DELETE FROM task_points")
    await db.execute("DELETE FROM npcs")
    # 修复：清空关联表，避免孤儿数据残留
    await db.execute("DELETE FROM task_point_npcs")
    await db.execute("DELETE FROM task_point_inventory")
    await db.execute("DELETE FROM cooldowns")
    await db.execute("DELETE FROM operation_log")
    # 重置游戏状态，避免 running 状态残留
    await db.execute("UPDATE game_state SET value='' WHERE key IN ('start_time','pause_time','frenzy_hint_given','victory_announced','global_task_complete_at')")
    await db.execute("UPDATE game_state SET value='0' WHERE key='elapsed_seconds'")
    await db.execute("UPDATE game_state SET value='idle' WHERE key='status'")
    await db.execute("UPDATE game_state SET value='0' WHERE key='frenzy_mode'")
    await db.commit()

# ===== 玩家 CRUD（前端管理） =====
async def add_player_web(group_num:int, name:str, note:str="")->dict:
    db=await get_db()
    c=await db.execute(
        "INSERT OR IGNORE INTO players(group_num,name,status,source,note)VALUES(?,?,'存活','web',?)",
        (group_num, name, note)
    )
    await db.commit()
    return {"ok": c.rowcount>0}

async def update_player(id:int, group_num:int, name:str, note:str)->dict:
    db=await get_db()
    c=await db.execute("SELECT id FROM players WHERE group_num=? AND name=? AND id!=?",(group_num,name,id))
    if await c.fetchone():
        return {"ok":False,"msg":"该组号+姓名已存在"}
    await db.execute("UPDATE players SET group_num=?,name=?,note=? WHERE id=?",(group_num,name,note,id))
    await db.commit()
    return {"ok":True}

async def delete_player(id:int)->dict:
    db=await get_db()
    await db.execute("DELETE FROM players WHERE id=?",(id,))
    await db.commit()
    return {"ok":True}

# ===== NPC =====
async def get_all_npcs():
    db=await get_db(); c=await db.execute("SELECT * FROM npcs ORDER BY qq")
    return [dict(r) for r in await c.fetchall()]

async def add_npc(qq:int,name:str="",role:str="hunter"):
    db=await get_db()
    await db.execute("INSERT OR REPLACE INTO npcs(qq,name,role)VALUES(?,?,?)",(qq,name or "",role))
    await db.commit()

async def remove_npc(qq:int):
    db=await get_db(); await db.execute("DELETE FROM npcs WHERE qq=?",(qq,)); await db.commit()

# ===== NPC CRUD（前端管理） =====
async def update_npc(qq:int, name:str, role:str)->dict:
    db=await get_db()
    await db.execute("UPDATE npcs SET name=?,role=? WHERE qq=?",(name or "",role,qq))
    await db.commit()
    return {"ok":True}

async def delete_npc_cascade(qq:int)->dict:
    """删除 NPC 并清理其在任务点中的关联，避免孤儿数据"""
    db=await get_db()
    await db.execute("DELETE FROM npcs WHERE qq=?",(qq,))
    await db.execute("DELETE FROM task_point_npcs WHERE npc_qq=?",(qq,))
    await db.commit()
    return {"ok":True}

async def is_npc(qq:int)->bool:
    db=await get_db(); c=await db.execute("SELECT 1 FROM npcs WHERE qq=?",(qq,))
    return await c.fetchone() is not None

async def get_npc_by_name(name: str) -> dict | None:
    """按姓名精确匹配 NPC，返回完整记录或 None"""
    db = await get_db()
    c = await db.execute("SELECT * FROM npcs WHERE name=? LIMIT 1", (name.strip(),))
    r = await c.fetchone()
    return dict(r) if r else None

async def get_npc(qq:int) -> dict | None:
    db=await get_db()
    c=await db.execute("SELECT * FROM npcs WHERE qq=?",(qq,))
    r=await c.fetchone(); return dict(r) if r else None

async def get_npc_task_point_links(qq:int)->list:
    db=await get_db()
    c=await db.execute("SELECT task_point_id FROM task_point_npcs WHERE npc_qq=?",(qq,))
    return [r["task_point_id"] for r in await c.fetchall()]

# ===== 任务点 =====
async def get_all_task_points():
    db=await get_db()
    c=await db.execute("SELECT * FROM task_points ORDER BY id")
    rows=[dict(r) for r in await c.fetchall()]
    # 注：任务点NPC名单已砍掉（线下口头约定），不再查 task_point_npcs
    c3=await db.execute("SELECT task_point_id, COUNT(*) as c FROM clues GROUP BY task_point_id")
    cc={r["task_point_id"]:r["c"] for r in await c3.fetchall()}
    for tp in rows:
        tp["clue_count"]=cc.get(tp["id"],0)
    c4=await db.execute("SELECT task_point_id, COUNT(*) as c FROM golden_dews WHERE status!='未收集' GROUP BY task_point_id")
    gc={r["task_point_id"]:r["c"] for r in await c4.fetchall()}
    for tp in rows:
        tp["golden_dew_collected"]=gc.get(tp["id"],0)
    return rows

async def replace_task_point_npcs(task_point_id:int, npc_qqs:list):
    """[已废弃] 任务点NPC名单改为线下口头约定，不再系统化管理。
    保留空实现以兼容旧调用方，但不写入任何数据。"""
    return

async def get_task_point_npcs(task_point_id:int)->list:
    """[已废弃] 返回空列表，任务点NPC不再系统化管理"""
    return []

async def add_task_point(id:int,name:str,tp_type:str="solo",card:str="",golden:int=0,
                         static_card_count:int=0,shield_card_count:int=0,status:str="启用"):
    """导入任务点（Excel）。静止卡/护盾卡为初始库存总数，已收集数重置为 0。
    注：任务点NPC名单已砍掉（线下口头约定），不再写 task_point_npcs。"""
    db=await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO task_points"
        "(id,name,tp_type,card_name,golden_dew_count,static_card_count,static_card_collected,"
        "shield_card_count,shield_card_collected,status)"
        "VALUES(?,?,?,?,?,?,0,?,0,?)",
        (id,name,tp_type,card,golden,static_card_count,shield_card_count,status)
    )
    await db.commit()

# ===== 普通露水 =====
async def get_all_dews():
    db=await get_db(); c=await db.execute("SELECT * FROM dews ORDER BY id")
    return [dict(r) for r in await c.fetchall()]

async def add_dew(id:int, hunter_name:str=None):
    """导入普通露水卡 — 已实现"一个露水同时关联任务点和猎人"：
    若 id 已存在（如任务点池的露水），且本次导入指定了猎人，则把猎人归属写入已有记录
    （ON CONFLICT(id) DO UPDATE SET hunter_name=excluded.hunter_name WHERE excluded.hunter_name IS NOT NULL）；
    若 id 不存在则直接插入。每张卡2滴露水值。"""
    db=await get_db()
    await db.execute(
        "INSERT INTO dews(id,status,dew_value,hunter_name)VALUES(?,'未收集',2,?) "
        "ON CONFLICT(id) DO UPDATE SET hunter_name=excluded.hunter_name WHERE excluded.hunter_name IS NOT NULL",
        (id, hunter_name)
    )
    await db.commit()

# ===== 普通露水 CRUD（前端管理） =====
async def add_dew_web(id:int, dew_value:int=2, status:str="未收集", hunter_name:str=None)->dict:
    db=await get_db()
    c=await db.execute(
        "INSERT OR IGNORE INTO dews(id,status,dew_value,hunter_name)VALUES(?,?,?,?)",
        (id, status, dew_value, hunter_name)
    )
    await db.commit()
    return {"ok": c.rowcount>0}

async def update_dew(id:int, dew_value:int=2, status:str="未收集", hunter_name:str=None)->dict:
    db=await get_db()
    await db.execute("UPDATE dews SET dew_value=?,status=?,hunter_name=? WHERE id=?",(dew_value,status,hunter_name,id))
    await db.commit()
    return {"ok":True}

async def delete_dew(id:int)->dict:
    db=await get_db()
    await db.execute("DELETE FROM dews WHERE id=?",(id,))
    await db.commit()
    return {"ok":True}

async def collect_dew(id:int)->bool:
    db=await get_db(); now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c=await db.execute("UPDATE dews SET status='已收集',collected_at=? WHERE id=? AND status='未收集'",(now,id))
    if c.rowcount==0: await db.commit(); return False
    # 联动：对应编号的真线索 → 已收集已发现（无论线索之前是什么状态）
    await db.execute(
        "UPDATE clues SET status='已收集已发现',discovered_at=? WHERE id=? AND clue_type='真'",
        (now, id)
    )
    await db.commit(); return True

async def get_dew_stats():
    """露水统计（按滴数计算）。返回 total_cards/collected_cards/total_value/collected_value/target"""
    db=await get_db()
    c=await db.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(dew_value),0) as val FROM dews")
    r=await c.fetchone(); total=int(r["cnt"]); total_value=int(r["val"])
    c=await db.execute("SELECT COUNT(*) as cnt, COALESCE(SUM(dew_value),0) as val FROM dews WHERE status='已收集'")
    r=await c.fetchone(); collected=int(r["cnt"]); collected_value=int(r["val"])
    target = await get_dew_target()
    return {"total_cards":total,"collected_cards":collected,"total_value":total_value,"collected_value":collected_value,"target":target}

# ===== 金露水 =====
async def get_all_golden_dews():
    db=await get_db(); c=await db.execute("SELECT * FROM golden_dews ORDER BY id")
    return [dict(r) for r in await c.fetchall()]

async def add_golden_dew(id:int,task_point_id:int):
    """导入金露水 — 已存在则跳过，不覆盖收集/使用状态"""
    db=await get_db()
    await db.execute("INSERT OR IGNORE INTO golden_dews(id,task_point_id,status)VALUES(?,?,'未收集')",(id,task_point_id))
    await db.commit()

# ===== 金露水 CRUD（前端管理） =====
async def add_golden_dew_web(id:int, task_point_id:int)->dict:
    db=await get_db()
    c=await db.execute(
        "INSERT OR IGNORE INTO golden_dews(id,task_point_id,status)VALUES(?,?,'未收集')",
        (id, task_point_id)
    )
    await db.commit()
    return {"ok": c.rowcount>0}

async def update_golden_dew(id:int, task_point_id:int)->dict:
    db=await get_db()
    await db.execute("UPDATE golden_dews SET task_point_id=? WHERE id=?",(task_point_id,id))
    await db.commit()
    return {"ok":True}

async def delete_golden_dew(id:int)->dict:
    db=await get_db()
    await db.execute("DELETE FROM golden_dews WHERE id=?",(id,))
    await db.commit()
    return {"ok":True}

async def collect_golden_dew(id:int)->bool:
    """标记金露水为已收集（进入库存，可用于复活）"""
    db=await get_db(); now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c=await db.execute("UPDATE golden_dews SET status='已收集',collected_at=? WHERE id=? AND status='未收集'",(now,id))
    await db.commit(); return c.rowcount>0

async def get_golden_dew_stats()->dict:
    """金露水统计：total=总数, collected=库存(可用), used=已消耗, available=可用库存"""
    db=await get_db()
    c=await db.execute("SELECT COUNT(*) as total FROM golden_dews")
    total=(await c.fetchone())["total"]
    c=await db.execute("SELECT COUNT(*) as cnt FROM golden_dews WHERE status='已收集'")
    collected=(await c.fetchone())["cnt"]
    c=await db.execute("SELECT COUNT(*) as cnt FROM golden_dews WHERE status='已使用'")
    used=(await c.fetchone())["cnt"]
    return {"total":total,"collected":collected,"used":used,"available":collected}

# ===== 线索 =====
async def get_all_clues():
    db=await get_db(); c=await db.execute("SELECT * FROM clues ORDER BY id")
    return [dict(r) for r in await c.fetchall()]

async def add_clue(id:int,clue_type:str="真",task_point_id:int=0,content:str="",hidden_npc_name:str=None,hunter_name:str=None):
    """导入线索 — 已存在则跳过，不覆盖收集状态。藏匿NPC用纯文本名字（线下口头约定）。
    hunter_name 有值时该线索归属猎人；task_point_id=0 且 hunter_name=None 则为无主线索。"""
    db=await get_db()
    await db.execute("INSERT OR IGNORE INTO clues(id,clue_type,task_point_id,content,hidden_npc_name,hunter_name,status)VALUES(?,?,?,?,?,?,'未收集')",(id,clue_type,task_point_id,content,hidden_npc_name,hunter_name))
    await db.commit()

async def collect_clue(id:int)->bool:
    """NPC 收集线索 → 已发现未收集（线索编号已发现，露水尚未收集）"""
    db=await get_db(); now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c=await db.execute("UPDATE clues SET status='已发现未收集',collected_at=? WHERE id=? AND status='未收集'",(now,id))
    await db.commit(); return c.rowcount>0

async def get_clues_by_task(task_point_id:int):
    db=await get_db()
    c=await db.execute("SELECT * FROM clues WHERE task_point_id=? ORDER BY id",(task_point_id,))
    return [dict(r) for r in await c.fetchall()]

async def get_clue(id:int)->dict|None:
    db=await get_db()
    c=await db.execute("SELECT * FROM clues WHERE id=?",(id,))
    r=await c.fetchone(); return dict(r) if r else None

async def update_clue(id:int, clue_type:str, task_point_id:int, content:str, hidden_npc_name:str|None, hunter_name:str|None=None):
    db=await get_db()
    old=await get_clue(id)
    old_tp = old.get("task_point_id") if old else None
    await db.execute(
        "UPDATE clues SET clue_type=?,task_point_id=?,content=?,hidden_npc_name=?,hunter_name=? WHERE id=?",
        (clue_type, task_point_id, content, hidden_npc_name, hunter_name, id)
    )
    await db.commit()
    # 校正 clue_count：旧任务点（归属变更时）与新任务点都要重算，
    # 避免「任务点A→任务点B」或「任务点A→猎人/无主」时旧点计数残留虚高
    if old_tp and old_tp != task_point_id:
        await db.execute(
            "UPDATE task_points SET clue_count=(SELECT COUNT(*) FROM clues WHERE task_point_id=?) WHERE id=?",
            (old_tp, old_tp))
    if task_point_id:
        await db.execute(
            "UPDATE task_points SET clue_count=(SELECT COUNT(*) FROM clues WHERE task_point_id=?) WHERE id=?",
            (task_point_id, task_point_id))
    await db.commit()

async def delete_clue(id:int)->dict:
    db=await get_db()
    old=await get_clue(id)
    if not old: return {"ok":False,"msg":"线索不存在"}
    await db.execute("DELETE FROM task_point_inventory WHERE item_type='线索' AND item_id=?",(id,))
    await db.execute("DELETE FROM clues WHERE id=?",(id,))
    # 校正所属任务点 clue_count（仅当原归属任务点时）
    if old.get("task_point_id"):
        await db.execute(
            "UPDATE task_points SET clue_count=(SELECT COUNT(*) FROM clues WHERE task_point_id=?) WHERE id=?",
            (old["task_point_id"], old["task_point_id"])
        )
        await db.commit()
    return {"ok":True}

async def collect_clue_manual(id:int)->bool:
    """管理员手动标记线索为已收集已发现（Web 端确认线索信息已被挖掘）"""
    db=await get_db(); now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c=await db.execute(
        "UPDATE clues SET status='已收集已发现',collected_at=?,discovered_at=? WHERE id=?",
        (now, now, id)
    )
    await db.commit(); return c.rowcount>0

async def reset_clue_status(id:int):
    """重置线索为未收集"""
    db=await get_db()
    await db.execute(
        "UPDATE clues SET status='未收集',collected_at=NULL,discovered_at=NULL WHERE id=?",
        (id,)
    )
    await db.commit()


# ===== 猎人持有物（线索/露水，靠名字字符串标识，不引入QQ名单）=====
async def get_hunter_items(hunter_name:str)->dict:
    """返回某猎人持有的线索 + 露水。露水直接按 dews.hunter_name 归属，与线索解耦（C 新建式独立记录）。"""
    db=await get_db()
    c=await db.execute("SELECT * FROM clues WHERE hunter_name=? ORDER BY id",(hunter_name,))
    clues=[dict(r) for r in await c.fetchall()]
    c2=await db.execute("SELECT * FROM dews WHERE hunter_name=? ORDER BY id",(hunter_name,))
    dews=[dict(r) for r in await c2.fetchall()]
    return {"hunter_name":hunter_name,"clues":clues,"dews":dews}

async def get_orphan_clues()->list:
    """无主线索（task_point_id=0 且 hunter_name IS NULL）+ 对应露水"""
    db=await get_db()
    c=await db.execute(
        "SELECT * FROM clues WHERE (task_point_id=0 OR task_point_id IS NULL) AND hunter_name IS NULL ORDER BY id")
    return [dict(r) for r in await c.fetchall()]

async def get_hunters_with_items()->list:
    """返回所有持有线索或露水的猎人名字（去重）"""
    db=await get_db()
    c=await db.execute(
        "SELECT DISTINCT hunter_name FROM ("
        "SELECT hunter_name FROM clues WHERE hunter_name IS NOT NULL "
        "UNION SELECT hunter_name FROM dews WHERE hunter_name IS NOT NULL) "
        "ORDER BY hunter_name")
    return [r["hunter_name"] for r in await c.fetchall()]

async def assign_clue_to_hunter(clue_id:int, hunter_name:str)->dict:
    """将线索分配给猎人（同时解除原任务点归属，clue_count 同步校正）"""
    db=await get_db()
    old=await get_clue(clue_id)
    if not old: return {"ok":False,"msg":"线索不存在"}
    old_tp=old.get("task_point_id")
    await db.execute(
        "UPDATE clues SET hunter_name=?, task_point_id=0 WHERE id=?",(hunter_name, clue_id))
    if old_tp:
        await db.execute(
            "UPDATE task_points SET clue_count=(SELECT COUNT(*) FROM clues WHERE task_point_id=?) WHERE id=?",
            (old_tp, old_tp))
    await db.commit()
    return {"ok":True}

async def unassign_clue(clue_id:int)->dict:
    """解除线索归属（变无主：task_point_id=0, hunter_name=NULL）"""
    db=await get_db()
    old=await get_clue(clue_id)
    if not old: return {"ok":False,"msg":"线索不存在"}
    old_tp=old.get("task_point_id")
    await db.execute(
        "UPDATE clues SET hunter_name=NULL, task_point_id=0 WHERE id=?",(clue_id,))
    if old_tp:
        await db.execute(
            "UPDATE task_points SET clue_count=(SELECT COUNT(*) FROM clues WHERE task_point_id=?) WHERE id=?",
            (old_tp, old_tp))
    await db.commit()
    return {"ok":True}

async def hunter_give_clue(hunter_name:str, clue_id:int)->dict:
    """猎人用静止卡把线索送出给玩家：校验该线索归此猎人持有，送出后置'已发现未收集'并解除猎人归属(变无主)"""
    db=await get_db()
    c=await db.execute("SELECT id,hunter_name,status FROM clues WHERE id=?",(clue_id,))
    row=await c.fetchone()
    if not row: return {"ok":False,"msg":"线索不存在"}
    if row["hunter_name"]!=hunter_name: return {"ok":False,"msg":"该线索不归此猎人持有"}
    # 揭示(已发现未收集)并解除猎人归属（线索离开猎人，变为玩家可收集的无主线索）
    await db.execute("UPDATE clues SET status='已发现未收集', hunter_name=NULL WHERE id=?",(clue_id,))
    await db.commit()
    return {"ok":True}

# ===== 游戏状态 =====
async def get_game_state(key:str)->str:
    db=await get_db(); c=await db.execute("SELECT value FROM game_state WHERE key=?",(key,))
    r=await c.fetchone(); return r["value"] if r else ""

async def set_game_state(key:str,value:str):
    db=await get_db()
    await db.execute("INSERT OR REPLACE INTO game_state(key,value)VALUES(?,?)",(key,str(value)))
    await db.commit()

async def get_frenzy_mode()->bool:
    """狂欢模式（上帝时刻）是否激活"""
    return await get_game_state("frenzy_mode") == "1"

async def set_frenzy_mode(active:bool):
    """设置狂欢模式状态"""
    await set_game_state("frenzy_mode", "1" if active else "0")

async def set_global_task_immune():
    """记录全局任务免疫时间戳（任务点完成时调用，全体玩家15s免疫）"""
    await set_game_state("global_task_complete_at", datetime.now().isoformat())

async def is_global_task_immune()->tuple[bool,int]:
    """检查是否在全局15s任务免疫期内。返回 (immune, remaining_seconds)"""
    ts = await get_game_state("global_task_complete_at")
    if not ts: return False, 0
    try:
        t = datetime.fromisoformat(ts)
        elapsed = (datetime.now() - t).total_seconds()
        if elapsed < 15: return True, int(15 - elapsed)
        return False, 0
    except: return False, 0

# ===== 系统配置 =====
async def get_config(key:str)->str:
    db=await get_db(); c=await db.execute("SELECT value FROM system_config WHERE key=?",(key,))
    r=await c.fetchone(); return r["value"] if r else ""

async def set_config(key:str,value:str):
    db=await get_db()
    await db.execute("INSERT OR REPLACE INTO system_config(key,value)VALUES(?,?)",(key,str(value)))
    await db.commit()

async def get_all_config()->dict:
    db=await get_db(); c=await db.execute("SELECT key,value FROM system_config")
    return {r["key"]:r["value"] for r in await c.fetchall()}

# ===== 任务点物资 =====
async def add_task_point_inventory(task_point_id:int, source:str, item_type:str, item_id:int=0):
    """记录任务点物资/完成事件
    source: 'complete'（任务完成获得） / 'receive'（接收物资）
    item_type: 线索 / 功能卡 / 露水 / 金露水
    """
    db=await get_db()
    await db.execute(
        "INSERT INTO task_point_inventory(task_point_id,source,item_type,item_id)VALUES(?,?,?,?)",
        (task_point_id, source, item_type, item_id)
    )
    await db.commit()

async def incr_task_point_card_collected(task_point_id:int, card_type:str)->bool:
    """任务点完成/接收获得静止卡/护盾卡时，联动 task_points 表的 collected 计数 +1
    card_type: 'static_card' 或 'shield_card'（对应 static_card_collected / shield_card_collected）
    """
    field = "static_card_collected" if card_type=="static_card" else "shield_card_collected"
    db=await get_db()
    c=await db.execute(f"UPDATE task_points SET {field}={field}+1 WHERE id=?",(task_point_id,))
    await db.commit(); return c.rowcount>0


# ===== 任务点指令录入（新格式：完整列出所有道具） =====

async def reveal_clue(clue_id: int) -> bool:
    """任务点送出线索 → 线索和对应露水状态变为"已发现未收集"
    - 线索：未收集 → 已发现未收集
    - 露水（同编号真线索对应的）：未收集 → 已发现未收集
    """
    db = await get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    # 线索状态变更
    c = await db.execute(
        "UPDATE clues SET status='已发现未收集', collected_at=? WHERE id=? AND status='未收集'",
        (now, clue_id)
    )
    if c.rowcount == 0:
        await db.commit()
        return False
    # 同编号真线索对应的露水也变为"已发现未收集"
    await db.execute(
        "UPDATE dews SET status='已发现未收集' WHERE id=? AND status='未收集'",
        (clue_id,)
    )
    await db.commit()
    return True


async def collect_dew_from_web(dew_id: int) -> bool:
    """前端收集露水 → 露水和对应真线索状态变为"已收集已发现"
    - 露水：已发现未收集 → 已收集已发现
    - 真线索（同编号）：已发现未收集 → 已收集已发现
    """
    db = await get_db()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c = await db.execute(
        "UPDATE dews SET status='已收集', collected_at=? WHERE id=? AND status='已发现未收集'",
        (now, dew_id)
    )
    if c.rowcount == 0:
        await db.commit()
        return False
    # 同编号真线索变为"已收集已发现"
    await db.execute(
        "UPDATE clues SET status='已收集已发现', collected_at=?, discovered_at=? WHERE id=? AND clue_type='真' AND status='已发现未收集'",
        (now, now, dew_id)
    )
    await db.commit()
    return True


async def check_task_point_stock(tp_id: int, golden_dew_count: int, shield_card_count: int, static_card_count: int) -> dict:
    """检测任务点库存是否足够送出指定数量的道具
    返回 {"ok": bool, "msg": str}
    """
    db = await get_db()
    tp = await get_task_point(tp_id)
    if not tp:
        return {"ok": False, "msg": f"任务点{tp_id} 不存在"}

    # 护盾卡库存
    if shield_card_count > 0:
        available = tp["shield_card_count"] - tp["shield_card_collected"]
        if shield_card_count > available:
            return {"ok": False, "msg": f"任务点{tp_id} 护盾卡库存不足（剩余{available}，需{shield_card_count}）"}

    # 静止卡库存
    if static_card_count > 0:
        available = tp["static_card_count"] - tp["static_card_collected"]
        if static_card_count > available:
            return {"ok": False, "msg": f"任务点{tp_id} 静止卡库存不足（剩余{available}，需{static_card_count}）"}

    # 金露水库存（未收集的金露水数量）
    if golden_dew_count > 0:
        c = await db.execute(
            "SELECT COUNT(*) as cnt FROM golden_dews WHERE task_point_id=? AND status='未收集'",
            (tp_id,)
        )
        available = (await c.fetchone())["cnt"]
        if golden_dew_count > available:
            return {"ok": False, "msg": f"任务点{tp_id} 金露水库存不足（剩余{available}，需{golden_dew_count}）"}

    return {"ok": True, "msg": ""}


async def process_task_point_complete(tp_id: int, clue_id: int | None, dew_id: int, golden_dew_count: int, shield_card_count: int, static_card_count: int) -> dict:
    """处理任务点完成指令：送出道具给玩家
    返回 {"ok": bool, "msg": str, "details": str}
    """
    if clue_id is None and dew_id == 0 and golden_dew_count == 0 and shield_card_count == 0 and static_card_count == 0:
        return {"ok": False, "msg": "未指定任何道具", "details": ""}
    db = await get_db()

    # 库存检测
    stock = await check_task_point_stock(tp_id, golden_dew_count, shield_card_count, static_card_count)
    if not stock["ok"]:
        return {"ok": False, "msg": stock["msg"], "details": ""}

    details = []

    # 线索处理
    if clue_id is not None:
        clue = await get_clue(clue_id)
        if not clue:
            return {"ok": False, "msg": f"线索{clue_id} 不存在", "details": ""}
        ok = await reveal_clue(clue_id)
        if not ok:
            return {"ok": False, "msg": f"线索{clue_id} 状态异常（可能已被送出）", "details": ""}
        details.append(f"线索{clue_id} → 已发现未收集")
        await add_task_point_inventory(tp_id, "complete", "线索", clue_id)

    # 露水处理段已砍掉：任务点完成不再送出露水（指令格式保留，dew_id 参数被忽略）。
    # 露水仅可由任务点/猎人"接收/存入"（process_task_point_receive）并经网页端编辑。

    # 金露水处理（按数量从该任务点的未收集中分配）
    if golden_dew_count > 0:
        c = await db.execute(
            "SELECT id FROM golden_dews WHERE task_point_id=? AND status='未收集' ORDER BY id ASC LIMIT ?",
            (tp_id, golden_dew_count)
        )
        gids = [r["id"] for r in await c.fetchall()]
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for gid in gids:
            await db.execute("UPDATE golden_dews SET status='已收集', collected_at=? WHERE id=?", (now, gid))
            await add_task_point_inventory(tp_id, "complete", "金露水", gid)
        details.append(f"金露水{golden_dew_count}个 → 已收集")

    # 护盾卡处理
    if shield_card_count > 0:
        await db.execute(
            "UPDATE task_points SET shield_card_collected=shield_card_collected+? WHERE id=?",
            (shield_card_count, tp_id)
        )
        for _ in range(shield_card_count):
            await add_task_point_inventory(tp_id, "complete", "护盾卡", 0)
        details.append(f"护盾卡{shield_card_count}张")

    # 静止卡处理
    if static_card_count > 0:
        await db.execute(
            "UPDATE task_points SET static_card_collected=static_card_collected+? WHERE id=?",
            (static_card_count, tp_id)
        )
        for _ in range(static_card_count):
            await add_task_point_inventory(tp_id, "complete", "静止卡", 0)
        details.append(f"静止卡{static_card_count}张")

    await db.commit()
    return {"ok": True, "msg": f"任务点{tp_id} 成功送出道具", "details": " | ".join(details) if details else "无道具"}


async def process_task_point_receive(tp_id: int, clue_id: int | None, dew_id: int, golden_dew_count: int, shield_card_count: int, static_card_count: int) -> dict:
    """处理任务点接收指令：从外部入库道具
    返回 {"ok": bool, "msg": str, "details": str}
    """
    if clue_id is None and dew_id == 0 and golden_dew_count == 0 and shield_card_count == 0 and static_card_count == 0:
        return {"ok": False, "msg": "未指定任何道具", "details": ""}
    db = await get_db()
    tp = await get_task_point(tp_id)
    if not tp:
        return {"ok": False, "msg": f"任务点{tp_id} 不存在", "details": ""}

    details = []

    # 线索处理（接收线索 → 已发现未收集）
    if clue_id is not None:
        clue = await get_clue(clue_id)
        if not clue:
            return {"ok": False, "msg": f"线索{clue_id} 不存在", "details": ""}
        ok = await reveal_clue(clue_id)
        if not ok:
            return {"ok": False, "msg": f"线索{clue_id} 状态异常", "details": ""}
        details.append(f"线索{clue_id} → 已发现未收集")
        await add_task_point_inventory(tp_id, "receive", "线索", clue_id)

    # 露水处理（按编号精确入库：把指定编号的散落露水收回到任务点池，状态重置为"未收集"）
    if dew_id > 0:
        c = await db.execute("SELECT d.id, d.status FROM dews WHERE id=?", (dew_id,))
        row = await c.fetchone()
        if not row:
            return {"ok": False, "msg": f"露水{dew_id} 不存在", "details": ""}
        old_status = row["status"]
        await db.execute("UPDATE dews SET status='未收集', hunter_name=NULL WHERE id=?", (dew_id,))
        await add_task_point_inventory(tp_id, "receive", "露水", dew_id)
        details.append(f"露水{dew_id} → 已入库（原状态：{old_status}）")

    # 金露水处理（增加任务点金露水总量，用自增避免ID冲突）
    if golden_dew_count > 0:
        for _ in range(golden_dew_count):
            await db.execute(
                "INSERT INTO golden_dews(task_point_id,status)VALUES(?,'已收集')",
                (tp_id,)
            )
            # 取刚插入的自增 id 写入 inventory
            c = await db.execute("SELECT last_insert_rowid()")
            gid = (await c.fetchone())[0]
            await add_task_point_inventory(tp_id, "receive", "金露水", gid)
        details.append(f"金露水{golden_dew_count}个 → 入库")

    # 护盾卡处理（增加库存总量）
    if shield_card_count > 0:
        await db.execute(
            "UPDATE task_points SET shield_card_count=shield_card_count+? WHERE id=?",
            (shield_card_count, tp_id)
        )
        for _ in range(shield_card_count):
            await add_task_point_inventory(tp_id, "receive", "护盾卡", 0)
        details.append(f"护盾卡{shield_card_count}张 → 入库")

    # 静止卡处理
    if static_card_count > 0:
        await db.execute(
            "UPDATE task_points SET static_card_count=static_card_count+? WHERE id=?",
            (static_card_count, tp_id)
        )
        for _ in range(static_card_count):
            await add_task_point_inventory(tp_id, "receive", "静止卡", 0)
        details.append(f"静止卡{static_card_count}张 → 入库")

    await db.commit()
    return {"ok": True, "msg": f"任务点{tp_id} 成功接收道具", "details": " | ".join(details) if details else "无道具"}


async def get_task_point_inventory(task_point_id:int)->list[dict]:
    """查询某个任务点的所有物资/完成记录"""
    db=await get_db()
    c=await db.execute(
        "SELECT * FROM task_point_inventory WHERE task_point_id=? ORDER BY created_at DESC",
        (task_point_id,)
    )
    return [dict(r) for r in await c.fetchall()]

async def get_all_task_point_inventory()->list[dict]:
    """查询所有任务点物资"""
    db=await get_db()
    c=await db.execute("SELECT * FROM task_point_inventory ORDER BY task_point_id, created_at DESC")
    return [dict(r) for r in await c.fetchall()]

# ===== 露水目标量 =====
async def get_dew_target()->int:
    """获取目标露水量（0表示默认80滴）"""
    v=await get_game_state("dew_target")
    t=int(v) if v else 0
    return t if t>0 else 80

async def set_dew_target(n:int):
    await set_game_state("dew_target",str(n))

# ===== 操作日志（用于撤销）=====
async def add_operation_log(op_type:str, target_desc:str, undo_data:str, operator_qq:int=0):
    db=await get_db()
    await db.execute(
        "INSERT INTO operation_log(op_type,target_desc,undo_data,operator_qq)VALUES(?,?,?,?)",
        (op_type,target_desc,undo_data,operator_qq)
    )
    await db.commit()

async def get_recent_operations(limit:int=5)->list[dict]:
    db=await get_db()
    c=await db.execute("SELECT * FROM operation_log ORDER BY id DESC LIMIT ?",(limit,))
    return [dict(r) for r in await c.fetchall()]

async def delete_operation_log(log_id:int):
    db=await get_db()
    await db.execute("DELETE FROM operation_log WHERE id=?",(log_id,))
    await db.commit()

async def undo_operation(op:dict, data:dict) -> str | None:
    """撤销单条操作。成功返回描述字符串，失败返回 None。由 backend.py 和 api.py 共用。"""
    import json as _json
    op_type = op["op_type"]
    desc = op["target_desc"]
    db = await get_db()
    undone = False

    if op_type == "eliminate":
        group_num = data.get("group_num")
        name = data.get("name")
        if not group_num or not name:
            return None  # undo_data 缺失，无法撤销
        # 恢复玩家状态
        c = await db.execute(
            "UPDATE players SET status='存活', source=NULL, eliminated_at=NULL WHERE group_num=? AND name=?",
            (group_num, name)
        )
        if c.rowcount == 0:
            return None  # 玩家状态可能已被其他操作改变
        # 清理对应猎人的抓捕冷却（如果有）
        hunter_qq = data.get("hunter_qq")
        if hunter_qq:
            await db.execute(
                "DELETE FROM cooldowns WHERE cooldown_type='capture' AND hunter_key=?",
                (str(hunter_qq),)
            )
        await db.commit()
        undone = True
    elif op_type == "revive":
        group_num = data.get("group_num")
        name = data.get("name")
        if not group_num or not name:
            return None
        await db.execute(
            "UPDATE players SET status='淘汰' WHERE group_num=? AND name=?",
            (group_num, name)
        )
        if data.get("golden_dew_id") is not None:
            await db.execute("UPDATE golden_dews SET status='已收集' WHERE id=?", (data["golden_dew_id"],))
        await db.commit()
        undone = True
    elif op_type == "collect_clue":
        clue_id = data.get("clue_id")
        if not clue_id:
            return None
        await db.execute("UPDATE clues SET status='未收集' WHERE id=?", (clue_id,))
        await db.commit()
        undone = True
    elif op_type == "collect_dew":
        dew_id = data.get("dew_id")
        if not dew_id:
            return None
        await db.execute("UPDATE dews SET status='未收集', collected_at=NULL WHERE id=?", (dew_id,))
        await db.commit()
        undone = True
    elif op_type == "collect_golden_dew":
        dew_id = data.get("dew_id")
        if not dew_id:
            return None
        await db.execute("UPDATE golden_dews SET status='未收集', collected_at=NULL WHERE id=?", (dew_id,))
        await db.commit()
        undone = True
    elif op_type == "tp_inventory":
        await db.execute(
            "DELETE FROM task_point_inventory WHERE id=("
            "SELECT id FROM task_point_inventory "
            "WHERE task_point_id=? AND source=? AND item_type=? AND item_id=? "
            "ORDER BY id DESC LIMIT 1)",
            (data.get("tp_id"), data.get("source"), data.get("item_type"), data.get("item_id"))
        )
        await db.commit()
        undone = True
    elif op_type == "tp_complete":
        # 撤销任务点完成：回滚库存 + 线索状态
        tp_id = data.get("tp_id")
        clue_id = data.get("clue_id")
        gd_count = data.get("golden_dew", 0) or 0
        sh_count = data.get("shield_card", 0) or 0
        st_count = data.get("static_card", 0) or 0
        if tp_id:
            # 回滚线索状态
            if clue_id is not None:
                await db.execute("UPDATE clues SET status='未收集', collected_at=NULL WHERE id=?", (clue_id,))
                await db.execute("UPDATE dews SET status='已发现未收集' WHERE id=?", (clue_id,))
                await db.execute("DELETE FROM task_point_inventory WHERE task_point_id=? AND source='complete' AND item_type='线索' AND item_id=? AND id=(SELECT id FROM task_point_inventory WHERE task_point_id=? AND source='complete' AND item_type='线索' AND item_id=? ORDER BY id DESC LIMIT 1)", (tp_id, clue_id, tp_id, clue_id))
            # 露水送出已在任务点完成中砍掉，此处不再回滚露水（接收/存入的露水由 tp_receive 撤销处理）
            # 回滚金露水
            if gd_count > 0:
                await db.execute(
                    "UPDATE golden_dews SET status='未收集', collected_at=NULL WHERE task_point_id=? AND status='已收集' ORDER BY id DESC LIMIT ?",
                    (tp_id, gd_count)
                )
                await db.execute("DELETE FROM task_point_inventory WHERE id IN (SELECT id FROM task_point_inventory WHERE task_point_id=? AND source='complete' AND item_type='金露水' ORDER BY id DESC LIMIT ?)", (tp_id, gd_count))
            # 回滚护盾卡
            if sh_count > 0:
                await db.execute("UPDATE task_points SET shield_card_collected=MAX(0,shield_card_collected-?) WHERE id=?", (sh_count, tp_id))
                await db.execute("DELETE FROM task_point_inventory WHERE id IN (SELECT id FROM task_point_inventory WHERE task_point_id=? AND source='complete' AND item_type='护盾卡' ORDER BY id DESC LIMIT ?)", (tp_id, sh_count))
            # 回滚静止卡
            if st_count > 0:
                await db.execute("UPDATE task_points SET static_card_collected=MAX(0,static_card_collected-?) WHERE id=?", (st_count, tp_id))
                await db.execute("DELETE FROM task_point_inventory WHERE id IN (SELECT id FROM task_point_inventory WHERE task_point_id=? AND source='complete' AND item_type='静止卡' ORDER BY id DESC LIMIT ?)", (tp_id, st_count))
            await db.commit()
            undone = True
    elif op_type == "tp_receive":
        # 撤销任务点接收：回滚入库
        tp_id = data.get("tp_id")
        clue_id = data.get("clue_id")
        dew_id = data.get("dew_id")
        gd_count = data.get("golden_dew", 0) or 0
        sh_count = data.get("shield_card", 0) or 0
        st_count = data.get("static_card", 0) or 0
        if tp_id:
            if clue_id is not None:
                await db.execute("UPDATE clues SET status='未收集', collected_at=NULL WHERE id=?", (clue_id,))
                await db.execute("UPDATE dews SET status='已发现未收集' WHERE id=?", (clue_id,))
                await db.execute("DELETE FROM task_point_inventory WHERE id IN (SELECT id FROM task_point_inventory WHERE task_point_id=? AND source='receive' AND item_type='线索' AND item_id=? ORDER BY id DESC LIMIT 1)", (tp_id, clue_id))
            if dew_id:
                await db.execute("UPDATE dews SET status='已发现未收集' WHERE id=?", (dew_id,))
                await db.execute("DELETE FROM task_point_inventory WHERE id IN (SELECT id FROM task_point_inventory WHERE task_point_id=? AND source='receive' AND item_type='露水' AND item_id=? ORDER BY id DESC LIMIT 1)", (tp_id, dew_id))
            if gd_count > 0:
                await db.execute("DELETE FROM golden_dews WHERE task_point_id=? AND status='已收集' ORDER BY id DESC LIMIT ?", (tp_id, gd_count))
                await db.execute("DELETE FROM task_point_inventory WHERE id IN (SELECT id FROM task_point_inventory WHERE task_point_id=? AND source='receive' AND item_type='金露水' ORDER BY id DESC LIMIT ?)", (tp_id, gd_count))
            if sh_count > 0:
                await db.execute("UPDATE task_points SET shield_card_count=MAX(0,shield_card_count-?) WHERE id=?", (sh_count, tp_id))
                await db.execute("DELETE FROM task_point_inventory WHERE id IN (SELECT id FROM task_point_inventory WHERE task_point_id=? AND source='receive' AND item_type='护盾卡' ORDER BY id DESC LIMIT ?)", (tp_id, sh_count))
            if st_count > 0:
                await db.execute("UPDATE task_points SET static_card_count=MAX(0,static_card_count-?) WHERE id=?", (st_count, tp_id))
                await db.execute("DELETE FROM task_point_inventory WHERE id IN (SELECT id FROM task_point_inventory WHERE task_point_id=? AND source='receive' AND item_type='静止卡' ORDER BY id DESC LIMIT ?)", (tp_id, st_count))
            await db.commit()
            undone = True
    elif op_type == "frenzy_reveal":
        # 撤销狂欢线索公示：恢复线索原状态
        clue_list = data.get("clues", [])
        await undo_reveal_clues(clue_list)
        undone = True

    elif op_type in ("delete_dew", "add_dew"):
        if op_type == "delete_dew":
            d = data.get("row", {})
            if not d.get("id"):
                return None
            await db.execute(
                "INSERT OR IGNORE INTO dews(id,status,collected_at,dew_value)VALUES(?,?,?,?)",
                (d["id"], d.get("status","未收集"), d.get("collected_at"), d.get("dew_value",2))
            )
        else:
            did = data.get("id")
            if not did:
                return None
            await db.execute("DELETE FROM dews WHERE id=?", (did,))
        await db.commit(); undone = True
    elif op_type in ("delete_golden_dew", "add_golden_dew"):
        if op_type == "delete_golden_dew":
            d = data.get("row", {})
            if not d.get("id"):
                return None
            await db.execute(
                "INSERT OR IGNORE INTO golden_dews(id,task_point_id,status,collected_at)VALUES(?,?,?,?)",
                (d["id"], d.get("task_point_id"), d.get("status","未收集"), d.get("collected_at"))
            )
        else:
            gid = data.get("id")
            if not gid:
                return None
            await db.execute("DELETE FROM golden_dews WHERE id=?", (gid,))
        await db.commit(); undone = True
    elif op_type in ("delete_player", "add_player", "update_player"):
        if op_type == "delete_player":
            d = data.get("row", {})
            if not d.get("id"):
                return None
            await db.execute(
                "INSERT OR IGNORE INTO players(id,group_num,name,status,source,eliminated_at,revived_at,note,created_at)"
                "VALUES(?,?,?,?,?,?,?,?,?)",
                (d.get("id"), d.get("group_num"), d.get("name"), d.get("status","存活"),
                 d.get("source"), d.get("eliminated_at"), d.get("revived_at"),
                 d.get("note"), d.get("created_at"))
            )
        elif op_type == "add_player":
            pid = data.get("id")
            if not pid:
                return None
            await db.execute("DELETE FROM players WHERE id=?", (pid,))
        else:
            old = data.get("old")
            pid = data.get("id")
            if not pid or not old:
                return None
            await db.execute(
                "UPDATE players SET group_num=?,name=?,note=? WHERE id=?",
                (old.get("group_num"), old.get("name"), old.get("note"), pid)
            )
        await db.commit(); undone = True
    elif op_type in ("delete_npc", "add_npc", "update_npc"):
        if op_type == "delete_npc":
            d = data.get("row", {})
            links = data.get("links", [])
            if not d.get("qq"):
                return None
            await db.execute(
                "INSERT OR IGNORE INTO npcs(qq,name,role,created_at)VALUES(?,?,?,?)",
                (d.get("qq"), d.get("name"), d.get("role","hunter"), d.get("created_at"))
            )
            for lk in links:
                await db.execute("INSERT OR IGNORE INTO task_point_npcs(task_point_id,npc_qq)VALUES(?,?)",(lk, d.get("qq")))
        elif op_type == "add_npc":
            qq = data.get("qq")
            if not qq:
                return None
            await db.execute("DELETE FROM task_point_npcs WHERE npc_qq=?",(qq,))
            await db.execute("DELETE FROM npcs WHERE qq=?", (qq,))
        else:
            old = data.get("old")
            qq = data.get("qq")
            if not qq or not old:
                return None
            await db.execute("UPDATE npcs SET name=?,role=? WHERE qq=?",(old.get("name"), old.get("role"), qq))
        await db.commit(); undone = True

    if undone:
        await delete_operation_log(op["id"])
        return f"已撤销：{desc}"
    return None

# ===== 露水/线索重置 =====
async def reset_dew(dew_id:int):
    """重置露水为未收集，同时重置对应真线索"""
    db=await get_db()
    await db.execute("UPDATE dews SET status='未收集',collected_at=NULL WHERE id=?",(dew_id,))
    # 对应真线索也重置为未收集
    await db.execute(
        "UPDATE clues SET status='未收集',collected_at=NULL,discovered_at=NULL WHERE id=? AND clue_type='真'",
        (dew_id,)
    )
    await db.commit()

async def reset_golden_dew(dew_id:int):
    """重置金露水为未收集"""
    db=await get_db()
    await db.execute("UPDATE golden_dews SET status='未收集',collected_at=NULL WHERE id=?",(dew_id,))
    await db.commit()

async def update_clue_status(clue_id:int, status:str):
    """修改线索状态"""
    db=await get_db()
    await db.execute("UPDATE clues SET status=? WHERE id=?",(status,clue_id))
    await db.commit()

async def reveal_all_clues()->list[dict]:
    """狂欢模式：把所有非"已收集已发现"的线索改为"已收集已发现"。
    返回被修改的线索列表 [{"id":id,"old_status":原状态}, ...] 供撤销使用。"""
    db=await get_db(); now=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    c=await db.execute("SELECT id,status FROM clues WHERE status!='已收集已发现'")
    changed=[{"id":r["id"],"old_status":r["status"]} for r in await c.fetchall()]
    if changed:
        await db.execute(
            "UPDATE clues SET status='已收集已发现',collected_at=COALESCE(collected_at,?),discovered_at=COALESCE(discovered_at,?) WHERE status!='已收集已发现'",
            (now,now)
        )
        await db.commit()
    return changed

async def undo_reveal_clues(clue_list:list[dict]):
    """撤销狂欢线索公示：恢复线索原状态"""
    db=await get_db()
    for item in clue_list:
        await db.execute("UPDATE clues SET status=? WHERE id=?",(item["old_status"],item["id"]))
    await db.commit()

# ===== 冷却持久化 =====
import time as _time
async def add_cooldown(cooldown_type:str, hunter_key:str, hunter_name:str, seconds:int):
    """新增冷却记录：expire_at 使用截断到秒的 isoformat，保证字符串比较语义正确"""
    from datetime import datetime, timedelta
    db=await get_db()
    expire=datetime.now()+timedelta(seconds=seconds)
    await db.execute(
        "INSERT INTO cooldowns(cooldown_type,hunter_key,hunter_name,expire_at)VALUES(?,?,?,?)",
        (cooldown_type, str(hunter_key), hunter_name, expire.strftime("%Y-%m-%dT%H:%M:%S"))
    )
    await db.commit()

async def check_cooldown(cooldown_type:str, hunter_key:str)->tuple[bool,int]:
    """检查冷却状态 (can_act, remaining_seconds)，使用秒级 isoformat 比较"""
    db=await get_db()
    from datetime import datetime
    now_str = datetime.now().strftime("%Y-%m-%dT%H:%M:%S")
    c=await db.execute(
        "SELECT expire_at FROM cooldowns WHERE cooldown_type=? AND hunter_key=? AND expire_at>? ORDER BY expire_at DESC LIMIT 1",
        (cooldown_type, str(hunter_key), now_str)
    )
    r=await c.fetchone()
    if not r: return True, 0
    t=datetime.fromisoformat(r["expire_at"])
    remaining=int((t-datetime.now()).total_seconds())
    return False, max(0,remaining)

async def get_expired_cooldowns()->list[dict]:
    """获取已过期、需要播报的冷却"""
    db=await get_db()
    from datetime import datetime
    c=await db.execute(
        "SELECT * FROM cooldowns WHERE expire_at<=? AND broadcast=1",
        (datetime.now().strftime("%Y-%m-%dT%H:%M:%S"),)
    )
    return [dict(r) for r in await c.fetchall()]

async def remove_cooldown(id:int):
    db=await get_db()
    await db.execute("DELETE FROM cooldowns WHERE id=?",(id,))
    await db.commit()

async def get_all_cooldowns()->list[dict]:
    db=await get_db()
    c=await db.execute("SELECT * FROM cooldowns ORDER BY expire_at DESC")
    return [dict(r) for r in await c.fetchall()]

# ===== 任务点CRUD =====
async def get_task_point(id:int)->dict|None:
    db=await get_db()
    c=await db.execute("SELECT * FROM task_points WHERE id=?",(id,))
    r=await c.fetchone()
    return dict(r) if r else None

async def add_task_point_full(id:int, name:str, tp_type:str, card_name:str, golden_dew_count:int, status:str="启用",
        static_card_count:int=0, static_card_collected:int=0, shield_card_count:int=0, shield_card_collected:int=0, clue_count:int=0):
    """新增完整任务点（任务点NPC名单已砍掉，不再写 task_point_npcs）"""
    db=await get_db()
    await db.execute(
        "INSERT OR REPLACE INTO task_points(id,name,tp_type,card_name,golden_dew_count,status,static_card_count,static_card_collected,shield_card_count,shield_card_collected,clue_count)VALUES(?,?,?,?,?,?,?,?,?,?,?)",
        (id,name,tp_type,card_name,golden_dew_count,status,static_card_count,static_card_collected,shield_card_count,shield_card_collected,clue_count)
    )
    # 金露水：按配置数自动生成，使用高位 ID（9000+tp_id*100）避免与 Excel 导入的 ID 冲突
    for i in range(golden_dew_count):
        gid = 9000 + id * 100 + i
        await db.execute("INSERT OR IGNORE INTO golden_dews(id,task_point_id,status)VALUES(?,?,'未收集')",(gid, id))
    await db.commit()

async def update_task_point(id:int, name:str, tp_type:str, card_name:str, golden_dew_count:int, status:str="启用",
        static_card_count:int=0, static_card_collected:int=0, shield_card_count:int=0, shield_card_collected:int=0, clue_count:int=0)->dict:
    """修改任务点（含联动更新）。任务点NPC名单已砍掉，不再写 task_point_npcs。"""
    db=await get_db()
    # 查询旧数据
    old=await get_task_point(id)
    if not old: return {"ok":False,"msg":"任务点不存在"}
    # 更新任务点
    await db.execute(
        "UPDATE task_points SET name=?,tp_type=?,card_name=?,golden_dew_count=?,status=?,static_card_count=?,static_card_collected=?,shield_card_count=?,shield_card_collected=?,clue_count=? WHERE id=?",
        (name,tp_type,card_name,golden_dew_count,status,static_card_count,static_card_collected,shield_card_count,shield_card_collected,clue_count,id)
    )
    # 任务点NPC名单已砍掉（线下口头约定），不再写 task_point_npcs
    # 金露水联动：增则补、减则删多余未收集（已收集/已使用保留，避免丢数据）
    cur=await db.execute("SELECT COUNT(*) as cnt FROM golden_dews WHERE task_point_id=?",(id,))
    cur_cnt=(await cur.fetchone())["cnt"]
    if golden_dew_count > cur_cnt:
        for i in range(cur_cnt, golden_dew_count):
            gid = 9000 + id * 100 + i
            await db.execute("INSERT OR IGNORE INTO golden_dews(id,task_point_id,status)VALUES(?,?,'未收集')",(gid, id))
    elif golden_dew_count < cur_cnt:
        need_del = cur_cnt - golden_dew_count
        # 优先删 Web 生成的高位 ID（>=9000），保护 Excel 导入的低位有意义的 ID
        await db.execute(
            "DELETE FROM golden_dews WHERE id IN (SELECT id FROM golden_dews WHERE task_point_id=? AND status='未收集' AND id>=9000 ORDER BY id DESC LIMIT ?)",
            (id, need_del)
        )
        # 如果高位不够，再删低位
        remain = await db.execute("SELECT COUNT(*) as cnt FROM golden_dews WHERE task_point_id=?", (id,))
        remain_cnt = (await remain.fetchone())["cnt"]
        if remain_cnt > golden_dew_count:
            extra = remain_cnt - golden_dew_count
            await db.execute(
                "DELETE FROM golden_dews WHERE id IN (SELECT id FROM golden_dews WHERE task_point_id=? AND status='未收集' ORDER BY id DESC LIMIT ?)",
                (id, extra)
            )
    # 校正 clue_count（以线索表实际条数为准）
    await db.execute("UPDATE task_points SET clue_count=(SELECT COUNT(*) FROM clues WHERE task_point_id=?) WHERE id=?",(id,id))
    await db.commit()
    return {"ok":True}

async def delete_task_point(id:int)->dict:
    """删除任务点（级联删除关联数据）"""
    db=await get_db()
    old=await get_task_point(id)
    if not old: return {"ok":False,"msg":"任务点不存在"}
    # 删关联的露水（通过真线索ID）
    c=await db.execute("SELECT id FROM clues WHERE task_point_id=? AND clue_type='真'",(id,))
    clue_ids=[r["id"] for r in await c.fetchall()]
    for cid in clue_ids:
        await db.execute("DELETE FROM dews WHERE id=?",(cid,))
    # 删关联线索
    await db.execute("DELETE FROM clues WHERE task_point_id=?",(id,))
    # 删关联金露水
    await db.execute("DELETE FROM golden_dews WHERE task_point_id=?",(id,))
    # 删物资记录
    await db.execute("DELETE FROM task_point_inventory WHERE task_point_id=?",(id,))
    # 删 NPC 关联
    await db.execute("DELETE FROM task_point_npcs WHERE task_point_id=?",(id,))
    # 删任务点
    await db.execute("DELETE FROM task_points WHERE id=?",(id,))
    await db.commit()
    return {"ok":True}

async def update_task_point_status(id:int, status:str):
    db=await get_db()
    await db.execute("UPDATE task_points SET status=? WHERE id=?",(status,id))
    await db.commit()
