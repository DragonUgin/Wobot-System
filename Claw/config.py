# SPDX-License-Identifier: GPL-3.0-or-later
"""全局配置 —— 三级热加载架构

1. .env 提供初始默认值
2. system_config 表存储运行时可变值
3. config.py 内存缓存供插件引用

插件用法：
  import config
  gid = config.get_game_group()
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ============================================================
# 基础路径
# ============================================================

BASE_DIR = Path(__file__).resolve().parent

_env_file = BASE_DIR / ".env"
if _env_file.exists():
    load_dotenv(_env_file, override=False)

# ============================================================
# .env 默认值（首次启动写入 system_config 表）
# ============================================================

def _env_int(key: str, default: int = 0) -> int:
    """读取 .env 整数，空字符串返回 default"""
    val = os.getenv(key, "")
    if not val or not val.strip():
        return default
    return int(val.strip())

_env_game_group = _env_int("GAME_GROUP")
_env_work_group = _env_int("WORK_GROUP")
_env_backend_group = _env_int("BACKEND_GROUP")
_env_admin_qq = [int(q.strip()) for q in os.getenv("ADMIN_QQ", "").split(",") if q.strip()]
_env_bot_qq = _env_int("BOT_QQ")

# ============================================================
# 金山文档（不变）
# ============================================================

KDOCS_APP_ID = os.getenv("KDOCS_APP_ID", "")
KDOCS_APP_SECRET = os.getenv("KDOCS_APP_SECRET", "")
KDOCS_FILE_ID = os.getenv("KDOCS_FILE_ID", "")
KDOCS_ENABLED = bool(KDOCS_APP_ID and KDOCS_APP_SECRET and KDOCS_FILE_ID)

# ============================================================
# 路径
# ============================================================

DB_PATH = Path(os.getenv("DB_PATH", str(BASE_DIR / "data" / "claw.db")))
DASHBOARD_PATH = BASE_DIR / "data" / "dashboard.png"

# ============================================================
# 播报间隔（默认值）
# ============================================================

BROADCAST_SCHEDULE = [
    (0.60, 15),
    (0.40, 10),
    (0.20, 5),
    (0.05, 2),
    (0.00, 1),
]

# 金山文档同步间隔
KDOCS_SYNC_INTERVAL = 30

# ============================================================
# 运行时配置缓存（从 system_config 表加载）
# ============================================================

_runtime_config: dict = {}


async def init_config():
    """启动时调用：将 .env 默认值写入 system_config（仅首次），并加载到内存缓存"""
    from utils.db import get_db

    db = await get_db()
    defaults = {
        "game_group": str(_env_game_group),
        "work_group": str(_env_work_group),
        "backend_group": str(_env_backend_group),
        "admin_qq": ",".join(str(q) for q in _env_admin_qq),
    }
    for key, value in defaults.items():
        # 先查当前值，为空才写入（保护 Web 页面手动修改的配置）
        cursor = await db.execute(
            "SELECT value FROM system_config WHERE key=?", (key,)
        )
        row = await cursor.fetchone()
        existing = row["value"] if row else None
        if not existing or existing == "0" or existing == "":
            await db.execute(
                "INSERT OR REPLACE INTO system_config (key, value) VALUES (?, ?)",
                (key, value),
            )
    await db.commit()
    await reload_config()


async def reload_config():
    """从 system_config 表重新加载所有配置到内存缓存"""
    global _runtime_config
    from utils.db import get_all_config

    _runtime_config = await get_all_config()


# ============================================================
# 配置访问函数（插件调用这些，不用直接读变量）
# ============================================================

def get_game_group() -> int:
    raw = _runtime_config.get("game_group", "")
    return int(raw) if raw else _env_game_group


def get_work_group() -> int:
    raw = _runtime_config.get("work_group", "")
    return int(raw) if raw else _env_work_group


def get_backend_group() -> int:
    raw = _runtime_config.get("backend_group", "")
    return int(raw) if raw else _env_backend_group


def get_admin_qqs() -> list[int]:
    raw = _runtime_config.get("admin_qq", "")
    if raw:
        return [int(q.strip()) for q in raw.split(",") if q.strip()]
    return list(_env_admin_qq)


def is_admin(qq: int) -> bool:
    return qq in get_admin_qqs()
