"""
Orchestrate parallel scraping of all 15 accounts.
Splits accounts into 3 groups of 5; each group runs in a separate process.
task_queue.json tracks state to allow safe restarts.
"""
import asyncio
import fcntl
import json
import multiprocessing
import random
from datetime import datetime
from pathlib import Path

BASE_DIR = Path.home() / "qingjian" / "寺庙核查"
TASK_QUEUE = Path.home() / "qingjian" / "task_queue.json"

ACCOUNTS = [
    "lammichaeltw", "penpen_popnews", "FreeAll_protest", "shKdufS8Ln39062",
    "zetu_rrr", "tourouken555", "ChinaVideos1", "manchuriareview",
    "sam51824016070", "QuanLujun", "TruthMedia123", "zhihui999",
    "LucyZha94759559", "xinwendiaocha", "DXDWX999",
]

GROUPS = [ACCOUNTS[i:i + 5] for i in range(0, len(ACCOUNTS), 5)]


def init_task_queue():
    if TASK_QUEUE.exists():
        return
    tasks = {
        acc: {"timeline": "pending", "followers": "pending"}
        for acc in ACCOUNTS
    }
    TASK_QUEUE.write_text(json.dumps(
        {"created_at": datetime.utcnow().isoformat(), "tasks": tasks},
        indent=2,
    ))


def update_queue(account: str, task_type: str, status: str):
    with open(TASK_QUEUE, "r+") as f:
        fcntl.flock(f, fcntl.LOCK_EX)
        data = json.load(f)
        data["tasks"][account][task_type] = status
        f.seek(0)
        json.dump(data, f, indent=2)
        f.truncate()
        fcntl.flock(f, fcntl.LOCK_UN)


def should_skip(account: str, task_type: str) -> bool:
    data = json.loads(TASK_QUEUE.read_text())
    return data["tasks"][account][task_type] == "done"


def run_group(accounts: list[str], group_id: int):
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from common import random_delay as _random_delay

    # Import scrapers inside subprocess to avoid sharing event loops
    from importlib import import_module
    timeline_mod = import_module("02c_timeline_scraper")
    followers_mod = import_module("02d_followers_scraper")

    async def _run():
        for account in accounts:
            print(f"[Group {group_id}] Starting @{account}")

            if not should_skip(account, "timeline"):
                update_queue(account, "timeline", "in_progress")
                try:
                    await timeline_mod.scrape_timeline(account)
                    update_queue(account, "timeline", "done")
                except Exception as e:
                    update_queue(account, "timeline", "error")
                    print(f"[Group {group_id}] @{account} timeline error: {e}")

            await asyncio.sleep(random.uniform(8, 15))

            if not should_skip(account, "followers"):
                update_queue(account, "followers", "in_progress")
                try:
                    await followers_mod.scrape_followers(account)
                    update_queue(account, "followers", "done")
                except Exception as e:
                    update_queue(account, "followers", "error")
                    print(f"[Group {group_id}] @{account} followers error: {e}")

            await asyncio.sleep(random.uniform(8, 15))

        print(f"[Group {group_id}] All accounts complete")

    asyncio.run(_run())


def print_summary():
    data = json.loads(TASK_QUEUE.read_text())
    print("\n=== Task Summary ===")
    for acc, tasks in data["tasks"].items():
        tl = tasks["timeline"]
        fo = tasks["followers"]
        print(f"  @{acc:<24} timeline={tl:<12} followers={fo}")


if __name__ == "__main__":
    init_task_queue()
    print(f"Starting parallel scrape: {len(ACCOUNTS)} accounts in {len(GROUPS)} groups")

    with multiprocessing.Pool(processes=3) as pool:
        pool.starmap(run_group, [(group, i) for i, group in enumerate(GROUPS)])

    print_summary()
    print("\nAll groups complete. Run python3 scripts/04_analyze.py next.")
