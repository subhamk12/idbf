import os

# 1. Target domain (change to your target site's domain)
DOMAIN = ".idbf.in" 

# 2. Raw Cookie Header string from DevTools Network Tab
RAW_COOKIE_HEADER = "_ga_0LR2K01YFQ=GS2.1.s1791490586$o7$g1$t1791490591$j55$l0$h0; _ga=GA1.1.594182871.1791317821; null=null"

def create_cookie_jar(raw_header, domain, output_filename="session_cookies.txt"):
    lines = [
        "# Netscape HTTP Cookie File",
        "# http://curl.haxx.se/rfc/cookie_spec.html",
        "# Generated automatically",
        ""
    ]
    
    # Expiration set far in the future (1 year epoch timestamp)
    expiry = "1823026591" 

    pairs = raw_header.split(";")
    for pair in pairs:
        pair = pair.strip()
        if not pair or "=" not in pair:
            continue
        
        name, value = pair.split("=", 1)
        name = name.strip()
        value = value.strip()

        # Skip dummy null cookies
        if name == "null":
            continue

        # Format: domain, include_subdomains, path, secure, expiry, name, value
        cookie_line = f"{domain}\tTRUE\t/\tFALSE\t{expiry}\t{name}\t{value}"
        lines.append(cookie_line)

    filepath = os.path.join(os.path.dirname(os.path.abspath(__file__)), output_filename)
    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")
    
    print(f"Successfully generated Netscape cookie jar at: {filepath}")

if __name__ == "__main__":
    create_cookie_jar(RAW_COOKIE_HEADER, DOMAIN)