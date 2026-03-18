#!/usr/bin/env python3
"""
PCA Mart Scraper - Playwright (JS rendering)
Real HTML parsing after page loads
"""

import re
import logging
import asyncio
from typing import Dict, List
import hashlib

try:
    from playwright.async_api import async_playwright
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: pip install playwright beautifulsoup4")
    exit(1)

logger = logging.getLogger(__name__)


class PCAMartScraperPlaywright:
    """PCA Mart scraper using Playwright for JS rendering."""

    BASE_URL = "https://mart.pca.org"

    def __init__(self):
        self.browser = None
        self.page = None

    async def init(self):
        """Start Playwright."""
        playwright = await async_playwright().start()
        self.browser = await playwright.chromium.launch(headless=True)
        self.page = await self.browser.new_page()
        self.page.set_default_timeout(30000)

    async def close(self):
        """Close browser."""
        if self.page:
            await self.page.close()
        if self.browser:
            await self.browser.close()

    def _hash_listing(self, ad_number: str) -> str:
        """Generate hash by ad number."""
        return hashlib.md5(str(ad_number).encode()).hexdigest()

    def _parse_price(self, price_text: str) -> int:
        """Extract price as integer from '$65,000 USD'."""
        if not price_text:
            return 0
        cleaned = ''.join(c for c in price_text if c.isdigit())
        return int(cleaned) if cleaned else 0

    def _parse_year(self, title: str) -> int:
        """Extract year from title."""
        if not title:
            return 0
        match = re.search(r'\b((?:19|20)\d{2})\b', title)
        return int(match.group(1)) if match else 0

    def _extract_model(self, title: str) -> str:
        """Extract model from title."""
        if not title:
            return 'Unknown'
        title_no_year = re.sub(r'\d{4}\s+', '', title)
        return title_no_year.strip()

    def _parse_mileage(self, description: str) -> int:
        """Extract mileage from description."""
        if not description:
            return 0
        match = re.search(r'([\d,]+)\s*(?:Original\s+)?Miles?', description, re.IGNORECASE)
        if match:
            cleaned = match.group(1).replace(',', '')
            return int(cleaned) if cleaned.isdigit() else 0
        return 0

    def _extract_ad_number(self, ad_text: str) -> str:
        """Extract ad number from 'Ad Number: 81082'."""
        if not ad_text:
            return ''
        match = re.search(r'Ad Number:\s*(\d+)', ad_text)
        return match.group(1) if match else ''

    def _extract_published_date(self, description: str) -> str:
        """Extract and format published date to MM.DD.YY - HH:MMAM/PM."""
        if not description:
            return 'N/A'
        
        # Try both "Published:" and "Updated:" labels
        # Match up to first newline or <
        match = re.search(r'(?:Published|Updated):\s*([A-Za-z]+ \d+, \d{4})', description)
        if not match:
            return 'N/A'
        
        date_str = match.group(1).strip()
        # Expected format: "March 18, 2026" or similar
        # Convert to MM.DD.YY - HH:MMAM/PM
        try:
            from datetime import datetime
            # Try parsing common formats
            for fmt in ['%B %d, %Y', '%b %d, %Y', '%m/%d/%Y']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    # Format as MM.DD.YY - time unknown, use 12:00AM placeholder
                    return dt.strftime('%m.%d.%y - 12:00AM')
                except:
                    continue
            # If no format matches, return as-is with note
            return date_str
        except:
            return date_str

    def _build_thumbnail_url(self, img_src: str) -> str:
        """Convert relative path to full URL."""
        if not img_src or img_src == 'includes/images/blank.jpg':
            return ''
        if img_src.startswith('http'):
            return img_src
        return self.BASE_URL + '/' + img_src.lstrip('/')

    async def scrape(self) -> List[Dict]:
        """Scrape PCA Mart listings."""
        listings = []

        try:
            logger.info(f"PCA Mart: Loading {self.BASE_URL}...")
            await self.page.goto(self.BASE_URL, wait_until='networkidle', timeout=60000)

            # Wait for listings container to load
            await self.page.wait_for_selector('#martAdsDisplay div.row.border-bottom', timeout=30000)

            # Get page HTML after JS renders
            html = await self.page.content()

            soup = BeautifulSoup(html, 'html.parser')
            listing_rows = soup.find_all('div', {'class': 'row border-bottom'})
            logger.info(f"PCA Mart: Found {len(listing_rows)} total rows")

            for row in listing_rows:
                try:
                    left_col = row.find('div', class_='col-lg-4')
                    # right_col might have multiple classes: 'col-lg-8 align-center'
                    right_col = None
                    for div in row.find_all('div', recursive=False):
                        if 'col-lg-8' in div.get('class', []):
                            right_col = div
                            break

                    if not left_col or not right_col:
                        continue

                    # Extract image
                    img_tag = left_col.find('img', {'class': 'martHeroImages'})
                    thumbnail = self._build_thumbnail_url(img_tag['src']) if img_tag and img_tag.get('src') else ''

                    # Extract title
                    title_tag = right_col.find('a', {'class': 'martListingTitle'})
                    title = title_tag.get_text(strip=True) if title_tag else 'Unknown'

                    # Filter: only 911s
                    if '911' not in title.upper():
                        continue

                    # Extract ad number
                    ad_h6 = right_col.find('h6')
                    ad_number = self._extract_ad_number(ad_h6.get_text(strip=True)) if ad_h6 else ''

                    # Extract price
                    price_tag = right_col.find('span', {'class': 'martListingPrice'})
                    price_text = price_tag.get_text(strip=True) if price_tag else '0'
                    price = self._parse_price(price_text)

                    # Extract description
                    desc_tag = right_col.find('p', {'class': 'martAdDescription'})
                    description = desc_tag.get_text() if desc_tag else ''

                    # Extract fields
                    published_date = self._extract_published_date(description)
                    mileage = self._parse_mileage(description)
                    year = self._parse_year(title)
                    model = self._extract_model(title)

                    # Build URL
                    listing_link = title_tag.get('href') if title_tag else ''
                    url = f"{self.BASE_URL}/{listing_link}" if listing_link else ''

                    # Filter: 1986-2024, <100K miles, $15K+
                    if year < 1986 or year > 2024:
                        continue
                    if mileage > 100000:
                        continue
                    if price < 15000:
                        continue

                    listing = {
                        'ad_number': ad_number,
                        'title': title,
                        'year': year,
                        'model': model,
                        'price': price,
                        'mileage': mileage,
                        'published_date': published_date,
                        'thumbnail': thumbnail,
                        'url': url,
                        'source': 'mart.pca.org',
                        'seller': 'Private',
                    }

                    listings.append(listing)
                    logger.info(f"PCA: {year} {model} - ${price:,} - {mileage:,}mi")

                except Exception as e:
                    logger.warning(f"PCA: Parse error: {e}")
                    continue

        except Exception as e:
            logger.error(f"PCA scrape failed: {e}")

        logger.info(f"PCA: Scraped {len(listings)} valid 911s")
        return listings


async def scrape_pca_mart() -> List[Dict]:
    """Main entry point."""
    scraper = PCAMartScraperPlaywright()
    await scraper.init()
    try:
        listings = await scraper.scrape()
        return listings
    finally:
        await scraper.close()


if __name__ == '__main__':
    import json
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    listings = asyncio.run(scrape_pca_mart())
    print(json.dumps(listings[:5], indent=2, default=str))
