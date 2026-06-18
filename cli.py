"""
统一 CLI 入口 — 裁判系统所有功能的统一命令行
=============================================
用法:
    python cli.py judge                          # 双裁判评估（24条默认用例）
    python cli.py judge --cases hard_tests       # 高难度测试
    python cli.py test --suite room_service_300  # 批量回归测试
    python cli.py test --suite weakness_300      # 弱项针对性测试
    python cli.py dashboard                      # 启动可视化仪表盘
    python cli.py results --report latest        # 查看最新评估报告
"""
import sys
import os

# 确保项目根目录在 path
_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HERE, "agent主体框架"))


def cmd_judge(args):
    """双裁判质量评估"""
    script = os.path.join(_HERE, "裁判系统", "dual_judge.py")
    os.system(f"{sys.executable} {script} {' '.join(args)}")


def cmd_test(args):
    """批量回归测试"""
    from importlib import import_module

    suite_map = {
        "room_service_300": "run_300",
        "weakness_300": "run_weakness",
        "hard_tests": "run_hard_tests",
        "external_100": "run_ext",
    }

    suite = None
    for i, a in enumerate(args):
        if a == "--suite" and i + 1 < len(args):
            suite = args[i + 1]
            break

    if suite is None:
        print("可用测试套件:")
        for k in suite_map:
            print(f"  {k}")
        print("\n用法: python cli.py test --suite room_service_300")
        return

    script_name = suite_map.get(suite)
    if script_name is None:
        # 直接作为文件名
        script_path = os.path.join(_HERE, "裁判系统", "历史脚本", f"{suite}.py")
        if os.path.exists(script_path):
            os.system(f"{sys.executable} {script_path}")
        else:
            print(f"未找到测试套件: {suite}")
        return

    script_path = os.path.join(_HERE, "裁判系统", "历史脚本", f"{script_name}.py")
    if os.path.exists(script_path):
        os.system(f"{sys.executable} {script_path}")
    else:
        print(f"脚本不存在: {script_path}")


def cmd_dashboard(args):
    """启动可视化仪表盘"""
    script = os.path.join(_HERE, "裁判系统", "双裁判引擎", "dashboard_server.py")
    os.system(f"{sys.executable} {script}")


def cmd_results(args):
    """查看评估结果"""
    import json
    from datetime import datetime

    report_path = os.path.join(_HERE, "裁判系统", "测试结果", "judge_report.json")

    if not os.path.exists(report_path):
        print("暂无评估报告。请先运行: python cli.py judge")
        return

    with open(report_path, "r", encoding="utf-8") as f:
        report = json.load(f)

    print(f"📊 最新评估报告")
    print(f"   生成时间: {report.get('generated_at', 'unknown')}")
    print(f"   测试总数: {report.get('total', '?')}")
    print(f"   ✅ PASS:  {report.get('pass', '?')}")
    print(f"   ❌ FAIL:  {report.get('fail', '?')}")
    print(f"   ⚠️  REVIEW: {report.get('review', '?')}")
    print(f"   通过率:   {report.get('pass_rate', '?')}%")
    print(f"   耗时:     {report.get('elapsed_seconds', 0):.0f}s")

    # 检查弱项测试
    weakness_path = os.path.join(_HERE, "裁判系统", "测试结果", "weakness_issues.json")
    if os.path.exists(weakness_path):
        with open(weakness_path, "r", encoding="utf-8") as f:
            wi = json.load(f)
        print(f"\n📋 弱项测试: 发现 {wi.get('total', 0)} 个问题")


def cmd_help(args):
    print(__doc__)


COMMANDS = {
    "judge": cmd_judge,
    "test": cmd_test,
    "dashboard": cmd_dashboard,
    "results": cmd_results,
    "help": cmd_help,
}

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print(__doc__)
        print("可用命令: " + ", ".join(COMMANDS.keys()))
        sys.exit(0)

    cmd = sys.argv[1]
    rest = sys.argv[2:]

    handler = COMMANDS.get(cmd)
    if handler:
        handler(rest)
    else:
        print(f"未知命令: {cmd}")
        print("可用命令: " + ", ".join(COMMANDS.keys()))
