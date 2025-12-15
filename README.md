# CatieBot

一个功能完整的 Discord AI 聊天机器人，支持流式回复、用户记忆、知识库检索等功能。

## 功能特性

### Discord Bot
- **消息交互**: @机器人 或 回复机器人触发对话
- **流式回复**: 实时显示生成内容
- **上下文理解**: 读取频道最近N条消息作为上下文
- **图片识别**: 支持识别用户发送的图片
- **频道标注**: 读取置顶消息作为答疑参考
- **表情支持**: 可使用服务器表情
- **艾特成员**: 可艾特频道成员

### 管理命令

- `/ban` - 将用户加入黑名单
- `/unban` - 解除用户黑名单
- `/blacklist` - 查看黑名单列表
- `/addchannel` - 将当前频道加入白名单
- `/removechannel` - 移除频道白名单
- `/channels` - 查看频道白名单

**权限说明**: 服务器管理员或内置开发者 (ID: 1373778569154658426) 可执行管理命令

### 后端功能
- **用户记忆**: 自动保存对话，定期AI总结用户特征
- **知识库**: 关键词搜索，自动检索相关知识
- **内容安全**: 敏感词过滤、破甲话术检测
- **黑名单**: 支持限时/永久拉黑
- **Web后台**: BOT管理、知识库管理、记忆查看

## 技术栈

- **后端**: FastAPI + SQLite + SQLAlchemy
- **Bot**: discord.py
- **AI**: OpenAI 兼容 API
- **调度**: APScheduler
- **分词**: jieba

## 快速开始

### 1. 安装依赖

```bash
pip install -r requirements.txt
```

### 2. 配置环境变量

复制 `.env.example` 为 `.env` 并填写配置：

```bash
cp .env.example .env
```

配置项说明：

| 配置项              | 说明                                     |
| ------------------- | ---------------------------------------- |
| `DISCORD_BOT_TOKEN` | Discord Bot Token                        |
| `BACKEND_URL`       | 后端API地址 (默认 http://localhost:8000) |
| `LLM_BASE_URL`      | LLM API 地址                             |
| `LLM_API_KEY`       | LLM API Key                              |
| `LLM_MODEL`         | 模型名称 (如 gpt-4o-mini)                |
| `CONTEXT_LIMIT`     | 上下文消息条数 (默认 10)                 |
| `ADMIN_PASSWORD`    | Web管理后台密码                          |

### 3. 启动服务

**启动后端 API:**

```bash
python run_backend.py
```

后端将在 http://localhost:8000 启动

**启动 Discord Bot:**

```bash
python run_bot.py
```

### 4. 访问管理后台

打开浏览器访问 http://localhost:8000/admin

使用配置的 `ADMIN_PASSWORD` 登录

## 项目结构

```
BOT/
├── backend/                 # 后端 API
│   ├── main.py             # FastAPI 应用入口
│   ├── schemas.py          # Pydantic 模型
│   ├── routes/             # API 路由
│   │   ├── chat.py         # 聊天接口
│   │   ├── admin.py        # 管理接口
│   │   └── knowledge.py    # 知识库接口
│   └── services/           # 业务服务
│       ├── chat_service.py
│       ├── user_service.py
│       ├── memory_service.py
│       ├── knowledge_service.py
│       ├── blacklist_service.py
│       ├── channel_service.py
│       └── content_filter.py
├── bot/                    # Discord Bot
│   ├── main.py            # Bot 入口
│   └── client.py          # Bot 客户端和命令
├── database/              # 数据库
│   ├── database.py        # 数据库连接
│   └── models.py          # 数据模型
├── web/                   # Web 管理后台
│   └── templates/
│       └── admin.html     # 管理界面
├── config.py              # 配置管理
├── requirements.txt       # 依赖
├── run_backend.py         # 启动后端
├── run_bot.py            # 启动 Bot
└── README.md
```

## API 文档

启动后端后访问 http://localhost:8000/docs 查看完整 API 文档

## 定时任务

- **用户记忆总结**: 每天凌晨3点自动运行
- **过期黑名单清理**: 每30分钟运行一次

## 许可证

MIT License
