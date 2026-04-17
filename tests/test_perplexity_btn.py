import asyncio
import os
import json
from playwright.async_api import async_playwright
import playwright_stealth

async def run_test():
    print("🚀 Starting Perplexity Interaction Test...")
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            viewport={'width': 1280, 'height': 720},
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )
        page = await context.new_page()
        
        try:
            st_func = getattr(playwright_stealth, 'stealth_async', getattr(playwright_stealth, 'stealth', None))
            if st_func: await st_func(page)
        except: pass

        cookies_path = "cookies.json"
        if os.path.exists(cookies_path):
            with open(cookies_path, 'r') as f:
                try:
                    raw = json.load(f)
                    clean = []
                    for c in raw:
                        if not isinstance(c, dict): continue
                        nc = {"name": str(c.get("name", "")), "value": str(c.get("value", "")), "domain": str(c.get("domain", "")), "path": str(c.get("path", "/")), "secure": bool(c.get("secure", True)), "httpOnly": bool(c.get("httpOnly", False))}
                        if "expirationDate" in c: nc["expires"] = int(float(c["expirationDate"]))
                        clean.append(nc)
                    await context.add_cookies(clean)
                    print("🍪 Cookies injected.")
                except: pass

        print("📡 Navigating to Perplexity...")
        await page.goto("https://www.perplexity.ai", wait_until="load", timeout=60000)
        await asyncio.sleep(5)
        
        print("🖱️ Clearing cookie banner...")
        try:
            await page.click("button:has-text('Entendi'), button:has-text('Accept')", timeout=5000)
            print("✅ Banner cleared.")
        except:
            print("ℹ️ No banner found or already cleared.")

        print("🖱️ Interacting with input...")
        try:
            # Perplexity's input is often a div contenteditable or textarea
            await page.click("textarea, [contenteditable='true']", timeout=10000)
            print("✅ Focused.")
            
            # Click the 'Write' or 'Submit' button (arrow icon)
            # The button usually has a specific class or svg icon
            await page.click("button:has(svg), [aria-label*='Submit']", timeout=5000)
            print("✅ Clicked.")
        except Exception as e:
            print(f"⚠️ Interaction failed: {e}")
            
        await asyncio.sleep(5)
        await page.screenshot(path="tests/perplexity_test_result_final.png")
        print("📸 Final screenshot saved.")
        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test())
