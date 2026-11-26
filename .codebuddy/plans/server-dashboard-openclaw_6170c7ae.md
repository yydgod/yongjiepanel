---
name: server-dashboard-openclaw
overview: 设计并搭建一个原子化卡片式服务器管理看板：Vue3 + FastAPI 全栈，每张服务卡片（Docker 容器 / systemd 进程）绑定专属 agent，支持 DeepSeek/Hunyuan/Qwen 多模型接入，AI 网关统一走 OpenClaw，并提供 AI 生成卡片能力。本轮交付架构方案 + 可运行 MVP 骨架。
design:
  architecture:
    framework: vue
  styleKeywords:
    - 深色科技控制台
    - 玻璃拟态
    - 极光渐变光晕
    - 状态呼吸动效
    - 等宽数值仪表
  fontSystem:
    fontFamily: Noto Sans SC
    heading:
      size: 22px
      weight: 600
    subheading:
      size: 15px
      weight: 500
    body:
      size: 13px
      weight: 400
  colorSystem:
    primary:
      - "#35E0C8"
      - "#7C6CFF"
      - "#3B82F6"
    background:
      - "#070B12"
      - "#0F1620"
      - "#161D28"
    text:
      - "#E8EEF6"
      - "#9AA9BE"
      - "#5F7085"
    functional:
      - "#2FBF71"
      - "#F5A524"
      - "#FF5C7A"
      - "#1E2937"
todos:
  - id: env-scaffold
    content: 安装 Python 3.11+ 与 Node 20+，搭建 backend/frontend 骨架及 Makefile、.env.example、docker-compose
    status: completed
  - id: backend-data-layer
    content: 实现 SQLAlchemy 模型、Pydantic Schema、Alembic 初始迁移、Fernet 加密与种子数据
    status: completed
    dependencies:
      - env-scaffold
  - id: collector-status
    content: 实现 Docker/systemd/端口采集器、5s 调度循环、内存状态仓库与不可用降级诊断
    status: completed
    dependencies:
      - backend-data-layer
  - id: ai-gateway
    content: 实现 AI Gateway 双通道（OpenClaw + OpenAI 兼容）、健康探测降级与供应商 CRUD/连通性测试接口
    status: completed
    dependencies:
      - backend-data-layer
  - id: card-agent-tools
    content: 实现卡片 CRUD、Agent 配置、工具注册表与对话编排（SSE 流式、确认令牌、审计）、AI 生成卡片接口
    status: completed
    dependencies:
      - collector-status
      - ai-gateway
  - id: frontend-board
    content: 实现看板网格、卡片状态与快捷操作、拖拽排序、卡片详情抽屉（指标曲线+日志）
    status: completed
    dependencies:
      - card-agent-tools
  - id: frontend-ai-pages
    content: 实现 Agent 对话面板、模型供应商管理页、AI 生成卡片三步向导与系统状态页
    status: completed
    dependencies:
      - frontend-board
  - id: verify-docs
    content: 端到端启动验证，用 [skill:playwright-cli] 截图核对界面，补齐 README 与 docs/architecture.md
    status: completed
    dependencies:
      - frontend-ai-pages
---

## 产品概述

一个面向单机服务器的原子化卡片管理看板：服务器上的每个容器、systemd 服务或端口服务都以一张独立卡片呈现，采用类 App 图标网格布局。每张卡片绑定一个专属 agent，可对话、可执行运维操作、可查看指标与日志。系统内置 AI 能力网关对接 OpenClaw，并支持自定义配置多家大模型（DeepSeek、腾讯混元、Qwen 等）。卡片本身也能由 AI 生成。

## 核心功能

- **应用面板（看板首页）**：卡片网格，按分组/搜索/状态筛选，拖拽排序，卡片实时显示状态灯、CPU/内存、端口、运行时长与最近事件；支持一键启停/重启（二次确认）。
- **卡片详情**：指标趋势曲线、日志尾部输出、快捷操作、Agent 对话区。
- **卡片专属 Agent**：每张卡片独立配置模型供应商、模型名、系统提示词、可用工具集、温度等；对话支持流式输出与工具调用过程可视化。
- **多模型接入**：供应商管理页可新增/编辑/测试 DeepSeek、混元、Qwen 及任意 OpenAI 兼容端点，API Key 加密保存且前端不回显明文，可设默认模型。
- **OpenClaw 网关**：所有 agent 推理统一经由网关路由；OpenClaw 不可用时自动降级直连供应商，并在界面标注当前通道。
- **AI 生成卡片**：用自然语言描述需求，AI 输出结构化卡片定义（类型、目标对象、展示配置、推荐 agent 提示词与工具），预览确认后落库；也支持对已有卡片做自然语言定制。
- **系统状态**：采集器异常（无 docker 权限、systemd 不可用）时卡片显示「不可用」并给出原因，不阻塞看板使用。
- **审计**：所有破坏性操作与工具调用留存审计记录，可在界面查看。

