========================================
  乌波 // 极限挑战游戏系统
  U盘便携版 v3.0
========================================

【快速开始】

1. 双击 start.bat 启动系统
2. NapCat 窗口弹出后，用 QQ 小号 0 扫码登录
3. 浏览器打开管理页面：http://127.0.0.1:8080
4. 在"管理"标签页导入测试数据

【包含内容】

├── start.bat              ← 双击启动
├── python-embed\          ← Python 3.12 嵌入式（无需安装）
├── Claw\                  ← 游戏系统代码
│   ├── bot.py             ← 机器人入口
│   ├── web\index.html     ← Web管理页面
│   └── data\              ← 数据库存放
└── napcat\                ← QQ机器人协议端

【端口与账号】

Web管理页   : http://127.0.0.1:8080
NapCat WebUI : http://127.0.0.1:6099
Bot小号QQ   : 见 Claw\.env 的 BOT_QQ
群号/管理员 : 见 Claw\.env（GAME_GROUP / WORK_GROUP / BACKEND_GROUP / ADMIN_QQ）

【首次使用】

1. 启动后打开 http://127.0.0.1:8080
2. 切换到"管理"标签页
3. 群号配置：填写工作群、后台群号并保存
4. 导入数据：上传 Excel（可用 data/test_import.xlsx 测试）
5. 切换到"看板"开始游戏

【注意事项】

- 必须先启动 Bot，再让 NapCat 扫码登录
- 启动顺序 start.bat 已自动处理
- 如遇端口冲突，关闭其他占用 8080 端口的程序
- 数据库文件自动创建在 Claw\data\claw.db

【升级方法】

替换 Claw\ 目录中的文件即可（保留 data\claw.db 不清除数据）
