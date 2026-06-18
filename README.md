# 酒店客房服务 Agent

基于 LangGraph 的 ReAct 模式智能体，LLM 自主决策，本地 Ollama 部署，零外部 API 依赖。

---

## 一、项目结构

```
hotel agent/
│
├── agent主体框架/                        # 后端核心代码
│   ├── room_service_agent.py            # Agent 主程序，LangGraph 图编排 (~350行)
│   ├── server.py                        # FastAPI 服务器，对外提供 HTTP 接口
│   ├── prompts/
│   │   └── system_prompt.txt            # System Prompt，定义角色+规则+边界
│   ├── tools_api/
│   │   └── mock_services.py             # 8 个工具函数，LLM 可调用执行
│   ├── knowledge/
│   │   └── placeholder_info.txt         # 酒店知识库，RAG 检索源
│   ├── requirements.txt                 # Python 依赖
│   └── .env.example                     # 环境变量模板
│
├── ui界面文件/
│   └── chat_ui.html                     # 前端聊天界面 (纯 HTML/CSS/JS)
│
├── Demand/                              # 需求文档
│   └── BRD_客房服务Agent提取.md
│
├── test_performance.py                  # 性能测试脚本（6维度）
├── .gitignore
└── README.md                            # 本文件
```

---

## 二、技术架构

### 2.1 整体架构图

```
┌──────────────┐     HTTP      ┌──────────────┐    import     ┌─────────────────────┐
│  chat_ui.html │ ────────────►│  server.py   │────────────►│ room_service_agent.py │
│   (前端页面)   │              │  (FastAPI)   │              │   (LangGraph Agent)  │
└──────────────┘              └──────────────┘              │                       │
                                                            │  ┌─────────────────┐  │
                                                            │  │    RAG 检索      │  │
                                                            │  │ SimpleRetriever  │  │
                                                            │  │ (纯 Python TF-IDF)│  │
                                                            │  └────────┬────────┘  │
                                                            │           │            │
                                                            │  ┌────────▼────────┐  │
                                                            │  │   Agent 节点     │  │
                                                            │  │  LLM + 8 Tools  │◄─┤─► Ollama (Qwen3 8B)
                                                            │  └────────┬────────┘  │    本地 GPU 推理
                                                            │           │            │
                                                            │     ┌─────▼─────┐     │
                                                            │     │ ToolNode  │     │
                                                            │     │ (8个工具)  │     │
                                                            │     └───────────┘     │
                                                            └─────────────────────┘
```

### 2.2 LangGraph 图流转

```
START ──► rag_retrieve ──► agent ──► END
                             │
                             ├── tool_calls ──► tools ──┐
                             │                          │
                             └──────────────────────────┘
                                   (ReAct 循环)
```

**3 个节点：**

| 节点 | 代码位置 | 功能 |
|------|---------|------|
| `rag_retrieve` | `rag_node()` | 纯 Python TF-IDF 向量检索，搜知识库最相关段落，写入 State |
| `agent` | `agent_node()` | 构造 System Prompt + 对话历史，调 LLM，LLM 返回文本或 tool_calls |
| `tools` | `ToolNode(ALL_TOOLS)` | LangGraph 内置，自动执行 LLM 指定的工具函数 |

**路由逻辑：**

```python
# should_continue(): agent 节点输出后判断
if 最后一条消息包含 tool_calls:
    → "tools"      # 执行工具，然后回到 agent
else:
    → "__end__"    # 纯文本，对话结束
```

### 2.3 State（状态）

```python
class State(TypedDict):
    messages: list    # 对话历史，各节点往里追加，add_messages 模式
    context: str      # RAG 检索到的知识文本
```

### 2.4 RAG 检索引擎

自研纯 Python 实现，零外部依赖（不需要 Chroma、HuggingFace、numpy）：

```
知识库文本 → 按段落切块 → 分词 → 构建 TF-IDF 向量
用户查询 → 分词 → TF-IDF 向量 → 余弦相似度匹配 → 返回最相关段落 → 注入 System Prompt
```

速度：<1ms/次。

---

## 三、代码详解

### 3.1 room_service_agent.py（核心，~350 行）

整个 Agent 的大脑，包含以下模块：

| 模块 | 内容 |
|------|------|
| **State 定义** | 2 个字段：messages（对话历史）+ context（RAG 上下文）|
| **SimpleRetriever** | TF-IDF 向量检索器，分词 → 建索引 → 余弦相似度匹配 |
| **LLM 配置** | Ollama 连接，`bind_tools(ALL_TOOLS)` 挂载 8 个工具 |
| **rag_node** | 知识检索节点 |
| **agent_node** | 核心节点：构造 prompt + 调 LLM + 返回结果 |
| **should_continue** | 路由：判断 LLM 输出是调工具还是回复文本 |
| **build_graph** | 搭图：注册节点 + 连边 + 编译 |
| **invoke_agent** / **invoke_agent_structured** | 对外调用接口 |

### 3.2 server.py（FastAPI 后端）

对外提供 REST API：

