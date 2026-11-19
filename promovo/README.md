# Promovo

Gli agenti che trasformano il volantino del supermercato in contenuti pronti per i social:
Reel e video, grafiche, testi per Instagram e Facebook, piano della settimana.
Lavorano sul computer, **senza collegamenti obbligatori a servizi esterni**: l'IA di Anthropic e la
voce di ElevenLabs sono potenziamenti facoltativi, attivabili dalla pagina Impostazioni.

Pensato per chi cura la comunicazione di uno o più negozi (agenzia, professionista o il negozio
stesso): più negozi, ognuno con la sua identità, e un pacchetto ZIP pronto da consegnare.

## Gli agenti

| Agente | Cosa fa | Dove |
|---|---|---|
| Lettore | Testo del PDF quando c'è; per i volantini fatti di immagini la lettura ottica sul computer (RapidOCR, modelli PP-OCRv6 inclusi): trova i prezzi grandi, ricostruisce il nome anche su più righe, capisce se il nome sta sopra o sotto il prezzo, usa le caselle del volantino, ritaglia il riquadro dell'offerta | `modules/flyer/ocr.py`, `extract.py` |
| Controllo | Rilegge ogni prezzo su un ritaglio ingrandito (a due ingrandimenti); conferma solo se coincide, non cambia mai un prezzo da solo | `modules/flyer/ocr.py`, `crosscheck.py` |
| Stratega e copywriter | Fatti calcolati dal codice (risparmio, sotto l'euro, metà prezzo, cene complete con le offerte e il loro totale), scelta dell'idea della settimana, testi per Instagram e Facebook nel tono del negozio, rilettura automatica (frasi fatte, prezzi inesistenti, tu/voi, emoji) | `modules/content/writer.py` |
| Grafico | Copertina, storia e un'immagine per ogni offerta in evidenza | `modules/graphics` |
| Montatore | Video MP4 con musica originale, logo e QR code: schermo 16:9, Reel 9:16, post 1:1 | `modules/video` |
| Regista dal banco | Dal video girato col telefono al Reel: momenti migliori, stabilizzazione, prezzi verificati, sottotitoli, voce | `modules/clip` |
| Analista prezzi | Supermercati veri della zona (OpenStreetMap), confronto con i loro volantini (al kg/litro), prezzi medi della zona | `modules/radar` |
| Meteorologo | Previsioni MET Norway (gratuite anche per uso commerciale): cosa spingere nei giorni di caldo, freddo o pioggia | `modules/weather` |
| Pianificatore | Calendario di pubblicazione e cosa filmare al banco | `modules/content/service.py` |
| Pilota automatico | Dal caricamento del volantino a tutti i materiali, in un solo lavoro con l'avanzamento di ogni agente | `api/app.py` (`run_autopilot_job`) |
| Omnibus | Prezzi barrati confrontati con il minimo dei 30 giorni prima (volantini del negozio), correzione proposta | `modules/omnibus.py` |
| Revisore finale | Controllo di qualità prima della consegna: misure, durate, prezzi nei testi, materiali con prezzi vecchi | `modules/reviewer.py` |
| Stampa | Cartellini promozionali da scaffale (A4), locandina A4/A3 con QR, piano nel calendario (.ics) | `modules/printables.py` |
| Scontorno (aggiuntivo) | BiRefNet lite (MIT) sul computer: prodotto senza sfondo né prezzi, con controlli e lettura ottica | `cutout.py`, `extras.py` |
| Sottotitoli (aggiuntivo) | Whisper small (MIT) sul computer: sottotitoli a tempo di parola nei Reel dal banco | `modules/clip/transcribe.py` |
| Salvaspreco | Merce vicina alla scadenza in offerta lampo: blocco dei prodotti scaduti, sconto consigliato, storia/post/testi, cartellino «Salvami», chili e euro salvati, post del mese | `modules/rescue.py` |
| Parola alla cassa | Una parola d'ordine per canale nei testi (mai un prodotto in offerta, nuove a ogni volantino), contatore +1 e foglio per la cassa, clienti per canale, consigli, nel report | `modules/till.py` |
| Filiera vicina | Produttori del territorio con distanza vera (OpenStreetMap), riconoscimento nel volantino, produttore della settimana, mappa della filiera, etichette da scaffale | `modules/filiera.py` |
| Spesa a budget | Momento del mese (scorta, spesa regolare, fine mese, tredicesima), giorno consigliato, cestino vero nel budget con totale al centesimo e risparmio, immagine e testo | `modules/budget.py` |
| Copia di sicurezza | Backup ZIP, ripristino anche su un altro PC (percorsi riscritti), pacchetto assistenza, avviso nuova versione | `backup.py` |

Tutti gli importi sono in centesimi interi. L'IA facoltativa è Claude (`claude-opus-5-5`, configurabile).

## Avvio

Per Windows: **Promovo_Setup.exe** dalla pagina delle release (prova automatica su Windows a ogni versione).
Accesso di prova: `demo@promovo.it` / `promovo2026`. Guida per l'utente: [GUIDA.md](GUIDA.md).

Da sorgente:

```bash
cd promovo
pip install -e ".[test]"
python -m promovo --demo --open
```

Variabili d'ambiente:

| Variabile | Default | Significato |
|---|---|---|
| `PROMOVO_DATABASE_URL` | `sqlite:///./promovo.db` | Database (anche PostgreSQL) |
| `PROMOVO_DATA_DIR` | `./promovo_data` | PDF, ritagli, video, chiavi facoltative (`chiavi.json`) |
| `PROMOVO_MODEL` | `claude-opus-5-5` | Modello dell'IA facoltativa |
| `PROMOVO_AI` | `claude` | `off` per impedire l'IA facoltativa |
| `PROMOVO_MAX_UPLOAD_MB` | `40` | Dimensione massima dei volantini |
| `PROMOVO_MAX_VIDEO_MB` | `400` | Dimensione massima dei video "dal banco" |
| `PROMOVO_WEATHER` | `on` | `off` per non chiedere le previsioni a MET Norway |

Le chiavi facoltative si inseriscono dalla pagina Impostazioni (vengono provate prima di essere salvate);
valgono anche `ANTHROPIC_API_KEY` ed `ELEVENLABS_API_KEY` all'avvio.

## Come vengono controllati i prezzi

1. **testo PDF**: il prezzo compare nel testo del PDF;
2. **doppia lettura**: per i volantini fatti di immagini, il prezzo riletto su un ritaglio ingrandito coincide;
3. **OCR / doppia lettura IA**: per i volantini letti dall'IA facoltativa;
4. **persona**: corretto o confermato a mano.

Un prezzo mai confermato resta giallo, e il pilota automatico porta l'utente a controllarlo.

## Test

```bash
cd promovo
python -m pytest
```

I test non chiamano servizi esterni. Coprono importi, date, sicurezza, lettura dei volantini (testo,
immagini, nove impaginazioni diverse), controllo dei prezzi, testi della redazione in tutti i toni,
video nei tre formati, grafiche, pacchetto ZIP, pilota automatico, chiavi facoltative e tutte le API.
