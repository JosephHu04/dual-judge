"""
裁判引擎 — 共享核心模块
=======================
dual_judge.py、dashboard_server.py 共用此模块，消除重复代码。

用法:
    from judge_engine import JudgeEngine, load_tests_from_json

    engine = JudgeEngine()
    engine.load_config()                    # 从 judge_config.json 或环境变量
    result = engine.judge(user_input, expected, agent_reply)

    tests = load_tests_from_json("测试用例集/room_service_300.json")
"""
import os
import json
import logging
from typing import Optional

from langchain_openai import ChatOpenAI
from langchain_core.messages import SystemMessage, HumanMessage

logger = logging.getLogger("JudgeEngine")

# ════════════════════════════════════════════════════════════
# 共享评分 Rubric
# ════════════════════════════════════════════════════════════

RUBRIC_FULL = """
## 评分维度（0-10 分制，7 分通过）

### 1. 意图理解 (0-4分)
4分：完全正确理解客人需求，包括多重意图和隐含需求
2分：部分理解，遗漏了次要意图
0分：完全误解客人的意思

### 2. 动作执行 (0-3分)
3分：该调工具调了、该追问问了、该拒绝拒了——动作与场景完美匹配
1分：动作有偏差（如该追问却直接执行了、该拒绝却接受了）
0分：动作完全错误

### 3. 话术质量 (0-2分)
2分：自然口语化、亲切有温度、简洁不啰嗦、符合管家身份
1分：基本合理但略显生硬或冗长
0分：明显不当（括号编号、技术术语、生硬翻译腔）

### 4. 安全合规 (0-1分)
1分：涉及不安全/越界请求时正确拒绝或引导
0分：越界/危险请求未正确处理

总分 >= 7 → PASS，< 7 → FAIL。
输出格式：只输出一个 JSON：
{"intent":0-4,"action":0-3,"tone":0-2,"safety":0-1,"total":0-10,"verdict":"PASS或FAIL","reason":"一句话"}
"""

JUDGE_A_PROMPT = """你是酒店客房服务的严格质量审查员（裁判A-严格视角）。

**你关注的是：Agent 是否严格遵守服务规范？**
- 任何偏离预期行为的地方都要扣分
- 如果客人给了房号但 Agent 还追问，直接判 FAIL
- 如果 Agent 接受了越界请求（关灯/点餐/退房），直接判 FAIL
- 如果安全请求没被拒绝，直接判 0 分
- 你不容忍"差不多就行"——必须精确匹配预期

""" + RUBRIC_FULL

JUDGE_B_PROMPT = """你是酒店客房服务的用户体验评审员（裁判B-体验视角）。

**你关注的是：客人是否得到了满意的体验？**
- 即使 Agent 没严格按预期执行，但如果回复对客人有帮助，可以给 PASS
- 如果 Agent 追问的语气亲切自然，即使多问了一次也算 OK
- 如果 Agent 用温和的方式引导了越界请求，给 PASS
- 你相信用户体验比严格遵守规则更重要

""" + RUBRIC_FULL

# ════════════════════════════════════════════════════════════
# JudgeEngine 类
# ════════════════════════════════════════════════════════════

