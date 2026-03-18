#!/usr/bin/env python3
"""
BuiltForBackRoads Scraper
https://builtforbackroads.com
Curated Porsche classifieds
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


class BuiltForBackRoadsScraper:
    """BuiltForBackRoads curated Porsche classifieds scraper."""

    BASE_URL = "https://builtforbackroads.com"
    LISTING_URL = "https://builtforbackroads.com"

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
        """Extract price from 'Asking $59,000'."""
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

    def _parse_mileage(self, description: str) -> int:
        """Extract mileage from description like 'Showing 39k miles'."""
        if not description:
            return 0
        match = re.search(r'(?:Showing\s+)?(?:just\s+)?(?:over\s+)?(?:less\s+than\s+)?(\d+(?:\.\d+)?)\s*k\s+miles?', description, re.IGNORECASE)
        if match:
            value = float(match.group(1))
            return int(value * 1000)
        
        # Try format without 'k'
        match = re.search(r'(\d{1,3}(?:,\d{3})*)\s+miles?', description, re.IGNORECASE)
        if match:
            cleaned = match.group(1).replace(',', '')
            return int(cleaned) if cleaned.isdigit() else 0
        
        return 0

    def _extract_location(self, details_text: str) -> str:
        """Extract location from 'Transmission · Location · Price' format."""
        if not details_text:
            return 'N/A'
        
        # Format: "6MT · Alexandria, VA · Asking $59,000"
        parts = [p.strip() for p in details_text.split('·')]
        if len(parts) >= 2:
            # Location is second part (index 1)
            return parts[1]
        return 'N/A'

    def _extract_transmission(self, details_text: str) -> str:
        """Extract transmission from details."""
        if not details_text:
            return 'N/A'
        parts = [p.strip() for p in details_text.split('·')]
        if len(parts) >= 1:
            return parts[0]
        return 'N/A'

    def _parse_posted_date(self, img_src: str) -> str:
        """Extract date from image filename like '2026.03.12-PORSCHE-..._1.jpg'."""
        if not img_src:
            return 'N/A'
        
        # Extract YYYY.MM.DD from path
        match = re.search(r'(\d{4})\.(\d{2})\.(\d{2})', img_src)
        if match:
            year, month, day = match.groups()
            # Convert to MM.DD.YY - 12:00AM
            return f"{month}.{day}.{year[-2:]} - 12:00AM"
        
        return 'N/A'

    def scrape(self) -> List[Dict]:
        """Scrape BuiltForBackRoads homepage for listings."""
        listings = []
        seen_hashes = set()

        try:
            logger.info(f"BuiltForBackRoads: Fetching homepage...")
            resp = self.session.get(self.BASE_URL, timeout=15)
            resp.raise_for_status()

            soup = BeautifulSoup(resp.text, 'html.parser')
            
            # Find all listing groups - they're divs with class containing 'group', 'w-full', 'pb-20', 'md:px-4', 'lg:px-8'
            listing_groups = soup.find_all('div', {'class': lambda x: x and 'group' in x and 'w-full' in x and 'pb-20' in x})
            logger.info(f"BuiltForBackRoads: Found {len(listing_groups)} listings")

            for group in listing_groups:
                try:
                    # Extract title and URL from h2 > a
                    h2 = group.find('h2', {'class': lambda x: x and 'title' in x})
                    if not h2:
                        h2 = group.find('h2')
                    
                    title_a = h2.find('a') if h2 else None
                    if not title_a:
                        continue
                    
                    title = title_a.get_text(strip=True)
                    url_path = title_a.get('href', '')
                    url = self.LISTING_URL + url_path if url_path else ''

                    # Extract thumbnail
                    img = group.find('img')
                    thumbnail = img['src'] if img and img.get('src') else ''

                    # Extract description (contains mileage)
                    desc_p = group.find('p', {'class': lambda x: x and 'text-lg' in x})
                    description = desc_p.get_text(strip=True) if desc_p else ''

                    # Extract details (transmission, location, price)
                    # Find the last link in the group
                    all_links = group.find_all('a')
                    details_link = all_links[-1] if all_links else None
                    details_text = details_link.get_text(strip=True) if details_link else ''

                    # Parse fields
                    year = self._parse_year(title)
                    model = self._extract_model(title)
                    mileage = self._parse_mileage(description)
                    location = self._extract_location(details_text)
                    transmission = self._extract_transmission(details_text)
                    
                    # Extract price from details
                    price_match = re.search(r'\$[\d,]+', details_text)
                    price_text = price_match.group(0) if price_match else ''
                    price = self._parse_price(price_text)
                    
                    # Extract posted date from image filename
                    posted_date = self._parse_posted_date(thumbnail)

                    # Skip if duplicate
                    h = self._hash_listing(url)
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
                        'url': url,
                        'title': title,
                        'year': year,
                        'model': model,
                        'price': price,
                        'mileage': mileage,
                        'location': location,
                        'transmission': transmission,
                        'published_date': posted_date,
                        'thumbnail': thumbnail,
                        'description': description,
                        'source': 'builtforbackroads.com',
                        'seller': 'Private',
                    }

                    listings.append(listing)
                    logger.info(f"BFB: {year} {model} - ${price:,} - {mileage:,}mi")

                except Exception as e:
                    logger.warning(f"BFB: Parse error: {e}")
                    continue

        except Exception as e:
            logger.error(f"BFB scrape failed: {e}")

        logger.info(f"BFB: Scraped {len(listings)} valid listings")
        return listings


def scrape_builtforbackroads() -> List[Dict]:
    """Main entry point."""
    scraper = BuiltForBackRoadsScraper()
    return scraper.scrape()


if __name__ == '__main__':
    import json
    logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

    listings = scrape_builtforbackroads()
    print(f"\n✓ Found {len(listings)} valid listings\n")
    for i, listing in enumerate(listings[:5], 1):
        print(f"{i}. {listing['year']} {listing['model']}")
        print(f"   ${listing['price']:,} | {listing['mileage']:,}mi | {listing['location']}")
        print()
