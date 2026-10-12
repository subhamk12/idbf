import asyncio
from playwright.async_api import async_playwright

async def inspect_target(url):
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        context = await browser.new_context()
        page = await context.new_page()

        # Listen to response headers
        page.on("response", lambda resp: print(f"[HTTP {resp.status}] {resp.url}\n  Server: {resp.headers.get('server')}\n  Set-Cookie: {resp.headers.get('set-cookie')}\n"))

        print(f"--- Navigating to {url} ---")
        await page.goto(url)
        
        # Evaluate common bot flags inside the loaded page
        bot_flags = await page.evaluate("""() => ({
            webdriver: navigator.webdriver,
            hasChromeObj: !!window.chrome,
            userAgent: navigator.userAgent,
            pluginsCount: navigator.plugins.length,
            languages: navigator.languages
        })""")
        
        print("--- Browser Context Flags ---")
        for k, v in bot_flags.items():
            print(f"  {k}: {v}")
            
        await browser.close()

# Run inspection against your target URL
asyncio.run(inspect_target("https://mumbai.idbf.in/"))