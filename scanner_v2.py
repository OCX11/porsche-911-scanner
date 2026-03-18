#!/usr/bin/env python3
"""
Porsche 911 Scanner v2.0 - Lean, efficient, multi-site
PCA Mart + Rennlist (coming next)
10-min or faster cycles, dedup, Telegram notifications
"""

import json
import os
import sys
import time
import logging
import asyncio
from datetime import datetime
from pathlib import Path
import hashlib

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(levelname)s] %(message)s',
    handlers=[
        logging.FileHandler('scanner.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

CONFIG = {
    'dedup_file': 'seen_porsche_list.json',
    'max_seen_cars': 100,
    'scan_interval': 600,  # 10 minutes
    'telegram_token': os.getenv('TELEGRAM_BOT_TOKEN'),
    'telegram_chat_id': os.getenv('TELEGRAM_CHAT_ID', '6687839356'),
}

class PorscheScanner:
    def __init__(self):
        self.seen_cars = self._load_seen()
        self.new_listings = []

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
        sorted_seen = sorted(
            self.seen_cars.items(),
            key=lambda x: x[1].get('seen_at', 0),
            reverse=True
        )[:CONFIG['max_seen_cars']]
        self.seen_cars = dict(sorted_seen)

        with open(CONFIG['dedup_file'], 'w') as f:
            json.dump(self.seen_cars, f, indent=2)
        logger.info(f"Saved {len(self.seen_cars)} cars to dedup list")

    def _hash_listing(self, url: str, title: str) -> str:
        """Create unique hash for listing."""
        key = f"{url}:{title}".encode()
        return hashlib.md5(key).hexdigest()

    def _is_duplicate(self, url: str, title: str) -> bool:
        """Check if listing already seen."""
        listing_hash = self._hash_listing(url, title)
        return listing_hash in self.seen_cars

    def _add_seen(self, listing: dict):
        """Add to dedup list."""
        url = listing.get('url', '')
        title = listing.get('title', '')
        listing_hash = self._hash_listing(url, title)
        self.seen_cars[listing_hash] = {
            'url': url,
            'title': title,
            'price': listing.get('price'),
            'mileage': listing.get('mileage'),
            'location': listing.get('location'),
            'source': listing.get('source'),
            'seen_at': int(time.time())
        }

    def notify_telegram(self, listing: dict) -> bool:
        """Send Telegram notification in standard format."""
        if not CONFIG['telegram_token'] or not CONFIG['telegram_chat_id']:
            logger.warning("Telegram not configured")
            return False

        message = self._format_telegram(listing)

        import requests
        url = f"https://api.telegram.org/bot{CONFIG['telegram_token']}/sendMessage"
        payload = {
            'chat_id': CONFIG['telegram_chat_id'],
            'text': message,
            'parse_mode': 'Markdown'
        }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                logger.info(f"Telegram: {listing['year']} {listing['model']} - ${listing['price']:,}")
                return True
            else:
                logger.error(f"Telegram API: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"Telegram send failed: {e}")
            return False

    def _format_telegram(self, listing: dict) -> str:
        """Format listing for Telegram (standard format)."""
        year = listing.get('year', 'N/A')
        model = listing.get('model', 'N/A')
        price = listing.get('price', 0)
        mileage = listing.get('mileage', 0)
        vin = listing.get('vin', '')
        location = listing.get('location', 'N/A')
        transmission = listing.get('transmission', 'N/A')
        posted_date = listing.get('posted_date', datetime.now().strftime('%B %d, %Y'))
        url = listing.get('url', 'N/A')
        thumbnail = listing.get('thumbnail', '')
        source = listing.get('source', 'N/A')

        msg = f"""🚗 New Porsche Listing Found

{year} Porsche 911 {model}
{model}

"""
        if thumbnail:
            msg += f"📷 [View Photo]({thumbnail})\n\n"

        msg += f"""Miles: {mileage:,}
Price: ${price:,}"""
        if vin:
            msg += f"\nVIN: {vin}"
        msg += f"""
Location: {location}
Seller: Private
Site: {source}
Date Found: {posted_date}

🔗 [View Full Listing]({url})"""

        return msg

    async def run_cycle(self):
        """Execute one scan cycle."""
        logger.info("=" * 60)
        logger.info(f"Starting scan cycle at {datetime.now().isoformat()}")

        self.new_listings = []

        # Import and run scrapers
        try:
            from scrapers.pca_mart import scrape_pca_mart
            listings = await scrape_pca_mart()
            
            for listing in listings:
                url = listing.get('url', '')
                title = listing.get('title', '')

                if not self._is_duplicate(url, title):
                    self.new_listings.append(listing)
                    self._add_seen(listing)
                    self.notify_telegram(listing)
                    time.sleep(1)  # Don't spam Telegram

        except ImportError:
            logger.error("PCA Mart scraper not available")
        except Exception as e:
            logger.error(f"PCA Mart cycle error: {e}")

        # Save state
        self._save_seen()

        logger.info(f"Scan complete: {len(self.new_listings)} new listings")
        logger.info(f"Total rolling list: {len(self.seen_cars)}")
        logger.info("=" * 60)

    async def loop(self):
        """Run scanner in continuous loop."""
        logger.info(f"Starting Porsche 911 Scanner v2.0")
        logger.info(f"Config: scan_interval={CONFIG['scan_interval']}s, max_seen={CONFIG['max_seen_cars']}")

        while True:
            try:
                await self.run_cycle()
                logger.info(f"Waiting {CONFIG['scan_interval']}s until next scan...")
                await asyncio.sleep(CONFIG['scan_interval'])
            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except Exception as e:
                logger.error(f"Cycle error: {e}")
                await asyncio.sleep(CONFIG['scan_interval'])


async def main():
    scanner = PorscheScanner()
    await scanner.loop()


if __name__ == '__main__':
    asyncio.run(main())
