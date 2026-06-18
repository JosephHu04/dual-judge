"""
酒店客房服务 Agent — FastAPI 服务器
=============================================
启动方式:
    python server.py

接口:
    POST   /api/chat             — 对话接口
    GET    /api/health           — 健康检查
    GET    /api/sessions         — 活跃会话列表
    DELETE /api/sessions/{id}    — 清除会话（退房）
"""
import os
import logging, time, json
from contextlib import asynccontextmanager
from collections import deque

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel, Field

from room_service_agent import invoke_agent, invoke_agent_structured, clear_session
from tools_api.mock_services import ALL_TOOLS

# ==========================================
# 日志
# ==========================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] Server - %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("HotelServer")

# 最近 50 条调用日志（供监控面板读取）
recent_logs = deque(maxlen=200)

def _add_log(session_id, message, reply, tool_count, elapsed):
    recent_logs.append({
        "time": time.strftime("%H:%M:%S"),
        "session": session_id,
        "input": message[:60],
        "reply": reply[:60],
        "tools": tool_count,
        "elapsed": f"{elapsed:.1f}s",
    })

# ==========================================
# 数据模型
# ==========================================

class ChatRequest(BaseModel):
    """对话请求"""
    message: str = Field(..., description="客人消息", min_length=1, max_length=2000)
    session_id: str = Field(
        default="default",
        description="会话标识，建议用房间号，如 '301'。同 session_id 共享对话记忆。"
    )

class ChatResponse(BaseModel):
    """对话响应 — ReAct Agent 版本"""
    response: str = Field(..., description="Agent 的自然语言回复")
    session_id: str = Field(..., description="会话标识（回传）")
    tool_calls: list[dict] = Field(default_factory=list, description="本轮调用的工具列表")

class HealthResponse(BaseModel):
    """健康检查响应"""
    status: str
    agent: str
    model: str
    tools: list[str]

# ==========================================
# FastAPI 应用 & 生命周期
# ==========================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """启动 / 关闭时的钩子"""
    logger.info("=" * 50)
    logger.info("🏨 酒店客房服务 Agent 启动")
    logger.info("   模型: qwen3:8b (Ollama 本地)")
    logger.info("   工具: %s", [t.name for t in ALL_TOOLS])
    logger.info("=" * 50)
    yield
    logger.info("Agent 服务器已关闭")

app = FastAPI(
    title="Hotel Room Service Agent",
    description="酒店客房服务智能体 — 支持清扫、补给、报修、洗衣、唤醒、呼叫前台",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS — 允许总控 Agent 从任何来源调用
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ==========================================
# API 端点
# ==========================================

@app.post("/api/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    核心对话接口。

    总控 Agent (MainRouter) 将客人的消息 POST 到此端点，
    Agent 根据消息内容决定：直接回答、或调用工具执行实际操作。

    支持多轮对话：传入相同的 session_id 可保持对话上下文。
    """
    logger.info("会话[%s] 收到: %s", request.session_id, request.message[:100])

    t0 = time.time()
    try:
        structured = invoke_agent_structured(
            message=request.message,
            session_id=request.session_id,
        )
    except Exception as e:
        logger.error("会话[%s] 处理失败: %s", request.session_id, str(e))
        raise HTTPException(status_code=500, detail="内部处理错误，请稍后重试")
    elapsed = time.time() - t0

    _add_log(request.session_id, request.message,
             structured.get("response_text", ""),
             len(structured.get("tool_calls", [])), elapsed)

    return ChatResponse(
        response=structured.get("response_text", ""),
        session_id=request.session_id,
        tool_calls=structured.get("tool_calls", []),
    )


@app.get("/monitor", response_class=HTMLResponse)
async def monitor_page():
    """实时监控面板"""
    monitor_path = os.path.join(os.path.dirname(__file__), "..", "ui界面文件", "monitor.html")
    if os.path.exists(monitor_path):
        with open(monitor_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>监控页面未找到</h1>"


@app.get("/chat", response_class=HTMLResponse)
async def chat_page():
    """聊天界面"""
    chat_path = os.path.join(os.path.dirname(__file__), "..", "ui界面文件", "chat_ui.html")
    if os.path.exists(chat_path):
        with open(chat_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>聊天界面未找到</h1>"


@app.get("/", response_class=HTMLResponse)
async def launch_panel():
    """启动面板"""
    panel_path = os.path.join(os.path.dirname(__file__), "..", "ui界面文件", "启动面板.html")
    if os.path.exists(panel_path):
        with open(panel_path, "r", encoding="utf-8") as f:
            return f.read()
    return "<h1>启动面板未找到</h1>"


@app.get("/api/monitor/logs")
async def monitor_logs():
    """返回最近 200 条调用记录"""
    return {"total": len(recent_logs), "logs": list(recent_logs)}


@app.post("/api/monitor/logs/clear")
async def clear_monitor_logs():
    """清空监控日志"""
    count = len(recent_logs)
    recent_logs.clear()
    logger.info("监控日志已清空（共 %d 条）", count)
    return {"status": "ok", "message": f"已清空 {count} 条日志"}


@app.get("/api/health", response_model=HealthResponse)
async def health():
    """
    健康检查接口。

    总控 Agent 启动时调用此接口确认客房服务 Agent 在线。
    也可用于监控系统定期探测。
    """
    return HealthResponse(
        status="ok",
        agent="RoomServiceAgent",
        model="qwen35-4b (vLLM 服务器)",
        tools=[t.name for t in ALL_TOOLS],
    )


@app.get("/api/sessions")
async def list_sessions():
    """
    列出当前活跃会话（简化版）。

    生产环境应返回实际 MemorySaver 中的 thread 列表。
    """
    return {
        "message": "MemorySaver 模式下会话存储在内存中，重启后自动清除",
        "note": "升级为 SqliteSaver 后可查询持久化会话列表",
    }


@app.delete("/api/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    清除指定会话的对话历史。

    客人退房后，前台系统应调用此接口清除该房间的对话记忆，
    以保护客人隐私。
    """
    clear_session(session_id)
    logger.info("会话[%s] 已手动清除（退房操作）", session_id)
    return {"status": "ok", "message": f"会话 {session_id} 已清除"}


# ==========================================
# 直接运行
# ==========================================

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(
        "server:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=[os.path.join(os.path.dirname(__file__))],
        log_level="info",
    )
