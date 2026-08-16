# 乌波 // 极限挑战 游戏系统（Claw v3.0）

线下活动用的 QQ 群机器人游戏管理系统：玩家在游戏群查询状态，猎人 / 任务点 NPC 在工作群发指令，管理员在后台群 / Web 页面管理。

> ⚠️ 本项目为**私有项目**，仅供作者学习与使用。第三方组件的许可见 [THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md)。

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