## 视觉要求

深色科技控制台风格：玻璃质感卡片、青绿到紫的渐变光晕、状态色呼吸动效、数值使用等宽字体，整体像一块可交互的运维驾驶舱；响应式适配桌面与平板。

## 技术栈选型

| 层 | 选型 | 说明 |
| --- | --- | --- |
| 前端 | Vue 3.5 + TypeScript + Vite + Element Plus + Pinia + Vue Router + ECharts + SortableJS | 遵循用户选择使用 Element Plus；ECharts 画指标曲线；SortableJS 做卡片拖拽排序 |
| 后端 | Python 3.11 + FastAPI + Pydantic v2 + SQLAlchemy 2.0（同步 Session）+ Alembic | 同步 Session 由 FastAPI 线程池承载，避免引入 aiosqlite 复杂度 |
| 数据库 | SQLite（WAL 模式），SQLAlchemy 屏蔽差异 | MVP 零外部依赖；换 PostgreSQL 仅改 `DATABASE_URL` |
| 采集 | docker SDK for Python、psutil、`systemctl`（argv 调用） | 只读采集，全部包在超时与异常降级中 |
| AI | httpx（异步）+ 自建 AI Gateway 抽象 | OpenClaw 通道 + OpenAI 兼容直连通道 |
| 安全 | `cryptography` Fernet 加密 API Key、可选 Bearer 鉴权 | 密钥仅从环境变量注入 |
| 工程 | pytest + ruff、Docker Compose、Makefile、`.env.example` | 一键启动与自检 |


**环境约束（已实测）**：当前为空的 `/data/workspace`；系统 Python 为 3.6.8 不可用，Node 未安装。第一步必须先安装 Python 3.11+ 与 Node 20+；若 Node 安装失败则启用前端 CDN 兜底方案（见实施注意事项）。

## 实现思路

**总体策略**：配置与状态彻底分离。数据库只存「配置类」数据（主机、卡片、Agent、供应商、审计、会话）；运行时状态（CPU/内存/日志/端口/健康度）由后台采集循环写入进程内状态仓库，API 直接读内存。这样采集频率再高也不会造成数据库写放大，是性能与寿命的关键决策。

**1. 卡片类型注册表（可扩展核心）**
每种卡片类型声明一份 `CardTypeSpec`：类型标识、显示名、目标引用字段的 JSON Schema、可采集指标字段、可用工具集、图标。内置 `container` / `systemd` / `port` / `custom` 四种；新增类型只需注册 spec，前后端均从 `/api/card-types` 动态渲染表单，核心代码零改动。

**2. 采集器统一契约 + 优雅降级**
`BaseCollector` 提供 `available()` / `collect(targets) -> list[Snapshot]`。`DockerCollector` 使用 docker SDK；`SystemdCollector` 用 `systemctl show <unit> --value -p ...`（argv 列表、3s 超时）；`PortCollector` 用 psutil 监听端口映射到 PID 及进程名。任何采集器初始化失败只标记 `available=False` 并记录一条诊断原因，接口层返回 `status=unavailable`，前端卡片降级展示，绝不 500。

**3. AI 网关双通道 + 自动降级**
`AIGateway.chat()` 为唯一出口。路由策略：Agent 指定 `gateway=openclaw` 且健康探测（30s 缓存）通过则走 `OpenClawClient`（OpenAI 兼容 `/v1/chat/completions`，透传 session/agent 元数据，另留 channel 模式适配位）；否则降级 `OpenAICompatClient` 直连供应商。DeepSeek(`api.deepseek.com/v1`)、Qwen(百炼 compatible-mode)、混元(`api.hunyuan.cloud.tencent.com/v1`) 三者协议同源，用「通用适配器 + 供应商默认参数表」实现，避免为每家写一个类。降级事件写日志与审计，并通过响应字段 `channel` 回传前端展示。

