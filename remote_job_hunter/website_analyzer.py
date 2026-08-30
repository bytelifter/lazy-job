import base64
import uuid
import requests
from playwright.sync_api import sync_playwright
import time
import os

class WebsiteAnalyzer:
    def __init__(self):
        pass

    def capture_and_analyze(self, url: str) -> str:
        """
        Naviga al sito web specificato, cattura uno screenshot della pagina
        e lo invia a Llava per una critica su UI/UX.
        Ritorna la critica generata o una stringa vuota in caso di fallimento.
        """
        print(f"🌐 [WEB CRITIC] Analisi visiva del sito: {url}")
        screenshot_path = f"temp_screenshot_{uuid.uuid4().hex}.png"
        
        # 1. Cattura Screenshot
        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True)
                page = browser.new_page()
                page.set_viewport_size({"width": 1280, "height": 800})
                
                # Aggiungiamo http se manca
                if not url.startswith("http"):
                    url = "https://" + url
                    
                page.goto(url, timeout=20000)
                time.sleep(3) # Aspetta che carichi immagini
                
                page.screenshot(path=screenshot_path, full_page=False)
                browser.close()
                print("  └ 📸 Screenshot catturato con successo.")
        except Exception as e:
            print(f"  └ ⚠️ Impossibile accedere o catturare il sito: {e}")
            return ""

        # 2. Invia a Llava
        try:
            with open(screenshot_path, "rb") as image_file:
                img_b64 = base64.b64encode(image_file.read()).decode('utf-8')

            prompt = """
You are an expert Web Designer and Software Architect. 
Look at this screenshot of a small business website. 
Critique it briefly (max 2 sentences). 
Look for missing modern features: is it outdated? Does it look like it's missing a booking/reservation system? Does it look cheap? 
Provide your critique in Italian. Do not use quotes.
"""
            payload = {
                "model": "llava:7b",
                "prompt": prompt,
                "images": [img_b64],
                "stream": False
            }
            
            print("  └ 🧠 Richiesta valutazione a Llava...")
            res = requests.post("http://localhost:11434/api/generate", json=payload, timeout=120)
            
            if res.status_code == 200:
                critique = res.json().get("response", "").strip()
                print(f"  └ 💡 Critica generata: {critique}")
                
                # Cleanup
                if os.path.exists(screenshot_path):
                    os.remove(screenshot_path)
                    
                return critique
            else:
                print("  └ ⚠️ Errore di connessione a Ollama.")
                
        except Exception as e:
            print(f"  └ ⚠️ Errore durante l'analisi visiva del sito: {e}")
            
        if os.path.exists(screenshot_path):
            os.remove(screenshot_path)
            
        return ""
            
    def analyze_performance(self, url: str) -> str:
        """
        Interroga gratuitamente le API di Google PageSpeed Insights per recuperare 
        il tempo di caricamento (Time to Interactive / FCP) da mobile.
        Ritorna una stringa con la metrica o vuota se fallisce.
        """
        print(f"⚡ [SEO CRITIC] Analisi performance del sito: {url}")
        
        # Aggiungiamo http se manca
        if not url.startswith("http"):
            url = "https://" + url
            
        api_url = f"https://www.googleapis.com/pagespeedonline/v5/runPagespeed?url={url}&strategy=mobile"
        
        try:
            res = requests.get(api_url, timeout=30)
            if res.status_code == 200:
                data = res.json()
                try:
                    # Estraiamo il First Contentful Paint o il Time to Interactive
                    metrics = data["lighthouseResult"]["audits"]
                    tti_score = metrics["interactive"]["displayValue"]
                    speed_index = metrics["speed-index"]["displayValue"]
                    
                    critique = f"Le performance mobili sono scarse. Il sito impiega {tti_score} a diventare interattivo."
                    print(f"  └ 💡 Dati Estratti: {tti_score} TTI")
                    return critique
                except KeyError:
                    return ""
            else:
                return ""
        except Exception as e:
            print(f"  └ ⚠️ Errore PageSpeed: {e}")
            return ""
