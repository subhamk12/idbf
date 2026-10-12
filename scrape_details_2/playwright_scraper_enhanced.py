
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
# Dynamic Headers & User-Agent Generators
# ============================================================

USER_AGENTS = [
    "Mozilla/5.0 (X11; Linux x86_64; rv:151.0) Gecko/20100101 Firefox/151.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:125.0) Gecko/20100101 Firefox/125.0",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
]

REFERRERS_POOL = [
    "https://www.google.com/",
    "https://www.bing.com/",
    "https://idbf.in/",
    "https://patna.idbf.in/",
]


def generate_mutated_headers():
    """Generates custom real-browser headers with randomized mutation variations."""
    encodings = [
        "gzip, deflate, br, zstd",
        "gzip, deflate, br",
        "gzip, deflate",
    ]
    languages = [
        "en-US,en;q=0.9",
        "en-US,en;q=0.8,hi;q=0.5",
        "en-GB,en;q=0.9,en-US;q=0.8",
    ]

    return {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Encoding": random.choice(encodings),
        "Accept-Language": random.choice(languages),
        "Cache-Control": random.choice(["no-cache", "max-age=0"]),
        "Pragma": "no-cache",
        "Priority": random.choice(["u=0, i", "u=1"]),
        "Sec-Fetch-Dest": "document",
        "Sec-Fetch-Mode": "navigate",
        "Sec-Fetch-Site": random.choice(["same-origin", "cross-site", "none"]),
        "Upgrade-Insecure-Requests": "1",
    }


# ============================================================
# JSON & Challenge Verification
# ============================================================

def is_bot_challenge_or_empty(scraped_data, html):
    """Inspects response for empty payloads or anti-bot defense signatures."""
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
    return any(signal in html_lower for signal in challenge_signals)


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


def clean_text(value):
    if not value:
        return ""
    value = unescape(str(value))
    value = re.sub(r"\s+", " ", value)
    return value.strip()


# ============================================================
# Playwright Human Interaction Engine
# ============================================================

def trigger_random_interactions(page):
    """Simulates realistic user actions (scrolls, pauses, micro movements)."""
    try:
        # Randomized scrolling
        scroll_steps = random.randint(1, 3)
        for _ in range(scroll_steps):
            scroll_amount = random.randint(150, 450)
            page.mouse.wheel(0, scroll_amount)
            time.sleep(random.uniform(0.4, 1.2))

        # Mouse position jitter
        x = random.randint(100, 900)
        y = random.randint(100, 700)
        page.mouse.move(x, y)
        time.sleep(random.uniform(0.2, 0.8))

        # Random upward scroll back
        if random.random() < 0.4:
            page.mouse.wheel(0, -random.randint(100, 250))
            time.sleep(random.uniform(0.3, 0.7))
    except Exception as e:
        logging.debug("Interaction note: %s", e)


def fetch_page_playwright(page, url, referrer=None):
    """Navigates to URL with context-aware referrers and human interaction."""
    try:
        options = {"wait_until": "domcontentloaded", "timeout": 45000}
        
        # Determine referrer dynamically if not explicitly provided
        if not referrer:
            referrer = random.choice(REFERRERS_POOL)
            
        options["referer"] = referrer

        response = page.goto(url, **options)
        status = response.status if response else 0

        # Execute human movement sequence
        trigger_random_interactions(page)

        html = page.content()

        if status in (403, 429):
            return {
                "success": False,
                "status": status,
                "html": html,
                "error": f"Blocked with HTTP status {status}.",
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
# Extractor Logic
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
            details["website"] = link.get("href").strip() if link and link.get("href") else value_text

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
# Checkpoint & Cache Helpers
# ============================================================

def cache_path(business_id):
    safe_id = re.sub(r"[^a-zA-Z0-9_-]", "_", str(business_id))
    return os.path.join(getattr(config, "HTML_CACHE_DIR", "html_cache"), f"{safe_id}.html")


def save_html(business_id, html):
    with open(cache_path(business_id), "w", encoding="utf-8") as f:
        f.write(html)


def load_html(business_id):
    path = cache_path(business_id)
    return open(path, "r", encoding="utf-8").read() if os.path.exists(path) else None


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
    delay_base = getattr(config, "REQUEST_DELAY", 4.0)
    jitter = random.uniform(0.8, 3.5)
    delay = delay_base + jitter
    logging.info("Pacing delay: %.2f seconds...", delay)
    time.sleep(delay)


# ============================================================
# Main Execution Loop
# ============================================================

def create_browser_context(p):
    """Spawns persistent browser context using mutated headers and real user profile."""
    user_agent = random.choice(USER_AGENTS)
    headers = generate_mutated_headers()
    # Example: Injecting predefined cookies into the persistent context

    context = p.chromium.launch_persistent_context(
        user_data_dir=USER_DATA_DIR,
        headless=False,
        extra_http_headers=headers,
        user_agent=user_agent,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--no-sandbox",
        ],
        viewport={"width": random.choice([1280, 1366, 1440]), "height": random.choice([720, 768, 900])},
    )
    context.add_cookies([
    {
        "name": "_ga",
        "value": "GA1.1.594182871.1791317821",
        "domain": ".idbf.in",
        "path": "/",
    },{
        "name":"_ga_0LR2K01YFQ",
        "value":"GS2.1.s1791498464$o9$g1$t1791499128$j56$l0$h0",
        "domain":".idbf.in",
        "path":"/",
    },
    {
        "name": "null",
        "value": "null",
        "domain": ".idbf.in",
        "path": "/",
    }
    ])
    page = context.pages[0] if context.pages else context.new_page()

    if HAS_STEALTH:
        stealth_sync(page)

    return context, page


