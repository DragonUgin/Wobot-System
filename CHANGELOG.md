# 更新日志 / Changelog

本项目所有重要改动记录于此。

格式遵循 [Keep a Changelog](https://keepachangelog.com/)，
版本号遵循 [语义化版本 Semantic Versioning](https://semver.org/lang/zh-CN/)。

## [Unreleased]

### 新增
- Web API Bearer Token 认证（D1）：`config.py` 读取 `ADMIN_TOKEN`，`api.py` 中间件拦截 `/api/*`，前端 `index.html` 登录框与 401 处理
- 公开前规范文档：`SECURITY.md`、`CODE_OF_CONDUCT.md`、`CONTRIBUTING.md`
- `docs/其他NPC指南.md`
- README 鸣谢区「教育改变晋江」机构徽标、作者的话新版
- `docs/游戏介绍配图/非游戏区域地图.jpg` 及 `docs/游戏介绍.md` 区域地图配图

### 变更
- 项目英文名统一为 **Wobot**，GitHub 仓库名改为 **Wobot-System**
- `README.md`、`start.bat`、`setup.bat`、`docs/游戏介绍.md` 中 `Wubot` → `Wobot`

### 安全
- 用 `git filter-repo --replace-text` 重写历史，剔除真实 QQ / 群号 / 姓名 / token 等功能性敏感数据
- 完成凭据轮换：撤销 GitHub OAuth 授权、修改 QQ bot 密码、更换 NapCat WebUI token

### 文档
- `公开前准备清单.md` 同步公开前收尾结论，新增「容易忽视的清单」提醒维护 `待修复备忘录.md` 与 `CHANGELOG.md`
- `README.md` 鸣谢徽标与游戏介绍地图统一采用左对齐

## [1.0.0] - 2026-08-17

### 新增
- 初始化版本管理，数据与系统分离（`.gitignore` 排除密钥 / 数据库 / 生成数据 / 第三方运行时）
- 新增 `Claw/.env.example`、`setup.bat`、`README.md`、`THIRD_PARTY_NOTICES.md`
- 提交身份设为 `DragonUgin`，远程 `origin` 指向 GitHub 私有仓库 `5botSystem`
- 新增 `CHANGELOG.md` 作为版本更新日志

### 修复 / 安全
- 清理 `start.bat`、`README.txt` 中的明文 Token 与过期群号
- 修正首次提交的作者邮箱（改用 GitHub noreply 地址，规避 GH007 隐私保护）

### 变更
- 许可证由"保留所有权利"改为 **GPL-3.0-or-later**
- 所有 `.py` 源文件顶部加 `SPDX-License-Identifier: GPL-3.0-or-later` 标识