**4. Agent 工具编排（function calling 闭环）**
`ToolRegistry` 注册工具：`get_status`、`get_metrics`、`tail_logs`、`list_ports`（只读，自动执行）；`restart_container`、`stop_container`、`start_container`、`restart_unit`（破坏性，需确认令牌）。对话循环：模型返回 `tool_calls` → 校验工具是否在 Agent 白名单 → 只读直接执行、破坏性返回 `pending_confirmation` + 一次性 `confirm_token`（写库、5 分钟过期）→ 前端弹确认 → `POST /api/chat/confirm` 执行 → 结果回填模型继续，最多 4 轮，防死循环。命令执行一律 argv 白名单，禁止 shell 拼接。

**5. AI 生成卡片**
`card_generator` 使用结构化输出：直连通道用 `response_format=json_object`；OpenClaw 通道用提示词约束 JSON + Pydantic 校验，失败自动修复重试一次。产出 `CardDraft`（类型、target_ref、分组、展示配置、推荐 system_prompt、推荐工具集、图标），前端三步向导（描述 → 预览编辑 → 确认落库）后调用常规创建接口，复用同一套校验，避免第二条写入路径。自定义卡片采用「预设布局 + 字段映射」的声明式配置，不做任何代码求值。

## 性能与可靠性要点

- 采集循环 `asyncio` 任务，阻塞调用（docker/psutil/subprocess）走 `asyncio.to_thread`，默认 5s 周期、单次整体 8s 超时；只采卡片引用的目标，不扫全量容器。
- 指标历史保存在每卡 `deque(maxlen=180)`（约 15 分钟），不落库；日志仅取尾部 200 行按需拉取，不进轮询。
- `docker stats(stream=False)` 是主要开销点（每容器约 1~1.5s），N>30 时改为按需采样 + 状态变更走 `docker events`；此优化在文档中标注为扩展路径。
- 列表接口一次返回「卡片配置 + 最新快照」，避免前端 N+1 请求。
- 对话走 SSE 逐字下发；工具调用与确认令牌均有超时兜底。
- 所有外部调用（docker/systemctl/LLM）统一 `try/except + 超时 + 结构化日志`，错误分类为 `unavailable/denied/timeout/upstream_error` 上报前端。

## 安全设计

- API Key 用 Fernet 加密入库，密钥来自 `SECRET_KEY` 环境变量；序列化层对 key 只返回 `sk-****abcd` 掩码，不提供任何回显接口。
- 破坏性工具 = 白名单校验 + 一次性确认令牌 + 审计记录（操作者、目标、参数、结果、时间）。
- 默认仅监听 `127.0.0.1`；提供可选 `ADMIN_TOKEN` Bearer 保护，CORS 白名单化。
- docker socket 只读挂载（`/var/run/docker.sock:ro`），后端容器不做特权运行。

## 系统架构

```mermaid
graph TD
  UI[Vue3 看板 UI<br/>网格/详情/供应商/生成向导] -->|REST + SSE| API[FastAPI 路由层]
  API --> SVC[领域服务层<br/>Card / Agent / Provider / Chat / Audit]
  SVC --> DB[(SQLite<br/>配置·审计·会话)]
  SVC --> STORE[运行时状态仓库<br/>内存快照 + 指标环形缓冲]
  SVC --> GW[AI Gateway<br/>路由·降级·流式]
  GW --> OC[OpenClaw 网关]
  GW --> OAI[OpenAI 兼容通道<br/>DeepSeek / 混元 / Qwen]
  SVC --> TOOLS[Tool Registry<br/>只读 + 破坏性(确认令牌)]
  TOOLS --> COLL
  LOOP[采集调度器 5s] --> COLL[Docker / Systemd / Port Collector]
  COLL --> STORE
  COLL -->|不可用诊断| STORE
```

## 数据模型（要点）

- `hosts`：id、name、kind(local|agent)、status、last_seen —— 单机期只有一条 local 记录，为多机预留。
- `service_cards`：id、host_id、title、card_type、target_ref、group_name、icon、sort_order、display_config(JSON)、status_snapshot(JSON，非权威缓存)、enabled。
- `agents`：id、card_id(唯一)、name、provider_id、model、system_prompt、tools(JSON 白名单)、temperature、max_tokens、gateway(openclaw|direct)。
- `providers`：id、name、kind(deepseek|hunyuan|qwen|custom)、base_url、default_model、models(JSON)、api_key_encrypted、extra(JSON)、is_default、enabled。
- `chat_sessions` / `chat_messages`：会话与消息（含 role、content、tool_calls、tokens、channel）。
- `pending_actions`：确认令牌、工具名、参数、过期时间、状态。
- `audit_logs`：actor、action、target_type、target_id、params、result、error、created_at。

## 目录结构

