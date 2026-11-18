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
| Montatore | Video MP4 con musica originale, logo e QR code: schermo 16:9, Reel 9:16, post 1:1 | `modules/video` |
| Grafico | Immagini per i social: copertina, storia e una per ogni offerta in evidenza | `modules/graphics` |
| Regista | "Crea tutto" in un clic, con avanzamento, e pacchetto ZIP della settimana | `modules/kit.py` |
| Montatore dal banco | Dal video girato col telefono al Reel: sceglie i momenti migliori, stabilizza, riconosce i prodotti (IA) e mette i prezzi verificati, sottotitoli e voce | `modules/clip` |
| Voce del negozio | Voce registrata dal negoziante o voce clonata ElevenLabs (con consenso firmato e scritta "Voce generata con IA") | `voice.py` |
| Radar del quartiere | Legge i volantini dei concorrenti e confronta i prezzi (al kg/litro se i formati sono diversi) | `modules/radar` |
| Meteo | Previsioni Open-Meteo della zona: cosa spingere nei giorni di caldo, freddo o pioggia | `modules/weather` |
| Assistente clienti | Risponde su offerte, orari e servizi; crea prenotazioni da ritirare, validate dal codice | `modules/assistant` |
| Analista | Importa le vendite di cassa (CSV) e misura l'effetto di ogni offerta | `modules/analytics` |
| Fedeltà | Messaggi personali solo ai clienti con consenso; gestione dello STOP | `modules/loyalty` |

L'IA è Claude (modello `claude-opus-5-5`, configurabile). Tutti gli importi sono in centesimi interi.

## Avvio

Il modo più semplice: doppio clic su `AVVIA_PROMOVO_WINDOWS.bat` (o `AVVIA_PROMOVO_MAC.command`).
Installa tutto, crea un negozio dimostrativo e apre il browser da solo
(accesso: `demo@promovo.it` / `promovo2026`). La guida passo passo è in [GUIDA.md](GUIDA.md).

A mano:

```bash
cd promovo
pip install -e ".[test]"
export ANTHROPIC_API_KEY=...        # facoltativa
python -m promovo --demo --open
```

Senza chiave l'IA è spenta e la piattaforma usa i metodi senza IA dove esistono
(lettura dei volantini con il testo dentro il PDF, testi a modello, video e grafiche);
l'assistente clienti e la lettura dei volantini fatti di sole immagini richiedono l'IA.

Variabili d'ambiente:

| Variabile | Default | Significato |
|---|---|---|
| `PROMOVO_DATABASE_URL` | `sqlite:///./promovo.db` | Database (anche PostgreSQL) |
| `PROMOVO_DATA_DIR` | `./promovo_data` | PDF, ritagli e video |
| `PROMOVO_MODEL` | `claude-opus-5-5` | Modello Claude |
| `PROMOVO_AI` | `claude` | `off` per spegnere l'IA |
| `PROMOVO_MAX_UPLOAD_MB` | `40` | Dimensione massima dei PDF |
| `PROMOVO_MAX_VIDEO_MB` | `400` | Dimensione massima dei video "dal banco" |
| `PROMOVO_WEATHER` | `on` | `off` per non chiedere le previsioni a Open-Meteo |
| `ELEVENLABS_API_KEY` | – | Facoltativa: voce generata del negozio |

`ffmpeg` arriva già con il pacchetto `imageio-ffmpeg`. Per controllare i prezzi dei volantini fatti solo di
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
video nei tre formati, grafiche, pacchetto ZIP, ordini, assistente, vendite, fedeltà e tutte le API,
compreso l'isolamento tra organizzazioni diverse.

## Cosa manca per andare in produzione

- Invio reale su WhatsApp (WhatsApp Business API) e pubblicazione sui social (es. Metricool):
  oggi i messaggi e i post vengono preparati e approvati, non inviati.
- Coda di lavori dedicata per i video, se i negozi diventano molti.
- Hosting, backup del database, HTTPS e informativa privacy/GDPR.
