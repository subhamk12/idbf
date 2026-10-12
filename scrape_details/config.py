import os

# ============================================================
# Request Pacing & Rate Limits
# ============================================================

# Base delay between requests
REQUEST_DELAY = 45.0

# Random additional delay
JITTER_RANGE = (15, 45.0)

# Maximum retries for transient failures
MAX_RETRIES = 3

# Exponential backoff factor
BACKOFF_FACTOR = 5.0

# Stop the scraper after this many consecutive failures
MAX_CONSECUTIVE_ERRORS = 5


# ============================================================
# Curl Execution
# ============================================================

CURL_BIN = "/usr/bin/curl"
CURL_MAX_TIME = 45

# Exact template string matching your working subprocess terminal test
CURL_COMMAND_TEMPLATE = (
    'curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36" '
    '-b "null=null" '
    '-H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36" '
    '-H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8" '
    '-H "Accept-Language: en-US,en;q=0.9" '
    '-H "Sec-Fetch-Dest: document" '
    '-H "Sec-Fetch-Mode: navigate" '
    '-H "Sec-Fetch-Site: same-origin" '
    '-w "\\n\\nHTTP STATUS: %{{http_code}}\\n" {url}'
)


# ============================================================
# Paths
# ============================================================

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

INPUT_FILE = os.path.join(BASE_DIR, "businesses.json")
OUTPUT_FILE = os.path.join(BASE_DIR, "scraped_businesses.json")
CHECKPOINT_FILE = os.path.join(BASE_DIR, "checkpoint.json")
FAILED_FILE = os.path.join(BASE_DIR, "failed_businesses.json")
HTML_CACHE_DIR = os.path.join(BASE_DIR, "html_cache")
LOG_FILE = os.path.join(BASE_DIR, "scraper.log")


# ============================================================
# Scraping Behavior
# ============================================================

SAVE_HTML = True
USE_HTML_CACHE = True
FORCE_RESTART = False


# ============================================================
# Extraction Options
# ============================================================

EXTRACT_CONTACT = True
EXTRACT_FAQS = True
EXTRACT_WHY_CHOOSE = True
EXTRACT_REVIEWS = True
MAX_REVIEWS = 100