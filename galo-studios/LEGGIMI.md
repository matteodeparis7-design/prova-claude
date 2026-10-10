# Galó Studios: sito web

Il sito è un unico file: **`index.html`**. Non servono server, database o installazioni.

## Pubblicarlo online (gratis)

- **Netlify Drop:** vai su https://app.netlify.com/drop e trascina la cartella `galo-studios`. In pochi secondi ricevi un indirizzo pubblico, che puoi collegare a un dominio tuo (es. `galostudios.it`).
- **GitHub Pages:** nelle impostazioni del repository attiva Pages e indica la cartella che contiene `index.html`.
- Va bene anche qualsiasi hosting normale (Aruba, Register, ecc.): carica `index.html` nella cartella principale.

## Modificare prezzi, orari e contatti

Apri `src/galo-studios.html`, cerca il blocco `CONFIGURAZIONE` all'inizio dello script e cambia:

| Voce | A cosa serve |
|---|---|
| `ig` | Profilo Instagram a cui arrivano le richieste (`prod.galo_`) |
| `whatsapp` | Numero WhatsApp con prefisso e senza `+` (es. `393331234567`). Se lo inserisci compare il pulsante "Invia su WhatsApp" |
| `email` | Email facoltativa mostrata nella finestra di invio |
| `open` / `close` | Orario dello studio (ore intere) |
| `closedWeekdays` | Giorni di chiusura (0 = domenica) |
| `closedDates` | Giorni chiusi, es. `['2026-12-25']` |
| `busy` | Ore già occupate, es. `{'2026-10-20':[14,15,16]}` |
| `SERVICES` | Nome, descrizione e prezzo dei quattro servizi |

I prezzi compaiono anche come testo nella sezione Listino, nel titolo principale e nelle Domande frequenti: se li cambi, aggiorna anche quei punti (cerca `€` nel file).

Dopo ogni modifica rigenera `index.html`:

```
python3 build.py
```

## Come arrivano le richieste

Il sito non invia nulla da solo. Quando un cliente completa la prenotazione o la scheda del beat, il sito prepara un messaggio con tutti i dati e un codice (`GS-…` per le sessioni, `BM-…` per i beat). Il cliente lo copia e lo manda su Instagram (o su WhatsApp, se configurato). La sessione è confermata solo quando rispondi.
