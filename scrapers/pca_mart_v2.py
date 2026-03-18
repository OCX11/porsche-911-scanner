#!/usr/bin/env python3
"""
PCA Mart Scraper v2 - Real HTML parsing, no hallucinations
https://mart.pca.org - server-rendered, BeautifulSoup based
"""

import re
import logging
from typing import Dict, List
import hashlib

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: pip install requests beautifulsoup4")
    exit(1)

logger = logging.getLogger(__name__)


class PCAMartScraperV2:
    """PCA Mart scraper using direct HTTP + BeautifulSoup."""

    BASE_URL = "https://mart.pca.org"

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.session.timeout = 15
        self.seen_hashes = set()

    def _hash_listing(self, ad_number: str) -> str:
        """Generate unique hash for listing by ad number."""
        return hashlib.md5(str(ad_number).encode()).hexdigest()

    def _is_duplicate(self, ad_number: str) -> bool:
        """Check if listing already processed."""
        h = self._hash_listing(ad_number)
        if h in self.seen_hashes:
            return True
        self.seen_hashes.add(h)
        return False

    def _parse_price(self, price_text: str) -> int:
        """Extract price as integer from '$65,000 USD'."""
        if not price_text:
            return 0
        cleaned = ''.join(c for c in price_text if c.isdigit())
        return int(cleaned) if cleaned else 0

    def _parse_year(self, title: str) -> int:
        """Extract year from title '2020 718 Boxster'."""
        if not title:
            return 0
        match = re.search(r'\b(19|20)\d{2}\b', title)
        return int(match.group(1)) if match else 0

    def _extract_model(self, title: str) -> str:
        """Extract model from title."""
        if not title:
            return 'Unknown'
        # Remove year
        title_no_year = re.sub(r'\d{4}\s+', '', title)
        return title_no_year.strip()

    def _parse_mileage(self, description: str) -> int:
        """Extract mileage from description text."""
        if not description:
            return 0
        # Look for patterns like "21000 miles", "51,000 miles", etc.
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
        """Extract published date from description."""
        if not description:
            return 'N/A'
        match = re.search(r'Published:\s*([^<\n]+)', description)
        return match.group(1).strip() if match else 'N/A'

    def _build_thumbnail_url(self, img_src: str) -> str:
        """Convert relative image path to full URL."""
        if not img_src or img_src == 'includes/images/blank.jpg':
            return ''
        if img_src.startswith('http'):
            return img_src
        return self.BASE_URL + '/' + img_src.lstrip('/')

    def scrape(self) -> List[Dict]:
        """Scrape PCA Mart for Porsche 911 listings."""
        listings = []

        try:
            logger.info(f"PCA Mart: Fetching {self.BASE_URL}...")
            resp = self.session.get(self.BASE_URL, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')

            # Find all listing rows
            listing_rows = soup.find_all('div', {'class': 'row border-bottom'})
            logger.info(f"PCA Mart: Found {len(listing_rows)} total listing rows")

            for row in listing_rows:
                try:
                    # Skip non-listing rows (headers, ads, etc.)
                    left_col = row.find('div', {'class': 'col-lg-4'})
                    right_col = row.find('div', {'class': 'col-lg-8'})

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

                    # Skip if duplicate
                    if self._is_duplicate(ad_number):
                        continue

                    # Extract price
                    price_tag = right_col.find('span', {'class': 'martListingPrice'})
                    price_text = price_tag.get_text(strip=True) if price_tag else '0'
                    price = self._parse_price(price_text)

                    # Extract full description (contains published date + details)
                    desc_tag = right_col.find('p', {'class': 'martAdDescription'})
                    description = desc_tag.get_text() if desc_tag else ''

                    # Extract published date
                    published_date = self._extract_published_date(description)

                    # Extract mileage
                    mileage = self._parse_mileage(description)

                    # Extract year and model
                    year = self._parse_year(title)
                    model = self._extract_model(title)

                    # Build URL
                    listing_link = title_tag.get('href') if title_tag else ''
                    url = f"{self.BASE_URL}/{listing_link}" if listing_link else ''

                    # Filter by criteria: 1986-2024, <100K miles, $15K+
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
                    logger.info(f"PCA Mart: {year} {model} - ${price:,} - {mileage:,}mi - Ad #{ad_number}")

                except Exception as e:
                    logger.warning(f"PCA Mart: Error parsing row: {e}")
                    continue

        except Exception as e:
            logger.error(f"PCA Mart scrape failed: {e}")

        logger.info(f"PCA Mart: Scraped {len(listings)} valid 911 listings")
        return listings


def scrape_pca_mart() -> List[Dict]:
    """Main entry point."""
    scraper = PCAMartScraperV2()
    return scraper.scrape()


if __name__ == '__main__':
    import json
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    listings = scrape_pca_mart()
    print(json.dumps(listings, indent=2, default=str))
