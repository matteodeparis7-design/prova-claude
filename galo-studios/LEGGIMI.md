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
| `booking` | Link della pagina di prenotazione Google Calendar di Galó (`https://calendar.app.google/NAn1qdoeCUBPVAHu9`) |
| `open` / `close` | Orario mostrato sul sito, in ore intere (ora: 16 e 19). Deve coincidere con la disponibilità impostata nel calendario Google |
| `closedWeekdays` | Giorni di chiusura (ora: `[0,1,6]` = domenica, lunedì, sabato → aperto dal martedì al venerdì) |
| `SERVICES` | Nome, descrizione e prezzo dei quattro servizi |

I prezzi compaiono anche come testo nella sezione Listino, nel titolo principale e nelle Domande frequenti: se li cambi, aggiorna anche quei punti (cerca `€` nel file).

Dopo ogni modifica rigenera `index.html`:

```
python3 build.py
```

## Come arrivano prenotazioni e richieste

**Sessioni in studio:** il cliente sceglie il servizio sul sito e prenota giorno e orario sul calendario Google di Galó. Riceve subito un'email di conferma da Google; l'appuntamento compare nel calendario di Galó e l'orario non è più disponibile per altri. Giorni chiusi, ferie e orari occupati si gestiscono solo dal calendario Google: il sito non va toccato.

**Beat:** il cliente compila la scheda del beat; il sito prepara un messaggio con tutti i dettagli e un codice (`BM-…`), che il cliente copia e manda a Galó su Instagram (o su WhatsApp, se configurato). Il sito non invia nulla da solo: la richiesta arriva solo se il cliente manda il messaggio. Se il cliente non segue Galó, il messaggio finisce in "Richieste di messaggi" su Instagram.
