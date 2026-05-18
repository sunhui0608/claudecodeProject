"""Scrape all accounts that retweeted the target tweet (scroll to bottom)."""
import asyncio
import json
from datetime import datetime

from playwright.async_api import async_playwright

from common import BASE_DIR, new_browser_context, check_session_alive, log_error, random_delay

RETWEET_URL = "https://x.com/penpen_popnews/status/2005483654743744630/retweets"
OUTPUT = BASE_DIR / "retweeters.json"


async def main():
    retweeters = []
    seen_ids: set[str] = set()

    async with async_playwright() as p:
        browser, context = await new_browser_context(p, headless=True)
        page = await context.new_page()

        async def handle_response(response):
            if "Retweeters" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    entries = (
                        data.get("data", {})
                        .get("retweeters_timeline", {})
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
                            retweeters.append({
                                "id": uid,
                                "screen_name": legacy.get("screen_name"),
                                "name": legacy.get("name"),
                                "followers_count": legacy.get("followers_count"),
                                "friends_count": legacy.get("friends_count"),
                                "created_at": legacy.get("created_at"),
                                "verified": legacy.get("verified"),
                                "description": legacy.get("description"),
                            })
                except Exception as e:
                    log_error("02b_retweeters", "penpen_popnews", str(e))

        page.on("response", handle_response)

        try:
            await page.goto(RETWEET_URL, wait_until="networkidle", timeout=90000)
            if not await check_session_alive(page):
                return

            prev_count = 0
            stall_count = 0
            while stall_count < 3:
                await page.keyboard.press("End")
                await random_delay(3, 6)
                if len(retweeters) == prev_count:
                    stall_count += 1
                else:
                    stall_count = 0
                    prev_count = len(retweeters)
                    print(f"  {len(retweeters)} retweeters so far...")

            OUTPUT.write_text(json.dumps({
                "source_tweet": RETWEET_URL,
                "total": len(retweeters),
                "scraped_at": datetime.utcnow().isoformat(),
                "retweeters": retweeters,
            }, ensure_ascii=False, indent=2))
            print(f"Saved {len(retweeters)} retweeters to {OUTPUT}")

        except Exception as e:
            log_error("02b_retweeters", "penpen_popnews", str(e))
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
