"""Scrape up to 5000 latest followers for a single account."""
import asyncio
import json
import sys
from datetime import datetime

from playwright.async_api import async_playwright

from common import (
    BASE_DIR, new_browser_context, check_session_alive,
    log_error, random_delay,
)

MAX_FOLLOWERS = 5000


async def scrape_followers(account: str):
    output_path = BASE_DIR / "followers" / f"{account}.json"
    if output_path.exists():
        print(f"[SKIP] {account} followers already exist")
        return

    followers: list[dict] = []
    seen_ids: set[str] = set()

    async with async_playwright() as p:
        browser, context = await new_browser_context(p, headless=True)
        page = await context.new_page()

        async def handle_response(response):
            if "Followers" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    entries = (
                        data.get("data", {})
                        .get("followers_timeline", {})
                        .get("timeline", {})
                        .get("instructions", [{}])[0]
                        .get("entries", [])
                    )
                    for entry in entries:
                        user = (
                            entry.get("content", {})
                            .get("itemContent", {})
                            .get("user_results", {})
                            .get("result", {})
                        )
                        uid = user.get("rest_id")
                        if uid and uid not in seen_ids:
                            seen_ids.add(uid)
                            legacy = user.get("legacy", {})
                            followers.append({
                                "id": uid,
                                "screen_name": legacy.get("screen_name"),
                                "name": legacy.get("name"),
                                "created_at": legacy.get("created_at"),
                                "followers_count": legacy.get("followers_count"),
                                "friends_count": legacy.get("friends_count"),
                                "tweet_count": legacy.get("statuses_count"),
                                "description": legacy.get("description"),
                                "location": legacy.get("location"),
                                "verified": legacy.get("verified"),
                            })
                except Exception as e:
                    log_error("02d_followers", account, str(e))

        page.on("response", handle_response)

        try:
            await page.goto(
                f"https://x.com/{account}/followers",
                wait_until="networkidle",
                timeout=90000,
            )
            if not await check_session_alive(page):
                return

            stall_count = 0
            prev_count = 0
            while len(followers) < MAX_FOLLOWERS and stall_count < 3:
                await page.keyboard.press("End")
                await random_delay(8, 15)
                if len(followers) == prev_count:
                    stall_count += 1
                else:
                    stall_count = 0
                    prev_count = len(followers)
                    print(f"  @{account}: {len(followers)} followers...")

            output_path.write_text(json.dumps({
                "account": account,
                "scraped_at": datetime.utcnow().isoformat(),
                "total": len(followers),
                "followers": followers,
            }, ensure_ascii=False, indent=2))
            print(f"[DONE] @{account}: {len(followers)} followers saved")

        except Exception as e:
            log_error("02d_followers", account, str(e))
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    account = sys.argv[1] if len(sys.argv) > 1 else "penpen_popnews"
    asyncio.run(scrape_followers(account))
