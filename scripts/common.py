"""Shared utilities: session management, stealth setup, retry logic, error logging."""
import asyncio
import json
import os
import random
from datetime import datetime
from pathlib import Path

os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", "/opt/pw-browsers")

from playwright.async_api import Browser, BrowserContext, async_playwright
from playwright_stealth import Stealth

_stealth = Stealth()

SESSION_PATH = Path.home() / "qingjian" / "x_session.json"
BASE_DIR = Path.home() / "qingjian" / "寺庙核查"
ERROR_LOG = Path.home() / "qingjian" / "error.log"

ACCOUNTS = [
    "lammichaeltw", "penpen_popnews", "FreeAll_protest", "shKdufS8Ln39062",
    "zetu_rrr", "tourouken555", "ChinaVideos1", "manchuriareview",
    "sam51824016070", "QuanLujun", "TruthMedia123", "zhihui999",
    "LucyZha94759559", "xinwendiaocha", "DXDWX999",
]

USER_AGENT = (
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
)


def is_session_valid() -> bool:
    if not SESSION_PATH.exists():
        return False
    data = json.loads(SESSION_PATH.read_text())
    for cookie in data.get("cookies", []):
        if cookie.get("name") == "auth_token" and "x.com" in cookie.get("domain", ""):
            return True
    return False


def log_error(script: str, account: str, error: str):
    entry = {
        "timestamp": datetime.utcnow().isoformat(),
        "script": script,
        "account": account,
        "error": error,
    }
    with open(ERROR_LOG, "a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")
    print(f"[ERROR] {script}/{account}: {error}")


async def new_browser_context(p, headless: bool = True) -> tuple[Browser, BrowserContext]:
    browser = await p.chromium.launch(
        headless=headless,
        args=[
            "--no-sandbox",
            "--disable-blink-features=AutomationControlled",
            "--disable-dev-shm-usage",
        ],
    )
    storage = str(SESSION_PATH) if SESSION_PATH.exists() else None
    context = await browser.new_context(
        storage_state=storage,
        viewport={"width": 1280, "height": 900},
        user_agent=USER_AGENT,
        locale="zh-TW",
        timezone_id="Asia/Taipei",
        ignore_https_errors=True,
    )
    await _stealth.apply_stealth_async(context)
    return browser, context


async def check_session_alive(page) -> bool:
    url = page.url
    if "login" in url or "/i/flow/login" in url:
        print("[ERROR] Session expired. Re-run scripts/01_login.py")
        return False
    content = await page.content()
    if '"errors"' in content and '"code":32' in content:
        print("[ERROR] Auth error (code 32). Re-run scripts/01_login.py")
        return False
    return True


async def random_delay(min_s: float = 8, max_s: float = 15):
    await asyncio.sleep(random.uniform(min_s, max_s))


async def with_retry(coro_fn, retries: int = 3, script: str = "", account: str = ""):
    for attempt in range(retries):
        try:
            return await coro_fn()
        except Exception as e:
            if attempt == retries - 1:
                log_error(script, account, str(e))
                raise
            await asyncio.sleep(random.uniform(4, 8))