```
/data/workspace/
├── docs/architecture.md              # [NEW] 架构文档：分层、数据模型 ER、采集/对话/生成卡片时序、扩展点（新增卡片类型/工具/供应商的接入步骤）、安全基线
├── README.md                         # [NEW] 快速启动（安装 3.11/Node20、venv、npm i、make dev）、默认端口、常见故障（docker socket 权限、systemd 不可用）
├── Makefile                          # [NEW] dev / api / web / test / lint / seed 目标
├── docker-compose.yml                # [NEW] backend + frontend(nginx)，挂载 docker.sock 只读，env 注入
├── .env.example                      # [NEW] DATABASE_URL、SECRET_KEY、ADMIN_TOKEN、OPENCLAW_BASE_URL/TOKEN/MODE、采集周期
├── backend/
│   ├── pyproject.toml                # [NEW] 依赖与 ruff/pytest 配置
│   ├── alembic.ini + alembic/versions/0001_init.py   # [NEW] 初始迁移（建全部表）
│   ├── app/main.py                   # [NEW] 应用装配：lifespan 启动采集循环、注册路由、CORS、统一异常处理器
│   ├── app/core/{config.py,logging.py,security.py,errors.py}   # [NEW] pydantic-settings 配置；JSON 结构化日志（脱敏）；Fernet 加解密；AppError 错误码体系
│   ├── app/db/{session.py,base.py,init_db.py}                  # [NEW] engine/Session 依赖、Base、建表与种子入口
│   ├── app/models/*.py               # [NEW] hosts/service_cards/agents/providers/chat/pending_actions/audit
│   ├── app/schemas/*.py              # [NEW] CardCreate/CardDraft/AgentConfig/ProviderIn(掩码输出)/ChatRequest/ToolCallOut 等
│   ├── app/api/routes/{cards,card_types,hosts,agents,providers,chat,generate,audit,health}.py  # [NEW] REST + SSE；chat 含 /stream 与 /confirm
│   ├── app/services/{card_service,agent_service,provider_service,chat_service,card_generator,audit_service,status_service}.py  # [NEW] 领域逻辑，路由层不写业务
│   ├── app/collectors/{base,docker_collector,systemd_collector,port_collector,registry,scheduler}.py  # [NEW] 采集契约、四类实现、调度循环与不可用诊断
│   ├── app/ai/{gateway,openclaw_client,openai_compat,providers.py,router_policy.py}  # [NEW] 双通道客户端、供应商默认参数表、健康探测与降级策略
│   ├── app/tools/{registry,status_tools,container_tools,systemd_tools}.py  # [NEW] 工具定义（名字/描述/JSON Schema/风险级别/执行器）与 argv 白名单
│   ├── app/seeds.py                  # [NEW] 示例：3 张容器卡片（含当前可见容器）、1 张 systemd 卡片、1 个 DeepSeek 供应商（无 key 时标记未配置）
│   └── tests/{test_cards,test_providers,test_chat_flow,test_collectors}.py  # [NEW] 服务层单测 + TestClient 集成测试，外部依赖全部 mock
├── frontend/
│   ├── package.json / vite.config.ts / tsconfig.json   # [NEW] Vue3+TS；dev proxy /api → 127.0.0.1:8000
│   ├── src/main.ts / App.vue                            # [NEW] 装配 Element Plus 深色主题变量、路由、Pinia
│   ├── src/api/{client.ts,cards.ts,providers.ts,chat.ts} # [NEW] fetch 封装、错误码映射、SSE 解析
│   ├── src/stores/{board.ts,providers.ts,chat.ts}        # [NEW] 看板数据与 5s 轮询（页面隐藏暂停）、供应商、会话
│   ├── src/views/{BoardView.vue,ProvidersView.vue,SystemView.vue}  # [NEW] 主看板；供应商管理；系统/采集器健康与审计
│   ├── src/components/board/{BoardToolbar.vue,ServiceCard.vue,CardGrid.vue}  # [NEW] 筛选/搜索/视图切换；状态灯呼吸、指标微条、hover 快捷操作；SortableJS 拖拽持久化
│   ├── src/components/card/{CardDetailDrawer.vue,MetricsChart.vue,LogPanel.vue,ActionBar.vue}  # [NEW] 详情抽屉、ECharts 曲线、日志尾部、带二次确认的操作条
│   ├── src/components/agent/{AgentChatPanel.vue,ToolCallTimeline.vue,AgentConfigPanel.vue}  # [NEW] 流式对话、工具调用与确认卡片、Agent 配置表单（模型/提示词/工具勾选）
│   ├── src/components/providers/ProviderForm.vue        # [NEW] 新增/编辑（key 掩码输入）、连通性测试按钮
│   ├── src/components/ai/CardGeneratorWizard.vue        # [NEW] 三步向导：描述 → 卡片与 Agent 预览编辑 → 确认创建
│   └── src/styles/{tokens.scss,global.scss}             # [NEW] 设计令牌（深色背景、渐变、玻璃态、状态色）与全局样式
└── scripts/dev.sh                    # [NEW] 并行启动 uvicorn 与 vite 并汇总日志
```

