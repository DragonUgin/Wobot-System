# 第三方组件许可声明（Third-Party Notices）

本项目在“私有、学习、非商用”前提下使用了以下第三方开源 / 自由软件组件。
各组件按其上游许可条款使用；具体许可文本以其官方仓库为准。

> 说明：NoneBot2 / FastAPI 等为宽松许可（MIT / BSD），可自由使用、修改、再分发。
> NapCat 为“受限再分发”许可，本仓库**不包含其代码**，仅提供官方下载指引，
> 使用须遵守其许可（个人 / 非商用，禁止再分发 / 发布修改版 / 商用）。

## 直接依赖（Claw/requirements.txt）

| 组件 | 版本约束 | 许可 | 仓库 |
|---|---|---|---|
| nonebot2[fastapi] | >=2.3.0 | MIT | https://github.com/nonebot/nonebot2 |
| nonebot-adapter-onebot | >=2.4.0 | MIT | https://github.com/nonebot/nonebot2 |
| aiosqlite | >=0.19.0 | MIT | https://github.com/omnilib/aiosqlite |
| Pillow | >=10.0.0 | MIT-CMU / HPND | https://github.com/python-pillow/Pillow |
| APScheduler | >=3.10.0 | MIT | https://github.com/agronholm/apscheduler |
| httpx | >=0.25.0 | BSD-3-Clause | https://github.com/encode/httpx |
| pydantic | >=2.0.0 | MIT | https://github.com/pydantic/pydantic |
| openpyxl | >=3.1.0 | MIT | https://foss.heptapod.net/openpyxl/openpyxl |
| python-multipart | >=0.0.6 | MIT | https://github.com/andrew-d/python-multipart |
| python-dotenv | >=1.0 | BSD-3-Clause | https://github.com/theskumar/python-dotenv |

## 其他第三方组件

- **NapCat（QQ 协议端）**：受限再分发许可。
  官方仓库：https://github.com/NapNeko/NapCatQQ/releases
  使用限制：个人 / 非商用使用；**禁止再分发、禁止发布修改版、禁止商用**。
  本仓库不包含 NapCat 代码，仅通过 `setup.bat` 指引用户自行下载官方 Release。

- **Vue 3（Web 前端）**：MIT 许可（通过 CDN / 内联方式使用，非本仓库直接依赖）。
- **FastAPI / Starlette / Uvicorn** 等由 nonebot2[fastapi] 间接引入，许可同上（MIT / BSD）。

## 合规承诺

作者承诺：仅以个人、非商业、学习研究目的使用上述组件；不将 NapCat 再分发；
如需对外发布本项目，将另行取得相关授权并补充相应许可文件。
