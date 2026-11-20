# Promovo e le regole: cosa è stato controllato (novembre 2026)

Questo documento raccoglie le leggi italiane ed europee che riguardano Promovo e i contenuti che prepara, e
spiega come il programma le rispetta. È un controllo tecnico accurato, **non un parere legale**: prima di
vendere Promovo conviene farlo leggere a un avvocato e al commercialista (vedi l'ultima sezione).

## 1. Cosa è stato tolto, e perché

| Funzione tolta | Motivo |
|---|---|
| **Radar del quartiere** (confronto con i volantini dei concorrenti) | Copiare in modo sistematico volantini e prezzi altrui tocca il diritto d'autore e il diritto sulle banche dati (L. 633/1941, artt. 2 e 102-bis), i termini d'uso dei siti che li pubblicano e le regole sulla pubblicità comparativa (D.Lgs. 145/2007). Anche se usato solo «internamente», era un rischio inutile. |
| **Prezzi medi della zona** | Stessi dati dei concorrenti: tolto per lo stesso motivo. |
| **Mappa dei concorrenti** e **volantino da link** | Servivano solo al Radar. |
| **PyMuPDF** (la libreria che leggeva i PDF) | Ha licenza AGPL: vendere Promovo senza pubblicarne tutto il codice avrebbe violato la licenza (e quindi il diritto d'autore). Sostituita da pypdfium2, pdfplumber e ReportLab, a licenza permissiva. |

All'avvio Promovo cancella da solo gli eventuali volantini dei concorrenti caricati con le versioni precedenti.
**Promovo usa solo i dati del negozio** (il suo volantino, i suoi prodotti, i suoi avvisi) **e fonti pubbliche
ufficiali** (festività, previsioni del tempo, mappa per la distanza dei produttori).

## 2. Cosa è stato aggiunto

- **Prodotti che non si possono pubblicizzare** (modulo `compliance.py`): escono da grafiche, video, testi, radio,
  audio, caratteri grandi, cartellini promozionali, locandine e spesa a budget. Il Correttore li segnala nella
  bozza del volantino.
  - tabacco e sigarette elettroniche: pubblicità vietata (L. 165/1962; D.Lgs. 6/2016, art. 21);
  - giochi con vincite in denaro: pubblicità vietata (D.L. 87/2018 «Decreto Dignità», art. 9);
  - latte per lattanti 0-6 mesi: pubblicità e promozioni vietate nei punti vendita (D.M. 82/2009; Reg. UE 2016/127);
  - farmaci: la pubblicità al pubblico richiede l'autorizzazione del Ministero della Salute (D.Lgs. 219/2006).
- **Frasi che la legge non permette**: il caporedattore scarta i testi che le contengono, il Revisore le segnala
  in rosso anche nei testi modificati a mano, e Radio, Avvisi, Salvaspreco e Filiera le bloccano:
  - concorsi, estrazioni, «vinci», «in palio» (DPR 430/2001: servono regolamento, cauzione e comunicazioni);
  - superlativi non dimostrabili e confronti con altri negozi («i prezzi più bassi», «imbattibili»)
    (Codice del Consumo, artt. 20-22; D.Lgs. 145/2007);
  - proprietà salutari dei cibi («fa bene», «rinforza le difese», «dimagrante») (Reg. CE 1924/2006);
  - «km zero» detto da Promovo (dichiarazione da provare);
  - alcol associato a minori, guida, sport, salute o prestazioni (L. 125/2001, art. 13).
- **Parola alla cassa**: il vantaggio per chi dice la parola deve essere uno sconto. Gli sconti non sono
  «operazioni a premio» (DPR 430/2001, art. 6); omaggi, regali, buoni e punti sì, e Promovo non li accetta.
- **Filiera vicina**: nome, foto e frase del produttore si usano solo con il suo consenso (artt. 7 e 10 c.c.,
  art. 96 L. 633/1941). Senza consenso il produttore non compare in post, mappa ed etichette.
- **Dal banco al Reel**: avviso a riprendere prodotti e banco; se si riconoscono persone serve il loro consenso.
- **Licenze**: file `LICENZE_TERZE_PARTI.txt` nel programma; il codice sorgente di FFmpeg (GPLv3, usato come
  programma separato) viene pubblicato insieme a ogni versione.

## 3. I servizi e le regole che rispettano

| Servizio | Regole | Come Promovo le rispetta |
|---|---|---|
| Lettura del volantino, testi, grafiche, video | Codice del Consumo artt. 20-23 (pratiche ingannevoli); D.Lgs. 145/2007 | Prezzi presi solo dal volantino e riletti due volte; nessuna qualità del prodotto inventata; niente superlativi, confronti, concorsi, claim salutari; prodotti vietati esclusi. |
| Prezzi barrati (Agente Omnibus) | Codice del Consumo art. 17-bis (Direttiva Omnibus): il prezzo «prima» è il più basso dei 30 giorni precedenti | Controlla con i volantini precedenti del negozio e propone la correzione. Conosce solo i prezzi dei volantini: quelli praticati fuori dal volantino li conosce il negozio. |
| Correttore, cartellini scaffale | D.Lgs. 206/2005 artt. 14-17 e Direttiva 98/6/CE (prezzo per unità di misura) | Segnala il prezzo al kg/litro mancante o sbagliato; i cartellini lo riportano sempre. |
| Banco e allergeni | Reg. UE 1169/2011 (art. 44 e All. II); D.Lgs. 231/2017 | 14 allergeni proposti dagli ingredienti, dubbi evidenziati, **conferma e firma di una persona**; registro, cartellini e cartello. |
| Salvaspreco | Reg. UE 1169/2011 art. 24; L. 166/2016 | Blocca i prodotti con data di scadenza («da consumarsi entro») superata; dopo il «preferibilmente entro» permette la vendita e scrive la data per trasparenza. |
| Parola alla cassa | DPR 430/2001; GDPR | Solo sconti; si contano numeri, nessun dato dei clienti. |
| Avvisi di servizio | Calendario festività (L. 260/1949 e succ., L. 151/2025 per il 4 ottobre) | Festività nazionali già inserite; il patrono lo aggiunge il negozio. |
| Radio, volantino da ascoltare | AI Act (Reg. UE 2024/1689) art. 50; L. 132/2025 | All'inizio si dice che la voce è sintetica; la musica è generata da Promovo (nessun diritto da pagare). |
| Voce del negozio (clonata) | AI Act art. 50; GDPR (la voce è un dato personale) | Solo con il consenso della persona, registrato con nome e data; i video riportano «Voce generata con IA». |
| Lavora con noi | D.Lgs. 198/2006; D.Lgs. 215 e 216/2003; D.Lgs. 276/2003 art. 10; GDPR art. 13; Direttiva UE 2023/970 | Blocca richieste su età, genere, stato civile, aspetto, nazionalità, religione; titolo per tutti i generi; nota privacy; consiglio di indicare la retribuzione. |
| Filiera vicina | Diritto al nome e all'immagine; Nominatim/OSM (ODbL) | Consenso del produttore obbligatorio; distanza calcolata, mai «km 0»; attribuzione © OpenStreetMap. |
| Meteo | Licenza dei dati MET Norway (CC BY 4.0) | Fonte citata. |
| Dati del programma | GDPR | Tutto resta sul computer del negozio; nessun dato dei clienti finali; password cifrate (PBKDF2); le chiavi dei servizi restano locali e non entrano nelle copie di sicurezza. |

## 4. Le licenze del software

Tutte le librerie hanno licenze permissive (MIT, BSD, Apache-2.0, ISC, PSF, MPL-2.0) che permettono la vendita.
Le due eccezioni sono gestite: **FFmpeg** (GPLv3) è un programma separato, accompagnato da licenza e codice
sorgente; le librerie FFmpeg di **PyAV** sono LGPL, separate e sostituibili. I caratteri sono SIL OFL 1.1 o
DejaVu. Elenco completo in `packaging/LICENZE_TERZE_PARTI.txt`.

## 5. Cosa resta responsabilità del negozio

- I prezzi, gli sconti e le promozioni: li decide il negozio; Promovo controlla e segnala.
- Il prezzo «prima» dei barrati quando il prodotto è stato venduto a un prezzo diverso fuori dal volantino.
- La verità di quello che scrive a mano (frasi sui produttori, annunci della radio, avvisi).
- I consensi: produttori, persone riprese nei video, voce clonata.
- La pubblicazione: Promovo prepara, il negozio guarda e pubblica.

## 6. Cosa serve a te per vendere Promovo

- **Posizione fiscale**: per vendere con continuità (abbonamenti, servizi) serve la partita IVA; per qualche
  prova occasionale chiedi al commercialista i limiti della prestazione occasionale.
- **Contratto con i clienti**: cosa fa Promovo, chi pubblica, responsabilità sui prezzi (del negozio),
  durata e prezzo.
- **Privacy**: se gestisci tu i dati dei negozi (account, materiali), sei «responsabile del trattamento»
  per loro: serve un accordo scritto (art. 28 GDPR).
- **Intelligenza artificiale**: la L. 132/2025 chiede ai professionisti di dire ai clienti quando usano
  strumenti di IA; scrivilo nel contratto o nell'offerta.
- **Marchio**: prima di usare il nome «Promovo» come marchio conviene una ricerca di anteriorità.
