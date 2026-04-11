import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def inspect_chat_input():
    url = "https://www.perplexity.ai/search/quais-as-ultimas-noticias-sobr-I5CPnHy8STedOVHTqbOWwA"
    async with async_playwright() as p:
        user_data_dir = "./.playwright_data"
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            channel="chrome"
        )
        page = browser_context.pages[0]
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)
        
        try:
            await page.goto(url, wait_until="load")
            await asyncio.sleep(10)
            
            # Tenta capturar todos os possíveis inputs
            textareas = await page.query_selector_all("textarea")
            print(f"🔎 Encontradas {len(textareas)} textareas.")
            for i, ta in enumerate(textareas):
                placeholder = await ta.get_attribute("placeholder")
                print(f"TA {i}: placeholder='{placeholder}'")
            
            divs = await page.query_selector_all("div[contenteditable='true']")
            print(f"🔎 Encontrados {len(divs)} divs editáveis.")
            
            await page.screenshot(path="tests/inspect_layout.png")
            print("📸 Layout inspecionado e salvo em tests/inspect_layout.png")

        except Exception as e:
            print(f"❌ Erro: {e}")
        
        await browser_context.close()

if __name__ == "__main__":
    asyncio.run(inspect_chat_input())
