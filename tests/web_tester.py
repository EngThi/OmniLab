import asyncio
import sys
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def run_web_test():
    # Pega a URL do argumento do terminal ou usa uma padrão com muita proteção
    target_url = sys.argv[1] if len(sys.argv) > 1 else "https://nowsecure.nl"
    
    async with async_playwright() as p:
        user_data_dir = "./.playwright_data"
        
        print(f"👻 Iniciando Testador Fantasma para: {target_url}")
        
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False, # Essencial para passar em proteções avançadas
            channel="chrome", # Usa o seu Chrome real
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-position=0,0", # Janela VISÍVEL no monitor
                "--disable-infobars"
            ],
            viewport={'width': 1920, 'height': 1080}
        )

        page = browser_context.pages[0]
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)
        
        try:
            print(f"🔗 Navegando...")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            
            print("⏳ MODO VISÍVEL: Aguardando 30 segundos para você clicar no Cloudflare manualmente se aparecer...")
            await asyncio.sleep(30)


            title = await page.title()
            print(f"✅ Título da página: {title}")
            
            # Gera um nome de arquivo limpo baseado na URL
            safe_name = target_url.replace("https://", "").replace("http://", "").replace("/", "_").replace("?", "_")[:30]
            snapshot_path = f"tests/result_{safe_name}.png"
            
            await page.screenshot(path=snapshot_path, full_page=True)
            print(f"📸 Sucesso! Veja o que o robô enxergou abrindo o arquivo: {snapshot_path}")

        except Exception as e:
            print(f"❌ Falha ao acessar a página: {e}")
            await page.screenshot(path="tests/error_snapshot.png")
            print("📸 Snapshot do erro salvo em tests/error_snapshot.png")
        
        await browser_context.close()

if __name__ == "__main__":
    asyncio.run(run_web_test())
