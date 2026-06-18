# ⚖️ Dual-Judge — 让 AI 测试结果真正有说服力

[![Python](https://img.shields.io/badge/Python-3.12-blue)](https://python.org)
[![LangGraph](https://img.shields.io/badge/LangGraph-ReAct-orange)](https://langchain.com)
[![accuracy](https://img.shields.io/badge/准确率-100%25-brightgreen)](裁判系统/测试结果/)
[![license](https://img.shields.io/badge/license-MIT-lightgrey)](LICENSE)

> ⚖️ **双裁判评估方法论** — 用两个不同人格的 LLM 交叉验证 AI 回复质量，让评估结果不再依赖单一模型的偏见。
>
> ⚖️ **Dual-Judge Evaluation** — Cross-validate AI outputs with two LLMs of opposing personas. Eliminate single-judge bias. Make AI testing trustworthy.

**中文** | [**English**](#english)

---

## 🎯 解决什么问题

AI Agent 测试有个根本难题：**谁来判定回复对不对？**

- ❌ 关键词匹配 → 太机械，"时间不对"和"时间好像不太对"都能匹配到"不对"，但前者生硬后者温和
- ❌ 人工评审 → 太慢，300 条测试逐条看要几个小时，且标准不一
- ❌ 单一 LLM 评审 → 太片面，一个 LLM 的"偏见"就是你的全部结论

**双裁判方案**：让两个"性格相反"的 LLM 分别打分——一个严苛到吹毛求疵，一个宽容到客人说了算。两者都 PASS 才是真 PASS，分歧自动上报人工裁决。**这套方法论适用于任何需要评估对话质量的 AI Agent。**

---

## 🏗️ 核心架构

```
被测 AI Agent                   双裁判引擎（Judge Engine）
─────────────                  ──────────────────────────────
                               
  Agent 回复 ─────────────┬──→ 裁判A (Strict)  严苛审查员
                          │    人格: 任何偏差都扣分
                          │    模型: DeepSeek / 任意 API
                          │
                          └──→ 裁判B (Liberal) 体验评审员
                               人格: 客人满意就行
                               模型: 本地千问3 / Ollama
                                               │
                          ┌─────────────────────┤
                          ▼                     ▼
                       双 PASS              双 FAIL
                    ✅ 自动通过           ❌ 自动拒绝
                          │
                          ├── 分歧 ──→ review_queue.json
                          │           人工裁决，不丢数据
```

### 评分维度（通用 Rubric，可自定义）

| 维度 | 分值 | 用法 |
|------|------|------|
| 意图理解 | 0-4 | AI 是否正确理解用户想干什么 |
| 动作执行 | 0-3 | 该调用什么 / 该追问问 / 该拒绝了——动作对不对 |
| 话术质量 | 0-2 | 语气自然吗、啰嗦吗、像真人吗 |
| 安全合规 | 0-1 | 危险 / 越界请求有没有正确处理 |

**总分 ≥7 → PASS，<7 → FAIL。** 这套 Rubric 可以根据你的业务场景替换。

---

## 🧰 项目组成

```
├── 裁判系统/                 ← ★ 核心产品：独立可复用的双裁判引擎
│   ├── judge_engine.py               共享引擎（dual_judge + dashboard 共用）
│   ├── dual_judge.py                 双裁判 CLI 主程序
│   ├── 双裁判引擎/
│   │   ├── dashboard_server.py       可视化仪表盘后端（SSE 实时推送）
│   │   ├── dashboard.html            仪表盘前端（动画小人实时展示）
│   │   └── judge_config.example.json 裁判 LLM 配置模板
│   ├── 测试用例集/                    可复用的测试用例格式
│   └── README.md
│
├── agent主体框架/             ← 示例：一个酒店客房服务 Agent
│   ├── room_service_agent.py         LangGraph ReAct Agent
│   ├── server.py                     FastAPI 服务器
│   └── tools_api/mock_services.py    8 个 Mock 服务工具
│
├── cli.py                             统一命令行入口
└── ui界面文件/                         示例前端界面
```

> 💡 **裁判系统完全独立于具体的 Agent。** 你只需要把你的 Agent 的调用接口换成你自己的，裁判引擎不用改一行代码。

---

## ⚡ 快速开始

```bash
# 1. 双裁判评估（用内置测试用例）
python cli.py judge

# 2. 带自己的测试用例
python cli.py judge --cases 你的测试.json

# 3. 可视化仪表盘
python cli.py dashboard

# 4. 查看报告
python cli.py results
```

### 裁判配置

编辑 `裁判系统/双裁判引擎/judge_config.json` 或用环境变量：

```json
{
  "judge_a": { "model": "deepseek-chat", "api_key": "sk-xxx", "base_url": "https://api.deepseek.com" },
  "judge_b": { "model": "qwen3:8b", "api_key": "ollama", "base_url": "http://localhost:11434/v1" }
}
```

---

## 📊 示例应用：酒店客房服务 Agent

作为双裁判方法论的应用示例，本项目包含了一个完整的酒店客房服务智能体：

| 特性 | 说明 |
|------|------|
| 🤖 **ReAct Agent** | LangGraph 状态图，LLM 自主 Thought → Action → Observation |
| 🔧 **8 个工具** | 配送 / 打扫 / 报修 / 洗衣 / 呼叫前台 / 叫醒 / 闹钟 |
| 🗂️ **RAG** | TF-IDF 纯 Python 实现，零外部依赖 |
| 🏠 **本地部署** | Ollama / vLLM，数据不出内网 |

### 示例测试成绩

| 类别 | 数量 | 通过 | 通过率 |
|------|------|------|--------|
| 安全拒绝 | 30 | 30 | 100% |
| 时间有效性 | 25 | 25 | 100% |
| 异常数量质疑 | 10 | 10 | 100% |
| 缺失信息追问 | 50 | 50 | 100% |
| 越界拒绝引导 | 28 | 28 | 100% |
| **关键类别合计** | **143** | **143** | **100%** |

---

## 🔧 怎么用到你自己的项目

1. **替换被测 Agent**：在 `dual_judge.py` 里把 `invoke_agent()` 换成你自己的调用函数
2. **写测试用例**：用 JSON 格式 `[{"input": "...", "expected": "..."}]`
3. **调整 Rubric**：修改 `judge_engine.py` 里的评分维度和标准
4. **运行**：`python cli.py judge --cases 你的用例.json`

---

<a name="english"></a>
## ⚖️ Dual-Judge — Making AI Evaluation Trustworthy

> **The Problem:** Who judges the judge? Single-LLM evaluation is inherently biased — one model's opinion becomes your entire quality metric.
>
> **The Solution:** Two LLMs with opposing personas cross-validate each other. Both must agree to pass. Disagreements are saved for human review.

### How It Works

1. Your AI agent generates a response
2. **Judge A** (strict) scores it — any deviation from expected behavior costs points
3. **Judge B** (liberal) scores it — if the user is satisfied, it passes
4. **Both PASS** → auto-approved. **Both FAIL** → auto-rejected. **Split** → saved for human adjudication

### Why This Matters

- 🔬 **Scientific rigor** — two independent raters is the standard in human evaluation (inter-rater reliability). We apply the same logic to LLM judges.
- 🎭 **Persona diversity** — strict + liberal judges catch different types of errors. A strict judge finds protocol violations; a liberal judge prevents over-refusal.
- 👁️ **Human in the loop** — disagreements aren't hidden. They're surfaced for human review, where the hardest calls belong.

### Try It

```bash
python cli.py judge      # Built-in test cases
python cli.py dashboard  # Live visualization
```

**Completely framework-agnostic.** The judge engine is decoupled from any specific AI agent. Swap in your own agent with one line of code.

---

## 📄 License

MIT — use it, modify it, build on it.
