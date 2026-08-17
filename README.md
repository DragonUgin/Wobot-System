# 乌波 // 极限挑战 游戏系统（Claw v3.0）

线下活动用的 QQ 群机器人游戏管理系统：玩家在游戏群查询状态，猎人 / 任务点 NPC 在工作群发指令，管理员在后台群 / Web 页面管理。

> 本项目以 **GPL-3.0-or-later** 许可证开源（当前为私有仓库，计划后续公开）。第三方组件的许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 技术架构

| 层 | 技术 | 说明 |
|---|---|---|
| 机器人框架 | NoneBot2（MIT） | 接收 / 解析 QQ 消息指令 |
| QQ 协议端 | NapCat（受限再分发） | 桥接 QQ 与 OneBot，需单独下载 |
| Web 服务 | FastAPI（MIT） | 提供 8080 端口管理页面 |
| 前端 | Vue3 单文件（web/index.html） | 看板 / 管理 / 导入 |
| 数据库 | SQLite + aiosqlite（WAL） | 游戏状态持久化 |
| 运行时 | Python 3.12 嵌入式（python-embed） | 便携，无需安装 |
| 办公文档 | openpyxl / Pillow | Excel 与看板图生成 |

### 三群权限模型

- **游戏群（GAME_GROUP）**：玩家查询状态、接收播报。
- **工作群（WORK_GROUP）**：猎人 / 任务点 NPC 在此发业务指令（靠 QQ 群成员身份保证，系统不做发送者名单校验）。
- **后台群（BACKEND_GROUP）**：管理员发管理指令。
- **Web 管理页**：浏览器打开 `http://127.0.0.1:8080`，管理员 QQ 在 `.env` 的 `ADMIN_QQ` 中配置。

## 目录结构

```
58系统/
├── start.bat            # 一键启动（Bot + NapCat + 浏览器）
├── setup.bat            # 首次：装 Python 依赖 + NapCat 下载指引
├── .gitignore           # 数据与系统分离
├── Claw/                # 系统源码（入库）
│   ├── bot.py           # 机器人入口
│   ├── config.py        # 配置（读取 .env + system_config 表）
│   ├── .env             # 真实配置（已忽略，不入库）
│   ├── .env.example     # 配置模板（入库）
│   ├── requirements.txt # Python 依赖
│   ├── src/ plugins/    # 指令插件
│   ├── utils/           # db / 计时 / 播报 / 冷却
│   ├── web/             # Vue3 管理页
│   └── data/            # 数据库 + 导入/生成脚本（*.db/*.xlsx 已忽略）
├── napcat/              # NapCat 程序（已忽略，单独下载）
└── python-embed/        # 嵌入式 Python（已忽略）
```

## 文件说明

| 文件 / 目录 | 用途 |
|---|---|
| `start.bat` | 一键启动：拉起 NapCat + Bot，并打开浏览器访问 Web 管理页 |
| `setup.bat` | 首次安装：用嵌入式 Python 装依赖 + 指引下载 NapCat |
| `.gitignore` | 数据与系统分离：密钥 / 数据库 / 生成数据 / 第三方运行时不入库 |
| `README.md` | 本说明文档 |
| `LICENSE` | GPL-3.0-or-later 许可证全文 |
| `CHANGELOG.md` | 版本更新日志（Keep a Changelog 规范） |
| `THIRD_PARTY_NOTICES.md` | 第三方依赖许可声明 |
| `待修复备忘录.md` | 已知 bug / 设计问题清单（非紧急，有空再修） |
| `Claw/bot.py` | 机器人入口，加载插件与配置 |
| `Claw/config.py` | 三级热加载配置（读取 `.env` + `system_config` 表） |
| `Claw/.env` | 真实配置（已忽略，**不入库**） |
| `Claw/.env.example` | 配置模板（入库，复制为 `.env` 后填写） |
| `Claw/requirements.txt` | Python 依赖清单 |
| `Claw/src/plugins/` | 指令插件：`api`(Web 路由) / `backend`(管理指令) / `game_group`(玩家查询) / `work_group`(猎人·NPC 上报) / `debug`(诊断) / `timer`(计时播报) / `private_msg`(私聊转发) |
| `Claw/utils/` | 核心库：`db`(数据库层/状态机/撤销) / `cooldown`(冷却) / `broadcast`(三群播报) / `timer_logic`(计时逻辑) / `excel_importer`(Excel 导入) / `kdocs_sync`(金山文档同步，当前未启用) |
| `Claw/web/index.html` | Vue3 单文件 Web 管理后台（看板 / 管理 / 导入） |
| `Claw/data/` | 数据库 + 数据生成 / 导入脚本（`*.db/*.xlsx` 已忽略，不入库） |

## 快速开始

1. **首次准备**：双击 `setup.bat` 安装 Python 依赖，并按提示下载 NapCat 到 `napcat/`。
2. **配置**：复制 `Claw/.env.example` 为 `Claw/.env`，填入你的 Bot QQ、三个群号、管理员 QQ。
3. **启动**：双击 `start.bat`，NapCat 窗口用 QQ 小号扫码登录。
4. **管理**：浏览器打开 `http://127.0.0.1:8080`，在“管理”页导入数据、开始游戏。

## 数据与系统分离（Git）

为保护隐私与减小仓库体积，以下**不入库**（见 `.gitignore`）：

- `Claw/.env`（密钥与群号）
- `Claw/data/*.db` 及所有备份、诊断库
- `Claw/data/*.xlsx *.docx *.png`（生成的游戏数据）
- `*.log`
- `napcat/`、`python-embed/`（第三方程序 / 运行时，单独放置）

入库的只有：源码、配置模板、导入 / 生成脚本、文档。

## 开源合规

- **NoneBot2 / FastAPI / openpyxl 等**：MIT / BSD 等宽松许可，可自由使用、修改、分发，并已通过 `requirements.txt` 声明依赖。
- **NapCat**：**受限再分发**许可 —— 允许个人 / 非商用使用，**禁止再分发、禁止发布修改版、禁止商用**。本仓库**不包含** NapCat 本体，仅提供官方 Release 下载指引。
- 第三方许可详情见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 许可证

本项目以 **GPL-3.0-or-later**（GNU 通用公共许可证 v3 或更高版本）发布，版权归属 **DragonUgin**。

- 每个源码文件顶部均标注 `SPDX-License-Identifier: GPL-3.0-or-later`。
- 完整许可证文本见 [LICENSE](LICENSE)。
- 第三方依赖（NoneBot2 / FastAPI 等 MIT；NapCat 受限再分发）的许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)，与本项目许可证不冲突：NapCat 不随仓库分发，由使用者单独下载。

## 推送到远程

本仓库已配置远程 `origin`（GitHub 私有仓库）。日常改动流程：

```bash
git add <改动的文件>
git commit -m "type: 简短说明"
git push
```

首次推送（或分支重置后）：

```bash
git branch -M main
git push -u origin main
```

> 提示：提交作者邮箱建议使用 GitHub 提供的 `noreply` 地址（`用户名@users.noreply.github.com`），避免真实邮箱被写入公开 git 历史（GitHub 隐私保护 GH007）。
>
> 若推送被拒 `failed to push some refs`，说明远程已有提交：先 `git pull origin main --allow-unrelated-histories` 合并；或确认远程无重要内容后，用 `git push --force-with-lease` 覆盖（比 `--force` 安全）。
