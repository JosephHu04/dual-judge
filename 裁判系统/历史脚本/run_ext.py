"""运行外部 100 条测试"""
import json, time, sys, os

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.join(HERE, "..", "..")
AGENT = os.path.join(ROOT, "agent主体框架")
sys.path.insert(0, AGENT)
os.chdir(AGENT)

from room_service_agent import invoke_agent

with open(os.path.join(HERE, "..", "测试用例集", "external_100_tests.json"), "r", encoding="utf-8") as f:
    tests = json.load(f)

total_turns = sum(t["turn_count"] for t in tests)
print(f"{len(tests)}条 {total_turns}轮 预计~{total_turns*3/60:.0f}min")
print("=" * 50)

results = []
start = time.time()
done = 0

for i, test in enumerate(tests):
    sid = f"e_{test['id']}"
    turns_out = []
    for j, turn in enumerate(test["turns"]):
        try:
            reply = invoke_agent(turn, session_id=sid)
            turns_out.append({"t": j+1, "in": turn[:80], "out": reply[:150]})
        except Exception as e:
            turns_out.append({"t": j+1, "in": turn[:80], "out": f"ERR:{str(e)[:60]}"})
        done += 1
    results.append({"id": test["id"], "turns": turns_out})

    if (i+1) % 10 == 0:
        e = time.time() - start
        avg = e / done
        rem = total_turns - done
        print(f"[{i+1:3d}/{len(tests)}] {done}/{total_turns}轮 | {avg:.1f}s/轮 | 剩~{rem*avg/60:.0f}min")

elapsed = time.time() - start
out_path = os.path.join(HERE, "..", "测试结果", "external_100_results.json")
with open(out_path, "w", encoding="utf-8") as f:
    json.dump({"tests": len(tests), "turns": done, "elapsed": f"{elapsed:.0f}s", "results": results}, f, ensure_ascii=False, indent=2)

print(f"\nDONE! {len(tests)}条 {done}轮 | {elapsed/60:.1f}min | {elapsed/done:.1f}s/轮")
print(f"结果: {out_path}")
