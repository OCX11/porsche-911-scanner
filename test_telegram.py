#!/usr/bin/env python3
"""
Test Telegram notifications with sample PCA Mart listings
Shows formatting before full scraper launch
"""

import os
import time
import requests
from datetime import datetime

TOKEN = os.getenv('TELEGRAM_BOT_TOKEN')
CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '6687839356')

# Sample PCA Mart listings (top 5 most recent)
SAMPLE_LISTINGS = [
    {
        'year': 2018,
        'model': 'GT3 RS',
        'price': 215000,
        'mileage': 12450,
        'vin': 'WP0AF2A94JS192847',
        'location': 'Miami, FL',
        'transmission': 'Manual',
        'posted_date': 'March 18, 2026',
        'url': 'https://mart.pca.org/listing/2018-porsche-911-gt3-rs-12450-miles',
        'thumbnail': 'https://images.cars.com/cldstatic/v2/stock/12345/sample-porsche-gt3-rs.jpg',
        'source': 'mart.pca.org',
    },
    {
        'year': 2017,
        'model': 'Turbo S',
        'price': 185000,
        'mileage': 28500,
        'vin': 'WP0AD2A97HS169832',
        'location': 'Los Angeles, CA',
        'transmission': 'PDK',
        'posted_date': 'March 18, 2026',
        'url': 'https://mart.pca.org/listing/2017-porsche-911-turbo-s-28500-miles',
        'thumbnail': 'https://images.cars.com/cldstatic/v2/stock/12346/sample-porsche-turbo-s.jpg',
        'source': 'mart.pca.org',
    },
    {
        'year': 2016,
        'model': 'Carrera GTS',
        'price': 125000,
        'mileage': 47200,
        'vin': 'WP0CA2A98GL120456',
        'location': 'Austin, TX',
        'transmission': 'Manual',
        'posted_date': 'March 18, 2026',
        'url': 'https://mart.pca.org/listing/2016-porsche-911-carrera-gts-47200-miles',
        'thumbnail': 'https://images.cars.com/cldstatic/v2/stock/12347/sample-porsche-carrera-gts.jpg',
        'source': 'mart.pca.org',
    },
    {
        'year': 2015,
        'model': 'GT3',
        'price': 95000,
        'mileage': 63400,
        'vin': 'WP0AB2A92FS138902',
        'location': 'Chicago, IL',
        'transmission': 'Manual',
        'posted_date': 'March 18, 2026',
        'url': 'https://mart.pca.org/listing/2015-porsche-911-gt3-63400-miles',
        'thumbnail': 'https://images.cars.com/cldstatic/v2/stock/12348/sample-porsche-gt3.jpg',
        'source': 'mart.pca.org',
    },
    {
        'year': 2014,
        'model': 'Carrera',
        'price': 78000,
        'mileage': 89200,
        'vin': 'WP0AB2A97ES142578',
        'location': 'New York, NY',
        'transmission': 'PDK',
        'posted_date': 'March 18, 2026',
        'url': 'https://mart.pca.org/listing/2014-porsche-911-carrera-89200-miles',
        'thumbnail': 'https://images.cars.com/cldstatic/v2/stock/12349/sample-porsche-carrera.jpg',
        'source': 'mart.pca.org',
    },
]


def format_telegram(listing):
    """Format listing for Telegram (standard format)."""
    year = listing['year']
    model = listing['model']
    price = listing['price']
    mileage = listing['mileage']
    vin = listing['vin']
    location = listing['location']
    transmission = listing['transmission']
    posted_date = listing['posted_date']
    url = listing['url']
    thumbnail = listing['thumbnail']
    source = listing['source']

    msg = f"""🚗 New Porsche Listing Found

{year} Porsche 911 {model}
{model}

📷 [View Photo]({thumbnail})

Miles: {mileage:,}
Price: ${price:,}
VIN: {vin}
Location: {location}
Seller: Private
Site: {source}
Date Found: {posted_date}

🔗 [View Full Listing]({url})"""

    return msg


def send_telegram(message):
    """Send Telegram notification."""
    if not TOKEN or not CHAT_ID:
        print("ERROR: TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not set")
        return False

    url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
    payload = {
        'chat_id': CHAT_ID,
        'text': message,
        'parse_mode': 'Markdown'
    }

    try:
        resp = requests.post(url, json=payload, timeout=10)
        if resp.status_code == 200:
            print("✓ Telegram sent")
            return True
        else:
            print(f"✗ Telegram API error: {resp.status_code}")
            print(resp.text[:200])
            return False
    except Exception as e:
        print(f"✗ Telegram send failed: {e}")
        return False


def main():
    print("=" * 60)
    print("Testing Telegram notifications with top 5 PCA Mart listings")
    print("=" * 60)

    if not TOKEN:
        print("\nWARNING: TELEGRAM_BOT_TOKEN not set")
        print("Set it: export TELEGRAM_BOT_TOKEN='your_token'")
        return

    for i, listing in enumerate(SAMPLE_LISTINGS[:5], 1):
        print(f"\n[{i}/5] {listing['year']} {listing['model']} - ${listing['price']:,}")

        message = format_telegram(listing)
        print(f"\nFormatted message:\n{message}\n")

        success = send_telegram(message)
        if success:
            print(f"✓ Sent to Telegram chat {CHAT_ID}")
        else:
            print(f"✗ Failed to send")

        time.sleep(1)  # Rate limit

    print("\n" + "=" * 60)
    print("Test complete. Check your Telegram for 5 messages.")
    print("=" * 60)


if __name__ == '__main__':
    main()
