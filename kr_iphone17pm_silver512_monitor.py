#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
KR Apple Store | iPhone 17 Pro Max 512 GB Silver stock monitor (public / shareable)
-------------------------------------------------------------------------------
This is a **public-safe** version of the monitoring script with all
**personal credentials removed** and clear instructions for others to use.

What it does
------------
- Queries Apple's official pickup API for **one target SKU**
  (KR market iPhone 17 Pro Max 512GB Silver by default, configurable).
- Checks stock across KR Apple Stores (using a seed `store=` + `searchNearby=true`).
- Polls every 10–15s (randomized) to reduce rate-limit risk.
- Sends a **Bark** push notification when a store flips from `unavailable` → `available`.
- Appends each availability hit to a CSV log for later analysis.

How to use
----------
1) Install deps: `pip install requests pandas python-dateutil`
2) Configure your **target SKU** and **Apple API URL** below if you want a different model.
3) Configure **Bark** via environment variables (recommended) or hardcode for quick test.
   - ENV (recommended): set `BARK_DEVICE_KEY` and optionally `BARK_SERVER_BASE` (default: https://api.day.app)
   - OR set `BARK_PUSH_ENDPOINT` to a full endpoint like `https://api.day.app/<your_device_key>`
4) Run: `python kr_iphone17pm_silver512_monitor.py`
5) Stop with Ctrl+C. A CSV log `iphone17pm_silver_512_availability_log.csv` will be created next to the script.

