"""
高难度测试 — 25条复杂场景，含多轮对话
运行: python 裁判系统/run_hard_tests.py
"""
import sys, os, time, json

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "agent主体框架"))
os.chdir(os.path.join(os.path.dirname(__file__), "..", "..", "agent主体框架"))

from room_service_agent import invoke_agent

with open(os.path.join(os.path.dirname(__file__), "..", "测试用例集", "hard_tests.json"), "r", encoding="utf-8") as f:
    TESTS = json.load(f)

print(f"高难度测试: {len(TESTS)} 条")
print(f"  单轮: {sum(1 for t in TESTS if 'input' in t)}")
print(f"  多轮: {sum(1 for t in TESTS if 'turns' in t)}")
print(f"{'='*60}")

results = []
for i, test in enumerate(TESTS):
    tid = test["id"]
    cat = test["category"]
    checks = ", ".join(test["key_checks"][:3])

    if "turns" in test:
        # 多轮对话
        turns_output = []
        session = f"hard_{tid}"
        for j, turn in enumerate(test["turns"]):
            reply = invoke_agent(turn, session_id=session)
            turns_output.append({"turn": j+1, "input": turn, "reply": reply[:200]})
        print(f"  [{tid}] {cat:30s} | {len(test['turns'])}轮 | {checks[:60]}")
        results.append({"id": tid, "category": cat, "type": "multi", "turns": turns_output, "checks": test["key_checks"]})
    else:
        # 单轮
        reply = invoke_agent(test["input"], session_id=f"hard_{tid}")
        print(f"  [{tid}] {cat:30s} | 单轮 | {test['input'][:40]} | {reply[:50]}")
        results.append({"id": tid, "category": cat, "type": "single", "input": test["input"], "reply": reply[:300], "checks": test["key_checks"]})

    time.sleep(0.5)

# 保存完整记录供人工审核
out_path = os.path.join(os.path.dirname(__file__), "..", "测试结果", "hard_test_results.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump(results, f, ensure_ascii=False, indent=2)

print(f"\n完整记录: {out_path}")
print(f"打开文件查看每条回复，手动检查是否符合 key_checks。")
