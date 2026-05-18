#!/usr/bin/env bash
set -euo pipefail

echo "=== Creating directory structure ==="
mkdir -p ~/qingjian/寺庙核查/{timelines,followers,analysis}
mkdir -p ~/qingjian/browser_profile

echo "=== Installing Python dependencies ==="
pip3 install playwright playwright-stealth scikit-learn pandas numpy

echo "=== Downloading Chromium browser binary ==="
python3 -m playwright install chromium
python3 -m playwright install-deps chromium

echo "=== Verifying installation ==="
python3 -c "from playwright.async_api import async_playwright; print('playwright OK')"
python3 -c "from playwright_stealth import stealth_async; print('playwright-stealth OK')"
python3 -c "from sklearn.feature_extraction.text import TfidfVectorizer; print('scikit-learn OK')"

echo ""
echo "=== Setup complete! Next steps: ==="
echo "1. Run: python3 scripts/01_login.py"
echo "   (A browser window will open — log in manually, then press ENTER)"
echo "2. Run: python3 scripts/02a_tweet_meta.py"
echo "3. Run: python3 scripts/02b_retweeters.py"
echo "4. Run: python3 scripts/03_run_parallel.py   (parallel scrape all 15 accounts)"
echo "5. Run: python3 scripts/04_analyze.py"
echo "6. Run: python3 scripts/05_report.py"
