import subprocess

# Paste the EXACT list of arguments here
cmd = [
    "curl", "-v", "-sL",
    "-A", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "-H", "Accept-Language: en-US,en;q=0.9",
    "YOUR_URL_HERE",
    "YOUR_URL_HERE"
]

res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

print("Exit Code:", res.returncode)
print("Stderr/Verbose Output:\n", res.stderr[:1000])  # Look for SSL errors, 403s, or header rejections
print("Stdout Length:", len(res.stdout))