# Porsche 911 Scanner

Automated scanner for Porsche 911 listings across US classifieds.

## Features
- **Target:** Porsche 911 (all years 1986–2024), private sellers only
- **Filters:** < 100K miles, $15K minimum, nationwide USA
- **Dedup:** Rolling list of 100 most recent cars
- **Scan Interval:** Every 10 minutes (or as fast as rate limits allow)
- **Notifications:** Telegram messages for new listings
- **Sorted:** Newest listings first

## Sources
- Autotrader
- Cars.com
- Craigslist (rate-limited)
- Facebook Marketplace (browser automation)

## Setup

```bash
cd porsche-911-scanner
pip install requests beautifulsoup4 selenium  # selenium optional, for JS-heavy sites

export TELEGRAM_BOT_TOKEN="your_bot_token"
export TELEGRAM_CHAT_ID="6687839356"

python3 scanner.py
```

## Dedup List
Listings are stored in `seen_porsche_list.json` (max 100 entries). The scanner checks each new find against this list before sending notifications.

## Logs
- `scanner.log` — detailed scan logs
- stdout — real-time output

## Notes
- Some sites (Autotrader, Cars.com, Facebook) require JavaScript rendering; use Selenium for full coverage
- Craigslist has strict robots.txt; scraping may be rate-limited or blocked
- All scans respect site rate limits and User-Agent headers
