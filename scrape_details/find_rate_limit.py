import time
import sys
from curl_cffi import requests

# ============================================================
# TARGET CONFIGURATION
# ============================================================
TARGET_URL = "https://mumbai.idbf.in/"  # Replace with target domain URL
IMPERSONATE_BROWSER = "chrome120"       # TLS fingerprint matching Chrome

# Headers matching your real browser signature
HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}


def send_probe(url):
    """Executes a single probe request and checks for success vs rate-limit block."""
    try:
        resp = requests.get(
            url, 
            headers=HEADERS, 
            impersonate=IMPERSONATE_BROWSER, 
            timeout=10
        )
        if resp.status_code == 200:
            return True, resp.status_code
        elif resp.status_code in (403, 429, 503):
            return False, resp.status_code
        else:
            return False, resp.status_code
    except Exception as e:
        return False, str(e)


def measure_burst_capacity(url):
    """Phase 1: Finds immediate burst capacity before getting blocked."""
    print("\n[PHASE 1] Measuring Burst Capacity (Sending immediate rapid requests)...")
    count = 0
    while True:
        success, status = send_probe(url)
        if success:
            count += 1
            print(f"  Request #{count}: OK (HTTP 200)")
            time.sleep(0.05)  # Minimal network gap
        else:
            print(f"\n--> BLOCKED at Request #{count + 1}! Status: {status}")
            print(f"--> Measured Immediate Burst Capacity: {count} requests")
            return count


def binary_search_pacing_delay(url, min_delay=0.5, max_delay=30.0, max_test_requests=10):
    """
    Phase 2: Uses Binary Search to find the exact minimum delay (seconds/request)
    that allows continuous scraping without getting blocked.
    """
    print("\n[PHASE 2] Binary Search for Safe Request Pacing Delay...")
    print("----------------------------------------------------------------")
    print("NOTE: You MUST reset/change your IP (e.g., toggle VPN/Hotspot)")
    print("between failed runs if you are currently hard-blocked.")
    print("----------------------------------------------------------------")

    optimal_delay = max_delay
    low = min_delay
    high = max_delay
    tolerance = 0.5  # Stop searching when bounds are within 0.5s

    while (high - low) > tolerance:
        mid_delay = round((low + high) / 2, 2)
        print(f"\nTesting Candidate Delay: {mid_delay}s per request")
        
        input("--> Toggle/Reset your IP, then press ENTER to start this test batch...")

        is_stable = True
        successful_in_batch = 0

        for i in range(1, max_test_requests + 1):
            success, status = send_probe(url)
            if success:
                successful_in_batch += 1
                print(f"  [{i}/{max_test_requests}] Success ({status}) | Next probe in {mid_delay}s...")
                time.sleep(mid_delay)
            else:
                print(f"  [{i}/{max_test_requests}] BLOCKED ({status}) at delay {mid_delay}s!")
                is_stable = False
                break

        if is_stable:
            print(f"--> Delay of {mid_delay}s PASSED ({max_test_requests}/{max_test_requests} successful).")
            optimal_delay = mid_delay
            high = mid_delay  # Try searching for a faster safe delay
        else:
            print(f"--> Delay of {mid_delay}s FAILED. Slower delay required.")
            low = mid_delay   # Delay too fast, increase bounds

    print("\n========================================================")
    print(f"RESULT: Optimal Safe Request Delay = {optimal_delay}s per request")
    print(f"ESTIMATED RATE LIMIT = approx {round(3600 / optimal_delay)} requests / hour")
    print("========================================================")
    return optimal_delay


if __name__ == "__main__":
    print("=== Empirical Rate Limit & Binary Search Finder ===")
    
    # Phase 1: Measure rapid burst limit
    burst = measure_burst_capacity(TARGET_URL)
    
    # Phase 2: Binary Search for minimum safe pacing delay
    if burst < 5:
        print("\nBurst capacity is low. Executing Binary Search pacing probe...")
        binary_search_pacing_delay(TARGET_URL, min_delay=1.0, max_delay=30.0)
    else:
        print(f"\nBurst capacity is {burst}. Starting Binary Search starting from lower bounds...")
        binary_search_pacing_delay(TARGET_URL, min_delay=0.5, max_delay=15.0)