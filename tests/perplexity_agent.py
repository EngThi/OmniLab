import asyncio
import os
import sys
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def run_perplexity_agent():
    target_url = "https://www.perplexity.ai/"
    
    async with async_playwright() as p:
        user_data_dir = "./.playwright_data"
        
        print(f"🚀 Abrindo CHROME REAL para login no Perplexity...")
        
        # Mudanças cruciais:
        # 1. channel="chrome" (Usa o seu Chrome instalado)
        # 2. Menos flags de 'bot' no args
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            channel="chrome", # <--- USA SEU CHROME REAL
            args=[
                "--disable-blink-features=AutomationControlled",
                # Removido --no-sandbox e outras flags suspeitas
            ],
            # Deixamos o viewport real
            viewport={'width': 1366, 'height': 768}
        )

        page = browser_context.pages[0]
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)
        
        try:
            print(f"🔗 Navegando...")
            await page.goto(target_url, wait_until="networkidle", timeout=60000)
            
            print("\n" + "!"*50)
            print("DICA DE OURO PARA O LOGIN:")
            print("1. Se o login direto do Google falhar, tente entrar")
            print("   no seu Gmail primeiro na mesma janela.")
            print("2. Depois de logar no Gmail, volte para o Perplexity.")
            print("3. O Perplexity deverá reconhecer a sessão automaticamente.")
            print("!"*50 + "\n")
            
            # 3 minutos para você logar com calma
            await asyncio.sleep(180)
            
            await page.screenshot(path="tests/perplexity_top_session.png")
            print(f"✅ Sessão salva com sucesso!")

        except Exception as e:
            print(f"❌ Erro: {e}")
        
        await browser_context.close()

if __name__ == "__main__":
    asyncio.run(run_perplexity_agent())
