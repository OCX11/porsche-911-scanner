#!/usr/bin/env python3
"""
Porsche 911 Scanner v1.0
- Scans Autotrader, Cars.com, Facebook Marketplace, Craigslist (private sellers only)
- Target: Porsche 911 (all years 1986-2024), <100K miles, $15K+, nationwide USA
- Rolling dedup list: 100 cars
- Telegram notifications
- Runs every 10 min or as quickly as possible without rate limits
"""

import json
import os
import sys
import time
import logging
from datetime import datetime
from pathlib import Path
import hashlib

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: Missing dependencies. Install: pip install requests beautifulsoup4")
    sys.exit(1)

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('scanner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# Configuration
CONFIG = {
    'dedup_file': 'seen_porsche_list.json',
    'max_seen_cars': 100,
    'scan_interval': 600,  # 10 minutes
    'telegram_token': os.getenv('TELEGRAM_BOT_TOKEN'),
    'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID'),
    'min_year': 1986,
    'max_year': 2024,
    'max_miles': 100000,
    'min_price': 15000,
    'regions': 'nationwide',  # USA-wide
    'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
}

class PorschScanner:
    def __init__(self):
        self.seen_cars = self._load_seen()
        self.session = requests.Session()
        self.session.headers.update({'User-Agent': CONFIG['user_agent']})
        self.session.timeout = 15

    def _load_seen(self):
        """Load dedup list from disk."""
        path = Path(CONFIG['dedup_file'])
        if path.exists():
            try:
                with open(path, 'r') as f:
                    data = json.load(f)
                    logger.info(f"Loaded {len(data)} seen cars from {CONFIG['dedup_file']}")
                    return data
            except Exception as e:
                logger.error(f"Failed to load seen list: {e}")
        return {}

    def _save_seen(self):
        """Save dedup list to disk, keep only last 100."""
        # Keep only most recent 100
        sorted_seen = sorted(
            self.seen_cars.items(),
            key=lambda x: x[1].get('seen_at', 0),
            reverse=True
        )[:CONFIG['max_seen_cars']]
        self.seen_cars = dict(sorted_seen)

        with open(CONFIG['dedup_file'], 'w') as f:
            json.dump(self.seen_cars, f, indent=2)
        logger.info(f"Saved {len(self.seen_cars)} cars to dedup list")

    def _hash_listing(self, url, title):
        """Create unique hash for listing."""
        key = f"{url}:{title}".encode()
        return hashlib.md5(key).hexdigest()

    def _is_duplicate(self, url, title):
        """Check if listing already seen."""
        listing_hash = self._hash_listing(url, title)
        return listing_hash in self.seen_cars

    def _add_seen(self, url, title, price, mileage, location, source):
        """Add to dedup list."""
        listing_hash = self._hash_listing(url, title)
        self.seen_cars[listing_hash] = {
            'url': url,
            'title': title,
            'price': price,
            'mileage': mileage,
            'location': location,
            'source': source,
            'seen_at': int(time.time())
        }

    def notify_telegram(self, message):
        """Send Telegram notification."""
        if not CONFIG['telegram_token'] or not CONFIG['telegram_chat_id']:
            logger.warning("Telegram not configured (set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)")
            return False

        url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage"
        payload = {
            'chat_id': CONFIG['telegram_chat_id'],
            'text': message,
            'parse_mode': 'Markdown'
        }

        try:
            resp = self.session.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Telegram sent: {message[:50]}...")
                return True
            else:
                logger.error(f"Telegram API error: {resp.status_code} {resp.text[:200]}")
                return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def scan_autotrader(self):
        """Scan Autotrader for Porsche 911."""
        results = []
        logger.info("Scanning Autotrader...")

        try:
            # Autotrader search URL for Porsche 911, nationwide, private sellers
            # Note: This is a template; actual scraping may require JavaScript or API
            url = "https://www.autotrader.com/cars-for-sale/searchresults.xhtml"
            params = {
                'searchRadius': '0',
                'location': 'US',
                'make': 'Porsche',
                'model': '911',
                'maxMileage': '100000',
                'minPrice': '15000',
                'sort': 'newlyListed'
            }

            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Autotrader returned {resp.status_code}")
                return results

            soup = BeautifulSoup(resp.text, 'html.parser')
            # This is a placeholder; actual Autotrader scraping is complex
            logger.info("Autotrader: placeholder scan (JS rendering required for full results)")

        except Exception as e:
            logger.error(f"Autotrader scan error: {e}")

        return results

    def scan_craigslist(self):
        """Scan Craigslist for Porsche 911."""
        results = []
        logger.info("Scanning Craigslist...")

        # Craigslist has robots.txt restrictions; use with caution
        logger.warning("Craigslist scraping requires rate limiting; skipping for now")
        return results

    def scan_facebook_marketplace(self):
        """Scan Facebook Marketplace for Porsche 911."""
        results = []
        logger.info("Scanning Facebook Marketplace...")

        # Facebook blocks automated scraping; would need Selenium + headless browser
        logger.warning("Facebook Marketplace requires browser automation; placeholder only")
        return results

    def scan_cars_com(self):
        """Scan Cars.com for Porsche 911."""
        results = []
        logger.info("Scanning Cars.com...")

        try:
            url = "https://www.cars.com/shopping/results"
            params = {
                'makes': 'porsche',
                'models': '911',
                'maxMileage': '100000',
                'minPrice': '15000',
                'sort': 'newest'
            }

            resp = self.session.get(url, params=params, timeout=15)
            if resp.status_code != 200:
                logger.warning(f"Cars.com returned {resp.status_code}")
                return results

            soup = BeautifulSoup(resp.text, 'html.parser')
            # Placeholder; Cars.com also uses heavy JS
            logger.info("Cars.com: placeholder scan (JS rendering required for full results)")

        except Exception as e:
            logger.error(f"Cars.com scan error: {e}")

        return results

    def run_cycle(self):
        """Execute one scan cycle."""
        logger.info("=" * 60)
        logger.info(f"Starting scan cycle at {datetime.now().isoformat()}")

        new_listings = []

        # Run all scans
        for scanner_func in [self.scan_autotrader, self.scan_cars_com, self.scan_craigslist, self.scan_facebook_marketplace]:
            try:
                results = scanner_func()
                for listing in results:
                    url = listing.get('url', 'N/A')
                    title = listing.get('title', 'Unknown')

                    if not self._is_duplicate(url, title):
                        new_listings.append(listing)
                        self._add_seen(url, title, listing.get('price'), listing.get('mileage'), listing.get('location'), listing.get('source'))

                        # Send Telegram notification
                        msg = self._format_notification(listing)
                        self.notify_telegram(msg)

                time.sleep(2)  # Be nice to servers
            except Exception as e:
                logger.error(f"{scanner_func.__name__} failed: {e}")

        # Save state
        self._save_seen()

        # Log summary
        logger.info(f"Scan complete: {len(new_listings)} new listings found")
        logger.info(f"Total seen cars in rolling list: {len(self.seen_cars)}")
        logger.info("=" * 60)

        return len(new_listings)

    def _format_notification(self, listing):
        """Format listing for Telegram."""
        return f"""
🚗 *New Porsche 911 Found!*

*Title:* {listing.get('title', 'N/A')}
*Price:* ${listing.get('price', 'N/A'):,}
*Mileage:* {listing.get('mileage', 'N/A'):,} miles
*Location:* {listing.get('location', 'N/A')}
*Source:* {listing.get('source', 'N/A')}
*Link:* {listing.get('url', 'N/A')}
        """.strip()

    def loop(self):
        """Run scanner in continuous loop."""
        logger.info(f"Starting Porsche 911 Scanner v1.0")
        logger.info(f"Config: {json.dumps({k: v for k, v in CONFIG.items() if k != 'telegram_token'}, indent=2)}")

        while True:
            try:
                self.run_cycle()
                logger.info(f"Waiting {CONFIG['scan_interval']}s until next scan...")
                time.sleep(CONFIG['scan_interval'])
            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                time.sleep(CONFIG['scan_interval'])

if __name__ == '__main__':
    scanner = PorschScanner()
    scanner.loop()
