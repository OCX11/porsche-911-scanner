#!/usr/bin/env python3
"""
Porsche Scanner LIVE - 10-min cycles, PCA Mart + Rennlist (coming)
Dedup rolling list, Telegram photo notifications
"""

import json
import os
import sys
import time
import logging
import asyncio
import hashlib
from datetime import datetime
from pathlib import Path
from dotenv import load_dotenv

try:
    import requests
except ImportError:
    print("ERROR: pip install requests python-dotenv")
    exit(1)

# Load .env
load_dotenv()

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
                    logger.info(f"Loaded {len(data)} seen cars from dedup list")
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

    def _hash_listing(self, ad_number: str) -> str:
        """Create unique hash by ad number."""
        return hashlib.md5(str(ad_number).encode()).hexdigest()

    def _is_duplicate(self, ad_number: str) -> bool:
        """Check if listing already seen."""
        listing_hash = self._hash_listing(ad_number)
        return listing_hash in self.seen_cars

    def _add_seen(self, listing: dict):
        """Add to dedup list."""
        ad_number = listing.get('ad_number', '')
        listing_hash = self._hash_listing(ad_number)
        self.seen_cars[listing_hash] = {
            'ad_number': ad_number,
            'title': listing.get('title'),
            'price': listing.get('price'),
            'mileage': listing.get('mileage'),
            'source': listing.get('source'),
            'seen_at': int(time.time())
        }

    def send_telegram_photo(self, listing: dict) -> bool:
        """Send Telegram notification with photo + caption."""
        if not CONFIG['telegram_token'] or not CONFIG['telegram_chat_id']:
            logger.warning("Telegram not configured")
            return False

        token = CONFIG['telegram_token']
        chat_id = CONFIG['telegram_chat_id']
        thumbnail = listing.get('thumbnail', '')
        caption = self._format_caption(listing)

        # If we have a thumbnail, use sendPhoto (image + caption)
        if thumbnail:
            url = f"https://api.telegram.org/bot{token}/sendPhoto"
            payload = {
                'chat_id': chat_id,
                'photo': thumbnail,
                'caption': caption,
                'parse_mode': 'Markdown'
            }
        else:
            # Fallback to sendMessage if no image
            url = f"https://api.telegram.org/bot{token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': caption,
                'parse_mode': 'Markdown'
            }

        try:
            resp = requests.post(url, json=payload, timeout=10)
            if resp.status_code == 200:
                year = listing.get('year', 'N/A')
                model = listing.get('model', 'N/A')
                price = listing.get('price', 0)
                source = listing.get('source', 'N/A')
                logger.info(f"✓ Telegram: {year} {model} - ${price:,} from {source}")
                return True
            else:
                logger.error(f"✗ Telegram API: {resp.status_code}")
                return False
        except Exception as e:
            logger.error(f"✗ Telegram send failed: {e}")
            return False

    def _format_caption(self, listing: dict) -> str:
        """Format caption for Telegram photo."""
        year = listing.get('year', 'N/A')
        model = listing.get('model', 'N/A')
        price = listing.get('price', 0)
        mileage = listing.get('mileage', 0)
        published_date = listing.get('published_date', 'N/A')
        url = listing.get('url', 'N/A')
        ad_number = listing.get('ad_number', 'N/A')
        source = listing.get('source', 'N/A')

        caption = f"""🚗 *{year} Porsche {model}*

*Price:* ${price:,}
*Mileage:* {mileage:,} miles
*Ad #:* {ad_number}
*Listed:* {published_date}
*Source:* {source}

[View Full Listing]({url})"""

        return caption

    async def run_cycle(self):
        """Execute one scan cycle."""
        logger.info("=" * 60)
        logger.info(f"Starting scan at {datetime.now().isoformat()}")

        self.new_listings = []

        try:
            from scrapers.pca_mart_final import scrape_pca_mart
            from scrapers.rennlist import scrape_rennlist
            
            pca_listings = await scrape_pca_mart()
            rennlist_listings = scrape_rennlist(page=1)
            
            # Combine both sources
            listings = pca_listings + rennlist_listings

            for listing in listings:
                ad_number = listing.get('ad_number', '')

                if not self._is_duplicate(ad_number):
                    self.new_listings.append(listing)
                    self._add_seen(listing)
                    self.send_telegram_photo(listing)
                    time.sleep(1)  # Rate limit Telegram

        except Exception as e:
            logger.error(f"PCA cycle error: {e}")

        # Save state
        self._save_seen()

        logger.info(f"✓ Found {len(self.new_listings)} new listings this cycle")
        logger.info(f"✓ Rolling list total: {len(self.seen_cars)} cars")
        logger.info("=" * 60)

    async def loop(self):
        """Run scanner in continuous loop."""
        logger.info("🦞 Starting Porsche Scanner LIVE")
        logger.info(f"PCA Mart every {CONFIG['scan_interval']}s ({CONFIG['scan_interval']//60}min)")
        logger.info(f"Telegram bot configured")
        logger.info(f"Rennlist: coming next")

        while True:
            try:
                await self.run_cycle()
                logger.info(f"Next scan in {CONFIG['scan_interval']}s...")
                await asyncio.sleep(CONFIG['scan_interval'])
            except KeyboardInterrupt:
                logger.info("Stopped by user")
                break
            except Exception as e:
                logger.error(f"Loop error: {e}")
                await asyncio.sleep(CONFIG['scan_interval'])


async def main():
    scanner = PorscheScanner()
    await scanner.loop()


if __name__ == '__main__':
    asyncio.run(main())