def main():
    input_file = getattr(config, "INPUT_FILE", "businesses.json")
    output_file = getattr(config, "OUTPUT_FILE", "scraped_businesses.json")
    failed_file = getattr(config, "FAILED_FILE", "failed_businesses.json")
    checkpoint_file = getattr(config, "CHECKPOINT_FILE", "checkpoint.json")

    businesses = load_json(input_file, [])
    if not businesses or not isinstance(businesses, list):
        logging.error("Input file missing or invalid: %s", input_file)
        sys.exit(1)

    results = load_json(output_file, [])
    failed = load_json(failed_file, [])
    checkpoint = load_checkpoint()

    completed_ids = {str(item.get("id")) for item in results if item.get("id") is not None}
    start_index = checkpoint.get("next_index", 0)

    consecutive_errors = 0
    session_request_count = 0
    
    # Random batch size per browser session (15-45 visits before closing/re-opening)
    current_session_limit = random.randint(15, 45)
    visits_in_current_context = 0
    last_visited_url = None

    logging.info(
        "Loaded %d items | Completed: %d | Starting Index: %d",
        len(businesses), len(completed_ids), start_index
    )

    with sync_playwright() as p:
        context, page = create_browser_context(p)

        for index in range(start_index, len(businesses)):
            # Hard Safety Stop (2000 total requests max per run)
            if session_request_count >= 2000:
                logging.warning("Reached 2,000 total requests. Halting execution for safety.")
                break

            # Scheduled Long Break every 500 requests
            if session_request_count > 0 and session_request_count % 500 == 0:
                break_duration = random.uniform(300, 900)
                logging.info("500 requests reached. Taking %.1f minute sleep break...", break_duration / 60)
                time.sleep(break_duration)

            # Dynamic Session Lifecycle (close context & re-open every 15-45 visits)
            if visits_in_current_context >= current_session_limit:
                logging.info("Closing session context after %d requests to refresh browser state...", visits_in_current_context)
                context.close()
                time.sleep(random.uniform(4.0, 10.0))
                
                # Launch fresh context with mutated headers
                context, page = create_browser_context(p)
                visits_in_current_context = 0
                current_session_limit = random.randint(15, 45)

            business = businesses[index]
            business_id = str(business.get("id", ""))
            name = business.get("business_name", "Unknown")
            url = business.get("url")

            if business_id in completed_ids:
                checkpoint["next_index"] = index + 1
                checkpoint["last_business_id"] = business_id
                save_json(checkpoint_file, checkpoint)
                continue

            if not url:
                record_failure(failed, business, "Missing URL target")
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
                visits_in_current_context += 1

                success = False
                last_error = None
                last_status = None

                max_retries = getattr(config, "MAX_RETRIES", 3)
                backoff_factor = getattr(config, "BACKOFF_FACTOR", 5.0)

                for attempt in range(max_retries + 1):
                    if attempt > 0:
                        backoff = backoff_factor ** attempt
                        logging.warning("Retry %d/%d after backoff (%.1fs)", attempt, max_retries, backoff)
                        time.sleep(backoff)

                    # Dynamic Referrer: Alternate between last visited internal page and search engine root
                    referrer = last_visited_url if (last_visited_url and random.random() < 0.7) else random.choice(REFERRERS_POOL)

                    response = fetch_page_playwright(page, url, referrer=referrer)
                    last_status = response["status"]
                    last_error = response["error"]

                    if last_status in (403, 429):
                        logging.error("Rate limit or IP blocked (HTTP %s) for %s", last_status, url)
                        break

                    if response["success"]:
                        candidate_html = response["html"]
                        candidate_data = parse_business(candidate_html, business)

                        if is_bot_challenge_or_empty(candidate_data, candidate_html):
                            logging.warning("Bot challenge / CAPTCHA detected for URL: %s", url)
                            last_error = "Bot challenge / CAPTCHA detected"
                            break
                        else:
                            html = candidate_html
                            scraped_result = candidate_data
                            success = True
                            last_visited_url = url
                            break

                if not success:
                    consecutive_errors += 1
                    record_failure(failed, business, last_error or "Fetch failed", last_status)
                    checkpoint["failed"] += 1
                    checkpoint["processed"] += 1
                    checkpoint["next_index"] = index + 1
                    checkpoint["last_business_id"] = business_id
                    save_json(checkpoint_file, checkpoint)

                    if last_error == "Bot challenge / CAPTCHA detected" or last_status in (403, 429):
                        logging.error("Bot challenge encountered. Safe-exiting to safeguard process state.")
                        break

                    if consecutive_errors >= getattr(config, "MAX_CONSECUTIVE_ERRORS", 5):
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
                    name, scraped_result.get("mobile_number"), scraped_result.get("address")
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

                if consecutive_errors >= getattr(config, "MAX_CONSECUTIVE_ERRORS", 5):
                    logging.error("Circuit breaker triggered.")
                    break

        try:
            context.close()
        except Exception:
            pass

    logging.info("=" * 60)
    logging.info("SCRAPER FINISHED | Saved file: %s", output_file)
    logging.info("=" * 60)


if __name__ == "__main__":
    main()