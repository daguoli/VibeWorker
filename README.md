# VibeWorker

<p align="center">
  <strong>🧠 Your Local AI Digital Worker with Real Memory</strong>
</p>

---

VibeWorker 是一个轻量级且高度透明的 AI 数字员工 Agent 系统。它运行在本地，拥有"真实记忆"，可以帮助你处理各类任务——信息检索、数据处理、代码执行、文件管理等。

## ✨ 核心特性

- **文件即记忆 (File-first Memory)** — 所有记忆以 Markdown/JSON 文件形式存储，人类可读
- **技能即插件 (Skills as Plugins)** — 通过文件夹结构管理能力，拖入即用
- **透明可控** — 所有 Prompt 拼接、工具调用、记忆读写完全透明

## 🏗️ 技术栈

| 层级 | 技术 |
|------|------|
| 后端框架 | FastAPI (Python 3.10+) |
| Agent 引擎 | LangChain 1.x |
| RAG 引擎 | LlamaIndex |
| 前端框架 | Next.js 14+ (App Router) |
| UI 组件 | Shadcn/UI + Tailwind CSS |
| 代码编辑器 | Monaco Editor |

## 🚀 快速开始

### 后端启动

```bash
cd backend
pip install -r requirements.txt
python app.py
```

后端将在 `http://localhost:8088` 启动。

### 前端启动

```bash
cd frontend
npm install
npm run dev
```

前端将在 `http://localhost:3000` 启动。

## 📁 项目结构

```
vibeworker/
├── backend/                # FastAPI + LangChain/LangGraph
│   ├── app.py              # 入口文件
│   ├── config.py           # 配置管理
│   ├── memory/             # 记忆存储
│   ├── sessions/           # 会话记录
│   ├── skills/             # Agent Skills
│   ├── workspace/          # System Prompts
│   ├── tools/              # Core Tools
│   ├── graph/              # Agent 编排
│   ├── knowledge/          # RAG 知识库
│   ├── storage/            # 索引持久化
│   └── requirements.txt
├── frontend/               # Next.js 14+
│   ├── src/
│   │   ├── app/
│   │   ├── components/
│   │   └── lib/
│   └── package.json
└── README.md
```

## 📜 License

MIT
