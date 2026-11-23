# CareerPilot AI

面向大学生、应届毕业生、职场人士与转行者的职业发展智能体平台。

当前为**阶段一：独立工程初始化与最小可运行闭环**。已具备 FastAPI、PostgreSQL/Alembic、LangGraph 单 Agent 工作流、统一 LLM Client（Mock 模式）、SSE、Trace、Vue 3 Chat 页面与 Docker Compose 部署基础。

## 快速开始

### 1. 配置环境变量

```bash
cp deploy/.env.example .env
# 编辑 .env：设置独立数据库密码；LLM_API_KEY 由你自行填写
```

阶段一默认 `LLM_MODE=mock`，不会调用真实模型。未经明确授权不要切换为 `real`。

### 2. 启动容器

```bash
docker compose -f deploy/docker-compose.yml --env-file .env up -d --build
```

访问：

- 前端：http://127.0.0.1:5180
- API：http://127.0.0.1:8100
- 健康检查：http://127.0.0.1:8100/health
- 就绪检查：http://127.0.0.1:8100/ready

### 3. 本地开发

后端（Python 3.12）：

```bash
cd backend
uv venv --python 3.12.13 .venv
uv pip install --python .venv/Scripts/python.exe -e ".[dev]"
.venv/Scripts/python.exe -m alembic upgrade head
.venv/Scripts/python.exe -m uvicorn app.main:app --port 8100
```

前端（Node 22）：

```bash
cd frontend
npm install
npm run dev
```

## 项目边界

本阶段只实现工程基础设施与最小 Chat 闭环，不实现职业画像、市场数据、机会推荐、技能差距、成长规划等业务功能，不实现 Multi-Agent，不实现完整认证系统。

## 文档

- `docs/PROJECT_CONTEXT.md`
- `docs/DEVELOPMENT_STATUS.md`
- `docs/TECHNICAL_ARCHITECTURE.md`
- `docs/DECISIONS_AND_LOG.md`

## 测试

```bash
cd backend
.venv/Scripts/python.exe -m pytest
.venv/Scripts/python.exe -m ruff check app tests

cd frontend
npm run typecheck
npm run build
npm run test:unit
```

数据库集成测试使用独立测试库 `careerpilot_test`，不得对开发库执行破坏性操作。