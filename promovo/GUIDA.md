# Guida a Promovo

Promovo prende il volantino di un negozio (PDF o foto) e prepara da solo tutto quello che
serve per promuoverlo: video, grafiche per i social, testi e messaggi WhatsApp.
Tu controlli e approvi: niente esce senza il tuo ok.

## 1. Aprire Promovo

1. Doppio clic su **AVVIA_PROMOVO_WINDOWS.bat** (su Mac: AVVIA_PROMOVO_MAC.command).
2. La prima volta installa ciò che serve: può volerci qualche minuto.
3. Il browser si apre da solo. Accedi con **demo@promovo.it** e password **promovo2026**.
4. Per chiudere Promovo chiudi la finestra nera.

Trovi già un negozio di prova («Supermercato Demo») con logo e un volantino caricato.

## 2. Il lavoro di ogni settimana: 4 passi

Apri **Volantini** e premi **Nuovo volantino**, poi trascina il PDF o la foto del volantino.
Dentro il volantino trovi 4 passi, in alto, sempre visibili.

### Passo 1: Controlla le offerte

Promovo legge ogni offerta: nome, formato, prezzo, prezzo vecchio, sconto e foto del prodotto.

**Il controllo dei prezzi.** Il problema dei programmi che "leggono" le immagini è che a volte
sbagliano un numero. Per questo Promovo **legge ogni prezzo due volte, in due modi diversi**,
e lo segna come confermato solo quando le due letture coincidono:

| Volantino | Prima lettura | Seconda lettura (controllo) |
|---|---|---|
| PDF "digitale" (il testo si può selezionare) | il testo del PDF | il prezzo deve essere scritto proprio lì nel PDF |
| Volantino fatto di immagini o foto | l'intelligenza artificiale | lettura ottica del numero grande e una seconda lettura su un ritaglio ingrandito |

Il risultato lo vedi a colori:

- **Verde (confermato)**: le due letture coincidono. Non devi fare niente.
- **Giallo (da controllare)**: Promovo non è riuscito a esserne sicuro. Accanto all'offerta c'è il
  **ritaglio del volantino originale**: guardalo, e se il prezzo è giusto premi **«È giusto»**,
  altrimenti premi **Correggi** e scrivi quello vero.

Il controllo **non cambia mai un prezzo da solo**: ti segnala solo i dubbi. Così un prezzo
sbagliato non finisce mai su un video o un post.

Qui puoi anche:
- **Evidenziare** un'offerta (stella): finisce per prima nel Reel e nelle grafiche;
- **Aggiungere un'offerta mancante** o eliminarne una;
- premere **«Li ho controllati tutti»** se hai già guardato tutto.

### Passo 2: Crea i materiali

Scegli cosa ti serve (sono già selezionati i più utili) e premi **Crea i materiali**:

- **Reel 9:16**: per Instagram, TikTok e le storie (le 6 offerte migliori, con musica);
- **Video schermo 16:9**: per i televisori in negozio, con tutte le offerte;
- **Video post 1:1**: per il feed di Facebook e Instagram;
- **Immagini**: copertina, storia e un'immagine per ogni offerta in evidenza;
- **Testi**: post per Instagram e Facebook, messaggio WhatsApp e newsletter;
- **Messaggi personali**: un WhatsApp su misura per ogni cliente che ha dato il consenso.

Ci vuole circa un minuto: vedi l'avanzamento passo per passo.

### Passo 3: Approva e scarica

In cima trovi il **Piano della settimana**: giorno per giorno, cosa pubblicare, dove e a che ora
(per esempio: lunedì il Reel su Instagram, martedì mattina il WhatsApp ai clienti, venerdì la storia
per il fine settimana, l'ultimo giorno la storia «ultimi giorni»). Con l'IA accesa trovi anche
**l'idea della settimana**: il prodotto protagonista scelto e perché.

Guardi i video, sfogli le grafiche, leggi i testi (puoi modificarli e copiarli con un clic).
Approvi quello che ti piace e premi **Scarica tutto (ZIP)**: ricevi un'unica cartella con video,
immagini e testi pronti da pubblicare.

### Passo 4: Risultati

Se il negozio ti manda le vendite di cassa (file CSV), qui vedi quanto ha venduto ogni offerta.

## 3. Le altre pagine

- **Panoramica**: tutti i negozi che gestisci, a colpo d'occhio, con cosa c'è da fare in ognuno.
- **Negozio**: nome, logo, colori, tono di voce dei testi (familiare, elegante, giovane,
  essenziale), hashtag, musica dei video, indirizzo, orari, WhatsApp e sito. Il logo e i colori
  finiscono su tutti i video e le grafiche; nel finale dei video compare un QR code che apre
  WhatsApp (o il sito) del negozio.
- **Clienti**: l'elenco dei clienti, con il consenso a ricevere messaggi. Chi risponde STOP viene
  tolto subito.
- **Prenotazioni**: quando un cliente scrive all'assistente «mettetemi da parte 2 pacchi di caffè,
  passo domani», la richiesta arriva qui. Tu la prepari e gliela dai quando passa in negozio.
  Niente pagamenti online e niente consegne: è il vecchio «me lo tiene da parte?», ma via chat.
  Se non ti serve, la spegni dalle impostazioni del negozio.
- **Assistente**: risponde alle domande dei clienti su offerte, orari e servizi (serve l'IA).

## 4. Con o senza intelligenza artificiale

Senza chiave dell'IA Promovo funziona già: legge i volantini PDF digitali, crea video, grafiche
e testi a modello (scritti a mano, con i numeri veri: risparmio in euro, prezzi sotto l'euro).

Con l'IA accesa i testi li scrive una piccola redazione:
1. il **copywriter** sceglie l'idea della settimana e scrive un testo diverso per ogni canale;
2. il **caporedattore** lo rilegge e toglie tutto quello che «suona da IA»
   (imperdibile, scopri, viaggio nel gusto, emoji a ogni riga...);
3. infine Promovo controlla che ogni prezzo citato esista davvero nel volantino.

**Come accendere l'IA:** crea una chiave su console.anthropic.com (serve una carta: si paga a consumo,
pochi centesimi per volantino), crea accanto a AVVIA_PROMOVO_WINDOWS.bat un file di testo chiamato
**CHIAVE_IA.txt** e incollaci dentro la chiave. Riavvia Promovo: nella finestra nera comparirà
«Intelligenza artificiale: ACCESA». La chiave resta solo sul tuo computer: non mandarla a nessuno,
nemmeno in chat.
In basso a sinistra c'è sempre scritto se l'IA è accesa o spenta.

## 5. Se qualcosa non va

- **Il browser dice "impossibile raggiungere la pagina"**: aspetta qualche secondo e ricarica;
  la finestra nera deve restare aperta.
- **Un volantino non viene letto**: se è fatto di sole immagini serve l'IA; altrimenti puoi
  aggiungere le offerte a mano dal passo 1.
- **Un prezzo è sbagliato**: correggilo dal passo 1 e rifai i materiali dal passo 2;
  i vecchi file vengono sostituiti.