Notes
-----
- Apple may sometimes require `store=` in the query to return the store list; this script uses a seed store (R764 Hongdae) + `searchNearby=true` to reliably return all KR stores.
- If you share this publicly, **do not commit your personal Bark key**. Use ENV vars instead.
- This script prints one compact line of `store:status` per polling round.
- Optional debug snippet for Bark is provided (commented-out) and can be safely removed.
"""

import os, time, random, json, signal, sys, requests, pandas as pd
from datetime import datetime, timezone
from dateutil import tz

# --- Console: force UTF-8 & unbuffered prints (Python 3.7+) ---
try:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
except Exception:
    pass

def log(*args):
    print(*args, flush=True)

# ============================================================
# === Configuration (safe defaults for public sharing)    ===
# ============================================================

# Target SKU (KR market iPhone 17 Pro Max 512GB Silver)
# Replace if you want to monitor a different model.
SKU = os.getenv("TARGET_SKU", "MFYQ4KH/A").strip()

# Apple API URL: use a seed store + searchNearby=true to get all KR stores
SEED_STORE = os.getenv("SEED_STORE", "R764").strip()  # Hongdae by default
APPLE_API_URL = (
    "https://www.apple.com/kr/shop/retail/pickup-message"
    f"?pl=true&searchNearby=true&store={SEED_STORE}&parts.0=" + SKU
)

# Poll interval: randomized to reduce rate-limiting
POLL_INTERVAL_MIN = int(os.getenv("POLL_MIN", "10"))
POLL_INTERVAL_MAX = int(os.getenv("POLL_MAX", "15"))

# --- Bark configuration (public-safe) ---
# Preferred: set env `BARK_DEVICE_KEY` (and optionally `BARK_SERVER_BASE`) or `BARK_PUSH_ENDPOINT`.
BARK_DEVICE_KEY = os.getenv("BARK_DEVICE_KEY", "").strip()  # DO NOT commit your real key
BARK_SERVER_BASE = os.getenv("BARK_SERVER_BASE", "https://api.day.app").rstrip("/")
BARK_PUSH_ENDPOINT = os.getenv("BARK_PUSH_ENDPOINT", "").rstrip("/")  # optional full endpoint
BARK_GROUP = os.getenv("BARK_GROUP", "Apple KR 17PM").strip()
BARK_SOUND = os.getenv("BARK_SOUND", "minuet").strip()

# Log path (CSV)
LOG_CSV_PATH = os.getenv("LOG_CSV_PATH", "iphone17pm_silver_512_availability_log.csv")

# Timezone for human-readable timestamps
SEOUL_TZ = tz.gettz("Asia/Seoul")

# Request headers (light browser-like)
HEADERS = {
    "Accept": "application/json, text/javascript, */*; q=0.01",
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Referer": "https://www.apple.com/kr/shop",
}

# ============================================================
# === Bark push helper (public-safe; no key committed)     ===
# ============================================================

def bark_send(title: str, body: str, url: str | None = None):
    """Send a Bark push. No-op if not configured.
    Config precedence:
      1) BARK_DEVICE_KEY (+ optional BARK_SERVER_BASE)
      2) BARK_PUSH_ENDPOINT (full URL like https://api.day.app/<key>)
    """
    endpoint = ""
    payload = {"title": title, "body": body, "group": BARK_GROUP, "sound": BARK_SOUND}
    if url:
        payload["url"] = url

    if BARK_DEVICE_KEY:
        endpoint = f"{BARK_SERVER_BASE}/{BARK_DEVICE_KEY}"
    elif BARK_PUSH_ENDPOINT:
        endpoint = BARK_PUSH_ENDPOINT
    else:
        # not configured → skip silently
        log("[INFO] Bark not configured (set BARK_DEVICE_KEY or BARK_PUSH_ENDPOINT) — skipping push.")
        return

    try:
        r = requests.post(endpoint, json=payload, timeout=10)
        if r.status_code != 200:
            log(f"[WARN] Bark push failed HTTP {r.status_code}: {r.text[:200]}")
        else:
            try:
                jr = r.json()
                # many Bark deployments return {code: 200}, some return plain text
                if jr.get("code") not in (None, 0, 200):
                    log(f"[WARN] Bark returned non-OK payload: {jr}")
            except Exception:
                pass
    except Exception as e:
        log(f"[WARN] Bark push exception: {e}")

# ============================================================
# === Apple API parsing                                    ===
# ============================================================

def fetch_availability(session: requests.Session):
    """Fetch Apple's pickup message API and return per-store status list.
    Returns a list of dicts: [{storeNumber, storeName, city, pickupDisplay, quote}, ...]
    """
    r = session.get(APPLE_API_URL, headers=HEADERS, timeout=20)
    log(f"[DEBUG] HTTP {r.status_code} ← {APPLE_API_URL}")
    r.raise_for_status()

    try:
        data = r.json()
    except json.JSONDecodeError:
        log("[ERROR] JSON parse failed. First 300 chars:", r.text[:300])
        raise

    stores = data.get("body", {}).get("stores", []) or []
    out = []
    for s in stores:
        pa = (s.get("partsAvailability") or {}).get(SKU) or {}
        out.append({
            "storeNumber": s.get("storeNumber"),
            "storeName": s.get("storeName"),
            "city": s.get("city"),
            "pickupDisplay": pa.get("pickupDisplay"),
            "quote": ((pa.get("messageTypes") or {}).get("regular") or {}).get("storePickupQuote")
                     or pa.get("pickupSearchQuote") or "",
        })
    return out

# ============================================================
# === Logging utilities                                     ===
# ============================================================

def now_strs():
    dt_utc = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    dt_kr  = datetime.now(tz=SEOUL_TZ).strftime("%Y-%m-%d %H:%M:%S KST")
    return dt_utc, dt_kr

def ensure_log():
    if not os.path.exists(LOG_CSV_PATH):
        pd.DataFrame(columns=[
            "ts_utc","ts_kr","sku","storeName","storeNumber",
            "city","pickupDisplay","quote"
        ]).to_csv(LOG_CSV_PATH, index=False, encoding="utf-8-sig")

def append_log(rows):
    if not rows:
        return
    df = pd.DataFrame(rows)[[
        "ts_utc","ts_kr","sku","storeName","storeNumber",
        "city","pickupDisplay","quote"
    ]]
    df.to_csv(LOG_CSV_PATH, mode="a", header=False, index=False, encoding="utf-8-sig")

# ============================================================
# === Main loop                                            ===
# ============================================================

def main():
    log("=== KR iPhone 17 Pro Max 512GB Silver monitor (public) ===")
    log("API:", APPLE_API_URL)
    if BARK_DEVICE_KEY:
        log("Bark: using device key endpoint →", f"{BARK_SERVER_BASE}/<hidden>")
    elif BARK_PUSH_ENDPOINT:
        log("Bark: using explicit endpoint →", BARK_PUSH_ENDPOINT)
    else:
        log("Bark: not configured (set env vars if you want push)")
    log("Poll interval:", f"{POLL_INTERVAL_MIN}–{POLL_INTERVAL_MAX} s")
    ensure_log()

    session = requests.Session()
    last_flags: dict[str, bool] = {}
    stop = {"flag": False}

    def stop_signal(sig, _):
        stop["flag"] = True
        log("\n[INFO] Interrupt received, exiting…")
    signal.signal(signal.SIGINT, stop_signal)
    signal.signal(signal.SIGTERM, stop_signal)

    while not stop["flag"]:
        try:
            ts_utc, ts_kr = now_strs()
            res = fetch_availability(session)

            # Console: compact per-round status
            brief = " | ".join(f"{r['storeName']}:{r['pickupDisplay']}" for r in res)
            log(f"[{ts_kr}] {brief}")

            # --- Optional Bark test snippet (safe to delete) ---
            # try:
            #     hongdae = next((r for r in res if (r.get("storeName") == "홍대" or r.get("storeNumber") == "R764")), None)
            #     if hongdae:
            #         _title = "[TEST] Hongdae status - iPhone 17 Pro Max 512GB Silver"
            #         _body  = f"{ts_kr} status: {hongdae.get('pickupDisplay','?')}\n{hongdae.get('quote','').strip()}"
            #         bark_send(_title, _body, url="https://www.apple.com/kr/retail/hongdae")
            # except Exception as _e:
            #     log(f"[WARN] test push exception: {_e}")

            # Find available stores, log & push (only on state change: unavailable → available)
            avail_rows = []
            for r in res:
                avail = r.get("pickupDisplay") == "available"
                sid = r.get("storeNumber") or r.get("storeName")
                if avail:
                    avail_rows.append({
                        "ts_utc": ts_utc,
                        "ts_kr": ts_kr,
                        "sku": SKU,
                        **r,
                    })
                    if not last_flags.get(sid):
                        title = f"In stock: {r['storeName']} - iPhone 17 Pro Max 512GB Silver"
                        body  = f"{ts_kr} pickup available ({r.get('city','')})\n{r.get('quote','')}"
                        bark_send(title, body, url="https://www.apple.com/kr/shop/buy-iphone/iphone-17-pro")
                last_flags[sid] = avail

            append_log(avail_rows)

        except requests.HTTPError as he:
            log(f"[WARN] HTTP error: {he}")
        except requests.RequestException as re:
            log(f"[WARN] Network exception: {re}")
        except Exception as e:
            log(f"[WARN] Unknown exception: {e}")

        # Randomized sleep between polls
        time.sleep(random.uniform(POLL_INTERVAL_MIN, POLL_INTERVAL_MAX))

    log("Exit. CSV log at:", LOG_CSV_PATH)

if __name__ == "__main__":
    main()
