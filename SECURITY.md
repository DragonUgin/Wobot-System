# 安全政策（Security Policy）

## 支持版本

本项目处于快速迭代阶段，仅对 `main` 分支的最新版本提供安全更新。

| 版本 | 是否受支持 |
|---|---|
| main（最新） | ✅ 支持 |
| 其他历史版本 | ❌ 不支持 |

## 报告漏洞

如果你发现任何安全漏洞，请**不要**通过公开 Issue 披露。请选择以下任一方式私下报告：

- 在 GitHub 仓库页面点击 **Security → Report a vulnerability** 发起私有漏洞报告；
- 或联系维护者 **DragonUgin**（GitHub @DragonUgin）。

我们会在收到报告后尽快确认并响应，必要时发布安全更新与致谢（经你同意）。

## 已知安全边界与部署须知

Web 管理页（`http://127.0.0.1:8080`，FastAPI）的**全部 `/api/*` 接口均需要 Bearer Token 认证**：

- Token 由 `.env` 中的 `ADMIN_TOKEN` 配置，**为空时所有接口返回 401**（fail-closed，页面无法使用）。
- 部署前**务必**设置一个强随机 Token，例如：
  ```bash
  openssl rand -hex 24
  ```
- Token 仅保存在管理员本机浏览器 `localStorage`，不会上传服务器，但请不要在公共/共享设备上勾选「记住」。
- `.env` 已被 `.gitignore` 忽略，不会进入仓库；请勿将真实 Token 提交到 Git。

其他注意事项：

- 仓库历史已通过 `git filter-repo` 重写，清除了早期提交中的真实 QQ 号、群号与姓名；但**公开前仍建议轮换**曾出现在旧代码/明文文件中的 QQ 小号密码与 NapCat 登录凭证，因为旧历史的副本可能仍残留在 fork / clone / 缓存中。
- 本系统通过 NapCat 控制 QQ 机器人账号，请遵守腾讯相关协议，勿用于违规用途。
- 数据目录（`.db`、`.xlsx`、`.docx`、日志、`napcat/`、`python-embed/`）均已在 `.gitignore` 中排除，不会随仓库分发。
