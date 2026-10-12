import json
import logging
import os
import random
import re
import sys
import time
from html import unescape

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

import config

# Try importing playwright_stealth if available
try:
    from playwright_stealth import stealth_sync
    HAS_STEALTH = True
except ImportError:
    HAS_STEALTH = False


# ============================================================
# Logging Setup
# ============================================================

logging.basicConfig(
    filename=getattr(config, "LOG_FILE", "scraper.log"),
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s",
)

console = logging.StreamHandler()
console.setLevel(logging.INFO)
logging.getLogger("").addHandler(console)


# ============================================================
# Directory Setup
# ============================================================

os.makedirs(getattr(config, "HTML_CACHE_DIR", "html_cache"), exist_ok=True)
USER_DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "browser_user_data")


# ============================================================
# JSON & Validation Helpers
# ============================================================

def is_bot_challenge_or_empty(scraped_data, html):
    """
    Checks if the page returned dummy content or a bot challenge.
    """
    if not scraped_data.get("mobile_number") and not scraped_data.get("address"):
        return True

    challenge_signals = [
        "captcha", 
        "cf-challenge", 
        "just a moment...", 
        "access denied", 
        "enable javascript",
        "pardon our interruption",
        "checking your browser"
    ]
    html_lower = html.lower() if html else ""
    if any(signal in html_lower for signal in challenge_signals):
        return True

    return False


def load_json(path, default):
    if not os.path.exists(path):
        return default
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logging.error("Could not read %s: %s", path, e)
        return default


def save_json(path, data):
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
    os.replace(tmp, path)


# ============================================================
# Text Helpers
# ============================================================

def clean_text(value):
    if not value:
        return ""
    value = unescape(str(value))
    value = re.sub(r"\s+", " ", value)
    return value.strip()


# ============================================================
# Playwright Fetch & Interaction Functions
# ============================================================

def trigger_random_interactions(page):
    """
    Simulates human interactions to trigger dynamic client-side JS events and update cookies.
    """
    try:
        # Random vertical scroll
        scroll_amount = random.randint(200, 600)
        page.mouse.wheel(0, scroll_amount)
        time.sleep(random.uniform(0.5, 1.5))

        # Random mouse movements
        x = random.randint(100, 800)
        y = random.randint(100, 600)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.3, 1.0))

        # Scroll back slightly
        if random.random() < 0.5:
            page.mouse.wheel(0, -random.randint(100, 300))
            time.sleep(random.uniform(0.3, 0.8))
    except Exception as e:
        logging.debug("Interaction error: %s", e)


def fetch_page_playwright(page, url):
    """
    Navigates to URL using Playwright page instance with interaction jitter.
    """
    try:
        response = page.goto(url, wait_until="domcontentloaded", timeout=45000)
        status = response.status if response else 0

        # Inject micro-interactions to trigger dynamic cookie updates
        trigger_random_interactions(page)

        html = page.content()

        if status in (403, 429):
            return {
                "success": False,
                "status": status,
                "html": html,
                "error": f"Server returned HTTP {status}.",
            }

        return {
            "success": True,
            "status": status,
            "html": html,
            "error": "",
        }

    except Exception as e:
        return {"success": False, "status": 0, "html": "", "error": str(e)}


# ============================================================
# Contact Details Parsing
# ============================================================

def extract_contact(soup):
    details = {
        "address": None,
        "city_state": None,
        "mobile_number": None,
        "website": None,
    }

    for item in soup.select(".bd-info-item"):
        label_el = item.select_one(".bd-info-label")
        value_el = item.select_one(".bd-info-value")

        if not label_el or not value_el:
            continue

        label_text = clean_text(label_el.get_text(" ", strip=True))
        value_text = clean_text(value_el.get_text(" ", strip=True))

        if label_text == "Address":
            details["address"] = value_text
        elif label_text == "City / State":
            details["city_state"] = value_text
        elif label_text == "Mobile Number":
            details["mobile_number"] = value_text
        elif label_text == "Website":
            link = value_el.find("a")
            if link and link.get("href"):
                details["website"] = link.get("href").strip()
            else:
                details["website"] = value_text

    if not details["mobile_number"]:
        phone_btn = soup.select_one('a.bd-phone-btn[href^="tel:"]')
        if phone_btn:
            href = phone_btn.get("href", "")
            details["mobile_number"] = href.replace("tel:", "").strip()

    return details


