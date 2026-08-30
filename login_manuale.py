import json
import os
from playwright.sync_api import sync_playwright

def login_manuale():
    print("🚀 Avvio browser per il login manuale...")
    print("👉 Fai il login inserendo email e password, e risolvi il CAPTCHA manualmente.")
    print("⏳ Non chiudere il browser! Lo script si chiuderà da solo non appena il login andrà a buon fine.")
    
    with sync_playwright() as p:
        # headless=False ci permette di VEDERE il browser e interagire
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        page = context.new_page()
        
        page.goto("https://www.freelancer.com/login")
        
        # Aspettiamo che l'utente superi il login (quando scompare la pagina /login)
        print("Attendo che tu finisca il login...")
        page.wait_for_url(lambda url: "login" not in url, timeout=0) # 0 = aspetta all'infinito
        
        # Una volta loggati, diamo 5 secondi per far caricare bene i cookie
        page.wait_for_timeout(5000)
        
        # Salviamo i cookie
        os.makedirs("secrets", exist_ok=True)
        cookies = context.cookies()
        with open("secrets/freelancer_state.json", "w") as f:
            json.dump(cookies, f)
            
        print("\n✅ LOGIN COMPLETATO E COOKIE SALVATI!")
        print("Ho salvato i dati in secrets/freelancer_state.json.")
        print("Adesso il Demone o il Tester non avranno più bisogno di fare login o risolvere CAPTCHA!")

if __name__ == "__main__":
    login_manuale()
