"""
一键启动测试仪表盘（简化为 dashboard_server.py 的入口包装）
==========================================================
用法: python 裁判系统/双裁判引擎/启动仪表盘.py
"""
import subprocess
import sys
import os

_HERE = os.path.dirname(os.path.abspath(__file__))

if __name__ == "__main__":
    server_script = os.path.join(_HERE, "dashboard_server.py")
    print("启动仪表盘服务器...")
    subprocess.run([sys.executable, server_script])
