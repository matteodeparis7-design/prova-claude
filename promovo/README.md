# Promovo

Piattaforma di agenti IA per il marketing e i clienti dei supermercati.
Funziona in due modalità, senza cambiare codice:

- **Agenzia**: un'organizzazione gestisce molti punti vendita (sei tu che lavori per i negozi);
- **SaaS**: ogni negozio ha il suo account e usa la piattaforma da solo.

## Gli agenti

| Agente | Cosa fa | Dove |
|---|---|---|
| Lettore | Legge il PDF del volantino (con l'IA o, di riserva, senza), trova prodotti, prezzi, sconti e date, ritaglia le foto | `modules/flyer` |
| Controllo | Verifica ogni prezzo contro il testo del PDF; scarta prezzi barrati e sconti non stampati | `modules/flyer/extract.py` |
| Copywriter | Testi per Instagram, Facebook, WhatsApp e newsletter; un testo con un prezzo inesistente viene scartato | `modules/content` |
| Montatore | Video MP4 per schermi in negozio (16:9) e Reel/Storie (9:16) da qualsiasi volantino | `modules/video` |
| Assistente clienti | Risponde su offerte, orari e servizi; crea ordini da ritirare, validati dal codice | `modules/assistant` |
| Spesa intelligente | Ricette con i prodotti in offerta e lista della spesa con il totale esatto | `modules/recipes` |
| Analista | Importa le vendite di cassa (CSV) e misura l'effetto di ogni offerta | `modules/analytics` |
| Fedeltà | Messaggi personali solo ai clienti con consenso; gestione dello STOP | `modules/loyalty` |

L'IA è Claude (modello `claude-opus-5-5`, configurabile). Tutti gli importi sono in centesimi interi.

## Avvio

```bash
cd promovo
pip install -e ".[test]"
export ANTHROPIC_API_KEY=...        # oppure: ant auth login
python -m promovo --port 8000
```

Poi apri http://127.0.0.1:8000, crea un account, un negozio e carica un volantino.
Senza chiave l'IA è spenta e la piattaforma usa i metodi senza IA dove esistono
(lettura euristica dei volantini, testi a modello); assistente e ricette richiedono l'IA.

Variabili d'ambiente:

| Variabile | Default | Significato |
|---|---|---|
| `PROMOVO_DATABASE_URL` | `sqlite:///./promovo.db` | Database (anche PostgreSQL) |
| `PROMOVO_DATA_DIR` | `./promovo_data` | PDF, ritagli e video |
| `PROMOVO_MODEL` | `claude-opus-5-5` | Modello Claude |
| `PROMOVO_AI` | `claude` | `off` per spegnere l'IA |
| `PROMOVO_MAX_UPLOAD_MB` | `40` | Dimensione massima dei PDF |

Serve `ffmpeg` installato per i video. Per controllare i prezzi dei volantini fatti solo di
immagini serve anche l'OCR Tesseract (facoltativo ma consigliato):

```bash
sudo apt-get install -y ffmpeg tesseract-ocr tesseract-ocr-ita
```

## Come vengono controllati i prezzi

Ogni prezzo letto viene confermato in uno di questi modi, e il cruscotto mostra quale:

1. **testo PDF**: il prezzo compare nel testo del PDF (volantini "digitali");
2. **OCR**: per i volantini fatti di immagini, Tesseract trova lo stesso prezzo, scritto in grande,
   dentro il riquadro del prodotto (i prezzi al kg in piccolo non contano);
3. **doppia lettura IA**: Claude rilegge il prezzo su un ritaglio ingrandito del prodotto;
4. **persona**: corretto o confermato a mano nel cruscotto.

Un controllo non cambia mai un prezzo da solo: conferma oppure segnala "da controllare".
I volantini si leggono in background: per uno di 24 pagine servono alcuni minuti.

## Test

```bash
cd promovo
python -m pytest
```

I test non chiamano l'API: usano un LLM finto che esegue davvero gli strumenti.
Coprono importi, date, sicurezza, estrazione (con e senza IA), controllo prezzi,
video in entrambi i formati, ordini, assistente, ricette, vendite, fedeltà e tutte le API,
compreso l'isolamento tra organizzazioni diverse.

## Cosa manca per andare in produzione

- Invio reale su WhatsApp (WhatsApp Business API) e pubblicazione sui social (es. Metricool):
  oggi i messaggi e i post vengono preparati e approvati, non inviati.
- Coda di lavori dedicata per i video, se i negozi diventano molti.
- Hosting, backup del database, HTTPS e informativa privacy/GDPR.