def parse_business(html, business):
    soup = BeautifulSoup(html, "html.parser")
    extracted_contact = extract_contact(soup)

    return {
        "id": business.get("id"),
        "business_name": business.get("business_name"),
        "address": extracted_contact["address"],
        "city_state": extracted_contact["city_state"],
        "mobile_number": extracted_contact["mobile_number"],
        "website": extracted_contact["website"],
    }


# ============================================================
# Checkpoint & Cache Management
# ============================================================

def cache_path(business_id):
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(business_id))
    return os.path.join(getattr(config, "HTML_CACHE_DIR", "html_cache"), f"{safe_id}.html")


def save_html(business_id, html):
    with open(cache_path(business_id), "w", encoding="utf-8") as f:
        f.write(html)


def load_html(business_id):
    path = cache_path(business_id)
    if not os.path.exists(path):
        return None
    try:
        with open(path, "r", encoding="utf-8") as f:
            return f.read()
    except Exception:
        return None


def create_checkpoint():
    return {
        "next_index": 0,
        "processed": 0,
        "successful": 0,
        "failed": 0,
        "last_business_id": None,
    }


def load_checkpoint():
    if getattr(config, "FORCE_RESTART", False):
        return create_checkpoint()
    return load_json(getattr(config, "CHECKPOINT_FILE", "checkpoint.json"), create_checkpoint())


def record_failure(failed, business, reason, status=None):
    failed.append({
        "id": business.get("id"),
        "business_name": business.get("business_name"),
        "url": business.get("url"),
        "reason": reason,
        "status": status,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
    })
    save_json(getattr(config, "FAILED_FILE", "failed_businesses.json"), failed)


def wait_before_request():
    delay_base = getattr(config, "REQUEST_DELAY", 5.0)
    jitter_range = getattr(config, "JITTER_RANGE", (0.5, 3.0))
    jitter = random.uniform(jitter_range[0], jitter_range[1])
    delay = delay_base + jitter
    logging.info("Waiting %.2f seconds...", delay)
    time.sleep(delay)


# ============================================================
# Main Loop
# ============================================================