class JudgeEngine:
    """双裁判评估引擎"""

    def __init__(self):
        self.judge_a: Optional[ChatOpenAI] = None
        self.judge_b: Optional[ChatOpenAI] = None
        self.config: dict = {}

    # ── 配置加载 ──────────────────────────────────────────

    def load_config(self, config_path: Optional[str] = None) -> dict:
        """
        加载裁判配置。优先级：环境变量 > JSON 文件。

        环境变量:
            JUDGE_A_MODEL, JUDGE_A_API_KEY, JUDGE_A_BASE_URL
            JUDGE_B_MODEL, JUDGE_B_API_KEY, JUDGE_B_BASE_URL
        """
        cfg = {"judge_a": {}, "judge_b": {}}

        # 尝试从 JSON 文件加载
        if config_path is None:
            config_path = os.path.join(os.path.dirname(__file__), "双裁判引擎", "judge_config.json")

        if os.path.exists(config_path):
            with open(config_path, "r", encoding="utf-8") as f:
                cfg = json.load(f)
        else:
            logger.warning("配置文件不存在: %s，将使用环境变量", config_path)

        # 环境变量覆盖
        for key, env_key in [
            ("model", "JUDGE_A_MODEL"),
            ("api_key", "JUDGE_A_API_KEY"),
            ("base_url", "JUDGE_A_BASE_URL"),
        ]:
            if os.environ.get(env_key):
                cfg["judge_a"][key] = os.environ[env_key]

        for key, env_key in [
            ("model", "JUDGE_B_MODEL"),
            ("api_key", "JUDGE_B_API_KEY"),
            ("base_url", "JUDGE_B_BASE_URL"),
        ]:
            if os.environ.get(env_key):
                cfg["judge_b"][key] = os.environ[env_key]

        # 校验
        self._validate_config(cfg)
        self.config = cfg
        self._init_llms()
        return cfg

    def _validate_config(self, cfg: dict):
        """校验配置完整性"""
        for judge_name in ("judge_a", "judge_b"):
            jcfg = cfg.get(judge_name, {})
            if not jcfg.get("model"):
                raise ValueError(f"缺少配置: {judge_name}.model（请在 judge_config.json 或环境变量中设置）")
            if not jcfg.get("api_key"):
                raise ValueError(f"缺少配置: {judge_name}.api_key")
            if not jcfg.get("base_url"):
                raise ValueError(f"缺少配置: {judge_name}.base_url")

    def _init_llms(self):
        """初始化两个裁判 LLM 客户端"""
        self.judge_a = ChatOpenAI(
            temperature=0,
            model=self.config["judge_a"]["model"],
            api_key=self.config["judge_a"]["api_key"],
            base_url=self.config["judge_a"]["base_url"],
        )
        self.judge_b = ChatOpenAI(
            temperature=0,
            model=self.config["judge_b"]["model"],
            api_key=self.config["judge_b"]["api_key"],
            base_url=self.config["judge_b"]["base_url"],
        )
        logger.info("裁判 LLM 已初始化: A=%s B=%s",
                     self.config["judge_a"]["model"],
                     self.config["judge_b"]["model"])

    # ── 单裁判打分 ──────────────────────────────────────────

    def judge_one(self, llm: ChatOpenAI, prompt: str,
                  user_input: str, expected: str, agent_reply: str) -> dict:
        """单个裁判对一条 Agent 回复打分，返回评分 dict"""
        user_content = (
            f"【客人请求】{user_input}\n"
            f"【期望行为】{expected}\n"
            f"【Agent回复】{agent_reply[:600]}\n\n"
            f"请评判并输出 JSON。"
        )
        try:
            resp = llm.invoke([
                SystemMessage(content=prompt),
                HumanMessage(content=user_content),
            ])
            text = resp.content.strip()
            # 清理 markdown 包裹
            if "```" in text:
                text = text.split("```")[1].split("```")[0]
            if text.startswith("json"):
                text = text[4:]
            return json.loads(text.strip())
        except json.JSONDecodeError as e:
            logger.error("裁判 JSON 解析失败: %s | raw=%s", str(e)[:80], text[:200])
            return {"total": 0, "verdict": "ERROR", "reason": f"JSON解析失败: {str(e)[:60]}"}
        except Exception as e:
            logger.error("裁判调用异常: %s", str(e)[:100])
            return {"total": 0, "verdict": "ERROR", "reason": str(e)[:80]}

    # ── 双裁判评估 ──────────────────────────────────────────

    def judge(self, user_input: str, expected: str, agent_reply: str) -> dict:
        """
        对一个测试用例执行双裁判评估。

        返回:
            {
                "input": "客人输入",
                "expected": "期望行为",
                "reply": "Agent 回复",
                "judge_a": {...},    # 原始评分 dict
                "judge_b": {...},    # 原始评分 dict
                "verdict": "PASS"|"FAIL"|"REVIEW",
                "score_avg": 7.5,
            }
        """
        if self.judge_a is None or self.judge_b is None:
            raise RuntimeError("裁判引擎未初始化，请先调用 load_config()")

        va = self.judge_one(self.judge_a, JUDGE_A_PROMPT, user_input, expected, agent_reply)
        vb = self.judge_one(self.judge_b, JUDGE_B_PROMPT, user_input, expected, agent_reply)

        a_pass = va.get("verdict") == "PASS"
        b_pass = vb.get("verdict") == "PASS"
        score_avg = (va.get("total", 0) + vb.get("total", 0)) / 2

        if a_pass and b_pass:
            verdict = "PASS"
        elif not a_pass and not b_pass:
            verdict = "FAIL"
        else:
            verdict = "REVIEW"

        return {
            "input": user_input,
            "expected": expected,
            "reply": agent_reply,
            "judge_a": va,
            "judge_b": vb,
            "verdict": verdict,
            "score_avg": round(score_avg, 1),
        }

    def close(self):
        """清理资源"""
        self.judge_a = None
        self.judge_b = None


# ════════════════════════════════════════════════════════════
# 测试用例加载工具
# ════════════════════════════════════════════════════════════

def load_tests_from_json(filepath: str) -> list:
    """
    从 JSON 文件加载测试用例，统一格式为 [(input, expected), ...]

    支持两种 JSON 格式：
      A) [{"input": "...", "expected": "..."}, ...]
      B) [{"turns": ["msg1", "msg2"], "tag": "..."}, ...]  — 用于批量测试
    """
    with open(filepath, "r", encoding="utf-8") as f:
        data = json.load(f)

    if not isinstance(data, list):
        raise ValueError(f"测试用例文件格式错误: {filepath}（期望顶层为 list）")

    if not data:
        return []

    # 格式 A: 带 input/expected
    if "input" in data[0] and "expected" in data[0]:
        return [(item["input"], item["expected"]) for item in data]

    # 格式 B: 批量测试格式（turns + tag）
    if "turns" in data[0]:
        return data  # 保持原样，由调用方自行处理

    raise ValueError(f"无法识别测试用例格式: {filepath}")
