import asyncio
import os
import sys
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def run_stealth_agent():
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://www.google.com/search?q=OmniLab+EngThi"
    
    async with async_playwright() as p:
        user_data_dir = "./.playwright_data"
        
        print(f"🚀 Iniciando navegador em modo STEALTH para: {target_url}")
        
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=True, # Modo INVISÍVEL: Agora usando a sessão salva!
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-infobars",
                "--window-position=0,0",
                "--ignore-certificate-errors",
                "--disable-extensions",
                "--disable-notifications",
                "--password-store=basic"
            ],
            user_agent="Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36"
        )

        page = browser_context.pages[0]
        
        # Usando a classe Stealth explicitamente
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)
        
        try:
            print(f"🔗 Navegando...")
            await page.goto(target_url, wait_until="networkidle", timeout=60000)
            
            # Pequeno delay humano para o JS carregar
            await asyncio.sleep(5)
            
            title = await page.title()
            print(f"✅ Título alcançado: {title}")
            
            snapshot_path = "tests/stealth_result.png"
            await page.screenshot(path=snapshot_path, full_page=True)
            print(f"📸 Snapshot salvo em: {snapshot_path}")

        except Exception as e:
            print(f"❌ Erro: {e}")
        
        await browser_context.close()

if __name__ == "__main__":
    asyncio.run(run_stealth_agent())
