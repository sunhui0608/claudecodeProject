"""
Run all three analyses after data collection is complete:
  1. TF-IDF content similarity matrix
  2. 48-hour coordination window detection
  3. Common follower / suspicious account analysis
"""
import json
from collections import defaultdict
from datetime import datetime, timedelta, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

BASE_DIR = Path.home() / "qingjian" / "寺庙核查"
ANALYSIS_DIR = BASE_DIR / "analysis"

ACCOUNTS = [
    "lammichaeltw", "penpen_popnews", "FreeAll_protest", "shKdufS8Ln39062",
    "zetu_rrr", "tourouken555", "ChinaVideos1", "manchuriareview",
    "sam51824016070", "QuanLujun", "TruthMedia123", "zhihui999",
    "LucyZha94759559", "xinwendiaocha", "DXDWX999",
]

MIN_COMMON_TARGETS = 5
COORDINATION_WINDOW_HOURS = 48


# ─── 1. TF-IDF similarity ──────────────────────────────────────────────────

def load_timelines() -> dict[str, str]:
    texts: dict[str, str] = {}
    for acc in ACCOUNTS:
        path = BASE_DIR / "timelines" / f"{acc}.json"
        if not path.exists():
            print(f"[WARN] Missing timeline: {acc}")
            continue
        data = json.loads(path.read_text())
        original_tweets = [t["text"] for t in data["tweets"] if not t.get("is_retweet")]
        texts[acc] = " ".join(original_tweets)
    return texts


def compute_tfidf(texts: dict[str, str]) -> pd.DataFrame:
    accounts = list(texts.keys())
    corpus = [texts[a] for a in accounts]
    vectorizer = TfidfVectorizer(
        min_df=2,
        max_df=0.9,
        ngram_range=(1, 3),
        analyzer="char_wb",
        sublinear_tf=True,
    )
    matrix = vectorizer.fit_transform(corpus)
    sim = cosine_similarity(matrix)
    return pd.DataFrame(sim, index=accounts, columns=accounts)


def run_tfidf():
    print("Running TF-IDF analysis...")
    texts = load_timelines()
    if len(texts) < 2:
        print("[WARN] Not enough timelines for TF-IDF. Skipping.")
        return
    df = compute_tfidf(texts)
    df.to_csv(ANALYSIS_DIR / "tfidf_similarity_matrix.csv")
    df.to_json(ANALYSIS_DIR / "tfidf_similarity_matrix.json", orient="split")

    # Print focal comparison
    if "lammichaeltw" in df.index and "penpen_popnews" in df.columns:
        score = df.loc["lammichaeltw", "penpen_popnews"]
        print(f"  @lammichaeltw vs @penpen_popnews similarity: {score:.4f}")

    print(f"  Saved to {ANALYSIS_DIR}/tfidf_similarity_matrix.*")


# ─── 2. Coordination detection ────────────────────────────────────────────

def run_coordination():
    print("Running coordination detection...")
    all_tweets: list[dict] = []

    for acc in ACCOUNTS:
        path = BASE_DIR / "timelines" / f"{acc}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for t in data["tweets"]:
            try:
                created_dt = datetime.fromisoformat(t["created_at_iso"])
            except (ValueError, KeyError):
                continue
            all_tweets.append({
                "account": acc,
                "id": t["id"],
                "text": t["text"],
                "created_at": created_dt,
                "hashtags": t.get("hashtags", []),
            })

    # Hashtag-based coordination
    hashtag_posts: dict[str, list] = defaultdict(list)
    for t in all_tweets:
        for tag in t["hashtags"]:
            hashtag_posts[tag.lower()].append(t)

    events: list[dict] = []
    window = timedelta(hours=COORDINATION_WINDOW_HOURS)

    for tag, posts in hashtag_posts.items():
        if len(posts) < 2:
            continue
        posts.sort(key=lambda p: p["created_at"])
        for i, post in enumerate(posts):
            group = [p for p in posts[i:] if p["created_at"] - post["created_at"] <= window]
            accs = list({p["account"] for p in group})
            if len(accs) >= 2:
                events.append({
                    "type": "hashtag_coordination",
                    "hashtag": tag,
                    "accounts": accs,
                    "tweet_count": len(group),
                    "window_start": group[0]["created_at"].isoformat(),
                    "window_end": group[-1]["created_at"].isoformat(),
                    "sample_texts": [p["text"][:120] for p in group[:3]],
                })

    # Deduplicate overlapping windows for same hashtag
    seen = set()
    deduped: list[dict] = []
    for e in events:
        key = (e["hashtag"], frozenset(e["accounts"]), e["window_start"])
        if key not in seen:
            seen.add(key)
            deduped.append(e)

    deduped.sort(key=lambda e: len(e["accounts"]), reverse=True)

    output = ANALYSIS_DIR / "coordination_events.json"
    output.write_text(json.dumps(deduped, ensure_ascii=False, indent=2))
    print(f"  Found {len(deduped)} coordination events → {output}")


# ─── 3. Common follower analysis ──────────────────────────────────────────

def run_common_followers():
    print("Running common follower analysis...")
    follower_to_targets: dict[str, set] = defaultdict(set)
    follower_meta: dict[str, dict] = {}

    for acc in ACCOUNTS:
        path = BASE_DIR / "followers" / f"{acc}.json"
        if not path.exists():
            continue
        data = json.loads(path.read_text())
        for f in data["followers"]:
            uid = f["id"]
            follower_to_targets[uid].add(acc)
            if uid not in follower_meta:
                follower_meta[uid] = f

    suspicious: list[dict] = []
    for uid, targets in follower_to_targets.items():
        if len(targets) < MIN_COMMON_TARGETS:
            continue
        meta = follower_meta[uid]
        suspicious.append({
            "follower_id": uid,
            "screen_name": meta.get("screen_name"),
            "follows_targets": sorted(targets),
            "target_count": len(targets),
            "account_created_at": meta.get("created_at"),
            "followers_count": meta.get("followers_count"),
            "friends_count": meta.get("friends_count"),
            "tweet_count": meta.get("tweet_count"),
            "description": meta.get("description"),
        })

    suspicious.sort(key=lambda x: x["target_count"], reverse=True)

    # Flag registration clusters: accounts created within same 30-day window
    def parse_created(s: str | None) -> datetime | None:
        if not s:
            return None
        try:
            return datetime.strptime(s, "%a %b %d %H:%M:%S +0000 %Y").replace(
                tzinfo=timezone.utc
            )
        except ValueError:
            return None

    for entry in suspicious:
        dt = parse_created(entry["account_created_at"])
        entry["created_at_parsed"] = dt.isoformat() if dt else None

    output = ANALYSIS_DIR / "common_followers.json"
    output.write_text(json.dumps(suspicious, ensure_ascii=False, indent=2))

    df = pd.DataFrame(suspicious)
    if not df.empty:
        df.to_csv(ANALYSIS_DIR / "common_followers.csv", index=False)

    print(f"  Found {len(suspicious)} suspicious followers → {output}")


# ─── Main ──────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    ANALYSIS_DIR.mkdir(parents=True, exist_ok=True)
    run_tfidf()
    run_coordination()
    run_common_followers()
    print("\nAnalysis complete. Run python3 scripts/05_report.py next.")
