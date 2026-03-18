#!/usr/bin/env python3
"""
PCA Mart Scraper - Porsche Club of America Classifieds
https://www.pca.org/classifieds
Target: Porsche 911, 1986-2024, <100K miles, $15K+, private sellers
"""

import json
import logging
from datetime import datetime
from typing import Dict, List
import hashlib

try:
    from playwright.async_api import async_playwright, Browser
except ImportError:
    print("ERROR: Install Playwright: pip install playwright")
    print("Then: playwright install chromium")
    exit(1)

logger = logging.getLogger(__name__)

class PCAMartScraper:
    """PCA Mart scraper using Playwright for JS-heavy site."""

    BASE_URL = "https://www.pca.org/classifieds"
    FILTERS = {
        'category': 'vehicles',
        'make': 'Porsche',
        'model': '911',
        'min_year': 1986,
        'max_year': 2024,
        'max_miles': 100000,
        'min_price': 15000,
        'seller_type': 'private'  # PCA allows private sellers
    }

    def __init__(self):
        self.browser = None
        self.page = None
        self.seen_hashes = set()

    async def init_browser(self):
        """Start Playwright browser."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page()
        self.page.set_default_timeout(30000)
        await self.page.set_viewport_size({"width": 1920, "height": 1080})

    async def close_browser(self):
        """Close browser."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()

    def _hash_listing(self, url: str, title: str) -> str:
        """Generate unique hash for listing."""
        key = f"{url}:{title}".encode()
        return hashlib.md5(key).hexdigest()

    def _is_duplicate(self, url: str, title: str) -> bool:
        """Check if listing already processed."""
        h = self._hash_listing(url, title)
        if h in self.seen_hashes:
            return True
        self.seen_hashes.add(h)
        return False

    async def scrape(self) -> List[Dict]:
        """Scrape PCA Mart for Porsche 911 listings."""
        listings = []

        try:
            logger.info("PCA Mart: Navigating to classifieds...")
            await self.page.goto(self.BASE_URL, wait_until="networkidle", timeout=60000)

            # Wait for listings to load
            await self.page.wait_for_selector("div.listing-item, article.listing", timeout=30000)

            # Extract listing data
            listing_elements = await self.page.query_selector_all("div.listing-item, article.listing")
            logger.info(f"PCA Mart: Found {len(listing_elements)} raw elements")

            for elem in listing_elements:
                try:
                    # Extract fields
                    title = await elem.text_content('h2, h3, .title')
                    price_text = await elem.text_content('.price, [data-price]')
                    mileage_text = await elem.text_content('.mileage, [data-mileage]')
                    location = await elem.text_content('.location, [data-location]')
                    year_text = await elem.text_content('.year, [data-year]')
                    url = await elem.get_attribute('a', 'href')
                    vin = await elem.text_content('.vin, [data-vin]')
                    transmission = await elem.text_content('.transmission, [data-transmission]')
                    posted_date = await elem.text_content('.posted, [data-posted]')
                    photos_count = len(await elem.query_selector_all('img'))
                    thumbnail = await elem.query_selector('img')
                    thumbnail_src = await thumbnail.get_attribute('src') if thumbnail else None

                    # Build full URL if relative
                    if url and not url.startswith('http'):
                        url = self.BASE_URL + '/' + url.lstrip('/')

                    # Parse numbers
                    price = self._parse_price(price_text)
                    mileage = self._parse_mileage(mileage_text)
                    year = self._parse_year(year_text)

                    # Validate against filters
                    if not self._meets_criteria(year, mileage, price, title):
                        continue

                    if self._is_duplicate(url or '', title or ''):
                        continue

                    listing = {
                        'title': title.strip() if title else 'Unknown',
                        'model': self._extract_model(title),
                        'year': year,
                        'price': price,
                        'mileage': mileage,
                        'location': location.strip() if location else 'N/A',
                        'vin': vin.strip() if vin else '',
                        'transmission': transmission.strip() if transmission else 'N/A',
                        'posted_date': posted_date.strip() if posted_date else datetime.now().strftime('%B %d, %Y'),
                        'photos': photos_count,
                        'thumbnail': thumbnail_src,
                        'url': url,
                        'source': 'pca.org',
                        'seller': 'Private',
                    }

                    listings.append(listing)
                    logger.info(f"PCA Mart: Found {listing['year']} {listing['model']} - ${listing['price']:,} - {listing['mileage']:,}mi")

                except Exception as e:
                    logger.warning(f"PCA Mart: Error parsing element: {e}")
                    continue

        except Exception as e:
            logger.error(f"PCA Mart scrape failed: {e}")

        logger.info(f"PCA Mart: Scraped {len(listings)} valid listings")
        return listings

    def _meets_criteria(self, year: int, mileage: int, price: int, title: str) -> bool:
        """Validate listing meets filter criteria."""
        if not year or year < self.FILTERS['min_year'] or year > self.FILTERS['max_year']:
            return False
        if mileage > self.FILTERS['max_miles']:
            return False
        if price < self.FILTERS['min_price']:
            return False
        if '911' not in (title or '').upper():
            return False
        return True

    def _extract_model(self, title: str) -> str:
        """Extract Porsche model from title."""
        if not title:
            return '911'
        title_upper = title.upper()
        models = ['GT3 RS', 'GT3', 'GT2 RS', 'GT2', 'TURBO', 'CARRERA', '911']
        for model in models:
            if model in title_upper:
                return model
        return '911'

    def _parse_price(self, text: str) -> int:
        """Extract price as integer."""
        if not text:
            return 0
        # Remove $, commas, and convert to int
        cleaned = ''.join(c for c in text if c.isdigit())
        return int(cleaned) if cleaned else 0

    def _parse_mileage(self, text: str) -> int:
        """Extract mileage as integer."""
        if not text:
            return 0
        # Remove commas and non-digits
        cleaned = ''.join(c for c in text if c.isdigit())
        return int(cleaned) if cleaned else 0

    def _parse_year(self, text: str) -> int:
        """Extract year as integer."""
        if not text:
            return 0
        # Find 4-digit year between 1900-2099
        import re
        match = re.search(r'(19|20)\d{2}', text)
        return int(match.group(0)) if match else 0


async def scrape_pca_mart() -> List[Dict]:
    """Main entry point."""
    scraper = PCAMartScraper()
    await scraper.init_browser()
    try:
        listings = await scraper.scrape()
        return listings
    finally:
        await scraper.close_browser()


if __name__ == '__main__':
    import asyncio
    import sys

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s [%(levelname)s] %(message)s'
    )

    listings = asyncio.run(scrape_pca_mart())
    print(json.dumps(listings, indent=2, default=str))
