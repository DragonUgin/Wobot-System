# Wobot System — a NapCat-based QQ game system

> Real-time tracking & sync for large offline games.

为大型线下户外游戏提供**实时数据追踪与信息同步**的 QQ 群机器人系统：玩家在游戏群查状态，猎人 / 任务点 NPC 在工作群发指令，管理员在后台群或 Web 页面管理。

> 本项目以 **GPL-3.0-or-later** 许可证开源。第三方组件的许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

## 项目简介

本项目为「教育改变晋江」**承办**的 **2026 年第九期准大学生菁英训练营** 中大型线下户外游戏「极限挑战」而生，目标是将 100+ 名玩家的游戏状态、线索与露水实时汇总到一处，实现数据的实时追踪与信息同步。

## 技术架构

| 层 | 技术 | 说明 |
|---|---|---|
| 机器人框架 | NoneBot2（MIT） | 接收 / 解析 QQ 消息指令 |
| QQ 协议端 | NapCat（受限再分发） | 桥接 QQ 与 OneBot，需单独下载 |
| Web 服务 | FastAPI（MIT） | 提供 8080 端口管理页面 |
| 前端 | Vue3 单文件（web/index.html） | 看板 / 管理 / 导入 |
| 数据库 | SQLite + aiosqlite（WAL） | 游戏状态持久化 |
| 运行时 | Python 3.12 嵌入式 | 便携，无需安装 |
| 办公文档 | openpyxl / Pillow | Excel 与看板图生成 |

### 三群架构

系统用三个 QQ 群 + 一个 Web 管理页，把「玩家 / 工作人员 / 管理员」三类人隔开，降低单群消息密度、规避 Bot 账号风控：

- **玩家群（GAME_GROUP）**：玩家查状态、收播报的**唯一对外窗口**。
  - **设计意图**：只向玩家播报**必要信息**（淘汰、任务点完成、免疫、战况），不暴露工作指令与后台大盘——既保护工作人员动线，也把高频业务消息挡在玩家视野外。
  - 玩家在玩家群仅能使用 `查询状态` 一条指令。
- **工作群（WORK_GROUP）**：猎人 / 任务点 NPC 的**高频集散地**。
  - **设计意图**：所有业务指令（淘汰、功能卡、任务点完成 / 接收）都在这里收发，消息密度最高；靠 **QQ 群成员身份**保证身份，系统不做发送者名单校验。
  - 仅在工作群发的指令才会被系统处理。
- **后台群（BACKEND_GROUP）**：管理员的**大盘 + 操作**窗口。
  - **设计意图**：淘汰带道具、机动调度、异常告警等需要全局视野的消息在此汇总，管理员在此发管理指令、看实时战况。
- **Web 管理页**：浏览器打开 `http://127.0.0.1:8080`，管理员 QQ 在 `.env` 的 `ADMIN_QQ` 中配置，用于导入数据、开始 / 结束游戏、手动编辑状态。

## 玩法速览

五种道具的获取 / 作用 / 消耗 / 冷却 / 触发，以及完整游戏流程，见 [docs/游戏介绍.md](docs/游戏介绍.md)（§5 五种道具 + §10 完整游戏流程）。

## 实战记录

2026-08-04 于福州大学（晋江校区）首次实战，原计划 16:10–18:10，实际运行约 1 小时 47 分钟。

| 项目 | 数据 |
|---|---|
| 玩家 | 126 名 |
| 猎人 | 17 名（含 5 名露水 NPC） |
| 任务点 / 任务点 NPC | 6 个 / 12 名 |
| 后台管理员 | 3 名 |
| 机动人员 | 6 名 |
| 线索卡 / 露水卡 | 54 张 |
| 金露水卡 | 12 张 |
| 静止卡 | 6 × 5 = 30 张 |
| 护盾卡 | 6 × 5 = 30 张 |

> 运行至 17:57 崩溃，原因有二：一是定时任务循环报错；二是播报消息过于频繁，触发了 QQ 账号风控。相关问题已记录在 [待修复备忘录.md](待修复备忘录.md)。