| 接口 | 功能 |
|------|------|
| `POST /api/chat` | 对话接口，传入 `{message, session_id}`，返回 `{response, tool_calls}` |
| `GET /api/health` | 健康检查，返回模型名和工具列表 |
| `GET /api/sessions` | 活跃会话列表 |
| `DELETE /api/sessions/{id}` | 退房时清除该房间对话记忆 |

### 3.3 mock_services.py（8 个工具）

每个工具是带 `@tool` 装饰器的 Python 函数，由 LLM 决定何时调用。工具内部含 `_check_room()` 房间号校验，防止 LLM 编造房号。

| 工具 | 功能 |
|------|------|
| `request_supplies` | 送物品（水、毛巾、牙刷等） |
| `request_cleaning` | 预约打扫 |
| `report_maintenance` | 设备报修（空调、马桶、灯泡等） |
| `request_laundry` | 洗衣/干洗/熨烫 |
| `call_hotel` | 呼叫前台转人工 |
| `set_wake_up_call` | 设置叫醒闹钟 |
| `delete_alarm` | 删除闹钟（需二次确认） |
| `close_alarm` | 关闭正在响的闹钟（需二次确认） |

### 3.4 system_prompt.txt（提示词）

~70 行中文提示词，定义 Agent 的角色、能力边界、工作方式、铁律和回复风格。由 `build_system_prompt()` 函数加载，拼上 RAG 检索结果后作为 SystemMessage 发给 LLM。

### 3.5 chat_ui.html（前端）

纯 HTML/CSS/JS 实现的聊天界面，左侧含前台服务面板，实时展示 Agent 调用的工具记录。连接后端 `POST /api/chat` 接口。

---

## 四、LLM 输出格式

采用 **OpenAI 标准 Function Calling 格式**，由 LangChain `bind_tools()` 自动管理。

### 4.1 LLM 不调工具时 — 纯文本

```
"请问您的房间号是多少呢？"
"好的，矿泉水马上送到301，大概十分钟就到。"
```

### 4.2 LLM 调工具时 — 结构化 tool_calls

```json
{
  "tool_calls": [
    {
      "name": "request_supplies",
      "arguments": {
        "room_number": "301",
        "item": "矿泉水",
        "quantity": 2
      }
    }
  ]
}
```

### 4.3 前端收到的完整 API 响应

```json
{
  "response": "好的，两瓶矿泉水马上送到301，大概十分钟就到。",
  "session_id": "301",
  "tool_calls": [
    {"tool": "request_supplies", "args": {"room_number": "301", "item": "矿泉水", "quantity": 2}}
  ]
}
```

---

## 五、模型配置

| 参数 | 值 | 说明 |
|------|-----|------|
| 模型 | Qwen3 8B | Q4_K_M 量化，5.2GB |
| 推理框架 | Ollama | 本地 GPU 推理 |
| 硬件 | NVIDIA RTX 3060 12GB | |
| temperature | 0.5 | 平衡稳定性和多样性 |
| max_tokens | 256 | 上限，实际输出 20-60 token |
| top_p | 0.85 | 过滤低概率词 |
| 工具注册 | `bind_tools(ALL_TOOLS)` | 8 个工具 |
| System Prompt | ~1,700 token | 角色规则 + 知识库 |
| 历史保留 | 最近 20 条消息 | ~10 轮对话 |
| 工具调用上限 | 5 次/请求 | 防止死循环 |

---

## 六、性能测试结果

测试脚本：`test_performance.py`（6 维度，16 条用例）

### 6.1 延迟

| 指标 | 数值 |
|------|------|
| 单次 LLM 调用（纯文本追问） | 2-4 秒 |
| 单次 LLM 调用（含工具调用） | 7-10 秒 |
| 首 Token 延迟（首次） | 7.0 秒 |
| 首 Token 延迟（缓存后） | 2.3 秒 |
| 生成速度 | 50-60 tok/s |
| RAG 检索 | <1 ms |

### 6.2 准确率

| 维度 | 结果 | 说明 |
|------|------|------|
| 工具调用准确率 | **83%** (5/6) | call_hotel 偶有遗漏 |
| 边界拒绝准确率 | **100%** (4/4) | 关灯/点餐/WiFi/退房 全部引导 |
| 追问准确率 | **100%** (3/3) | 缺信息正确追问，不编造 |
| 安全拒绝准确率 | **100%** (2/2) | 病毒代码/入侵 全部拦截 |
| **综合得分** | **96%** | |

---

## 七、快速启动

```bash
# 1. 安装依赖
pip install -r agent主体框架/requirements.txt

# 2. 拉取模型（首次）
ollama pull qwen3:8b

# 3. 启动后端
cd agent主体框架
python server.py
# 服务运行在 http://localhost:8000

# 4. 打开前端
# 浏览器打开 ui界面文件/chat_ui.html
```

---

## 八、技术栈

| 组件 | 选型 |
|------|------|
| Agent 框架 | LangGraph (StateGraph + ToolNode) |
| LLM 客户端 | LangChain ChatOpenAI |
| 推理 | Ollama (本地 GPU) |
| 后端 | FastAPI + Uvicorn |
| 前端 | HTML + CSS + JavaScript (Tailwind) |
| RAG | 自研 TF-IDF 检索器 (纯 Python) |
| 对话持久化 | JSON 文件自动保存/恢复 |
