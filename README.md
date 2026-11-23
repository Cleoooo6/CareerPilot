# CareerPilot AI · 智绘职涯

面向大学生、应届毕业生、职场人士与转行者的 AI 职业发展平台。

CareerPilot AI 以「人」而不是「岗位」为核心：通过动态职业画像、就业市场洞察与 AI Agent，帮助用户探索职业方向、分析能力差距、制定并持续调整成长路线。它不是招聘平台、投递平台、课程推荐站或普通聊天机器人。

## 当前状态

当前版本是一个可本地运行的 MVP，已完成以下核心闭环：

- **AI Career Advisor**：基于个人画像、市场统计数据与路线信息给出职业建议；支持 SSE 流式回复、取消生成与工具调用。
- **Profile 职业画像**：支持简历上传（DOCX / PDF）与解析、画像编辑、用户确认后落库、画像版本历史。
- **Market Radar 市场洞察**：岗位概览、技能需求、分布与趋势、岗位详情；支持合成演示数据导入。
- **My Roadmap 成长路线**：基于画像与目标岗位生成路线草稿、技能差距分析、确认 / 放弃、任务状态与成果记录。

V1 规划的五大核心页面中，**Dashboard（发展驾驶舱）仍在规划中**；Opportunity Hub 已移出 V1 核心范围，实践机会将作为路线资源呈现。

### 未实现 / 当前限制

以下能力尚未实现或尚未完成真实验收，请勿将其视为已具备：

- **无正式用户认证**：`X-User-Id` 仅为开发态数据隔离骨架，不是认证机制，请求方可自行设置该请求头。仅限本地或受控环境演示，不要直接暴露到公网。
- **市场数据为合成演示数据**：真实招聘数据源尚未接入或获得授权，页面与 API 中的合成数据均已标注，相关统计不代表真实市场结论。
- **真实 LLM 未完成验收**：默认 `LLM_MODE=mock`，不会发起真实模型请求；真实模式下结构化输出的稳定性与完整链路尚未完成验收。
- **实时互联网搜索未实现**：Advisor 暂不具备按需实时检索能力。
- **长期记忆与动态成长管理**：尚未实现。
- **Dashboard**：尚未实现。

## 技术栈

| 层 | 技术 |
|---|---|
| 后端 | Python 3.12、FastAPI、Pydantic、LangGraph（Single-Agent + Tool Calling）、SSE |
| 数据 | PostgreSQL 16、SQLAlchemy、Alembic（迁移 0001–0006）、psycopg |
| 前端 | Vue 3、TypeScript、Vite、Vue Router、Vitest、Playwright |
| 部署 | Docker Compose、Nginx（SSE 反向代理）、PostgreSQL 容器 |
| 可观测 | 请求 ID、结构化日志、敏感信息脱敏、Agent Trace |

## 快速开始

### 1. 配置环境

```bash
cp deploy/.env.example .env
# 编辑 .env，设置独立的 POSTGRES_PASSWORD；LLM_API_KEY 仅在 real 模式需要
```

`.env` 已在 `.gitignore` 中，不会被提交。默认 `LLM_MODE=mock`，不会调用真实模型。

### 2. 启动容器

```bash
docker compose -f deploy/docker-compose.yml --env-file .env up -d --build
```

访问：

- 前端：http://127.0.0.1:5180
- API：http://127.0.0.1:8100
- 健康检查：http://127.0.0.1:8100/health
- 就绪检查：http://127.0.0.1:8100/ready
- OpenAPI：http://127.0.0.1:8100/docs

### 3. 本地开发

后端（Python 3.12）：

```bash
cd backend
uv venv --python 3.12 .venv
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

## 目录结构

```text
backend/
  app/agents/      LangGraph 图、节点、上下文与流式事件
  app/api/         FastAPI 路由（chat/profile/market/roadmap/meta/health）
  app/services/    业务服务（画像、简历、市场、路线、Chat）
  app/db/          连接池与仓储
  app/schemas/     Pydantic 模型
  app/tools/       Agent 工具注册表与市场、路线工具
  migrations/      Alembic 迁移（0001–0006）
  tests/           单元测试与 PostgreSQL 集成测试
frontend/
  src/pages/       Chat / Profile / Market / Roadmap 页面
  src/components/  通用组件
  src/api/         后端 API 客户端
  src/stores/      Chat 状态
  e2e/             Playwright 端到端测试与合成夹具
deploy/
  docker-compose.yml
  nginx/default.conf
  postgres/init/
```

## 测试

后端：

```bash
cd backend
.venv/Scripts/python.exe -m pytest tests/unit
.venv/Scripts/python.exe -m pytest tests/integration   # 需要 PostgreSQL
.venv/Scripts/python.exe -m ruff check app tests
```

前端：

```bash
cd frontend
npm run typecheck
npm run test:unit
npm run test:e2e        # 需要完整服务栈运行
```

集成测试使用独立测试库 `careerpilot_test`，不得对开发库执行破坏性操作。

## 数据与安全说明

- 仓库中的市场岗位数据为**合成演示数据**，公司名以「合成·」标注，仅用于功能演示与测试。
- 简历与画像相关测试使用虚构人物与虚构单位，不含真实个人信息。
- `.env`、本地数据库、日志、构建产物、测试产物与本地验收报告均不纳入版本控制。
- 本项目当前**没有正式认证与多租户隔离**，仅适合本地或受控环境演示。

## 许可证

暂未指定。