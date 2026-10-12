# Construct the exact terminal command string
import subprocess
command_str = 'curl -sL -A "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36" -b "null=null" -H "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36" -H "Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8" -H "Accept-Language: en-US,en;q=0.9" -H "Sec-Fetch-Dest: document" -H "Sec-Fetch-Mode: navigate" -H "Sec-Fetch-Site: same-origin" -w "\n\nHTTP STATUS: %{http_code}\n" "https://navi-mumbai.idbf.in/4840356/daikin-ac-sale-s-with-super-service-navi-mumbai"'
result = subprocess.run(command_str, shell=True, capture_output=True, text=True)
print(result)