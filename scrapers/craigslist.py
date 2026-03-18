#!/usr/bin/env python3
"""
Craigslist Scraper - Porsche 911
https://craigslist.org/search/cta?query=porsche
Clean HTML-based scraping, nationwide search
"""

import re
import logging
from typing import Dict, List
import hashlib
from datetime import datetime, timedelta

try:
    import requests
    from bs4 import BeautifulSoup
except ImportError:
    print("ERROR: pip install requests beautifulsoup4")
    exit(1)

logger = logging.getLogger(__name__)


class CraigslistScraper:
    """Craigslist Porsche classifieds scraper."""

    # Nationwide search URL
    BASE_URL = "https://craigslist.org/search/car"
    
    PARAMS = {
        'query': 'porsche',
        'min_price': 10000,
        'max_price': 500000,
        'min_auto_year': 1986,
        'max_auto_year': 2024,
        'auto_transmission': '',  # All transmissions
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.session.timeout = 15

    def _hash_listing(self, pid: str) -> str:
        """Generate hash from post ID."""
        return hashlib.md5(pid.encode()).hexdigest()

    def _parse_price(self, price_text: str) -> int:
        """Extract price from '$123,456'."""
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
        # Remove year
        model = re.sub(r'\d{4}\s+', '', title)
        return model.strip() if model else 'Unknown'

    def _parse_mileage(self, meta_text: str) -> int:
        """Extract mileage from meta like '89k mi'."""
        if not meta_text:
            return 0
        match = re.search(r'(\d+(?:\.\d+)?)\s*k\s+mi', meta_text, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            return int(value * 1000)
        
        # Try without 'k' suffix
        match = re.search(r'(\d{1,3}(?:,\d{3})*)\s+mi', meta_text, re.IGNORECASE)
        if match:
            cleaned = match.group(1).replace(',', '')
            return int(cleaned) if cleaned.isdigit() else 0
        
        return 0

    def _parse_posted_date(self, timestamp_str: str) -> str:
        """Extract and format date from title attribute like 'Tue Mar 17 2026 22:03:48 GMT-0400'."""
        if not timestamp_str:
            return 'N/A'
        
        # Parse timestamp - format varies but contains month/day/year
        try:
            # Try parsing common format: "Tue Mar 17 2026 22:03:48"
            match = re.search(r'([A-Za-z]+)\s+([A-Za-z]+)\s+(\d+)\s+(\d{4})', timestamp_str)
            if match:
                day_name, month_name, day, year = match.groups()
                # Create datetime
                month_map = {
                    'Jan': 1, 'Feb': 2, 'Mar': 3, 'Apr': 4, 'May': 5, 'Jun': 6,
                    'Jul': 7, 'Aug': 8, 'Sep': 9, 'Oct': 10, 'Nov': 11, 'Dec': 12
                }
                month = month_map.get(month_name, 1)
                dt = datetime(int(year), month, int(day))
                return dt.strftime('%m.%d.%y - 12:00AM')
        except:
            pass
        
        return 'N/A'

    def scrape(self) -> List[Dict]:
        """Scrape Craigslist nationwide Porsche listings."""
        listings = []
        seen_hashes = set()

        try:
            logger.info(f"Craigslist: Fetching nationwide Porsche listings...")
            resp = self.session.get(self.BASE_URL, params=self.PARAMS, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Find all listings
            listing_divs = soup.find_all('div', {'data-pid': True, 'class': 'cl-search-result'})
            logger.info(f"Craigslist: Found {len(listing_divs)} raw listings")

            for div in listing_divs:
                try:
                    # Extract post ID
                    pid = div.get('data-pid', '')
                    
                    # Extract title and URL
                    title_a = div.find('a', {'class': 'posting-title'})
                    if not title_a:
                        continue
                    
                    title_span = title_a.find('span', {'class': 'label'})
                    title = title_span.get_text(strip=True) if title_span else ''
                    url = title_a.get('href', '')

                    # Extract thumbnail
                    img = div.find('img', {'class': 'cl-thumb'})
                    thumbnail = img['src'] if img and img.get('src') else ''
                    # Handle relative URLs
                    if thumbnail and not thumbnail.startswith('http'):
                        thumbnail = 'https:' + thumbnail if thumbnail.startswith('//') else 'https://images.craigslist.org' + thumbnail

                    # Extract location
                    location_span = div.find('span', {'class': 'result-location'})
                    location = location_span.get_text(strip=True) if location_span else 'N/A'

                    # Extract meta info (price, mileage, date)
                    meta_div = div.find('div', {'class': 'meta'})
                    if not meta_div:
                        continue
                    
                    # Find price
                    price_span = meta_div.find('span', {'class': 'priceinfo'})
                    price_text = price_span.get_text(strip=True) if price_span else '0'
                    price = self._parse_price(price_text)

                    # Find date
                    date_spans = meta_div.find_all('span')
                    date_text = ''
                    mileage_text = ''
                    for span in date_spans:
                        text = span.get_text(strip=True)
                        if span.get('title'):  # Has timestamp in title
                            date_text = span.get('title', '')
                        if 'mi' in text:
                            mileage_text = text

                    posted_date = self._parse_posted_date(date_text)
                    mileage = self._parse_mileage(mileage_text)

                    # Parse fields
                    year = self._parse_year(title)
                    model = self._extract_model(title)

                    # Skip if duplicate
                    h = self._hash_listing(pid)
                    if h in seen_hashes:
                        continue
                    seen_hashes.add(h)

                    # FILTERS: Accept all Porsche vehicles
                    # - Must have a year
                    # - Year: 1986-2024
                    # - Mileage: <100K (if detected)
                    # - Price: >$10K
                    
                    if year == 0:
                        continue
                    if year < 1986 or year > 2024:
                        continue
                    if mileage > 0 and mileage > 100000:
                        continue
                    if price > 0 and price < 10000:
                        continue

                    listing = {
                        'pid': pid,
                        'url': url,
                        'title': title,
                        'year': year,
                        'model': model,
                        'price': price,
                        'mileage': mileage,
                        'location': location,
                        'published_date': posted_date,
                        'thumbnail': thumbnail,
                        'source': 'craigslist.org',
                        'seller': 'Private',
                    }

                    listings.append(listing)
                    logger.info(f"CL: {year} {model} - ${price:,} - {mileage:,}mi - {location}")

                except Exception as e:
                    logger.warning(f"CL: Parse error: {e}")
                    continue

        except Exception as e:
            logger.error(f"CL scrape failed: {e}")

        logger.info(f"CL: Scraped {len(listings)} valid listings")
        return listings


def scrape_craigslist() -> List[Dict]:
    """Main entry point."""
    scraper = CraigslistScraper()
    return scraper.scrape()


if __name__ == '__main__':
    import json
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    listings = scrape_craigslist()
    print(f"\n✓ Found {len(listings)} valid listings\n")
    for i, listing in enumerate(listings[:5], 1):
        print(f"{i}. {listing['year']} {listing['model']}")
        print(f"   ${listing['price']:,} | {listing['mileage']:,}mi | {listing['location']}")
        print()
