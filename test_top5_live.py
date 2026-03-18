#!/usr/bin/env python3
"""
Test: Send top 5 most recent PCA Mart 911s to Telegram
Even if already seen — to preview before going live
"""

import asyncio
import logging
import os
import requests

logging.basicConfig(level=logging.INFO, format='%(asctime)s [%(levelname)s] %(message)s')

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '6687839356')


async def test_top5():
    """Scrape PCA Mart and send top 5 most recent listings."""
    
    if not TOKEN:
        print("ERROR: TELEGRAM_BOT_TOKEN not set")
        return
    
    from scrapers.pca_mart_playwright import scrape_pca_mart
    
    listings = await scrape_pca_mart()
    
    if not listings:
        print("No 911 listings found")
        return
    
    # Sort by ad_number descending (most recent first)
    listings = sorted(listings, key=lambda x: int(x['ad_number'] or 0), reverse=True)
    
    print(f"\n{'='*60}")
    print(f"TOP 5 MOST RECENT PCA MART 911s (even if seen)")
    print(f"{'='*60}\n")
    
    for i, listing in enumerate(listings[:5], 1):
        year = listing['year']
        model = listing['model']
        price = listing['price']
        mileage = listing['mileage']
        ad_number = listing['ad_number']
        published_date = listing['published_date']
        url = listing['url']
        thumbnail = listing['thumbnail']
        
        print(f"[{i}/5] {year} {model}")
        print(f"      ${price:,} | {mileage:,}mi | Ad #{ad_number}")
        print(f"      Listed: {published_date}")
        
        # Format caption with NEW format
        caption = f"""🚗 *{year} Porsche 911 {model}*

*Price:* ${price:,}
*Mileage:* {mileage:,} miles
*Ad #:* {ad_number}
*Listed:* {published_date}

[View Full Listing]({url})"""
        
        # Send via Telegram
        if thumbnail:
            telegram_url = f"https://api.telegram.org/bot{TOKEN}/sendPhoto"
            payload = {
                'chat_id': CHAT_ID,
                'photo': thumbnail,
                'caption': caption,
                'parse_mode': 'Markdown'
            }
        else:
            telegram_url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
            payload = {
                'chat_id': CHAT_ID,
                'text': caption,
                'parse_mode': 'Markdown'
            }
        
        try:
            resp = requests.post(telegram_url, json=payload, timeout=10)
            if resp.status_code == 200:
                print(f"      ✓ Sent to Telegram")
            else:
                print(f"      ✗ Error: {resp.status_code}")
        except Exception as e:
            print(f"      ✗ Failed: {e}")
        
        print()
        await asyncio.sleep(1)  # Rate limit
    
    print(f"{'='*60}")
    print("Preview complete. Review in Telegram and confirm to go LIVE.")
    print(f"{'='*60}")


if __name__ == '__main__':
    asyncio.run(test_top5())
