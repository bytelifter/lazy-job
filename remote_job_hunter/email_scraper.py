import re
import requests
from bs4 import BeautifulSoup
from typing import Optional

class EmailScraper:
    """
    Visits a website and attempts to extract an email address using Regex.
    """
    
    def __init__(self):
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        }
        # Regex per email valide, escludendo estensioni di immagini o robaccia tecnica
        self.email_regex = re.compile(r'[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}')
        
    def extract_email(self, url: str) -> Optional[str]:
        """
        Cerca l'email del business su più pagine del sito.
        Prima prova la home, poi le pagine Contatti/Chi siamo più comuni.
        """
        if not url:
            return None
            
        if not url.startswith('http'):
            url = 'https://' + url
        
        base_url = url.rstrip('/')
        
        # Pagine da visitare in ordine di probabilità
        pages_to_try = [
            base_url,
            base_url + '/contatti',
            base_url + '/contact',
            base_url + '/chi-siamo',
            base_url + '/about',
            base_url + '/contatti.html',
            base_url + '/contact.html',
        ]
        
        for page_url in pages_to_try:
            result = self._scrape_email_from_page(page_url)
            if result:
                return result
                
        print(f"    └ ❌ Nessuna email trovata su nessuna pagina di {base_url}.")
        return None

    def _scrape_email_from_page(self, url: str) -> Optional[str]:
        """Tenta di estrarre una email da una singola pagina."""
        print(f"  └ 🌐 Controllo email: {url}...")
        try:
            response = requests.get(url, headers=self.headers, timeout=8)
            if response.status_code != 200:
                return None
                
            emails = self.email_regex.findall(response.text)
            
            # Filtra falsi positivi
            valid_emails = []
            for email in emails:
                email_lower = email.lower()
                if not any(email_lower.endswith(ext) for ext in ['.png', '.jpg', '.jpeg', '.gif', '.webp', '.svg']):
                    if not any(junk in email_lower for junk in ['sentry', 'wixpress', 'example.com', 'schema.org']):
                        valid_emails.append(email_lower)
            
            if valid_emails:
                best_email = valid_emails[0]
                # Preferisci info@, contatti@, hello@
                for em in valid_emails:
                    if any(em.startswith(p) for p in ['info@', 'contatt', 'hello@', 'contact@']):
                        best_email = em
                        break
                print(f"    └ 📧 Email trovata: {best_email}")
                return best_email
        except Exception:
            pass
        return None

if __name__ == "__main__":
    scraper = EmailScraper()
    print(scraper.extract_email("https://www.google.com"))
