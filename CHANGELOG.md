# 更新日志 / Changelog

本项目所有重要改动记录于此。

格式遵循 [Keep a Changelog](https://keepachangelog.com/)，
版本号遵循 [语义化版本 Semantic Versioning](https://semver.org/lang/zh-CN/)。

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

### 待办
- 待修复备忘录中的若干 bug / 设计问题（状态机、统计、撤销方向、双关联等），见 `待修复备忘录.md`
- Web API 无认证（FastAPI :8080）：计划公开前补 Token 校验（见备忘录 D1）