def main():
    input_file = getattr(config, "INPUT_FILE", "businesses.json")
    output_file = getattr(config, "OUTPUT_FILE", "scraped_businesses.json")
    failed_file = getattr(config, "FAILED_FILE", "failed_businesses.json")
    checkpoint_file = getattr(config, "CHECKPOINT_FILE", "checkpoint.json")

    businesses = load_json(input_file, [])

    if not businesses or not isinstance(businesses, list):
        logging.error("Invalid or empty input file: %s", input_file)
        sys.exit(1)

    results = load_json(output_file, [])
    failed = load_json(failed_file, [])
    checkpoint = load_checkpoint()

    completed_ids = {
        str(item.get("id"))
        for item in results
        if item.get("id") is not None
    }

    start_index = checkpoint.get("next_index", 0)
    consecutive_errors = 0
    session_request_count = 0  # Track requests in current execution session

    logging.info(
        "Loaded %d businesses | Completed: %d | Start Index: %d",
        len(businesses),
        len(completed_ids),
        start_index,
    )

    with sync_playwright() as p:
        # Launch persistent context to manage cookies and storage on disk automatically
        context = p.chromium.launch_persistent_context(
            user_data_dir=USER_DATA_DIR,
            headless=False,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
            ],
            viewport={"width": 1280, "height": 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        )

        # Add initial cookies to the context before navigating
        context.add_cookies([
    {
        "name": "_ga",
        "value": "GA1.1.594182871.1791317821",
        "domain": ".idbf.in",
        "path": "/",
    },
    {
        "name": "_ga_0LR2K01YFQ",
        "value": "GS2.1.s1791492623$o8$g1$t1791493973$j22$l0$h0",
        "domain": ".idbf.in",
        "path": "/",
    }
])

        page = context.pages[0] if context.pages else context.new_page()

        if HAS_STEALTH:
            stealth_sync(page)

        for index in range(start_index, len(businesses)):
            # --- Rule 1: Hard stop after 2000 requests per session run ---
            if session_request_count >= 2000:
                logging.warning("Reached 2,000 requests in this run. Stopping script to refresh initial cookies.")
                break

            # --- Rule 2: Random 5-15 min break every 500 requests ---
            if session_request_count > 0 and session_request_count % 500 == 0:
                break_duration = random.uniform(300, 900)  # 5 to 15 minutes
                logging.info(
                    "Completed %d requests in current run. Taking a break for %.1f minutes...",
                    session_request_count,
                    break_duration / 60,
                )
                time.sleep(break_duration)

            business = businesses[index]
            business_id = str(business.get("id", ""))
            name = business.get("business_name", "Unknown")
            url = business.get("url")

            if business_id in completed_ids:
                logging.info("[%d/%d] Already completed: %s", index + 1, len(businesses), name)
                checkpoint["next_index"] = index + 1
                checkpoint["last_business_id"] = business_id
                save_json(checkpoint_file, checkpoint)
                continue

            if not url:
                record_failure(failed, business, "Missing URL")
                checkpoint["next_index"] = index + 1
                checkpoint["failed"] += 1
                save_json(checkpoint_file, checkpoint)
                continue

            logging.info("[%d/%d] Processing: %s", index + 1, len(businesses), name)

            html = load_html(business_id) if getattr(config, "USE_HTML_CACHE", False) else None
            scraped_result = None

            if not html:
                wait_before_request()
                session_request_count += 1
                success = False
                last_error = None
                last_status = None

                max_retries = getattr(config, "MAX_RETRIES", 3)
                backoff_factor = getattr(config, "BACKOFF_FACTOR", 5.0)

                for attempt in range(max_retries + 1):
                    if attempt > 0:
                        backoff = backoff_factor ** attempt
                        logging.warning("Retry %d/%d after %.1fs", attempt, max_retries, backoff)
                        time.sleep(backoff)

                    response = fetch_page_playwright(page, url)
                    last_status = response["status"]
                    last_error = response["error"]

                    if last_status in (403, 429):
                        logging.error("Rate limit/blocked: HTTP %s for %s", last_status, url)
                        break

                    if response["success"]:
                        candidate_html = response["html"]
                        candidate_data = parse_business(candidate_html, business)

                        if is_bot_challenge_or_empty(candidate_data, candidate_html):
                            logging.warning("Bot challenge or empty dummy page detected for %s!", url)
                            last_error = "Bot challenge or empty dummy page detected"
                            break
                        else:
                            html = candidate_html
                            scraped_result = candidate_data
                            success = True
                            break

                if not success:
                    consecutive_errors += 1
                    record_failure(failed, business, last_error or "Request failed", last_status)
                    checkpoint["failed"] += 1
                    checkpoint["processed"] += 1
                    checkpoint["next_index"] = index + 1
                    checkpoint["last_business_id"] = business_id
                    save_json(checkpoint_file, checkpoint)

                    # Bot challenge exit condition
                    if last_error == "Bot challenge or empty dummy page detected" or last_status in (403, 429):
                        logging.error("Bot challenge detected or IP flagged. Exiting script to preserve progress.")
                        break

                    max_consec = getattr(config, "MAX_CONSECUTIVE_ERRORS", 5)
                    if consecutive_errors >= max_consec:
                        logging.error("Circuit breaker triggered (%d consecutive errors). Stopping.", consecutive_errors)
                        break
                    continue

            if getattr(config, "SAVE_HTML", False) and html:
                save_html(business_id, html)

            try:
                if not scraped_result:
                    scraped_result = parse_business(html, business)

                results.append(scraped_result)

                save_json(output_file, results)
                completed_ids.add(business_id)
                consecutive_errors = 0

                checkpoint["successful"] += 1
                checkpoint["processed"] += 1
                checkpoint["next_index"] = index + 1
                checkpoint["last_business_id"] = business_id
                save_json(checkpoint_file, checkpoint)

                logging.info(
                    "SUCCESS: %s | Mobile: %s | Address: %s",
                    name,
                    scraped_result.get("mobile_number"),
                    scraped_result.get("address"),
                )

            except Exception as e:
                logging.exception("Parser error for %s", name)
                consecutive_errors += 1
                record_failure(failed, business, f"Parser error: {e}")
                checkpoint["failed"] += 1
                checkpoint["processed"] += 1
                checkpoint["next_index"] = index + 1
                checkpoint["last_business_id"] = business_id
                save_json(checkpoint_file, checkpoint)

                max_consec = getattr(config, "MAX_CONSECUTIVE_ERRORS", 5)
                if consecutive_errors >= max_consec:
                    logging.error("Circuit breaker triggered.")
                    break

        context.close()

    logging.info("=" * 60)
    logging.info("SCRAPER FINISHED | Output: %s", output_file)
    logging.info("=" * 60)


if __name__ == "__main__":
    main()