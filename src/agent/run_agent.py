import sys
import uuid
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent))

from graph import build_agent, ask  # noqa: E402

if __name__ == "__main__":
    agent = build_agent()
    thread = str(uuid.uuid4())  # one conversation = one thread (memory)
    print("ცხრილის აგენტი. გასასვლელად: exit\n")
    while True:
        q = input("შენ: ").strip()
        if q.lower() in ("exit", "quit", ""):
            break
        answer, calls = ask(agent, q, thread)
        for name, args in calls:
            print(f"  [tool] {name}({args})")
        print("ბოტი:", answer, "\n")
