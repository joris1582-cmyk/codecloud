"""Post a Discord webhook payload (JSON file) to the webhook URL stored in .webhook next to this script.

Usage: python3 post_discord.py payload.json
The webhook URL is never printed. Prints the HTTP status (204 = success).
"""
import json, os, sys, time, urllib.request, urllib.error

here = os.path.dirname(os.path.abspath(__file__))
url = open(os.path.join(here, ".webhook")).read().strip()
payload = open(sys.argv[1], "rb").read()
json.loads(payload)  # validate

for attempt in range(2):
    req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json", "User-Agent": "StatsBot/1.0"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            print(r.status); break
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors="replace")
        if e.code == 429 and attempt == 0:
            wait = float(json.loads(body).get("retry_after", 2))
            time.sleep(wait); continue
        print(e.code, body[:300]); sys.exit(1)
