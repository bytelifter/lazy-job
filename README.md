# 🤖 LazyJobHunter V10 - The Virtual Company Empire

Benvenuto nella versione definitiva di LazyJobHunter. Questo sistema è progettato per generare income passivo e semi-passivo tramite l'automazione intelligente e la ricerca di clienti.

## L'Architettura

Il sistema si divide in due grandi anime:

### 1. I Cacciatori (Job & Lead Hunters)
Scansionano continuamente il web per trovare clienti disposti a pagare:
- **Freelancer Sniper (`freelancer_sniper.py`)**: Bot per auto-bidding su Freelancer.
- **Upwork Sniper (`upwork_sniper.py`)**: Bot per intercettare feed RSS privati.
- **Maps Lead Gen (`maps_lead_gen.py`)**: Estrazione dati (gratuita) per lead B2B.

### 2. La Virtual Company (C-Suite AI)
In `micro_llm_army.py` e `ai_council.py` risiede un'architettura ibrida per schede video da 6GB VRAM:
- **C-Suite (GPU - Sequenziale):** Llama 3.1 (CEO), Qwen2.5-Coder (CTO), Gemma2 (CMO), Mistral (Head of Copy), Llava (Design). Vengono caricati e scaricati uno alla volta per non sforare i 6GB.
- **Nano-Specialisti (CPU - Paralleli):** Modelli HuggingFace (FinBERT per la finanza, CodeBERTa per la sicurezza, traduttori multilingua) che girano leggeri in RAM per controllare il lavoro della C-Suite (Stress Test in Loop).

## 🚀 Come avviare tutto in Automatico (Il Demone)

Non devi avviare i file a mano uno per volta. Puoi semplicemente avviare il **Master Daemon**. Questo script girerà in background, pianificando automaticamente la ricerca di lavori e l'estrazione di contatti.

```bash
# Avvia il sistema automatizzato
python remote_job_hunter/master_daemon.py
```

### 🛑 Come Fermare il Sistema
Il demone è progettato per essere interrotto in sicurezza. Se vuoi fermare tutto:
- Clicca sulla finestra del terminale dove sta girando il demone.
- Premi `Ctrl + C`. 
Il demone riceverà il segnale, chiuderà i processi in modo sicuro e si spegnerà, lasciando un file di log dettagliato nella cartella `daemon_logs/` per permetterti di vedere tutto ciò che ha fatto in tua assenza.

---

## 🔒 Sicurezza e Privacy By Design
Questo sistema ha delle direttive "Core" inviolabili codificate nel suo cervello (AI Council):
1. **No pagamenti custom:** Qualsiasi progetto generato per un cliente o un SaaS userà SOLO processori verificati come Stripe. L'AI si rifiuterà di gestire carte di credito in modo nativo.
2. **GDPR Pronto:** I siti generati includono sempre Cookie Banner e avvisi Privacy.
3. **Budget Guard:** I sistemi API (es. Google Maps) contengono interruttori di emergenza che bloccano l'esecuzione appena Google rifiuta una connessione per limiti di budget, impedendo prelievi non autorizzati.
  
---

## 🚀 Recenti Aggiornamenti
- **Gmail Scanner Lightning Fast**: Sostituita la lettura massiva `RFC822` con `UID SEARCH` e `BODY.PEEK`. Ricerca delle email limitata agli ultimi 2 giorni. Lo script ora gira in <5 secondi rispetto ai ~10 minuti precedenti.
- **WhatsApp Scanner Resiliente**: Fixati i problemi di timeout. Il bot ora utilizza query molto più stabili (`#pane-side`, `#main`) su Playwright per assicurarsi che i box di chat siano interattivi.
- **Disabilitato Filtro Contractor**: Per massimizzare le probabilità di successo, ora l'AI analizza ed estrae form anche per lavori di tipo dipendente/full-time remoti.
- **Freelancer Sniper in Batch**: Incrementata la tolleranza fino a **300 gig analizzati a ciclo**. Il bot interromperà il ciclo solo alla prima Bid posizionata con successo per prevenire shadow-ban per spam.
