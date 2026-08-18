# SPDX-License-Identifier: GPL-3.0-or-later
"""Claw - 多人淘汰游戏 QQ 群管理机器人"""
import sys
from pathlib import Path

# 确保项目根目录在 Python 路径中
BASE_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BASE_DIR))

import nonebot
from nonebot.adapters.onebot.v11 import Adapter as OneBotV11Adapter

nonebot.init()

import config

driver = nonebot.get_driver()
driver.register_adapter(OneBotV11Adapter)


# 启动阶段 1：初始化配置（从 DB 热加载）
@driver.on_startup
async def _init_config():
    await config.init_config()
    nonebot.logger.info("=" * 40)
    nonebot.logger.info("Claw Bot Starting...")
    nonebot.logger.info(f"GAME_GROUP    = {config.get_game_group()}")
    nonebot.logger.info(f"WORK_GROUP    = {config.get_work_group()}")
    nonebot.logger.info(f"BACKEND_GROUP = {config.get_backend_group()}")
    nonebot.logger.info(f"ADMIN_QQ      = {config.get_admin_qqs()}")
    nonebot.logger.info(f"KDOCS_ENABLED = {config.KDOCS_ENABLED}")
    nonebot.logger.info(f"DB_PATH       = {config.DB_PATH}")
    nonebot.logger.info(f"Web           = http://127.0.0.1:8080")
    if not config.get_admin_token():
        nonebot.logger.warning(
            "ADMIN_TOKEN 未配置：Web 管理页的全部 /api/* 接口将返回 401，页面无法使用。"
            "请在 .env 中设置 ADMIN_TOKEN（建议 openssl rand -hex 24 生成）。"
        )
    else:
        nonebot.logger.info("ADMIN_TOKEN 已配置，Web 管理页已启用 Bearer Token 认证。")
    nonebot.logger.info("=" * 40)

nonebot.load_plugins("src/plugins")

if __name__ == "__main__":
    nonebot.run()
