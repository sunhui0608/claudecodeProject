"""Scrape 6-month timeline for a single account via UserTweets GraphQL interception."""
import asyncio
import json
import sys
from datetime import datetime, timedelta, timezone

from playwright.async_api import async_playwright

from common import (
    BASE_DIR, new_browser_context, check_session_alive,
    log_error, random_delay,
)

CUTOFF = datetime.now(timezone.utc) - timedelta(days=180)


async def scrape_timeline(account: str):
    output_path = BASE_DIR / "timelines" / f"{account}.json"
    if output_path.exists():
        print(f"[SKIP] {account} timeline already exists")
        return

    tweets: list[dict] = []
    seen_ids: set[str] = set()
    reached_cutoff = False

    async with async_playwright() as p:
        browser, context = await new_browser_context(p, headless=True)
        page = await context.new_page()

        async def handle_response(response):
            nonlocal reached_cutoff
            if "UserTweets" in response.url and response.status == 200:
                try:
                    data = await response.json()
                    instructions = (
                        data.get("data", {})
                        .get("user", {})
                        .get("result", {})
                        .get("timeline_v2", {})
                        .get("timeline", {})
                        .get("instructions", [])
                    )
                    for instr in instructions:
                        for entry in instr.get("entries", []):
                            tweet_result = (
                                entry.get("content", {})
                                .get("itemContent", {})
                                .get("tweet_results", {})
                                .get("result", {})
                            )
                            if not tweet_result:
                                continue
                            legacy = tweet_result.get("legacy", {})
                            tweet_id = legacy.get("id_str") or tweet_result.get("rest_id")
                            if not tweet_id or tweet_id in seen_ids:
                                continue
                            created_str = legacy.get("created_at", "")
                            try:
                                created_dt = datetime.strptime(
                                    created_str, "%a %b %d %H:%M:%S +0000 %Y"
                                ).replace(tzinfo=timezone.utc)
                            except ValueError:
                                continue
                            if created_dt < CUTOFF:
                                reached_cutoff = True
                                continue
                            seen_ids.add(tweet_id)
                            tweets.append({
                                "id": tweet_id,
                                "created_at": created_str,
                                "created_at_iso": created_dt.isoformat(),
                                "text": legacy.get("full_text", ""),
                                "lang": legacy.get("lang"),
                                "retweet_count": legacy.get("retweet_count"),
                                "favorite_count": legacy.get("favorite_count"),
                                "reply_count": legacy.get("reply_count"),
                                "quote_count": legacy.get("quote_count"),
                                "is_retweet": "retweeted_status_result" in tweet_result,
                                "hashtags": [
                                    h["text"]
                                    for h in legacy.get("entities", {}).get("hashtags", [])
                                ],
                                "urls": [
                                    u.get("expanded_url")
                                    for u in legacy.get("entities", {}).get("urls", [])
                                ],
                                "user_mentions": [
                                    m.get("screen_name")
                                    for m in legacy.get("entities", {}).get("user_mentions", [])
                                ],
                            })
                except Exception as e:
                    log_error("02c_timeline", account, str(e))

        page.on("response", handle_response)

        try:
            await page.goto(f"https://x.com/{account}", wait_until="networkidle", timeout=90000)
            if not await check_session_alive(page):
                return

            stall_count = 0
            prev_count = 0
            while not reached_cutoff and stall_count < 4:
                await page.keyboard.press("End")
                await random_delay(8, 15)
                if len(tweets) == prev_count:
                    stall_count += 1
                else:
                    stall_count = 0
                    prev_count = len(tweets)
                    print(f"  @{account}: {len(tweets)} tweets...")

            output_path.write_text(json.dumps({
                "account": account,
                "scraped_at": datetime.utcnow().isoformat(),
                "cutoff_date": CUTOFF.isoformat(),
                "total": len(tweets),
                "tweets": sorted(tweets, key=lambda t: t["created_at_iso"], reverse=True),
            }, ensure_ascii=False, indent=2))
            print(f"[DONE] @{account}: {len(tweets)} tweets saved")

        except Exception as e:
            log_error("02c_timeline", account, str(e))
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    account = sys.argv[1] if len(sys.argv) > 1 else "penpen_popnews"
    asyncio.run(scrape_timeline(account))
