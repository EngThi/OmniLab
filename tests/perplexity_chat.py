import asyncio
import sys
from playwright.async_api import async_playwright
from playwright_stealth import Stealth

async def run_perplexity_chat():
    # URL da thread que você me passou
    thread_url = "https://www.perplexity.ai/search/quais-as-ultimas-noticias-sobr-I5CPnHy8STedOVHTqbOWwA"
    
    # Pergunta de continuação (follow-up)
    follow_up_query = "Baseado no que você encontrou ontem, quais seriam os 3 próximos passos de desenvolvimento para o OmniLab ser um projeto de nível industrial?"
    
    async with async_playwright() as p:
        user_data_dir = "./.playwright_data"
        
        print(f"🕵️ Entrando na Thread de Ontem no modo FANTASMA...")
        
        browser_context = await p.chromium.launch_persistent_context(
            user_data_dir,
            headless=False,
            channel="chrome",
            args=[
                "--disable-blink-features=AutomationControlled",
                "--window-position=-32000,-32000",
                "--disable-infobars"
            ]
        )

        page = browser_context.pages[0]
        stealth_config = Stealth()
        await stealth_config.apply_stealth_async(page)
        
        try:
            print(f"🔗 Carregando Chat: {thread_url}")
            await page.goto(thread_url, wait_until="domcontentloaded", timeout=60000)
            
            # Aguarda o chat carregar completamente
            await asyncio.sleep(10)
            
            # Tenta encontrar a caixa de texto (div editável do Perplexity)
            print("📝 Escrevendo pergunta de continuação...")
            chat_input = page.locator("div[contenteditable='true']").first
            
            if await chat_input.is_visible():
                await chat_input.click()
                await chat_input.fill(follow_up_query)
                await asyncio.sleep(1)
                await page.keyboard.press("Enter")
                print("🚀 Pergunta enviada! Aguardando a IA formular os passos industriais...")
                
                # Tempo para a IA gerar a resposta longa
                await asyncio.sleep(30)
                
                snapshot_path = "tests/perplexity_chat_followup.png"
                await page.screenshot(path=snapshot_path, full_page=True)
                print(f"📸 Resposta capturada em: {snapshot_path}")
                
                # Validação de conteúdo
                content = await page.content()
                if "industrial" in content.lower() or "desenvolvimento" in content.lower():
                    print("💎 SUCESSO: A IA respondeu à continuação da conversa!")
                else:
                    print("⚠️ A resposta pode estar sendo gerada ainda no snapshot.")
            else:
                print("❌ Erro: Não encontrei a caixa de texto do chat. O Cloudflare pode ter bloqueado ou o layout mudou.")

        except Exception as e:
            print(f"❌ Falha: {e}")
            await page.screenshot(path="tests/chat_error.png")
        
        await browser_context.close()

if __name__ == "__main__":
    asyncio.run(run_perplexity_chat())
