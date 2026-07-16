#!/usr/bin/env python3
"""手动往像素办公室注入/移除 NPC（合成数据，用于演示 /office 页面）。
用法:
  python scripts/office_demo.py add  W1 "起草报告" writing        # 加一个
  python scripts/office_demo.py add  R1 "查资料"   reading main   # 带父节点
  python scripts/office_demo.py rm   W1                            # 移除一个
  python scripts/office_demo.py demo                               # 跑一段自动演示
  python scripts/office_demo.py clear                              # 清空全部
状态可选: writing(电脑) reading/searching(书架) thinking(白板) running(服务器)
"""
import sys, time, glob, json, os
from pathlib import Path
from tools.delegate_tool import _register_subagent, _unregister_subagent

def add(sid, goal="任务", status="writing", parent="main"):
    _register_subagent({"subagent_id": sid, "parent_id": parent, "depth": 1,
                        "goal": goal, "model": "kopi-o", "started_at": time.time(),
                        "tool_count": 0, "status": status})
    print(f"+ {sid} {status} ({goal})")

def rm(sid):
    _unregister_subagent(sid); print(f"- {sid}")

def clear():
    for f in glob.glob(str(Path.home() / ".kopi/office/subagents-*.json")):
        os.remove(f)
    print("已清空快照")

def demo():
    add("W1","起草季度报告","writing"); time.sleep(3)
    add("R1","查阅政策","reading");     time.sleep(3)
    add("T1","规划方案","thinking");    time.sleep(3)
    add("X1","执行部署","running");     time.sleep(3)
    add("W2","撰写脚本","writing","T1");time.sleep(4)  # 协作连线到 T1
    add("W1","核对数据","searching");   time.sleep(4)  # 换工位走位
    for s in ["R1","T1","W2","X1","W1"]:
        rm(s); time.sleep(1.5)
    print("演示结束")

cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
if cmd == "add":   add(*sys.argv[2:])
elif cmd == "rm":  rm(sys.argv[2])
elif cmd == "clear": clear()
else: demo()
