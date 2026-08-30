import os
from datetime import datetime

class DemoGenerator:
    def __init__(self):
        self.output_dir = "demos"
        if not os.path.exists(self.output_dir):
            os.makedirs(self.output_dir)

    def generate_mini_site(self, business_name: str, niche: str) -> str:
        """
        Genera un mini-sito demo in HTML per il potenziale cliente.
        Ritorna il percorso locale (o l'URL fittizio) della demo.
        """
        import re
        safe_name = re.sub(r'[^a-z0-9]', '_', business_name.lower())
        filename = f"{safe_name}_demo.html"
        filepath = os.path.join(self.output_dir, filename)
        
        html_content = f"""
<!DOCTYPE html>
<html lang="it">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Demo Gestionale - {business_name}</title>
    <style>
        body {{
            font-family: 'Inter', sans-serif;
            background-color: #f4f7f6;
            color: #333;
            margin: 0;
            padding: 0;
        }}
        header {{
            background-color: #1a1a1a;
            color: #fff;
            padding: 2rem;
            text-align: center;
        }}
        .container {{
            max-width: 800px;
            margin: 2rem auto;
            padding: 2rem;
            background: #fff;
            border-radius: 8px;
            box-shadow: 0 4px 6px rgba(0,0,0,0.1);
        }}
        .btn {{
            display: inline-block;
            background-color: #007bff;
            color: #fff;
            padding: 10px 20px;
            text-decoration: none;
            border-radius: 5px;
            margin-top: 20px;
        }}
    </style>
</head>
<body>
    <header>
        <h1>{business_name} - Il Tuo Nuovo Ecosistema Digitale</h1>
        <p>Soluzione su misura per la nicchia: {niche}</p>
    </header>
    <div class="container">
        <h2>Perché hai bisogno di questo sistema?</h2>
        <p>I tuoi clienti cercano comodità. Con questo portale potrai gestire prenotazioni, ordini e richieste in tempo reale, aumentando il fatturato senza sforzo.</p>
        
        <h3>Funzionalità Incluse:</h3>
        <ul>
            <li>Dashboard di controllo intuitiva</li>
            <li>Sistema di prenotazione h24</li>
            <li>Notifiche automatiche via WhatsApp ai clienti</li>
            <li>Ottimizzazione SEO per battere la concorrenza locale</li>
        </ul>
        
        <a href="#" class="btn">Prenota una Call Gratuita per l'Attivazione</a>
    </div>
</body>
</html>
"""
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html_content.strip())
            
        print(f"🎨 [DEMO GENERATOR] Mini-sito demo salvato localmente: {filepath}")
        
        # Il file HTML è pronto localmente.
        return filepath
        
    def host_on_surge(self, business_name: str, filepath: str) -> str:
        """
        Carica il file HTML su Surge.sh e ritorna l'URL HTTPS.
        Richiede che 'surge' sia installato globalmente e autenticato.
        """
        import re, shutil, subprocess
        safe_name = re.sub(r'[^a-z0-9]', '-', business_name.lower())[:20]
        domain = f"lazy-{safe_name}-demo.surge.sh"
        deploy_dir = os.path.join(self.output_dir, f"deploy_{safe_name}")
        os.makedirs(deploy_dir, exist_ok=True)
        shutil.copy(filepath, os.path.join(deploy_dir, "index.html"))
        
        try:
            print(f"🚀 [SURGE] Deploying demo per {business_name} su {domain}...")
            # Usa shell=True perché surge è uno script npm (surge.cmd) su Windows
            subprocess.run(["surge", deploy_dir, domain], shell=True, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            print(f"✅ [SURGE] Deploy completato: https://{domain}")
            return f"https://{domain}"
        except Exception as e:
            print(f"❌ Errore Surge: {e}")
            return ""
