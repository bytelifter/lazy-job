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
    return RedirectResponse(url="https://buy.stripe.com/test_4gM14n6Eug4p4fR8cCbII00")
    
if __name__ == "__main__":
    print("🚀 Server SaaS avviato! Apri http://127.0.0.1:8000 nel tuo browser.")
    uvicorn.run(app, host="127.0.0.1", port=8000)