# 贡献指南（Contributing）

感谢你关注 **乌波 // 极限挑战（Claw）** 游戏系统！本项目目前以「教育改变晋江」承办方内部使用为主，代码公开仅供参考与学习。欢迎通过 Issue 反馈问题或提出建议。

## 如何开始

1. Fork 并克隆仓库：
   ```bash
   git clone https://github.com/DragonUgin/5botSystem.git
   cd 5botSystem
   ```
2. 安装运行环境（详见 `README.md` 的「快速开始」）：
   - Python 3.10+ 与 `pip install -r requirements.txt`（或运行 `setup.bat`）；
   - 复制 `Claw/.env.example` 为 `Claw/.env` 并填入真实配置（`.env` 已被 `.gitignore` 忽略）。
3. **Web 管理页需要 Token**：在 `.env` 中设置 `ADMIN_TOKEN`（建议 `openssl rand -hex 24`），否则所有 `/api/*` 接口返回 401。

## 提交规范（必读）

本仓库对提交信息有强制要求：

- **每一次提交都必须写提交说明**，格式为「标题（subject）+ 正文（body）」；
- **正文中每个有变动的文件都要单独写一行说明**，说明改了什么、为什么；
- 标题简明扼要（一般 `<类型>: <简述>`），例如：
  `fix: 修正任务点接收露水库存计数`；
- 示例：
  ```
  docs: 补充三群架构设计意图、卡片表与完整游戏流程

  - README.md：三群架构补「设计意图」；卡片表迁移至 docs。
  - docs/游戏介绍.md：§5 改为六列道具表；全文改用相对时间。
  ```

> 提交身份统一为 `DragonUgin <562993317@qq.com>`。**未经维护者许可，请勿擅自推送（push）到主仓库。**

## 代码与文档约定

- **许可证**：本项目以 **GPL-3.0-or-later** 发布。所有新增 `.py` 源文件顶部请加入：
  ```python
  # SPDX-License-Identifier: GPL-3.0-or-later
  ```
- **指令格式**：猎人 / NPC / 管理员指令的权威说明以 `docs/` 下各角色指南为准，修改指令逻辑时请同步更新对应指南。
- **敏感信息**：严禁将真实 QQ 号、群号、姓名、Token 写入会被提交的文件；测试数据请脱敏，或放入已被 `.gitignore` 排除的目录。
- **数据分离**：`.db`、`.xlsx`、`.docx`、日志、`napcat/`、`python-embed/` 等运行数据不进入仓库。

## 反馈渠道

- Bug / 功能建议：通过 GitHub Issue；
- 安全漏洞：**不要**公开 Issue，请走 `SECURITY.md` 中的私有报告渠道。

再次感谢你的参与！