## 关键接口契约

```python
# app/collectors/base.py —— 采集器扩展点（新增服务类型只需实现该协议）
class BaseCollector(Protocol):
    kind: str                          # "container" | "systemd" | "port" | "custom"
    def available(self) -> tuple[bool, str | None]: ...   # (是否可用, 不可用原因)
    async def collect(self, targets: list[str]) -> list[dict]: ...  # 目标 -> 统一快照
```

```python
# app/ai/gateway.py —— 唯一 AI 出口，屏蔽 OpenClaw 与直连差异
class AIGateway(Protocol):
    async def chat(self, req: "ChatRequest") -> "ChatResult": ...
    async def stream(self, req: "ChatRequest") -> AsyncIterator["ChatDelta"]: ...
    async def structured(self, prompt: str, schema: type) -> dict: ...   # 供 AI 生成卡片使用
# ChatResult 需包含 content / tool_calls / usage / channel("openclaw"|"direct"|"fallback")
```

## 设计风格

深色科技控制台（Obsidian Control Room）：以近黑蓝为底，卡片为半透明玻璃面板，叠加极细内发光描边；状态以青绿（健康）、琥珀（告警）、品红（离线）三色呼吸光表达；数值统一等宽字体、字距收紧，配合细网格背景与缓慢漂移的极光渐变，营造"运维驾驶舱"质感。交互强调即时反馈：卡片 hover 上浮 4px 并强化光晕，操作按钮按风险分级着色，破坏性操作需在抽屉内二次确认。

## 页面规划（4 个核心页面）

1. **看板首页（BoardView）**：① 顶部导航条（Logo、全局搜索、采集器健康徽标、深/浅切换、新增卡片按钮）；② 状态概览条（在线/告警/离线计数、平均 CPU/内存、OpenClaw 通道状态胶囊）；③ 分组筛选 Chip 行 + 排序视图切换（网格/紧凑）；④ 卡片网格（每卡：图标、名称、状态灯、CPU/内存双色微条、端口标签、运行时长、hover 浮起快捷操作）；⑤ 空/异常态占位卡（悬浮说明采集器不可用原因）。
2. **卡片详情抽屉（CardDetailDrawer）**：① 抽屉头部（大图标、状态、目标对象、操作条）；② 指标区（CPU/内存双线 ECharts 曲线 + 近 1 分钟数值卡）；③ 日志区（等宽滚动面板、关键字高亮、跟随尾部）；④ Agent 对话区（流式气泡、工具调用时间线、确认令牌卡片、输入框快捷指令）；⑤ 配置标签页（模型/提示词/工具勾选）。
3. **供应商与模型（ProvidersView）**：① 顶部说明与「新增供应商」按钮；② 供应商卡片列表（厂商图标、默认模型、掩码 Key、启用开关、测试连通性按钮 + 结果提示）；③ 右侧抽屉表单（base_url、模型列表、超时/温度默认值）；④ 底部通道说明区，展示 OpenClaw 网关地址与最近降级记录。
4. **AI 生成卡片向导（CardGeneratorWizard，弹窗式）**：① 步骤条（描述 → 预览 → 确认）；② 描述输入区与生成中骨架动画；③ 预览区左「卡片外观实时预览」右「Agent 提示词与工具勾选可编辑」；④ 底部操作（重新生成 / 修改描述 / 创建并加入看板）。

## 动效与响应式

卡片入场 stagger 淡入；状态灯 2.4s 呼吸循环；对话 token 逐字浮现；抽屉右侧滑入 + 背景模糊；指标刷新数值做数字滚动补间。桌面 3-5 列自适应网格，≤1280px 降为 3 列，≤1024px 侧栏折叠为图标栏，抽屉改为全宽面板；所有交互目标不小于 40px。

## Skill

- **playwright-cli**
- Purpose: 在 MVP 启动后自动打开看板页面，验证卡片网格渲染、抽屉交互与生成向导可达，并截图存档
- Expected outcome: 产出首页与卡片详情截图，确认无控制台报错、无空白页