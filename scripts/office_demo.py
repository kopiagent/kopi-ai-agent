#!/usr/bin/env python3
"""手动往像素办公室注入/移除 NPC（合成数据，用于演示 /office 页面）。

直接读写 <KOPI_HOME>/office/subagents-demo.json（带 demo 标记的合成快照），
所以 add/rm 跨进程生效：add 完脚本退出后 NPC 仍会显示（最长 10 分钟，
由 web_server 的 _OFFICE_DEMO_TTL 控制），rm/clear 随时可移除。

用法:
  python scripts/office_demo.py add  W1 "起草报告" writing        # 加一个
  python scripts/office_demo.py add  R1 "查资料"   reading W1     # 带父节点（画协作线）
  python scripts/office_demo.py rm   W1                            # 移除一个
  python scripts/office_demo.py demo                               # 跑一段自动演示
  python scripts/office_demo.py clear                              # 清空合成数据
状态可选: writing(电脑) reading/searching(书架) thinking(白板) running(服务器) waiting(咖啡机)
"""
import sys, time, json, os
from pathlib import Path


def _office_dir() -> Path:
    try:
        from kopi_constants import get_kopi_home
        return get_kopi_home() / "office"
    except Exception:
        return Path(os.environ.get("KOPI_HOME", str(Path.home() / ".kopi"))) / "office"


DEMO_FILE = _office_dir() / "subagents-demo.json"


def _load() -> list:
    try:
        return json.loads(DEMO_FILE.read_text(encoding="utf-8")).get("agents", [])
    except Exception:
        return []


def _save(agents: list) -> None:
    DEMO_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = f"{DEMO_FILE}.tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump({"pid": None, "demo": True, "ts": time.time(), "agents": agents},
                  f, ensure_ascii=False)
    os.replace(tmp, DEMO_FILE)


def add(sid, goal="任务", status="writing", parent=None):
    agents = [a for a in _load() if a.get("subagent_id") != sid]
    agents.append({"subagent_id": sid, "parent_id": parent, "depth": 1 if parent else 0,
                   "kind": "subagent", "goal": goal, "model": "kopi-o",
                   "started_at": time.time(), "tool_count": 0, "status": status,
                   "ts": time.time()})
    _save(agents)
    print(f"+ {sid} {status} ({goal})" + (f" ↔ {parent}" if parent else ""))


def rm(sid):
    _save([a for a in _load() if a.get("subagent_id") != sid])
    print(f"- {sid}")


def clear():
    try:
        DEMO_FILE.unlink()
    except FileNotFoundError:
        pass
    print("已清空合成数据（真实 agent 的快照不受影响）")


def demo():
    add("W1", "起草季度报告", "writing");  time.sleep(3)
    add("R1", "查阅政策",     "reading");  time.sleep(3)
    add("T1", "规划方案",     "thinking"); time.sleep(3)
    add("X1", "执行部署",     "running");  time.sleep(3)
    add("W2", "撰写脚本",     "writing", "T1"); time.sleep(4)  # 协作连线到 T1
    add("W1", "核对数据",     "searching");     time.sleep(4)  # 换工位走位
    for s in ["R1", "T1", "W2", "X1", "W1"]:
        rm(s); time.sleep(1.5)
    clear()
    print("演示结束")


cmd = sys.argv[1] if len(sys.argv) > 1 else "demo"
if cmd == "add":   add(*sys.argv[2:6])
elif cmd == "rm":  rm(sys.argv[2])
elif cmd == "clear": clear()
else: demo()
