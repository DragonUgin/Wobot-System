"""金山文档云表格同步模块

双向同步策略：
1. Bot 写操作 → 同时更新本地 DB + 云表格
2. 定时轮询云表格 → 检测管理员编辑（复活操作）→ 同步到本地 DB

金山文档 Open API 文档：https://open.wps.cn/
"""
import httpx
import json
from datetime import datetime, timedelta
from typing import Optional
import config
from utils.db import (
    get_all_players,
    revive_player,
    get_player,
    get_db,
)

# ============================================================
# API 客户端
# ============================================================

_access_token: Optional[str] = None
_token_expires: Optional[datetime] = None


async def _get_access_token() -> str:
    """获取 access_token（简化版，生产环境需实现 OAuth 流程）"""
    global _access_token, _token_expires

    if _access_token and _token_expires and datetime.now() < _token_expires:
        return _access_token

    # TODO: 实现完整的 OAuth 授权流程
    # 1. 引导用户访问授权页面
    # 2. 获取授权码
    # 3. 用授权码换取 access_token
    # 4. 存储 refresh_token 用于续期

    # 当前使用 App ID + App Secret 的简化模式
    # 注意：金山文档 Open API 需要在 open.wps.cn 注册应用
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://open.wps.cn/oauth2/token",
            data={
                "grant_type": "client_credentials",
                "app_id": config.KDOCS_APP_ID,
                "app_secret": config.KDOCS_APP_SECRET,
            },
        )
        if resp.status_code == 200:
            data = resp.json()
            _access_token = data["access_token"]
            _token_expires = datetime.now() + timedelta(
                seconds=data.get("expires_in", 7200) - 300
            )
            return _access_token
        else:
            raise RuntimeError(f"获取 token 失败: {resp.text}")


async def _api_request(method: str, path: str, data: dict = None) -> dict:
    """发送 API 请求"""
    token = await _get_access_token()
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    url = f"https://open.wps.cn/api/v2{path}"
    async with httpx.AsyncClient(timeout=30) as client:
        if method == "GET":
            resp = await client.get(url, headers=headers, params=data)
        else:
            resp = await client.request(method, url, headers=headers, json=data)
        resp.raise_for_status()
        return resp.json()


# ============================================================
# 写操作（Bot → 云表格）
# ============================================================

# 云表格列映射：A=组号, B=姓名, C=状态, D=淘汰来源, E=淘汰时间, F=复活时间, G=备注
COL_MAP = {
    "group_num": "A",
    "name": "B",
    "status": "C",
    "source": "D",
    "eliminated_at": "E",
    "revived_at": "F",
    "note": "G",
}


def _find_row_for_player(players: list[dict], group_num: int, name: str) -> int:
    """在玩家列表中找到对应的行号（1-based）"""
    for i, p in enumerate(players):
        if p["group_num"] == group_num and p["name"] == name:
            return i + 2  # 跳过表头，行号从2开始
    return -1


async def _update_cell(row: int, col: str, value: str):
    """更新云表格单个单元格"""
    if not config.KDOCS_ENABLED:
        return
    try:
        await _api_request(
            "PUT",
            f"/files/{config.KDOCS_FILE_ID}/sheets/Sheet1/cells/{col}{row}",
            {"value": value},
        )
    except Exception as e:
        print(f"[金山文档] 更新单元格 {col}{row} 失败: {e}")


async def sync_elimination(group_num: int, name: str, location: str):
    """同步淘汰事件到云表格"""
    if not config.KDOCS_ENABLED:
        return
    try:
        players = await get_all_players()
        row = _find_row_for_player(players, group_num, name)
        if row < 0:
            return
        now = datetime.now().strftime("%H:%M")
        await _update_cell(row, "C", "淘汰")
        await _update_cell(row, "D", location)
        await _update_cell(row, "E", now)
        print(f"[金山文档] 已同步淘汰: {group_num}组{name}")
    except Exception as e:
        print(f"[金山文档] 同步淘汰失败: {e}")


async def sync_revival(group_num: int, name: str):
    """同步复活事件到云表格"""
    if not config.KDOCS_ENABLED:
        return
    try:
        players = await get_all_players()
        row = _find_row_for_player(players, group_num, name)
        if row < 0:
            return
        now = datetime.now().strftime("%H:%M")
        await _update_cell(row, "C", "复活")
        await _update_cell(row, "F", now)
        print(f"[金山文档] 已同步复活: {group_num}组{name}")
    except Exception as e:
        print(f"[金山文档] 同步复活失败: {e}")


async def sync_all_to_cloud():
    """全量同步本地数据到云表格（初始化或数据修复用）"""
    if not config.KDOCS_ENABLED:
        return
    try:
        players = await get_all_players()
        for i, p in enumerate(players):
            row = i + 2
            await _update_cell(row, "A", str(p["group_num"]))
            await _update_cell(row, "B", p["name"])
            await _update_cell(row, "C", p["status"])
            await _update_cell(row, "D", p.get("source", "") or "")
            await _update_cell(row, "E", p.get("eliminated_at", "") or "")
            await _update_cell(row, "F", p.get("revived_at", "") or "")
            await _update_cell(row, "G", p.get("note", "") or "")
        print(f"[金山文档] 全量同步完成，共 {len(players)} 条")
    except Exception as e:
        print(f"[金山文档] 全量同步失败: {e}")


# ============================================================
# 读操作（云表格 → Bot，检测管理员编辑）
# ============================================================

_last_cloud_state: dict[str, str] = {}  # "组号_姓名" -> "状态"


async def poll_cloud_changes() -> list[tuple[int, str, str]]:
    """轮询云表格变化，返回 [(组号, 姓名, 新状态), ...]"""
    if not config.KDOCS_ENABLED:
        return []
    try:
        data = await _api_request(
            "GET",
            f"/files/{config.KDOCS_FILE_ID}/sheets/Sheet1/range",
            {"range": "A2:G200"},
        )
        changes = []
        rows = data.get("values", [])
        for row in rows:
            if len(row) < 3:
                continue
            group_num = int(row[0])
            name = str(row[1]).strip()
            status = str(row[2]).strip()
            key = f"{group_num}_{name}"

            if key in _last_cloud_state and _last_cloud_state[key] != status:
                # 状态变化了！
                old_status = _last_cloud_state[key]
                if old_status == "淘汰" and status == "复活":
                    changes.append((group_num, name, status))
                elif old_status == "存活" and status == "淘汰":
                    # 管理员在云表格直接标记淘汰（少见但可能）
                    changes.append((group_num, name, status))

            _last_cloud_state[key] = status

        return changes
    except Exception as e:
        print(f"[金山文档] 轮询失败: {e}")
        return []


async def apply_cloud_changes():
    """检测并应用云表格变化到本地 DB"""
    changes = await poll_cloud_changes()
    for group_num, name, new_status in changes:
        if new_status == "复活":
            success = await revive_player(group_num, name)
            if success:
                print(f"[金山文档] 已从云端同步复活: {group_num}组{name}")
        elif new_status == "淘汰":
            # 管理员在云端直接标记淘汰，需要手动设置地点
            db = await get_db()
            await db.execute(
                """UPDATE players SET status='淘汰', eliminated_at=?, source='管理员标记'
                   WHERE group_num=? AND name=? AND status='存活'""",
                (datetime.now().strftime("%H:%M"), group_num, name),
            )
            await db.commit()
            print(f"[金山文档] 已从云端同步淘汰: {group_num}组{name}")
