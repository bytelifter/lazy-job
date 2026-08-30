import os
import time

class SaaSFactory:
    """
    Automated pipeline to generate a micro-SaaS product.
    Generates backend, frontend, and Stripe integration placeholders.
    Forces the user to review it locally before deployment.
    """
    
    def __init__(self, ai_council):
        self.ai = ai_council
        self.output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "my_saas_portfolio")
        os.makedirs(self.output_dir, exist_ok=True)
        
    def generate_micro_saas(self, idea_name: str, description: str, price_eur: int = 5):
        print(f"🏭 [SaaS Factory] Inizio generazione di: {idea_name}")
        
        project_dir = os.path.join(self.output_dir, idea_name.lower().replace(" ", "_"))
        os.makedirs(project_dir, exist_ok=True)
        
        print("  └ 💳 Generazione automatica del Link di Pagamento Stripe...")
        
        stripe_url = "https://buy.stripe.com/test_placeholder"
        
        try:
            import json
            import stripe
            stripe_api_key = os.environ.get("STRIPE_API_KEY", "")
            
            if stripe_api_key:
                    stripe.api_key = stripe_api_key
                    # 1. Crea il Prodotto su Stripe
                    # Siccome usiamo Managed Payments, specifichiamo un tax_code per software (txcd_10000000)
                    product = stripe.Product.create(
                        name=idea_name,
                        tax_code="txcd_10000000"
                    )
                    # 2. Crea il Prezzo (Stripe usa i centesimi, quindi 10€ = 1000)
                    price = stripe.Price.create(
                        product=product.id,
                        unit_amount=price_eur * 100,
                        currency="eur"
                    )
                    # 3. Genera il Link di Pagamento
                    payment_link = stripe.PaymentLink.create(
                        line_items=[{"price": price.id, "quantity": 1}]
                    )
                    stripe_url = payment_link.url
                    print(f"    └ ✅ Link Stripe creato con successo: {stripe_url}")
            else:
                print("    └ ⚠️ Nessuna 'STRIPE_API_KEY' in .env. Uso il link placeholder.")
        except Exception as e:
            print(f"    └ ❌ Errore API Stripe (Uso placeholder): {e}")

        print("  └ 🧠 Progettazione Architettura e Backend...")
        # Simulated AI Generation time
        time.sleep(1)
        
        backend_code = f"""
import uvicorn
from fastapi import FastAPI
from fastapi.responses import HTMLResponse, RedirectResponse
import os

app = FastAPI()

@app.get("/", response_class=HTMLResponse)
def serve_frontend():
    # Carica la pagina HTML in automatico
    html_path = os.path.join(os.path.dirname(__file__), "index.html")
    with open(html_path, "r", encoding="utf-8", errors="replace") as f:
        return f.read()

# CRITICAL RULE: Pagamenti gestiti SOLO via Stripe.
@app.get("/checkout")
def stripe_checkout():
    # Rimanda l'utente direttamente alla pagina di pagamento sicura di Stripe
    return RedirectResponse(url="{stripe_url}")
    
if __name__ == "__main__":
    print("🚀 Server SaaS avviato! Apri http://127.0.0.1:8000 nel tuo browser.")
    uvicorn.run(app, host="127.0.0.1", port=8000)
"""
        with open(os.path.join(project_dir, "main.py"), "w", encoding="utf-8") as f:
            f.write(backend_code.strip())
            
        print("  └ 🎨 Generazione Frontend (HTML/Tailwind)...")
        time.sleep(2)
        
        frontend_code = f"""
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{idea_name}</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 text-white flex flex-col items-center justify-center h-screen">
    <h1 class="text-4xl font-bold mb-4">{idea_name}</h1>
    <p class="text-gray-400 mb-8">{description}</p>
    
    <!-- Privacy e Sicurezza (GDPR) Inclusi di default -->
    <div class="fixed bottom-0 w-full bg-gray-800 p-4 text-center text-sm text-gray-400">
        Usiamo i cookie per migliorare il servizio. <a href="#" class="underline">Privacy Policy</a>
    </div>
    
    <a href="/checkout" class="bg-blue-600 hover:bg-blue-700 px-6 py-3 rounded-lg font-bold">
        Compra ora per {price_eur}€ (via Stripe)
    </a>
</body>
</html>
"""
        with open(os.path.join(project_dir, "index.html"), "w", encoding="utf-8") as f:
            f.write(frontend_code.strip())
            
        print("\n" + "="*50)
        print("✅ [SAAS GENERATO CON SUCCESSO]")
        print(f"I file si trovano in: {project_dir}")
        print("⚠️ AZIONE RICHIESTA: Apri il file 'index.html' nel tuo browser per visualizzarlo.")
        print("⚠️ Controlla l'aspetto e verifica che il link di Stripe sia inserito correttamente prima di pensare al deploy online.")
        print("="*50 + "\n")

if __name__ == "__main__":
    # Test run
    factory = SaaSFactory(ai_council=None)
    factory.generate_micro_saas("PDF Translator Pro", "Traduci PDF istantaneamente preservando il layout.", 10)
