import asyncio
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def find_perplexity_history():
    async with async_playwright() as p:
        user_data_dir = "./.playwright_data"
        print("🕵️ Buscando no seu histórico do Perplexity...")
        
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False, # Vamos manter visível para você ver se ele acha
            channel="chrome",
            args=["--window-position=0,0"]
        )

        page = browser_context.pages[0]
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)
        
        try:
            await page.goto("https://www.perplexity.ai/", wait_until="load")
            await asyncio.sleep(10) # Tempo para carregar a barra lateral
            
            # Busca todos os links que parecem threads
            links = await page.query_selector_all("a[href*='/search/']")
            print(f"\n📚 Threads encontradas no seu histórico:")
            for link in links:
                text = await link.inner_text()
                href = await link.get_attribute("href")
                if "OmniLab" in text or "EngThi" in text:
                    print(f"⭐ ENCONTRADO: {text} -> https://www.perplexity.ai{href}")
                else:
                    print(f"- {text[:30]}... -> https://www.perplexity.ai{href}")
            
            print("\n💡 Copie a URL desejada e me mande aqui!")
            await asyncio.sleep(60) # Tempo para você ver e copiar

        except Exception as e:
            print(f"❌ Erro: {e}")
        
        await browser_context.close()

if __name__ == "__main__":
    asyncio.run(find_perplexity_history())
