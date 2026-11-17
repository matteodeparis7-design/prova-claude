# Galó Studios – Piano di lavoro

## L'idea (in una riga)
**Trasformare il volantino di un negozio in video promozionali pronti da usare**
(maxi-schermo in negozio, Reel/TikTok, stati WhatsApp), consegnati in 24–48 ore,
con un abbonamento mensile. Il lavoro lo fanno agenti digitali; tu vendi, controlli la qualità e incassi.

## Perché proprio questa
- **L'hai già fatto.** Il video Superfreddo (volantino 13–22 ottobre, Decò Colleferro) è il primo
  lavoro del portfolio e il codice per rifarlo è in `sorgenti/definitivo/`.
- **Si ripete da solo.** I supermercati e i negozi fanno un volantino nuovo ogni 1–2 settimane:
  un cliente diventa un incasso ricorrente, non una vendita singola.
- **Pochi concorrenti a livello locale.** Un'agenzia chiede tempi e prezzi alti per un video;
  tu puoi consegnarlo in un giorno a una frazione del prezzo.
- **Si parte senza investire.** Servono un portfolio (ce l'hai già), un listino e dei messaggi da mandare.

## Cosa vendiamo (listino di partenza)
| Pacchetto | Cosa c'è dentro | Prezzo indicativo |
|---|---|---|
| **Prova** | 1 video dal volantino (formato orizzontale per lo schermo + verticale 30 s per i social) | 99 € (oppure gratis per i primi 2 clienti, in cambio di una recensione) |
| **Volantino** | Ogni volantino: video lungo per lo schermo + 3 clip verticali da 15–30 s | 180 € a volantino |
| **Abbonamento** | Tutti i volantini del mese + 8 contenuti social + testi dei post | 290–390 €/mese |

Sono prezzi di partenza: si alzano dopo i primi 3–5 clienti soddisfatti.

**Obiettivo realistico:** 3 clienti in abbonamento = circa 900–1.200 €/mese.
Non è un guadagno garantito: dipende da quanti negozi contatti e da quanti dicono sì.

## Gli agenti digitali (la "squadra")
| Agente | Cosa fa | Cosa fai tu |
|---|---|---|
| 1. **Lettore volantino** | Dal PDF del volantino estrae prodotti, prezzi, date e ritaglia le immagini (`cutout.py`) | Niente |
| 2. **Regista** | Sceglie l'ordine delle scene, i prodotti in evidenza, i testi e la musica | Approvi la scaletta (2 minuti) |
| 3. **Montatore** | Produce i video in tutti i formati (`render_final.py`) | Guardi l'anteprima |
| 4. **Social** | Scrive le didascalie e programma i post (Metricool è già collegato) | Approvi |
| 5. **Commerciale** | Trova i negozi della zona, prepara i messaggi personalizzati, tiene la lista contatti | **Mandi tu i messaggi** e parli con i clienti |

Il passo tecnico più importante: rendere il codice di Superfreddo **riutilizzabile per qualsiasi
volantino** (oggi è scritto su misura). Quando è fatto, un nuovo cliente costa ore, non giorni.

## Le prossime 4 settimane
**Settimana 1 – Vetrina**
- [ ] Chiedere a Superfreddo/Decò il permesso di mostrare il video come esempio (se non è già un cliente: proporglielo come primo lavoro)
- [ ] Pagina web di presentazione Galó Studios con il video e il listino
- [ ] Clip di 30 s verticale tratta dal video Superfreddo, da mandare su WhatsApp

**Settimana 2 – Primi contatti**
- [ ] Lista di 30 negozi entro 20–30 km (supermercati indipendenti, macellerie, ottici, negozi di arredo, palestre)
- [ ] 10 messaggi al giorno con `MESSAGGI.md`, più visite di persona ai più vicini
- [ ] Obiettivo: 2 clienti "Prova"

**Settimana 3 – Automazione**
- [ ] Trasformare il codice in una catena unica: PDF del volantino → video (agenti 1–3)
- [ ] Consegnare i primi 2 lavori

**Settimana 4 – Ricorrenza**
- [ ] Proporre l'abbonamento ai clienti della prova
- [ ] Raccogliere recensioni e aggiornare il portfolio

## Cose pratiche da non dimenticare
- **Partita IVA:** per fatturare con regolarità serve (il regime forfettario è il più semplice per iniziare; chiedi a un commercialista). Per le primissime prove si può valutare la prestazione occasionale.
- **Diritti:** usa solo loghi e foto che il cliente ti fornisce o ti autorizza a usare, e musica con licenza libera.
- **Contratto semplice:** cosa consegni, in quanti giorni, quante modifiche sono incluse.
