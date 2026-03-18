"""Cars.com Porsche classifieds scraper."""

import re
import json
import logging
from datetime import datetime
from typing import Optional
from bs4 import BeautifulSoup
from playwright.async_api import async_playwright

logger = logging.getLogger(__name__)

BASE_URL = "https://www.cars.com/shopping/results"

# Filter constants
YEAR_MIN = 1986
YEAR_MAX = 2024
MILEAGE_MAX = 100000
PRICE_MIN = 10000
EXCLUDE_MODELS = {"914", "taycan"}  # Case-insensitive


async def scrape_cars_com() -> list[dict]:
    """Scrape Cars.com for Porsche listings."""
    listings = []
    
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(headless=True)
            page = await browser.new_page()
            page.set_default_timeout(30000)
            
            # Search URL with Porsche filters (911 + 718 Cayman, private sellers only)
            search_url = (
                f"{BASE_URL}/"
                f"?stock_type=used"
                f"&makes%5B%5D=porsche"
                f"&models%5B%5D=porsche-911"
                f"&models%5B%5D=porsche-718_cayman"
                f"&year_min={YEAR_MIN}"
                f"&year_max={YEAR_MAX}"
                f"&mileage_max={MILEAGE_MAX}"
                f"&seller_type%5B%5D=private_seller"
                f"&maximum_distance=9999"
                f"&sort=listed_at_desc"
            )
            
            logger.info(f"Fetching Cars.com: {search_url}")
            await page.goto(search_url, wait_until="domcontentloaded")
            
            # Wait for results to load (increased timeout)
            await page.wait_for_selector("fuse-card[data-vehicle-details]", timeout=20000)
            
            # Get page HTML
            html = await page.content()
            await browser.close()
            
        soup = BeautifulSoup(html, "html.parser")
        
        # Find all vehicle cards
        cards = soup.find_all("fuse-card", {"data-vehicle-details": True})
        logger.info(f"Found {len(cards)} Cars.com listings")
        
        for card in cards:
            try:
                listing = _parse_card(card)
                if listing and _passes_filters(listing):
                    listings.append(listing)
            except Exception as e:
                logger.warning(f"Failed to parse Cars.com card: {e}")
                continue
        
        logger.info(f"Cars.com: Scraped {len(listings)} valid listings after filtering")
        return listings
    
    except Exception as e:
        logger.error(f"Cars.com scrape failed: {e}")
        return []


def _parse_card(card) -> Optional[dict]:
    """Extract listing data from a fuse-card element."""
    try:
        # Get JSON data from attribute
        data_str = card.get("data-vehicle-details", "{}")
        data = json.loads(data_str)
        
        # Get listing ID
        listing_id = card.get("data-listing-id", "")
        if not listing_id:
            return None
        
        # Build title
        year = data.get("year", "")
        model = data.get("model", "")
        trim = data.get("trim", "")
        title = f"{year} {model} {trim}".strip() if year else None
        if not title:
            return None
        
        # Parse numbers
        price_str = str(data.get("price", "0")).replace(",", "")
        mileage_str = str(data.get("mileage", "0")).replace(",", "")
        
        try:
            price = int(price_str) if price_str else 0
            mileage = int(mileage_str) if mileage_str else 0
        except ValueError:
            return None
        
        # Get seller name from card text (look for "Private seller: [Name]")
        card_text = card.get_text()
        seller_match = re.search(r"Private seller:\s*(.+?)(?:\n|$)", card_text)
        seller = seller_match.group(1).strip() if seller_match else "Unknown"
        
        # Get thumbnail
        thumbnail = data.get("primaryThumbnail", "")
        
        # Build detail URL
        detail_url = f"https://www.cars.com/vehicledetail/{listing_id}/"
        
        # Get published date - Cars.com doesn't show this prominently, use current time
        # (We'll note this limitation and can enhance later if needed)
        now = datetime.now()
        published_date = now.strftime("%m.%d.%y - %I:%M%p")
        
        return {
            "url": detail_url,
            "title": title,
            "year": int(year) if year else 0,
            "model": model,
            "price": price,
            "mileage": mileage,
            "published_date": published_date,
            "thumbnail": thumbnail,
            "source": "Cars.com",
            "seller": seller,
            "ad_number": listing_id,
            "vin": data.get("vin", ""),
            "trim": trim,
            "body_style": data.get("bodyStyle", ""),
        }
    
    except Exception as e:
        logger.debug(f"Error parsing card: {e}")
        return None


def _passes_filters(listing: dict) -> bool:
    """Check if listing passes filter criteria."""
    # Year range
    year = listing.get("year", 0)
    if year == 0 or year < YEAR_MIN or year > YEAR_MAX:
        return False
    
    # Mileage
    mileage = listing.get("mileage", 0)
    if mileage > 0 and mileage > MILEAGE_MAX:
        return False
    
    # Price
    price = listing.get("price", 0)
    if price > 0 and price < PRICE_MIN:
        return False
    
    # Model exclusions (Taycan, 914)
    model = (listing.get("model", "") or "").lower()
    if any(exclude in model for exclude in EXCLUDE_MODELS):
        return False
    
    # Private seller only (check seller field)
    seller = (listing.get("seller", "") or "").lower()
    if "private" not in seller and "unknown" not in seller:
        # If it's not explicitly private, assume it's a dealer - skip
        if "dealer" in seller or "dealer" in (listing.get("title", "") or "").lower():
            return False
    
    return True
