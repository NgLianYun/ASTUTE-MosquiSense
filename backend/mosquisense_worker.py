import argparse
import base64
import json
import logging
import mimetypes
import os
import signal
import time
from datetime import datetime, timezone
from pathlib import Path

import requests
from dotenv import load_dotenv

from app import find_predictions, ROBOFLOW_URL

ROOT = Path(__file__).resolve().parent
load_dotenv(ROOT / '.env', override=True)
PHOTO = ROOT / 'input' / 'Q-001.jpg'
STOP = False


def stop_handler(_signum, _frame):
    global STOP
    STOP = True


def require_environment():
    settings = {name: os.getenv(name, '').strip() for name in
                ('ROBOFLOW_API_KEY', 'SUPABASE_URL', 'SUPABASE_SERVICE_ROLE_KEY')}
    bad = [key for key, value in settings.items() if not value or value.startswith('YOUR_')]
    if bad:
        raise RuntimeError('Configure these variables in .env: ' + ', '.join(bad))
    url = settings['SUPABASE_URL'].rstrip('/')
    if not url.startswith('https://') or '/rest/v1' in url:
        raise ValueError('SUPABASE_URL must be https://PROJECT_REF.supabase.co (no /rest/v1)')
    settings['SUPABASE_URL'] = url
    return settings


def detect_from_photo(api_key, image_path=PHOTO):
    if not image_path.is_file():
        raise FileNotFoundError(f'Missing photo: {image_path}. Put a mosquito photo there.')
    mime_type = mimetypes.guess_type(image_path.name)[0] or 'image/jpeg'
    image64 = base64.b64encode(image_path.read_bytes()).decode('ascii')
    data_url = f'data:{mime_type};base64,{image64}'
    response = requests.post(
    ROBOFLOW_URL,
    json={
        "api_key": api_key,
        "inputs": {
            "image": {
                "type": "base64",
                "value": image64
            }
        }
    },
    timeout=120
    )

    if not response.ok:
      logging.error(
        "Roboflow status: %s",
        response.status_code
    )
    logging.error(
        "Roboflow response: %s",
        response.text[:1000]
    )
    response.raise_for_status()
    if not response.ok:
     print("Supabase status:", response.status_code)
     print("Supabase error:", response.text[:1000])
    response.raise_for_status()
    predictions = find_predictions(response.json())
    if predictions is None:
        raise ValueError('Roboflow did not return a recognized predictions list')
    return len(predictions)


def update_supabase(settings, count):
    url = f"{settings['SUPABASE_URL']}/rest/v1/live_data"
    response = requests.patch(url, params={'device_id': 'eq.Q-001'}, json={
        'mosquito_count': count,
        
        'updated_at': datetime.now(timezone.utc).isoformat()
    }, headers={
        'apikey': settings['SUPABASE_SERVICE_ROLE_KEY'],
        'Authorization': f"Bearer {settings['SUPABASE_SERVICE_ROLE_KEY']}",
        'Content-Type': 'application/json',
        'Prefer': 'return=representation'
    }, timeout=30)
    
    print("Supabase HTTP status:", response.status_code)

    if response.status_code >= 400:
     print("SUPABASE ERROR DETAILS:")
     print(response.text[:2000])

    response.raise_for_status()
  
    records = response.json()
    if len(records) != 1:
        raise RuntimeError('Q-001 row not found in quito_live_data. No row was updated.')
    return records[0]


def run_once(settings, image_path):
    
    count = detect_from_photo(settings['ROBOFLOW_API_KEY'], image_path)
    record = update_supabase(settings, count)
    logging.info('Q-001 synced: detected=%s; updated_at=%s', count, record.get('updated_at'))


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--once', action='store_true', help='Run one inference + database update')
    parser.add_argument('--interval', type=int, default=300, help='Seconds between sync cycles (default: 300)')
    parser.add_argument('--image', type=Path, default=PHOTO, help='Snapshot file to analyze')
    args = parser.parse_args()
    if args.interval < 1:
        parser.error('--interval must be a positive number')
    settings = require_environment()
    logging.basicConfig(level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')
    signal.signal(signal.SIGINT, stop_handler)
    signal.signal(signal.SIGTERM, stop_handler)
    logging.info('QUITO Q-001 Roboflow -> Supabase worker started, interval=%s seconds', args.interval)
    while not STOP:
        began = time.monotonic()
        try:
            run_once(settings, args.image)
        except (requests.RequestException, ValueError, RuntimeError, FileNotFoundError) as exc:
            logging.error('Sync failed (latest database count retained): %s', exc)
        if args.once:
            break
        # Sleep in short increments so Ctrl+C stops cleanly.
        deadline = began + args.interval
        while not STOP and time.monotonic() < deadline:
            time.sleep(min(1, deadline - time.monotonic()))


if __name__ == '__main__':
    main()
