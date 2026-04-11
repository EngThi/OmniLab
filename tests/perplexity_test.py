import asyncio
import os
import sys
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def run_perplexity_auto():
    # Pergunta de teste para o Perplexity
    query = "Quais as últimas notícias sobre o projeto OmniLab do EngThi no GitHub?"
    target_url = f"https://www.perplexity.ai/search?q={query.replace(' ', '+')}"
    
    async with async_playwright() as p:
        user_data_dir = "./.playwright_data"
        
        print(f"🕵️ Rodando PERPLEXITY em modo FANTASMA (Janela oculta)...")
        
        # O Truque de Mestre: Headed (passa no Cloudflare) mas fora da tela!
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-position=-32000,-32000", # Move a janela para fora da tela
                "--disable-infobars"
            ]
        )

        page = browser_context.pages[0]
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)
        
        try:
            print(f"🔗 Consultando Perplexity: '{query}'")
            await page.goto(target_url, wait_until="domcontentloaded", timeout=45000)
            
            # Rotina de Bypass de Cloudflare (Auto-Clique)
            print("🛡️ Verificando barreiras de segurança...")
            await asyncio.sleep(3)
            
            # Tenta encontrar o iframe do Cloudflare e clicar nele
            try:
                cf_frame = page.frame_locator("iframe").first
                if await cf_frame.locator("body").is_visible(timeout=3000):
                    print("🧩 Cloudflare detectado! Simulando clique humano...")
                    # Simula o mouse indo até o checkbox
                    box = await cf_frame.locator("body").bounding_box()
                    if box:
                        x = box["x"] + box["width"] / 2
                        y = box["y"] + box["height"] / 2
                        await page.mouse.move(x, y, steps=10) # Movimento suave
                        await asyncio.sleep(1)
                        await page.mouse.click(x, y)
                        print("🖱️ Clique executado! Aguardando liberação...")
                        await asyncio.sleep(5)
            except Exception:
                pass # Se não achar o iframe, segue a vida

            print("⏳ Aguardando a IA formular a resposta...")
            await asyncio.sleep(20)

            
            # Tira snapshot da resposta mesmo se o título não carregar completamente
            title = await page.title()
            print(f"✅ Página alcançada: {title}")
            
            snapshot_path = "tests/perplexity_result.png"
            await page.screenshot(path=snapshot_path, full_page=True)
            print(f"📸 Resultado da IA salvo em: {snapshot_path}")
            
            # Tenta extrair o texto da resposta se possível
            content = await page.content()
            if "OmniLab" in content:
                print("💎 SUCESSO: O Perplexity encontrou e respondeu sobre o OmniLab!")
            else:
                print("⚠️ O Perplexity carregou, mas a resposta pode estar incompleta no snapshot.")

        except Exception as e:
            print(f"❌ Erro na consulta: {e}")
            await page.screenshot(path="tests/perplexity_error.png")
        
        await browser_context.close()

if __name__ == "__main__":
    asyncio.run(run_perplexity_auto())
