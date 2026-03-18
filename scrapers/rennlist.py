#!/usr/bin/env python3
"""
Rennlist Classifieds Scraper
https://rennlist.com/forums/market/vehicles/porsche-2
Real HTML parsing, all Porsche vehicles
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


class RennlistScraper:
    """Rennlist classifieds scraper."""

    BASE_URL = "https://rennlist.com/forums/market/vehicles/porsche-2"
    
    PARAMS = {
        'countryid': 5,  # USA
        'sortby': 'dateline_desc',  # Newest first
        'intent[2]': 2,  # For sale
        'status[0]': 0,  # Open
        'type[0]': 1,  # Vehicles
        'filterstates[vehicle_sellertype]': 0,  # All sellers
        'filterstates[vehicle_types]': 1,  # Vehicles
        'filterstates[vehicle_statuses]': 1,  # Used
        'filterstates[vehicle_condition]': 0,  # All conditions
        'filterstates[vehicle_price]': 0,  # All prices
        'filterstates[vehicle_mileage]': 0,  # All mileage
        'filterstates[vehicle_location]': 0,  # All locations
    }

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36'
        })
        self.session.timeout = 15

    def _hash_listing(self, url: str) -> str:
        """Generate hash from URL."""
        return hashlib.md5(url.encode()).hexdigest()

    def _parse_price(self, price_text: str) -> int:
        """Extract price as integer from '$63,000'."""
        if not price_text:
            return 0
        cleaned = ''.join(c for c in price_text if c.isdigit())
        return int(cleaned) if cleaned else 0

    def _parse_year(self, subtitle: str) -> int:
        """Extract year from subtitle like '2005 Porsche 911'."""
        if not subtitle:
            return 0
        match = re.search(r'\b((?:19|20)\d{2})\b', subtitle)
        return int(match.group(1)) if match else 0

    def _extract_model(self, subtitle: str) -> str:
        """Extract model from subtitle."""
        if not subtitle:
            return 'Unknown'
        # Remove year
        model = re.sub(r'\d{4}\s+Porsche\s+', '', subtitle, flags=re.IGNORECASE)
        return model.strip() if model else 'Unknown'

    def _parse_mileage(self, title_attr: str) -> int:
        """Extract mileage from title attribute."""
        if not title_attr:
            return 0
        match = re.search(r'([\d,]+)\s*(?:k\s+)?miles?', title_attr, re.IGNORECASE)
        if match:
            text = match.group(1).replace(',', '')
            # Check if it's in thousands (e.g., "24k Miles" -> 24000)
            if 'k' in match.group(0).lower() and len(text) <= 3:
                return int(text) * 1000 if text.isdigit() else 0
            return int(text) if text.isdigit() else 0
        return 0

    def _parse_posted_date(self, text: str) -> str:
        """Extract and format posted date from 'Started: Yesterday' or 'Started: Mar 16, 2026'."""
        if not text:
            return 'N/A'
        
        match = re.search(r'Started:\s*(.+?)(?:<|$)', text)
        if not match:
            return 'N/A'
        
        date_str = match.group(1).strip()
        
        # Handle "Yesterday" → use today's date
        if date_str.lower() == 'yesterday':
            from datetime import datetime, timedelta
            yesterday = datetime.now() - timedelta(days=1)
            return yesterday.strftime('%m.%d.%y - 12:00AM')
        
        # Parse date like "Mar 16, 2026"
        try:
            from datetime import datetime
            for fmt in ['%b %d, %Y', '%B %d, %Y', '%m/%d/%Y']:
                try:
                    dt = datetime.strptime(date_str, fmt)
                    return dt.strftime('%m.%d.%y - 12:00AM')
                except:
                    continue
            return date_str
        except:
            return date_str

    def scrape(self, page: int = 1) -> List[Dict]:
        """Scrape Rennlist classifieds (first page by default)."""
        listings = []
        seen_hashes = set()

        try:
            logger.info(f"Rennlist: Fetching page {page}...")
            params = self.PARAMS.copy()
            params['page'] = page
            
            resp = self.session.get(self.BASE_URL, params=params, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Find all listing items
            listing_items = soup.find_all('div', {'class': 'shelf-item'})
            logger.info(f"Rennlist: Found {len(listing_items)} raw items")

            for item in listing_items:
                try:
                    # Extract thumbnail
                    img_tag = item.find('img')
                    thumbnail = img_tag['src'] if img_tag and img_tag.get('src') else ''
                    
                    # Build full URL for image if relative
                    if thumbnail and not thumbnail.startswith('http'):
                        thumbnail = 'https://' + thumbnail.lstrip('/')

                    # Extract title and URL
                    title_tag = item.find('h3', {'class': 'title'})
                    if not title_tag:
                        continue
                    
                    a_tag = title_tag.find('a')
                    if not a_tag:
                        continue
                    
                    title = a_tag.get_text(strip=True)
                    url = a_tag.get('href', '')
                    if url and not url.startswith('http'):
                        url = 'https://rennlist.com' + url

                    # Extract subtitle (year + make + model)
                    subtitle_tag = item.find('h4', {'class': 'sub-title'})
                    subtitle = subtitle_tag.get_text(strip=True) if subtitle_tag else ''

                    # Extract price
                    price_tag = item.find('div', {'class': 'price'})
                    price_text = price_tag.get_text(strip=True) if price_tag else '0'
                    price = self._parse_price(price_text)

                    # Extract location
                    location = 'N/A'
                    for small in item.find_all('small'):
                        if 'Location:' in small.get_text():
                            parent = small.parent
                            location_text = parent.get_text()
                            match = re.search(r'Location:\s*([^<\n]+)', location_text)
                            if match:
                                location = match.group(1).strip()
                            break

                    # Extract summary text for mileage
                    summary_container = item.find('div', {'class': 'summary-container'})
                    title_attr = summary_container.get('title', '') if summary_container else ''
                    
                    # Extract mileage
                    mileage = self._parse_mileage(title_attr)

                    # Extract year and model
                    year = self._parse_year(subtitle)
                    model = self._extract_model(subtitle)

                    # Extract posted date
                    posted_date = 'N/A'
                    for small in item.find_all('small'):
                        text = small.get_text()
                        if 'Started:' in text:
                            posted_date = self._parse_posted_date(text)
                            break

                    # Extract image count
                    img_indicator = item.find('div', {'class': 'image-indicator-overlay'})
                    photos = 0
                    if img_indicator:
                        match = re.search(r'(\d+)', img_indicator.get_text())
                        photos = int(match.group(1)) if match else 0

                    # Skip if duplicate
                    h = self._hash_listing(url)
                    if h in seen_hashes:
                        continue
                    seen_hashes.add(h)

                    # FILTERS: Accept all Porsche vehicles
                    # - Must have a year (vehicle, not ad)
                    # - Year: 1986-2024
                    # - Mileage: <100K (if detected)
                    # - Price: >$10K
                    
                    if year == 0:  # Not a vehicle
                        continue
                    if year < 1986 or year > 2024:
                        continue
                    if mileage > 0 and mileage > 100000:
                        continue
                    if price > 0 and price < 10000:
                        continue

                    listing = {
                        'url': url,
                        'title': title,
                        'subtitle': subtitle,
                        'year': year,
                        'model': model,
                        'price': price,
                        'mileage': mileage,
                        'location': location,
                        'published_date': posted_date,
                        'thumbnail': thumbnail,
                        'photos': photos,
                        'source': 'rennlist.com',
                        'seller': 'Private',
                    }

                    listings.append(listing)
                    logger.info(f"Rennlist: {year} {model} - ${price:,} - {mileage:,}mi")

                except Exception as e:
                    logger.warning(f"Rennlist: Parse error: {e}")
                    continue

        except Exception as e:
            logger.error(f"Rennlist scrape failed: {e}")

        logger.info(f"Rennlist: Scraped {len(listings)} valid listings from page {page}")
        return listings


def scrape_rennlist(page: int = 1) -> List[Dict]:
    """Main entry point."""
    scraper = RennlistScraper()
    return scraper.scrape(page=page)


if __name__ == '__main__':
    import json
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    listings = scrape_rennlist(page=1)
    print(f"\n✓ Found {len(listings)} valid listings\n")
    for i, listing in enumerate(listings[:5], 1):
        print(f"{i}. {listing['year']} {listing['model']}")
        print(f"   ${listing['price']:,} | {listing['mileage']:,}mi")
        print()
