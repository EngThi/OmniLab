import asyncio
import os
from playwright.async_api import async_playwright

import sys

async def run_test_agent():
    # Pega a URL do argumento se existir, senão usa localhost
    target_url = sys.argv[1] if len(sys.argv) > 1 else "http://localhost:8000"
    
    async with async_playwright() as p:
        browser_type = p.chromium
        try:
            browser = await browser_type.launch(headless=True)
        except Exception:
            print("Chromium padrão não encontrado, tentando canal 'chrome' do sistema...")
            browser = await browser_type.launch(headless=True, channel="chrome")

        page = await browser.new_page()
        print(f"Abrindo interface: {target_url}")
        await page.goto(target_url)

        # 1. Validar título e elementos iniciais
        title = await page.title()
        print(f"Título da página: {title}")
        
        # 2. Clicar no botão 'Scan' ou 'Analyze'
        print("Acionando comando de análise...")
        try:
            await page.click("button:has-text('Scan')", timeout=5000)
        except:
            print("Botão 'Scan' não encontrado, tentando 'Analyze'...")
            await page.click("button:has-text('Analyze')")

        # 3. Validar se o log apareceu no #log-console
        # O log-console no HTML tem flex-direction: column-reverse, 
        # então o novo log deve ser o primeiro item visualmente.
        await page.wait_for_selector(".log-entry")
        logs = await page.query_selector_all(".log-entry")
        if logs:
            last_log = await logs[0].inner_text()
            print(f"Último log capturado: {last_log}")
            if "ANALYZE" in last_log:
                print("SUCESSO: Comando Scan detectado no HUD!")
            else:
                print("FALHA: Comando não encontrado no log.")
        else:
            print("FALHA: Nenhum log gerado no console.")

        # 4. Tirar um snapshot visual (como sugerido pelo Playwright CLI)
        await page.screenshot(path="tests/hud_snapshot.png")
        print("Snapshot salvo em tests/hud_snapshot.png")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(run_test_agent())