## 使用指南

各角色指令清单已拆分到 `docs/`，请按需查阅：

| 角色 | 文档 |
|---|---|
| 管理员（部署 + 管理操作） | [docs/管理员指南.md](docs/管理员指南.md) |
| 玩家 | [docs/玩家指南.md](docs/玩家指南.md) |
| 猎人 | [docs/猎人指南.md](docs/猎人指南.md) |
| 任务点 NPC | [docs/任务点NPC指南.md](docs/任务点NPC指南.md) |
| 其他 NPC（露水 NPC / 机动人员 / 跟组辅导员） | [docs/其他NPC指南.md](docs/其他NPC指南.md) |
| 通用指令 | [docs/通用指令.md](docs/通用指令.md) |

## 快速开始（部署）

1. **首次准备**：双击 `setup.bat` 安装 Python 依赖，并按提示下载 NapCat 到 `napcat/`。
2. **配置**：复制 `Claw/.env.example` 为 `Claw/.env`，填入以下字段：`BOT_QQ`（Bot 小号）、`GAME_GROUP` / `WORK_GROUP` / `BACKEND_GROUP`（三个群号）、`ADMIN_QQ`（管理员）。
3. **启动**：双击 `start.bat`，NapCat 窗口用 Bot 小号扫码登录（NapCat 的 WebUI 在 `http://127.0.0.1:6099`）。
4. **管理**：浏览器打开 `http://127.0.0.1:8080`，在“管理”页导入数据、开始游戏。

## 升级方法

更新系统时，**只替换 `Claw/` 目录中的源码文件**即可，保留 `Claw/data/claw.db`（游戏数据库）不清除，历史数据不会丢失。`.env` 配置也保留，无需重填。

## 目录结构

```
58系统/
├── start.bat            # 一键启动（Bot + NapCat + 浏览器）
├── setup.bat            # 首次：装 Python 依赖 + NapCat 下载指引
├── .gitignore           # 数据与系统分离
├── docs/                # 各角色使用指南（指令清单）
├── Claw/                # 系统源码（入库）
│   ├── bot.py           # 机器人入口
│   ├── config.py        # 配置（读取 .env + system_config 表）
│   ├── .env.example     # 配置模板（入库）
│   ├── requirements.txt # Python 依赖
│   ├── src/plugins/     # 指令插件
│   ├── utils/           # db / 计时 / 播报 / 冷却
│   ├── web/             # Vue3 管理页
│   └── data/            # 数据库 + 生成脚本（*.db/*.xlsx 已忽略）
├── napcat/              # NapCat 程序（已忽略，单独下载）
└── python-embed/        # 嵌入式 Python（已忽略）
```

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

## 鸣谢

- **教育改变晋江**（承办方）

  <p align="center">
    <img src="docs/项目图标/教育改变晋江-徽标.jpg" alt="教育改变晋江 徽标" width="160" />
  </p>
- **2026 极限挑战策划组**
- **第九期准大学生菁英训练营**全体辅导员与营员
- 参考与使用的开源项目：NoneBot2、NapCat、FastAPI、openpyxl、Pillow

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

## 作者的话

这个项目的起点，是 2026 年 5 月我在报名准大学生辅导员时，看到去年「极限挑战」玩家群里淘汰通知的固定格式，萌生了"能不能让它自动化"的念头。

作为一个跌跌撞撞刚度过大一学期的学生，这是我第一次从零独立完成一个项目——全程用 vibe coding 摸索，绕了不少弯路，功能上也还有不少可以打磨的地方。但正是这个过程，让一个青涩的想法真正落了地。

这不仅仅是系统的源代码，更详细记录了整个游戏的完整流程方案。

希望到明年，无论这个系统有没有机会被复用，我都有能力把这个游戏策划得更好。

感谢每一个愿意接纳Wubot，陪我一起试错的人。

把爱留在教改！
