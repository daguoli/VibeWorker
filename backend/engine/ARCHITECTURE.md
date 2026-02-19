# Graph Agent 引擎架构文档

> 面向二次开发者的完整技术文档。基于 `backend/engine/` 目录下重构后的引擎代码。

---

## 目录

1. [架构总览](#1-架构总览)
2. [请求完整生命周期](#2-请求完整生命周期)
3. [模块逐一解析](#3-模块逐一解析)
4. [两阶段执行模型详解](#4-两阶段执行模型详解)
5. [事件系统](#5-事件系统)
6. [二次开发指南](#6-二次开发指南)
7. [调试指南](#7-调试指南)
8. [配置参考](#8-配置参考)

---

## 1. 架构总览

### 1.1 目录结构

```
backend/engine/
├── __init__.py            # 公共 API 导出 (run_agent, RunContext, get_llm, serialize_sse)
├── context.py             # RunContext — 每请求上下文，替代全局变量
├── events.py              # 事件类型常量 + 构建函数 + SSE 序列化
├── llm_factory.py         # LLM 实例创建与指纹缓存
├── messages.py            # 会话历史 → LangChain Message 格式转换
├── stream_adapter.py      # LangGraph astream_events → 标准化事件流
├── runner.py              # 顶层编排器 (DirectMode → PlanMode + Middleware 管线)
├── middleware/
│   ├── __init__.py        # 导出 Middleware, DebugMiddleware, DebugLevel
│   ├── base.py            # Middleware Protocol 定义（3 个方法）
│   └── debug.py           # DebugMiddleware 实现 + InMemoryCollector
└── modes/
    ├── direct.py          # Phase 1 — DirectMode (ReAct agent)
    └── plan.py            # Phase 2 — PlanMode (步骤循环 + Replanner)
```

### 1.2 核心设计理念

| 理念 | 说明 |
|------|------|
| **统一事件流** | 所有 Agent 输出（Token、工具调用、LLM 调试信息）统一为 `dict` 事件，由 `stream_adapter.py` 适配 LangGraph 原始事件 |
| **Middleware 管线** | 事件流经过可插拔的 Middleware 链（当前为 DebugMiddleware），支持审计、过滤、变换 |
| **请求隔离** | `RunContext` dataclass 封装每次请求的所有状态（session、plan、side-channel queues），彻底消除全局变量 |
| **两阶段模型** | Phase 1 (DirectMode) 处理所有请求；当 LLM 调用 `plan_create` 时自动切换到 Phase 2 (PlanMode) 逐步执行 |

### 1.3 技术栈依赖

| 依赖 | 版本 | 用途 |
|------|------|------|
| `langgraph` | `langgraph.prebuilt.create_react_agent` | 构建 ReAct Agent（Phase 1 + Phase 2 子 Agent） |
| `langchain-core` | 1.x | `HumanMessage`, `AIMessage`, `ToolMessage`, `tool` 装饰器 |
| `langchain-openai` | 1.x | `ChatOpenAI` 实例化 |
| `pydantic` | v2 | `ReplanDecision` 结构化输出模型 |
| `FastAPI` | — | SSE `StreamingResponse` 输出 |

---

## 2. 请求完整生命周期

### 2.1 数据流图

```
                              POST /api/chat (JSON body)
                                       │
                                       ▼
                            ┌─ app.py:chat() ─────────────────┐
                            │  L164: 验证 + 保存用户消息        │
                            │  L173: set_session_id()          │
                            │  L184: StreamingResponse(...)    │
                            └──────────┬──────────────────────┘
                                       │
                                       ▼
                      ┌─ app.py:_stream_agent_response() ─────┐
                      │  L236: 创建 RunContext                 │
                      │  L241: set_run_context(ctx)            │
                      │  L254: 创建 DebugMiddleware            │
                      │  L262: run_agent(msg, history, ctx,    │
                      │            middlewares=[debug_mw])     │
                      └──────────┬────────────────────────────┘
                                 │
                                 ▼
                  ┌─ runner.py:run_agent() ────────────────────┐
                  │  L37: mw.on_run_start(ctx) for each mw    │
                  │  L41-46: 选择 cached/uncached 路径          │
                  └──────────┬─────────────────────────────────┘
                             │
                             ▼
                  ┌─ runner.py:_run_uncached() ────────────────┐
                  │                                            │
                  │  ┌── Phase 1 ──────────────────────────┐   │
                  │  │ L92: DirectMode().execute(ctx)       │   │
                  │  │  → direct.py L27-37: 创建 ReAct Agent│   │
                  │  │  → stream_adapter.py: 事件流         │   │
                  │  │  → 检测 plan_create → break          │   │
                  │  └──────────────┬───────────────────────┘   │
                  │                 │                            │
                  │      ctx.plan_data is not None?             │
                  │          No ──→ yield build_done()          │
                  │          Yes ──↓                             │
                  │  ┌── Approval Gate ────────────────────┐    │
                  │  │ L99: plan_require_approval?          │    │
                  │  │   Yes → emit approval_request        │    │
                  │  │       → wait approval_event          │    │
                  │  │   No  → skip                         │    │
                  │  └──────────────┬───────────────────────┘    │
                  │                 │                             │
                  │  ┌── Phase 2 ──────────────────────────┐    │
                  │  │ L122: PlanMode(plan, msgs).execute() │    │
                  │  │  → plan.py: 步骤循环 + Replanner     │    │
                  │  └──────────────────────────────────────┘    │
                  └──────────┬──────────────────────────────────┘
                             │
                    ┌── runner.py:_pipe() ──┐
                    │  L131: 每个事件依次经过   │
                    │  middleware.on_event()  │
                    │  可被变换或抑制          │
                    └────────┬──────────────┘
                             │
                             ▼
                  ┌─ app.py:_stream_agent_response() ─────────┐
                  │  L266: drain plan_queue / approval_queue   │
                  │  L274-308: 累积 response + tool_calls      │
                  │  L310: yield serialize_sse(event)           │
                  │  L312-328: done → 持久化 session            │
                  └──────────┬─────────────────────────────────┘
                             │
                             ▼
                      SSE: data: {"type":"token","content":"..."}
                      SSE: data: {"type":"done"}
```

### 2.2 关键函数调用链

```
app.py:chat()                                         # L164
  └→ app.py:_stream_agent_response()                  # L233
       ├→ RunContext(session_id, debug, event_loop)    # L236
       ├→ set_run_context(ctx)                         # L241 (session_context.py:L15)
       ├→ DebugMiddleware(level)                       # L255
       └→ runner.py:run_agent()                        # L23
            ├→ mw.on_run_start()                       # L38
            └→ _run_uncached()                         # L86
                 ├→ DirectMode().execute(ctx)           # L93 → modes/direct.py:L26
                 │    ├→ get_llm()                      # llm_factory.py:L25
                 │    ├→ get_all_tools()                # tools/__init__.py:L62
                 │    ├→ build_system_prompt()           # prompt_builder.py
                 │    ├→ create_react_agent()            # langgraph.prebuilt
                 │    ├→ convert_history()               # messages.py:L14
                 │    └→ stream_agent_events()           # stream_adapter.py:L38
                 │         └→ agent.astream_events()     # LangGraph v2 事件流
                 │
                 └→ [if ctx.plan_data] PlanMode().execute(ctx)  # L123 → modes/plan.py:L40
                      ├→ _build_executor_prompt()       # plan.py:L126
                      ├→ create_react_agent() (子 Agent) # plan.py:L64
                      ├→ stream_agent_events()           # 每步独立事件流
                      └→ _evaluate_replan()              # plan.py:L145
```

---

## 3. 模块逐一解析

### 3.1 `context.py` — RunContext

**职责：** 每请求上下文对象，封装会话状态和事件侧通道，替代 6 个全局变量。

**关键 API：**

```python
@dataclass
class RunContext:
    session_id: str                          # 会话标识
    debug: bool = False                      # 是否开启调试
    stream: bool = True                      # 是否流式输出

    message: str = ""                        # 当前用户消息（runner 设置）
    session_history: list = field(...)       # 会话历史（runner 设置）

    plan_data: Optional[dict] = None         # Plan 数据（plan_create 设置）
    plan_queue: asyncio.Queue = field(...)   # Plan 事件侧通道
    approval_queue: asyncio.Queue = field(.) # 审批事件侧通道
    event_loop: Optional[AbstractEventLoop]  # 主事件循环引用

    def emit_plan_event(event: dict) -> None
        # 线程安全地发送 plan 事件到 SSE 流
        # 使用 call_soon_threadsafe 跨线程投递
```

**与其他模块的关系：**
- **imported by:** `runner.py`, `modes/direct.py`, `modes/plan.py`, `middleware/base.py`, `middleware/debug.py`, `app.py`, `session_context.py`, `tools/plan_tool.py`
- **imports:** `asyncio`, `dataclasses`

**核心逻辑：** `emit_plan_event()` 通过 `event_loop.call_soon_threadsafe()` 实现线程安全投递，因为 LangGraph 的工具执行可能在线程池中运行。

### 3.2 `events.py` — 事件类型 + 构建函数

**职责：** 定义所有 SSE 事件类型常量和构建函数，是事件系统的"Schema 层"。

**关键 API：**

```python
# 事件类型常量
TOKEN = "token"
TOOL_START = "tool_start"
TOOL_END = "tool_end"
LLM_START = "llm_start"
LLM_END = "llm_end"
DONE = "done"
ERROR = "error"
PLAN_CREATED = "plan_created"
PLAN_UPDATED = "plan_updated"
PLAN_REVISED = "plan_revised"
PLAN_APPROVAL_REQUEST = "plan_approval_request"

# 构建函数
build_token(content: str) -> dict
build_tool_start(tool_name: str, tool_input, motivation: str = None) -> dict
build_tool_end(tool_name: str, output: str, cached: bool, duration_ms: int = None) -> dict
build_llm_start(call_id: str, node: str, model: str, input_text: str, motivation: str) -> dict
build_llm_end(call_id: str, node: str, model: str, duration_ms: int, tokens: dict, ...) -> dict
build_done() -> dict
build_error(message: str) -> dict

# LangGraph 原始事件适配
build_tool_start_from_raw(event: dict) -> dict
build_tool_end_from_raw(event: dict, duration_ms: Optional[int] = None) -> dict
build_llm_end_from_raw(event: dict, tracked: dict) -> dict

# SSE 序列化
serialize_sse(event: dict) -> str   # → "data: {JSON}\n\n"
```

**与其他模块的关系：**
- **imported by:** `__init__.py`, `runner.py`, `stream_adapter.py`, `modes/direct.py`, `modes/plan.py`, `app.py`
- **imports:** `json`, `time`, `model_pool.resolve_model`（延迟导入）

**核心逻辑：** `TOOL_MOTIVATIONS` 字典为每个内置工具提供中文动机描述。`build_tool_end_from_raw()` 自动检测 `[CACHE_HIT]` 前缀标记缓存命中。

### 3.3 `llm_factory.py` — LLM 创建 + 指纹缓存

**职责：** 创建 `ChatOpenAI` 实例并基于配置指纹缓存，避免重复实例化。

**关键 API：**

```python
def get_llm(streaming: bool = True, scenario: str = "llm") -> ChatOpenAI
    # 根据配置指纹复用 LLM 实例
    # 指纹 = SHA256(api_key|api_base|model|temperature|max_tokens)[:16]
    # 缓存键 = "{fingerprint}_{streaming}"

def create_llm(streaming: bool = True) -> ChatOpenAI
    # Legacy 别名，等同于 get_llm(streaming=streaming)

def invalidate_llm_cache() -> None
    # 清空所有缓存实例（配置变更后调用）
```

**与其他模块的关系：**
- **imported by:** `__init__.py`, `modes/direct.py`, `modes/plan.py`, `app.py`
- **imports:** `config.settings`, `model_pool.resolve_model`（延迟导入）

**核心逻辑：** `_config_fingerprint()` 将模型池配置 + 全局参数组合成 SHA256 短哈希，当配置未变时直接返回缓存的 `ChatOpenAI` 实例。配置变更时由 `invalidate_llm_cache()` 清空（通过 `engine.invalidate_caches()` 暴露）。

### 3.4 `messages.py` — 会话历史转换

**职责：** 将 JSON 格式的会话历史转换为 LangChain 消息对象，正确处理 tool_calls。

**关键 API：**

```python
def convert_history(session_history: list[dict]) -> list[HumanMessage | AIMessage | ToolMessage]
    # session JSON 格式:
    #   {"role": "user", "content": "..."}
    #   {"role": "assistant", "content": "...", "tool_calls": [...]}
    #
    # 转换规则:
    #   user → HumanMessage
    #   assistant (无 tool_calls) → AIMessage
    #   assistant (有 tool_calls) → AIMessage(tool_calls=[...]) + ToolMessage × N
```

**与其他模块的关系：**
- **imported by:** `modes/direct.py`, `runner.py`
- **imports:** `langchain_core.messages`

**核心逻辑：** 当 assistant 消息包含 `tool_calls` 时，生成带 `tool_calls` 元数据的 `AIMessage` 以及对应的 `ToolMessage` 序列，确保 LLM 获得完整的工具调用上下文。`call_id` 从历史记录中取，若缺失则自动生成 `call_{i}_{tool_name}`。

### 3.5 `stream_adapter.py` — LangGraph 事件适配

**职责：** 将 LangGraph `astream_events` (v2) 原始事件流翻译为标准化 `AgentEvent` 字典。

**关键 API：**

```python
async def stream_agent_events(
    agent,                              # LangGraph agent (create_react_agent 返回)
    input_state: dict,                  # {"messages": [...]}
    config: dict,                       # {"recursion_limit": N}
    *,
    system_prompt: str = "",            # 调试显示用
    node_label: Optional[str] = None,   # 覆盖 langgraph_node（PlanMode 用 "executor"）
    motivation: Optional[str] = None,   # 覆盖 llm_start 动机
    instruction: Optional[str] = None,  # PlanMode executor_prompt（调试显示）
) -> AsyncGenerator[dict, None]
```

**与其他模块的关系：**
- **imported by:** `modes/direct.py`, `modes/plan.py`
- **imports:** `engine.events`, `model_pool.resolve_model`（延迟导入）

**核心逻辑：**
1. 维护 `debug_tracking` 字典跟踪进行中的 LLM/Tool 调用（以 `run_id` 为键）
2. 处理 5 种 LangGraph 事件：
   - `on_chat_model_stream` → `build_token(chunk.content)`
   - `on_chat_model_start` → `build_llm_start(...)` + 记录开始时间
   - `on_chat_model_end` → `build_llm_end_from_raw(...)` 计算耗时和 token 用量
   - `on_tool_start` → `build_tool_start_from_raw(...)`
   - `on_tool_end` → `build_tool_end_from_raw(...)` 计算工具耗时
3. `_serialize_debug_messages()` 和 `_format_debug_input()` 格式化调试输入显示

### 3.6 `runner.py` — 顶层编排器

**职责：** Agent 执行的唯一入口，协调 DirectMode → PlanMode 切换 + Middleware 管线 + LLM 缓存。

**关键 API：**

```python
async def run_agent(
    message: str,                   # 用户消息
    session_history: list[dict],    # 会话历史
    ctx: RunContext,                # 请求上下文
    middlewares: list = None,       # Middleware 链
) -> AsyncGenerator[dict, None]    # 事件流
```

**与其他模块的关系：**
- **imported by:** `__init__.py`, `app.py`
- **imports:** `config.settings`, `engine.context.RunContext`, `engine.events`, `engine.messages.convert_history`, `modes.direct.DirectMode`, `modes.plan.PlanMode`, `plan_approval`（延迟导入）, `prompt_builder`（延迟导入）, `cache`（延迟导入）

**核心逻辑流：**

```
run_agent()
  ├→ on_run_start() for each middleware
  ├→ enable_llm_cache? → _cached_run() : _run_uncached()
  └→ on_run_end() for each middleware (finally)

_run_uncached()
  ├→ Phase 1: DirectMode().execute(ctx) through _pipe()
  ├→ ctx.plan_data 非空?
  │    ├→ plan_require_approval? → Approval Gate (等待用户确认)
  │    └→ Phase 2: PlanMode(plan_data, messages).execute(ctx) through _pipe()
  └→ 否则: yield build_done()

_pipe(events_gen, middlewares, ctx)
  └→ 每个事件依次经过 mw.on_event()，返回 None 则抑制该事件
```

### 3.7 `middleware/` — Middleware 协议 + DebugMiddleware

#### `base.py` — Middleware Protocol

**职责：** 定义事件处理中间件的标准协议。

```python
@runtime_checkable
class Middleware(Protocol):
    async def on_event(self, event: dict, ctx: RunContext) -> Optional[dict]
        # 处理单个事件。返回 dict 传递下游，返回 None 抑制该事件。

    async def on_run_start(self, ctx: RunContext) -> None
        # Agent 运行开始时调用

    async def on_run_end(self, ctx: RunContext) -> None
        # Agent 运行结束时调用
```

#### `debug.py` — DebugMiddleware + InMemoryCollector

**职责：** 可配置级别的调试追踪中间件，收集工具调用和 LLM 调用数据。

```python
class DebugLevel(str, Enum):
    OFF = "off"           # 不记录
    BASIC = "basic"       # 仅 Tool 计时
    STANDARD = "standard" # + LLM start/end + Token 统计（截断大 payload）
    FULL = "full"         # + 完整 input/output 内容

class InMemoryCollector:
    # 在内存中累积 debug 事件，run 结束后批量持久化
    record_tool_start(event) / record_tool_end(event)
    record_llm_start(event)  / record_llm_end(event)
    get_all() -> list[dict]

class DebugMiddleware:
    def __init__(self, level: DebugLevel, collector: Optional[InMemoryCollector])
    async def on_event(event, ctx) -> Optional[dict]
        # BASIC+: 记录 tool_start / tool_end
        # STANDARD+: 记录 llm_start / llm_end
        # STANDARD: 截断 input > 2000 字符, output > 1000 字符
    async def on_run_end(ctx) -> None
        # 持久化 debug_calls 到 session JSON
```

**与其他模块的关系：**
- **imported by:** `middleware/__init__.py`, `app.py`
- **imports:** `engine.context.RunContext`, `sessions_manager`（延迟导入）

### 3.8 `modes/direct.py` — Phase 1 DirectMode

**职责：** Phase 1 ReAct Agent 执行，处理所有请求，检测 `plan_create` 触发。

**关键 API：**

```python
class DirectMode:
    async def execute(self, ctx: RunContext) -> AsyncGenerator[dict, None]
```

**与其他模块的关系：**
- **imported by:** `runner.py`
- **imports:** `config.settings`, `engine.context.RunContext`, `engine.events.TOOL_END`, `engine.llm_factory.get_llm`, `engine.messages.convert_history`, `engine.stream_adapter.stream_agent_events`, `prompt_builder.build_system_prompt`, `tools.get_all_tools`

**核心逻辑：**
1. 通过 `get_llm()` 获取 LLM、`get_all_tools()` 获取全部工具（含 `plan_create`）
2. 调用 `create_react_agent()` 创建 LangGraph ReAct Agent
3. 通过 `stream_agent_events()` 迭代事件流
4. 每个事件 yield 后检查：若 `type == "tool_end" && tool == "plan_create" && ctx.plan_data`，则 `return` 将控制权交还 runner

### 3.9 `modes/plan.py` — Phase 2 PlanMode + Replanner

**职责：** 逐步执行计划，每步独立子 Agent，步间 Replanner 评估。

**关键 API：**

```python
class ReplanDecision(BaseModel):
    action: str          # "continue" / "revise" / "finish"
    response: str        # action=finish 时的最终回复
    revised_steps: list[str]  # action=revise 时的新步骤
    reason: str          # 决策原因

class PlanMode:
    def __init__(self, plan_data: dict, original_messages: list)
    async def execute(self, ctx: RunContext) -> AsyncGenerator[dict, None]

    # 内部方法
    def _build_executor_prompt(system_prompt, plan_title, step_title,
                                step_index, total_steps, past_steps) -> str
    async def _evaluate_replan(plan_title, steps, past_steps,
                                current_index, system_prompt) -> Optional[ReplanDecision]
    def _should_skip_replan(past_steps, step_index, total) -> bool
```

**与其他模块的关系：**
- **imported by:** `runner.py`
- **imports:** `config.settings`, `engine.context.RunContext`, `engine.events`, `engine.llm_factory.get_llm`, `engine.stream_adapter.stream_agent_events`, `prompt_builder.build_system_prompt`, `tools.get_executor_tools`, `tools.plan_tool.send_plan_updated_event`, `tools.plan_tool.send_plan_revised_event`

**核心逻辑：** 见 [§4 两阶段执行模型详解](#4-两阶段执行模型详解)。

---

## 4. 两阶段执行模型详解

### 4.1 Phase 1 — DirectMode

```
用户消息 → DirectMode.execute()
              │
              ▼
    create_react_agent(llm, ALL_TOOLS, system_prompt)
              │
              ▼
    LangGraph ReAct Loop:
    ┌──────────────────────────────┐
    │  LLM 推理 → 决定下一步       │
    │    ├→ 直接回复 → yield tokens │
    │    └→ 调用工具 → yield events │
    │         │                     │
    │         ▼                     │
    │    工具执行 → yield result    │
    │         │                     │
    │    是 plan_create?            │
    │      Yes → ctx.plan_data 被设 │
    │           → return (退出)     │
    │      No → 循环继续             │
    └──────────────────────────────┘
```

DirectMode 拥有 **全部工具**（`get_all_tools()`），包括：
- 7 个 Core Tools（terminal, python_repl, fetch_url, read_file, search_knowledge_base, memory_write, memory_search）
- `plan_create` + `plan_update`（当 `plan_enabled=true` 时）
- MCP 动态工具（当 `mcp_enabled=true` 时）

### 4.2 plan_create 触发机制

**触发流程：**

1. LLM 在 Phase 1 中决定调用 `plan_create(title, steps)` 工具
2. `plan_tool.py:plan_create()` 执行（`L57-97`）：
   - 标准化步骤格式（处理 dict/string 混合输入）
   - 生成 `plan_id`（UUID hex[:8]）
   - 构建 plan 数据结构：`{plan_id, title, steps: [{id, title, status}]}`
   - 通过 `session_context.get_run_context()` 获取当前 `RunContext`
   - 将 plan 数据写入 `ctx.plan_data`
   - 通过 `_send_plan_event()` 发送 `plan_created` 侧通道事件
3. DirectMode 在 `yield event` 后检测（`direct.py:L46-48`）：
   ```python
   if event.get("type") == TOOL_END and event.get("tool") == "plan_create":
       if ctx.plan_data:
           return  # 退出 DirectMode
   ```
4. Runner 在 `_run_uncached()` 中检测 `ctx.plan_data` 非空（`runner.py:L97`），进入 Phase 2

### 4.3 Phase 2 — PlanMode 步骤循环

```
PlanMode.execute()
    │
    ▼
步骤循环 (step_index < len(steps) AND < plan_max_steps):
┌─────────────────────────────────────────────────────┐
│  1. send_plan_updated_event(step_id, "running")      │
│                                                      │
│  2. _build_executor_prompt()                         │
│     → System Prompt + 计划标题 + 当前步骤 + 已完成上下文│
│                                                      │
│  3. create_react_agent(llm, EXECUTOR_TOOLS, prompt)  │
│     → 独立子 Agent（不含 plan_create）                 │
│                                                      │
│  4. stream_agent_events(sub_agent, ...)              │
│     → node_label="executor", motivation="执行步骤 N"  │
│     → yield 所有事件，累积 step_response              │
│                                                      │
│  5. send_plan_updated_event(step_id, "completed")    │
│     → 失败时标记 "failed"                             │
│                                                      │
│  6. past_steps.append((step_title, response[:1000])) │
│                                                      │
│  7. _evaluate_replan()  →  决策                      │
│     ├→ None (continue): step_index++ 继续下一步       │
│     ├→ finish: 标记剩余步骤完成，break                 │
│     └→ revise: 替换剩余步骤，继续循环                  │
└─────────────────────────────────────────────────────┘
    │
    ▼
yield build_done()
```

Executor 子 Agent 使用 `get_executor_tools()`，包含 7 Core Tools + `plan_update`（无 `plan_create`），防止在 Phase 2 中嵌套创建新计划。

### 4.4 Replanner 决策逻辑 + 启发式跳过

**启发式跳过（`_should_skip_replan()`）：**
- 仅剩 1 步 → 跳过（无需重规划）
- 最后一步执行成功（response 中无 `[ERROR]`） → 跳过

**LLM 评估（`_evaluate_replan()`）：**
- 前提：`plan_revision_enabled=true` 且未被启发式跳过
- 使用 `get_llm(streaming=False)` + `with_structured_output(ReplanDecision)`
- Prompt 包含：计划标题、已完成步骤及结果、剩余步骤
- 三种决策：
  - `continue`: 继续执行下一步
  - `finish`: 目标已达成，标记剩余步骤完成
  - `revise`: 提供新的 `revised_steps`，替换剩余步骤

**失败降级：** Replanner LLM 调用异常时返回 `None`（等同于 continue）。

### 4.5 Approval Gate

当 `plan_require_approval=true` 时，在 Phase 1 → Phase 2 之间插入审批流程（`runner.py:L99-116`）：

1. 发送 `plan_approval_request` 侧通道事件（含 plan_id, title, steps）
2. 注册审批等待事件 `register_plan_approval(plan_id)`
3. `await approval_event.wait()` 阻塞等待用户响应
4. 用户通过 `POST /api/plan/approve` 提交审批
5. 审批通过 → 继续 PlanMode；拒绝 → 输出提示并结束

---

## 5. 事件系统

### 5.1 所有事件类型 + 字段 Schema

| 事件类型 | 字段 | 说明 |
|---------|------|------|
| `token` | `content: str` | LLM 流式输出的文本片段 |
| `tool_start` | `tool: str, input: str, motivation: str` | 工具调用开始 |
| `tool_end` | `tool: str, output: str, cached: bool, duration_ms: int?` | 工具调用结束 |
| `llm_start` | `call_id: str, node: str, model: str, input: str, motivation: str` | LLM 调用开始 |
| `llm_end` | `call_id: str, node: str, model: str, duration_ms: int, input_tokens: int?, output_tokens: int?, total_tokens: int?, input: str, output: str` | LLM 调用结束 |
| `done` | *(无额外字段)* | 整个 run 完成 |
| `error` | `content: str` | 运行时错误 |
| `plan_created` | `plan: {plan_id, title, steps: [{id, title, status}]}` | 计划创建（侧通道） |
| `plan_updated` | `plan_id: str, step_id: int, status: str` | 步骤状态变更（侧通道） |
| `plan_revised` | `plan_id: str, revised_steps: list, keep_completed: int, reason: str` | 计划修订（侧通道） |
| `plan_approval_request` | `plan_id: str, title: str, steps: list` | 审批请求（侧通道） |

### 5.2 事件流向

```
┌── 主事件流 ──────────────────────────────────────────────┐
│                                                          │
│  stream_adapter.py                                       │
│    │ (LangGraph raw events → standardized dicts)         │
│    ▼                                                     │
│  runner.py:_pipe()                                       │
│    │ (经过 Middleware 链: on_event → transform/suppress)  │
│    ▼                                                     │
│  app.py:_stream_agent_response()                         │
│    │ (累积数据 + serialize_sse)                           │
│    ▼                                                     │
│  HTTP SSE 输出 → 前端                                     │
└──────────────────────────────────────────────────────────┘

┌── 侧通道事件 ────────────────────────────────────────────┐
│                                                          │
│  plan_tool.py:_send_plan_event()                         │
│    │ → ctx.emit_plan_event() → ctx.plan_queue            │
│    │                                                     │
│  modes/plan.py:send_plan_updated_event()                 │
│    │ → plan_tool._send_plan_event() → ctx.plan_queue     │
│    │                                                     │
│  app.py:_stream_agent_response() L266-271                │
│    │ (drain plan_queue + approval_queue)                  │
│    │ → yield serialize_sse(side_event)                    │
│    ▼                                                     │
│  HTTP SSE 输出 → 前端                                     │
└──────────────────────────────────────────────────────────┘
```

**侧通道机制：** Plan 事件不经过 Middleware 链，而是通过 `RunContext.plan_queue`（asyncio.Queue）直接投递到 SSE 输出层。`app.py` 在每次主事件 yield 前 drain 这两个 queue。

---

## 6. 二次开发指南

### 6.1 添加新工具

**需修改的文件：**
- `backend/tools/{name}_tool.py`（新建）
- `backend/tools/__init__.py`

**步骤：**

1. 创建工具文件 `backend/tools/my_tool.py`：

```python
from langchain_core.tools import tool

@tool
def my_tool(param1: str, param2: int = 10) -> str:
    """工具描述（会显示给 LLM，用中文编写）。

    Args:
        param1: 参数说明
        param2: 参数说明
    """
    # 工具逻辑
    return "result"

def create_my_tool():
    return my_tool
```

2. 在 `backend/tools/__init__.py` 中注册：

```python
# 顶部添加导入
from tools.my_tool import create_my_tool

# 在 _get_core_tools() 中添加
def _get_core_tools() -> list:
    return [
        # ... 现有工具
        create_my_tool(),
    ]
```

3. （可选）在 `backend/engine/events.py` 的 `TOOL_MOTIVATIONS` 中添加中文动机：

```python
TOOL_MOTIVATIONS = {
    # ... 现有条目
    "my_tool": "执行自定义操作",
}
```

### 6.2 添加新执行模式（如 ParallelPlanMode）

**需修改的文件：**
- `backend/engine/modes/parallel.py`（新建）
- `backend/engine/runner.py`

**步骤：**

1. 创建新模式 `backend/engine/modes/parallel.py`：

```python
import asyncio
from engine.context import RunContext
from engine import events

class ParallelPlanMode:
    """并行执行多个步骤的模式。"""

    def __init__(self, plan_data: dict, original_messages: list):
        self.plan_data = plan_data
        self.original_messages = original_messages

    async def execute(self, ctx: RunContext):
        # 实现并行步骤执行逻辑
        # 必须 yield dict 事件
        yield events.build_token("并行执行中...")
        yield events.build_done()
```

2. 在 `runner.py:_run_uncached()` 中添加模式选择逻辑：

```python
from engine.modes.parallel import ParallelPlanMode

# 在 Phase 2 入口处
if ctx.plan_data:
    mode = ctx.plan_data.get("mode", "sequential")
    if mode == "parallel":
        plan_mode = ParallelPlanMode(ctx.plan_data, original_messages)
    else:
        plan_mode = PlanMode(ctx.plan_data, original_messages)
    async for event in _pipe(plan_mode.execute(ctx), mws, ctx):
        yield event
```

### 6.3 添加自定义中间件（如审计日志）

**需修改的文件：**
- `backend/engine/middleware/audit.py`（新建）
- `backend/engine/middleware/__init__.py`
- `backend/app.py`

**步骤：**

1. 创建中间件 `backend/engine/middleware/audit.py`：

```python
import logging
from typing import Optional
from engine.context import RunContext

logger = logging.getLogger(__name__)

class AuditMiddleware:
    """记录所有工具调用到审计日志。"""

    async def on_run_start(self, ctx: RunContext) -> None:
        logger.info(f"[AUDIT] Run started: session={ctx.session_id}")

    async def on_event(self, event: dict, ctx: RunContext) -> Optional[dict]:
        event_type = event.get("type", "")
        if event_type == "tool_start":
            logger.info(f"[AUDIT] Tool call: {event.get('tool')} "
                        f"session={ctx.session_id}")
        return event  # 不修改、不抑制

    async def on_run_end(self, ctx: RunContext) -> None:
        logger.info(f"[AUDIT] Run ended: session={ctx.session_id}")
```

2. 在 `backend/engine/middleware/__init__.py` 中导出：

```python
from engine.middleware.audit import AuditMiddleware
__all__ = ["Middleware", "DebugMiddleware", "DebugLevel", "AuditMiddleware"]
```

3. 在 `backend/app.py:_stream_agent_response()` 中注入：

```python
from engine.middleware import AuditMiddleware

# 在 run_agent 调用前
audit_mw = AuditMiddleware()
async for event in run_agent(message, history, ctx, middlewares=[debug_mw, audit_mw]):
    ...
```

### 6.4 修改 Replanner 策略

**需修改的文件：**
- `backend/engine/modes/plan.py`

**场景：** 改为每步都调用 Replanner（去除启发式跳过）。

```python
# plan.py:_should_skip_replan() — 修改为永不跳过
def _should_skip_replan(self, past_steps, step_index, total) -> bool:
    return False  # 每步都评估

# 或：增加自定义条件
def _should_skip_replan(self, past_steps, step_index, total) -> bool:
    if total - step_index <= 1:
        return True
    # 自定义：每 3 步评估一次
    if step_index % 3 != 0:
        return True
    return False
```

**场景：** 自定义 Replanner 的 Prompt。

修改 `_evaluate_replan()` 方法中的 `replan_prompt` 字符串（`plan.py:L167-182`）。

### 6.5 添加新事件类型

**需修改的文件：**
- `backend/engine/events.py`
- 相关发送方模块
- `backend/app.py`（如需在 SSE 层处理）

**步骤：**

1. 在 `events.py` 中添加常量和构建函数：

```python
# 常量
STEP_PROGRESS = "step_progress"

# 构建函数
def build_step_progress(step_id: int, progress: float, message: str) -> dict:
    return {
        "type": STEP_PROGRESS,
        "step_id": step_id,
        "progress": progress,
        "message": message,
    }
```

2. 在发送方（如 `modes/plan.py`）中 yield 该事件：

```python
from engine.events import build_step_progress
yield build_step_progress(step_id, 0.5, "正在处理...")
```

3. 前端通过 SSE 接收 `type: "step_progress"` 事件并渲染。

### 6.6 更换 LLM Provider

**需修改的文件：**
- `backend/engine/llm_factory.py`

`ChatOpenAI` 兼容所有 OpenAI API 协议的 Provider。只需在模型池中配置不同的 `api_base` 和 `model`。

如果需要使用非 OpenAI 协议的 Provider（如 Anthropic）：

```python
# llm_factory.py
from langchain_anthropic import ChatAnthropic

def get_llm(streaming: bool = True, scenario: str = "llm") -> BaseChatModel:
    fp = _config_fingerprint(scenario)
    key = f"{fp}_{streaming}"
    if key not in _llm_cache:
        from model_pool import resolve_model
        cfg = resolve_model(scenario)

        provider = cfg.get("provider", "openai")
        if provider == "anthropic":
            _llm_cache[key] = ChatAnthropic(
                model=cfg["model"],
                api_key=cfg["api_key"],
                streaming=streaming,
            )
        else:
            _llm_cache[key] = ChatOpenAI(...)
    return _llm_cache[key]
```

### 6.7 自定义 Debug 输出（如 OpenTelemetry）

**需修改的文件：**
- `backend/engine/middleware/debug.py`（或新建 `otel.py`）

**方法一：** 替换 `InMemoryCollector`

```python
from opentelemetry import trace

tracer = trace.get_tracer("vibeworker.agent")

class OTelCollector:
    """将 debug 事件发送到 OpenTelemetry。"""

    def __init__(self):
        self._calls = []
        self._spans = {}

    def record_tool_start(self, event):
        span = tracer.start_span(f"tool:{event.get('tool')}")
        self._spans[event.get("tool")] = span
        self._calls.append(event)

    def record_tool_end(self, event):
        span = self._spans.pop(event.get("tool"), None)
        if span:
            span.set_attribute("cached", event.get("cached", False))
            span.end()

    # ... record_llm_start / record_llm_end 类似

    def get_all(self):
        return self._calls

# 使用
debug_mw = DebugMiddleware(level=DebugLevel.STANDARD, collector=OTelCollector())
```

**方法二：** 创建独立的 Middleware（见 [§6.3](#63-添加自定义中间件如审计日志)）。

---

## 7. 调试指南

### 7.1 查看 System Prompt

System Prompt 由 `prompt_builder.py` 拼接生成。查看方式：

```python
# 在 Python REPL 中
from prompt_builder import build_system_prompt
print(build_system_prompt())
```

拼接顺序：`SKILLS_SNAPSHOT.xml` → `SOUL.md` → `IDENTITY.md` → `USER.md` → `AGENTS.md` → `MEMORY.md` → Daily Logs

### 7.2 查看完整 SSE 事件流

```bash
curl -N -X POST http://localhost:8088/api/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "你好", "session_id": "debug_test", "debug": true}'
```

`debug: true` 会启用 `DebugLevel.STANDARD`，额外输出 `llm_start` / `llm_end` 事件。

### 7.3 Debug 面板分级

| 级别 | 常量 | 记录内容 | 前端触发 |
|------|------|---------|---------|
| OFF | `DebugLevel.OFF` | 无 | `debug: false` |
| BASIC | `DebugLevel.BASIC` | Tool timing | — |
| STANDARD | `DebugLevel.STANDARD` | + LLM calls（截断） | `debug: true` |
| FULL | `DebugLevel.FULL` | + 完整 I/O | 需代码修改 |

当前 `app.py` 中 `debug=true` 映射到 `STANDARD`（`app.py:L254`）。

### 7.4 会话历史调试

会话文件位于 `{data_dir}/sessions/{session_id}.json`（默认 `~/.vibeworker/sessions/`）。

```bash
# 查看会话内容
cat ~/.vibeworker/sessions/debug_test.json | python -m json.tool

# 查看 debug_calls
cat ~/.vibeworker/sessions/debug_test_debug.json | python -m json.tool
```

Debug 数据由 `DebugMiddleware.on_run_end()` 通过 `session_manager.save_debug_calls()` 持久化。

### 7.5 LLM 缓存调试

LLM 缓存默认关闭（`ENABLE_LLM_CACHE=false`）。开启后：

- 缓存键基于 `system_prompt + recent_history[-3:] + message + model + temperature` 的 SHA256
- 命中时返回 cached 事件流（逐字符 yield + 10ms 延迟模拟流式）
- 缓存文件位于 `{data_dir}/.cache/llm/`

```bash
# 查看 LLM 缓存统计
curl http://localhost:8088/api/cache/stats | python -m json.tool

# 清空 LLM 缓存
curl -X POST "http://localhost:8088/api/cache/clear?type=llm"
```

### 7.6 Plan 执行调试

Plan 事件通过侧通道（`ctx.plan_queue`）发送。调试方法：

1. **SSE 流中观察：** `plan_created`, `plan_updated`, `plan_revised` 事件
2. **日志搜索：**
   ```bash
   # Replanner 决策
   grep "REPLANNER" backend.log

   # 步骤执行失败
   grep "Step.*failed" backend.log
   ```
3. **Session JSON：** 完成后的 plan 数据保存在 session 消息的 `plan` 字段中

### 7.7 常见问题排查表

| 问题 | 排查方向 |
|------|---------|
| LLM 不调用任何工具 | 检查 System Prompt 是否正确注入；检查 `get_all_tools()` 返回的工具列表 |
| plan_create 后不进入 Phase 2 | 检查 `ctx.plan_data` 是否被设置；确认 `session_context.get_run_context()` 返回正确的 ctx |
| SSE 流中缺少 plan 事件 | 检查 `emit_plan_event()` 的 `event_loop` 是否设置；确认 `plan_queue` drain 逻辑正常 |
| Replanner 总是返回 continue | 检查 `_should_skip_replan()` 启发式跳过条件；确认 `plan_revision_enabled=true` |
| 工具缓存不生效 | 检查 MCP 工具输出是否以 `[CACHE_HIT]` 开头；确认 `mcp_tool_cache_ttl` 设置 |
| LLM 实例不更新配置 | 配置变更后调用 `engine.invalidate_caches()`；或重启服务 |
| Phase 2 步骤数超限 | 检查 `plan_max_steps` 配置（默认 8）；过多步骤可能需要调大 |
| stream_adapter 事件丢失 | 确认 `astream_events` 的 `version="v2"`；检查 LangGraph 版本兼容性 |

---

## 8. 配置参考

以下列出所有影响 Agent 引擎行为的配置项，均通过 `.env` 文件或环境变量设置。

| 配置项 | 类型 | 默认值 | 说明 | 影响模块 |
|-------|------|--------|------|---------|
| `LLM_TEMPERATURE` | float | `0.7` | LLM 温度参数 | `llm_factory.py`, `config.py` |
| `LLM_MAX_TOKENS` | int | `4096` | LLM 最大生成 Token 数 | `llm_factory.py`, `config.py` |
| `AGENT_RECURSION_LIMIT` | int | `100` | LangGraph ReAct 循环最大递归次数 | `modes/direct.py` |
| `ENABLE_LLM_CACHE` | bool | `false` | 是否启用 LLM 响应缓存 | `runner.py` |
| `LLM_CACHE_TTL` | int | `86400` | LLM 缓存 TTL（秒） | `runner.py` |
| `PLAN_ENABLED` | bool | `true` | 是否启用 plan_create/plan_update 工具 | `tools/__init__.py` |
| `PLAN_REVISION_ENABLED` | bool | `true` | 是否启用 Replanner 评估 | `modes/plan.py` |
| `PLAN_REQUIRE_APPROVAL` | bool | `false` | Phase 2 执行前是否需要用户审批 | `runner.py` |
| `PLAN_MAX_STEPS` | int | `8` | Phase 2 最大执行步骤数 | `modes/plan.py` |
| `MCP_ENABLED` | bool | `true` | 是否启用 MCP 工具集成 | `tools/__init__.py` |
| `MCP_TOOL_CACHE_TTL` | int | `3600` | MCP 工具结果缓存 TTL（秒） | `mcp_module/` |
| `SECURITY_ENABLED` | bool | `true` | 是否启用安全网关 | `tools/__init__.py` |
| `MEMORY_AUTO_EXTRACT` | bool | `false` | 对话后是否自动提取记忆 | `app.py` |
| `MAX_PROMPT_CHARS` | int | `20000` | System Prompt 最大字符数 | `prompt_builder.py` |
| `MEMORY_MAX_PROMPT_TOKENS` | int | `4000` | 记忆注入 Prompt 的 Token 预算 | `prompt_builder.py` |

> 模型 API Key / Base / Model 由模型池管理（`~/.vibeworker/model_pool.json`），不在 `.env` 中。通过 `model_pool.resolve_model(scenario)` 解析。

---

*文档生成时间：2026-02-19 | 基于 commit: 532dbc5 (refactor: merge agent_mode and plan_enabled)*
