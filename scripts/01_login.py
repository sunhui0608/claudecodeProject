"""Open a visible browser, wait for manual X login, then save the session."""
import asyncio
from pathlib import Path

from playwright.async_api import async_playwright

SESSION_PATH = Path.home() / "qingjian" / "x_session.json"


async def main():
    SESSION_PATH.parent.mkdir(parents=True, exist_ok=True)

    async with async_playwright() as p:
        browser = await p.chromium.launch(
            headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        context = await browser.new_context(
            viewport={"width": 1280, "height": 900},
            user_agent=(
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
            ),
        )
        page = await context.new_page()
        await page.goto("https://x.com/login", wait_until="domcontentloaded", timeout=60000)

        print("=" * 60)
        print("Browser opened. Please log in to X manually.")
        print("Handle any MFA/verification prompts in the browser window.")
        print("Once you can see the home timeline, press ENTER here.")
        print("=" * 60)
        input()

        await context.storage_state(path=str(SESSION_PATH))
        print(f"Session saved to: {SESSION_PATH}")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
