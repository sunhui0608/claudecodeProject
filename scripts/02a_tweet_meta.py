"""Scrape full metadata for target tweet via GraphQL interception."""
import asyncio
import json
from datetime import datetime

from playwright.async_api import async_playwright

from common import BASE_DIR, new_browser_context, check_session_alive, log_error

TARGET_URL = "https://x.com/penpen_popnews/status/2005483654743744630"
OUTPUT = BASE_DIR / "tweet_meta.json"


async def main():
    captured = {}

    async with async_playwright() as p:
        browser, context = await new_browser_context(p, headless=False)
        page = await context.new_page()

        async def handle_response(response):
            if "TweetDetail" in response.url and response.status == 200:
                try:
                    captured["graphql"] = await response.json()
                except Exception:
                    pass

        page.on("response", handle_response)

        try:
            await page.goto(TARGET_URL, wait_until="networkidle", timeout=90000)
            if not await check_session_alive(page):
                return

            await page.wait_for_selector('article[data-testid="tweet"]', timeout=30000)

            dom_data = await page.evaluate("""() => {
                const a = document.querySelector('article[data-testid="tweet"]');
                if (!a) return null;
                return {
                    text: a.querySelector('[data-testid="tweetText"]')?.innerText,
                    timestamp: a.querySelector('time')?.getAttribute('datetime'),
                    likes: a.querySelector('[data-testid="like"] span')?.innerText,
                    retweets: a.querySelector('[data-testid="retweet"] span')?.innerText,
                    replies: a.querySelector('[data-testid="reply"] span')?.innerText,
                    views: a.querySelector('[data-testid="app-text-transition-container"] span')?.innerText,
                };
            }""")

            result = {
                "url": TARGET_URL,
                "scraped_at": datetime.utcnow().isoformat(),
                "dom": dom_data,
                "graphql": captured.get("graphql"),
            }
            OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2))
            print(f"Saved tweet metadata to {OUTPUT}")

        except Exception as e:
            log_error("02a_tweet_meta", "penpen_popnews", str(e))
            raise
        finally:
            await browser.close()


if __name__ == "__main__":
    asyncio.run(main())
