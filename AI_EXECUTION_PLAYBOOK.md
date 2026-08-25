# ⚡ AI & Scripting Execution Playbook
### *Come Risolvere Qualsiasi Gig o Contratto in 15 Minuti con l'AI e Python*

Questa guida contiene la "ricetta" tecnica esatta e gli strumenti gratuiti/open-source da usare per ogni tipo di lavoro trovato da **LazyJobHunter** e **Upwork Sniper**.

---

## 1. 🌐 Traduzione, Localizzazione & Sottotitoli (Tutte le Lingue)
> **Paga Tipica:** 100$ – 600$ per documento/sito o 2.000€–3.500€/mese
* **Strumenti da usare:**
  * **Testi lunghi / Documenti:** `DeepL API` (Free Tier) oppure Ollama locale (`qwen2.5-coder:7b` / `qwen2.5:1.5b`).
  * **Audio / Video in Testo / Sottotitoli:** `faster-whisper` (Python) o `Whisper.cpp` (ultra-veloce su GPU/CPU).
  * **Editing Sottotitoli:** `SubtitleEdit` (Open Source) o libreria Python `pysrt`.
* **Ricetta di Esecuzione (10 Minuti):**
  1. Per documenti (`.docx`, `.pdf`, `.md`): usa uno script Python che legge i paragrafi, li passa a DeepL/Ollama preservando tag HTML e formattazione, e salva il file tradotto.
  2. Per audio/video: lancia `whisper audio.mp3 --model medium --language it` e ottieni il file `.srt` timestampato perfetto in 30 secondi.

---

## 2. ✍️ Copywriting, Articoli SEO & Newsletter
> **Paga Tipica:** 150$ – 800$ per batch di articoli
* **Strumenti da usare:**
  * **Generatore:** Ollama (`qwen2.5-coder:7b`) oppure script Python con API Groq/OpenAI.
  * **Formattatore:** Libreria Python `markdown` o `python-docx`.
* **Ricetta di Esecuzione (5 Minuti):**
  1. Prendi la lista di 10-20 keyword fornite dal cliente.
  2. Esegui uno script Python che cicla sulle keyword con un prompt strutturato (H1, H2, FAQ, SEO meta description).
  3. L'AI genera 20 articoli completi e formattati in Markdown in 2 minuti. Fai una rapida lettura di 3 minuti ed esporta in Word/PDF.

---

## 3. 🐍 Web Scraping & Raccolta Dati (E-Commerce, Real Estate, Directory)
> **Paga Tipica:** 200$ – 1.000$ a sito
* **Strumenti da usare:**
  * **Siti dinamici con JavaScript/Cloudflare:** `Playwright Python` o `curl_cffi`.
  * **Siti statici:** `Requests` + `BeautifulSoup4`.
  * **Esportazione:** `Pandas` (per creare `.csv` o `.xlsx`).
* **Ricetta di Esecuzione (15 Minuti):**
  1. Chiedi all'AI: *"Scrivi uno script Playwright Python che apre [URL], naviga le pagine 1..N, estrae Titolo, Prezzo, Immagine e salva in dataset.csv con Pandas"*.
  2. Lanci lo script (`python scrape.py`), verifichi il CSV ed invii il file finale al cliente.

---

## 4. 📊 Data Cleaning, Elaborazione Tabelle & Automazione Excel
> **Paga Tipica:** 200$ – 800$ per progetto o 2.500€–4.300€/mese
* **Strumenti da usare:**
  * **Librerie Python:** `Pandas`, `Openpyxl`, `PyReadstat` (per file SPSS `.sav`), `DuckDB`.
* **Ricetta di Esecuzione (10 Minuti):**
  1. Carica il dataset grezzo con `df = pd.read_csv("dirty_data.csv")` o `pd.read_excel()`.
  2. Rimuovi duplicati (`df.drop_duplicates()`), standardizza date, gestisci i campi nulli e calcola le colonne richieste.
  3. Esporta il report finale pulito con `df.to_excel("final_report.xlsx", index=False)`.

---

## 5. 📦 E-Commerce, Cataloghi & Shopify/WooCommerce Bulk Upload
> **Paga Tipica:** 300$ – 1.200$ per catalogo
* **Strumenti da usare:**
  * **Librerie Python:** `Openpyxl`, `Shopify Python API`, `Pillow` (ridimensionamento immagini).
* **Ricetta di Esecuzione (15 Minuti):**
  1. Prendi i titoli e dati grezzi dei prodotti del fornitore.
  2. L'AI genera in batch descrizioni accattivanti ed elenchi puntati con le feature.
  3. Uno script Python inserisce i dati nel template CSV standard di Shopify/WooCommerce pronto per l'importazione con 1 click.

---

## 6. 🔌 Integrazione API, Webhook & Sincronizzazione Dati
> **Paga Tipica:** 400$ – 1.500$
* **Strumenti da usare:**
  * **Server leggero:** `FastAPI` (Python) o `n8n` (tool visuale no-code/low-code self-hosted gratuito).
  * **Deploy gratuito:** Render.com, Railway o VPS locale.
* **Ricetta di Esecuzione (20 Minuti):**
  1. Crea un endpoint FastAPI di 30 righe che riceve il Webhook (es. da Stripe/Shopify), manipola il JSON e aggiorna il database del cliente (Airtable, Google Sheets, PostgreSQL).
  2. Fai il deploy e consegni l'URL del webhook al cliente.

---

### 💡 La Regola d'Oro: *Fake It Till You Make It*
Non devi aver già fatto 100 volte un lavoro specifico per candidarti: con **Python + Ollama + Playwright + Pandas**, hai in mano il kit universale per risolvere **qualsiasi task digitale in pochi minuti**.
