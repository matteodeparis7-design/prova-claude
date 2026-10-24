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
| `calendly` | Link dell'evento Calendly di Galó Studios (ora: `https://calendly.com/galobeat-prod/rec-session`). Se è vuoto, le prenotazioni arrivano come messaggio su Instagram |
| `open` / `close` | Orario mostrato sul sito, in ore intere (ora: 16 e 19). Deve coincidere con la disponibilità impostata su Calendly |
| `closedWeekdays` | Giorni di chiusura (ora: `[0,1,6]` = domenica, lunedì, sabato → aperto dal martedì al venerdì) |
| `legal` | **Dati legali obbligatori** mostrati nel footer e nella pagina Privacy: titolare, indirizzo, partita IVA (o codice fiscale), email, indicazione IVA sui prezzi, regole di disdetta, data di aggiornamento |
| `SERVICES` | Nome, descrizione e prezzo dei quattro servizi |

I prezzi compaiono anche come testo nella sezione Listino, nel titolo principale e nelle Domande frequenti: se li cambi, aggiorna anche quei punti (cerca `€` nel file).

Dopo ogni modifica rigenera `index.html`:

```
python3 build.py
```

## Come arrivano prenotazioni e richieste

**Sessioni in studio:** il cliente sceglie il servizio sul sito e prenota giorno e orario dal calendario Calendly di Galó Studios, mostrato direttamente nella pagina Prenota (il servizio scelto viene già scritto nella prima domanda del modulo Calendly). Riceve un'email di conferma; la prenotazione arriva a chi gestisce l'account Calendly e l'orario non è più disponibile per altri. Giorni chiusi, ferie e orari occupati si gestiscono solo da Calendly. Finché `calendly` è vuoto, il cliente indica quando preferirebbe venire e il sito prepara un messaggio da mandare a Galó su Instagram.

**Beat:** il cliente compila la scheda del beat; il sito prepara un messaggio con tutti i dettagli e un codice (`BM-…`), che il cliente copia e manda a Galó su Instagram (o su WhatsApp, se configurato). Il sito non invia nulla da solo: la richiesta arriva solo se il cliente manda il messaggio. Se il cliente non segue Galó, il messaggio finisce in "Richieste di messaggi" su Instagram.


## Privacy e cookie

- I caratteri sono incorporati nel file: il sito non si collega a Google o ad altri server esterni.
- Il calendario Calendly viene caricato solo dopo che il visitatore preme "Mostra il calendario" (la scelta viene ricordata e si può revocare dalla pagina Privacy).
- Il sito non usa cookie di profilazione o statistiche: per questo non serve il banner dei cookie. Se in futuro si aggiungono strumenti come Google Analytics, Meta Pixel o video incorporati, serve un banner di consenso e va aggiornata l'informativa.
- La pagina "Privacy, cookie e note legali" è raggiungibile dal footer (`#privacy`).
