# Le tracce del professore, risolte {#tracce}

::: obiettivi Cosa imparerai
- come si risolvono le tracce d'esempio pubblicate dal professore
- come si scrive una risposta completa all'esercizio 3
- come presentare un'esecuzione simulata con i record di attivazione
:::

Queste sono **le tracce d'esempio pubblicate sul sito del corso** (cartella "Testi d'esame d'esempio"), con soluzioni complete. Il codice è stato compilato e provato. Prima di leggere ogni soluzione, prova a scriverla tu su carta.

## Traccia 1: "Segnala un guasto!"

::: esercizio Testo (esempio 1, immatricolati 2025-26 e successivi; tempo: 2h30)
**Esercizio 1** (0-13 punti). Una società di distribuzione del gas organizza tutte le segnalazioni di guasto in una tabella di guasti. Ogni guasto è caratterizzato da: **descrizione** (stringa di lunghezza non nota a priori); **tipologia** (intero: 1 = perdita lieve, 2 = interruzione, 3 = perdita ragguardevole); **servizio** (carattere: R per "riscaldamento + acqua calda", A per "solo acqua calda"); **codice utente** (stringa di 9 caratteri alfanumerici); **numero d'ordine** della chiamata (intero).
Quando una squadra è disponibile le si assegna il guasto più importante, eliminandolo dalla tabella. **importanza = tipologia\*11 - numero d'ordine**.
Scrivere la definizione dei tipi necessari a gestire la tabella di guasti come **lista** rappresentata mediante record e puntatori. Poi scrivere una funzione `eser1` che, ricevendo (almeno) una lista di guasti e un intero `imp`, restituisca il **puntatore alla segnalazione più importante**, il **numero di guasti più importanti di imp** e il **numero di guasti meno importanti di imp**.

**Esercizio 2** (10 punti). Scrivere una funzione `eser2()` che, ricevendo (almeno) una lista di segnalazioni, **elimini la segnalazione più importante**.

**Esercizio 3** (da -1 a 7 punti). Descrivere con completezza il metodo di verifica della correttezza **a scatola trasparente**. Applicarlo alla verifica di `eser1()`: quali test e con quali dati di prova? Giustificare ciascun test. Verificare il successo dei test con esecuzioni simulate.
*(Nella versione per gli immatricolati 2024-25 e precedenti l'esercizio 3 chiedeva invece il metodo a **scatola nera**: lo risolvo sotto.)*
:::

### Esercizio 1: i tipi

{{inc guasti.c tipi}}

Una funzione di servizio rende il codice più leggibile:

{{inc guasti.c importanza}}

### Esercizio 1: la funzione eser1

Tre risultati: il puntatore con `return`, i due conteggi come **parametri di output**. La lista si legge soltanto, quindi si passa come `TipoListaGuasti`.

{{inc guasti.c eser1}}

Algoritmo: scansione unica; per ogni nodo calcolo l'importanza, aggiorno uno dei due contatori (un guasto con importanza **uguale** a `imp` non va in nessuno dei due) e aggiorno il candidato massimo. Con lista vuota il ciclo non viene eseguito e si restituisce `NULL` con entrambi i contatori a 0.

### Esercizio 2: eser2

Per eliminare il nodo più importante serve **il suo predecessore**: durante la scansione tengo `prec`/`corr` e, quando trovo un nuovo massimo, ricordo anche il suo predecessore (`precMax`).

{{inc guasti.c eser2}}

Casi controllati: lista vuota (restituisce 0); massimo in testa (`precMax == NULL`: cambia la testa, per questo il parametro è `TipoListaGuasti *`); massimo in mezzo o in coda (scavalcamento). Prima del nodo si libera la descrizione, che è una stringa esatta.

Per provare le funzioni serve anche un inserimento (non richiesto dal testo), che mostra come si riempie un nodo con una stringa esatta:

{{inc guasti.c aggiungi}}

Output della prova (`guasti.c`): con i guasti di importanza 18, 30, 20, 10 e `imp = 18`, `eser1` restituisce il guasto "odore di gas in cantina" (30), 2 più importanti, 1 meno importante; tre chiamate di `eser2` eliminano, nell'ordine, quello da 30 (in mezzo), quello da 20 (in mezzo) e quello da 18 (in testa).

### Esercizio 3: scatola trasparente applicata a eser1

**Il metodo.** Nella verifica a scatola trasparente i test si scelgono **guardando il codice** della funzione, con l'obiettivo di far eseguire, nel complesso dei test, tutte le sue parti. Si applicano criteri di copertura via via più scrupolosi: (1) **copertura delle istruzioni**: ogni istruzione eseguita almeno una volta; (2) **copertura delle decisioni**: ogni decisione (condizione di `if`/`for`/`while`) almeno una volta vera e una volta falsa; (3) **copertura delle condizioni**: ogni condizione elementare di una decisione composta almeno una volta vera e una volta falsa; (4) **valori limite**: test con valori uguali ai limiti delle condizioni e vicini a essi. Per i cicli si provano 0, 1 e più iterazioni. Per ogni test si calcola prima l'**output atteso**, poi si esegue e lo si confronta con l'**output effettivo**; se differiscono si fa debugging. Nessun criterio garantisce l'assenza di errori, ma più criteri si soddisfano più la verifica è affidabile.

**Le decisioni in eser1**:

- **D1** `p != NULL` (ciclo `for`);
- **D2** `i > imp`;
- **D3** `i < imp` (valutata solo se D2 è falsa);
- **D4** `i > importanza(max->info)`.

**I test** (la lista è scritta dalla testa alla coda; per ogni guasto indico tipologia/numero d'ordine e l'importanza risultante):

| Test | Lista (importanze) | imp | Perché | Atteso |
|---|---|---|---|---|
| T1 | vuota | 0 | D1 falsa subito (0 iterazioni); istruzioni fuori dal ciclo | `NULL`, 0, 0 |
| T2 | g(2/2) → **20** | 20 | 1 iterazione; D2 e D3 false (valore **limite** i == imp); D4 falsa | g, 0, 0 |
| T3 | g(1/1)=**10**, g(3/3)=**30**, g(2/4)=**18** | 18 | più iterazioni; D2 vera (30) e falsa; D3 vera (10) e falsa (18 == imp); D4 vera (30 > 10) e falsa (18) | nodo da 30, 1, 1 |
| T4 | **30**, 10, 18 | 25 | massimo **in testa**: D4 sempre falsa, `max` deve restare il primo | nodo da 30, 1, 2 |
| T5 | 10, 18, **30** | 9 | massimo **in coda**; tutti più importanti | nodo da 30, 3, 0 |

T1 e T3 da soli coprono già tutte le istruzioni e tutte le decisioni (vere e false); T2, T4 e T5 aggiungono i valori limite (importanza uguale a `imp`, un solo nodo, massimo agli estremi).

**Esecuzione simulata di T3** (imp = 18):

| passo | p (importanza) | i | D2 i>18 | D3 i<18 | *piuImp | *menoImp | D4 | max |
|---|---|---|---|---|---|---|---|---|
| inizio | - | - | - | - | 0 | 0 | - | nodo 10 |
| 1 | nodo 10 | 10 | F | **V** | 0 | 1 | 10>10 F | nodo 10 |
| 2 | nodo 30 | 30 | **V** | - | 1 | 1 | 30>10 **V** | nodo 30 |
| 3 | nodo 18 | 18 | F | F | 1 | 1 | 18>30 F | nodo 30 |
| fine | NULL (D1 falsa) | | | | **1** | **1** | | **nodo 30** |

Output effettivo = atteso. Analogamente T1: il ciclo non parte, i contatori restano 0 e `max` vale `lista` cioè `NULL`: corretto.

### Variante: scatola nera applicata a eser1

**Il metodo.** I test si scelgono **senza guardare il codice**, in base alla **specifica**: si partiziona l'insieme dei possibili input in **classi di equivalenza** (input per cui ci si aspetta lo stesso comportamento) e si sceglie un rappresentante per ogni classe. Più le classi sono specifiche (casi particolari, casi limite), più test si fanno e più si è sicuri.

**Classi per eser1** (input: una lista di guasti e un intero imp):

| Classe | Rappresentante | Atteso |
|---|---|---|
| lista vuota | `NULL`, imp = 5 | `NULL`, 0, 0 |
| un solo guasto, più importante di imp | [20], imp = 5 | g20, 1, 0 |
| un solo guasto, meno importante | [20], imp = 25 | g20, 0, 1 |
| un solo guasto, importanza = imp | [20], imp = 20 | g20, 0, 0 |
| più guasti, massimo in testa | [30, 10, 18], imp = 15 | g30, 2, 1 |
| più guasti, massimo in coda | [10, 18, 30], imp = 15 | g30, 2, 1 |
| più guasti, massimo in mezzo | [10, 30, 18], imp = 15 | g30, 2, 1 |
| tutti più importanti di imp | [10, 30, 18], imp = 0 | g30, 3, 0 |
| tutti meno importanti | [10, 30, 18], imp = 40 | g30, 0, 3 |
| due guasti con la stessa importanza massima | [30, 30] | il primo dei due (la specifica non lo dice: va deciso e scritto) |
| importanze negative (numero d'ordine grande) | tipologia 1, ordine 50 → -39 | il massimo è comunque il più grande |

L'ultima classe è importante: un'implementazione che partisse con "massimo = 0" sbaglierebbe con importanze tutte negative.

## Traccia 2: "Giovani Marmotte"

::: esercizio Testo (esempi 2 e 3, immatricolati 2025-26 e successivi)
**Esercizio 1** (0-13 punti). Il reggimento delle Giovani Marmotte è composto da iscritti, ciascuno specificato da: **cognome e nome** (stringa di lunghezza non prefissata); **associazione** (numero di anni di presenza nel reggimento); **grado** (stringa di 8 caratteri); **numero medaglie** ricevute durante l'anno; **numero reprimende**.
Scrivere la definizione del tipo `TipoReggimento`, che rappresenta il reggimento come **lista** (record e puntatori). Poi scrivere una funzione `eser1` che, ricevendo (almeno) un reggimento `gm` e un grado `rank`, restituisca il **numero di marmotte di quel grado**, la **media (intera) delle loro medaglie** e la **media (intera) delle loro reprimende**.

**Esercizio 2** (10 punti). Assumendo la lista ordinata in senso crescente del cognome e nome, scrivere `eser2()` che, ricevendo una lista-reggimento e 5 ulteriori parametri con i dati di una nuova marmotta, la **aggiunga mantenendo l'ordinamento**.

**Esercizio 3** (da -1 a 7 punti). *Esempio 2:* rappresentazione floating point su 32 bit di **1216.37**, descrivendo i passaggi. *Esempio 3:* funzione **ricorsiva** `eser3()` che, ricevendo un reggimento e un grado, restituisca il numero di marmotte con quel grado; mostrarne il funzionamento su un reggimento di almeno 5 marmotte con un'**esecuzione simulata** dettagliando i **record di attivazione**.
:::

### Esercizio 1

{{inc marmotte.c tipi}}

{{inc marmotte.c eser1}}

"Media intera" significa **divisione intera** tra interi (niente cast). Senza marmotte di quel grado si evita la divisione per zero.

### Esercizio 2

{{inc marmotte.c eser2}}

I cinque parametri sono i cinque campi. La posizione è il primo nodo con nome **maggiore o uguale** a quello nuovo (`strcmp(...) < 0` fa avanzare).

### Esercizio 3 (esempio 2): floating point

È svolto per intero, con tutti i passaggi, nel [capitolo 2](#rappresentazione). Il risultato è

```text
0 10001001 00110000000101111010111
```

(segno 0; esponente 10 + 127 = 137 = `10001001`; mantissa = le cifre dopo l'1 di `1.0011000000 0101111010111`).

### Esercizio 3 (esempio 3): ricorsione con RDA

{{inc marmotte.c eser3}}

**Esecuzione simulata** sul reggimento (in ordine di cognome):

```text
gm --> [Amato Sara | general5] --> [Bianchi Ugo | berretto] --> [Conti Leo | berretto]
   --> [Neri Luca | berretto] --> [Rossi Anna | marmotta] --> NULL
```

chiamata dal main: `n = eser3(gm, "berretto");`

```text
FASE DI ANDATA: ogni RDA contiene i parametri (gm = indirizzo del nodo, rank)
e il punto di ritorno

 +--------------------------------------------------------------+
 | RDA 6: gm = NULL                 caso base        -> 0       |  in cima
 +--------------------------------------------------------------+
 | RDA 5: gm = [Rossi, marmotta]    grado != rank:  eser3(NULL) |
 +--------------------------------------------------------------+
 | RDA 4: gm = [Neri, berretto]     uguale: 1 + eser3([Rossi])  |
 +--------------------------------------------------------------+
 | RDA 3: gm = [Conti, berretto]    uguale: 1 + eser3([Neri])   |
 +--------------------------------------------------------------+
 | RDA 2: gm = [Bianchi, berretto]  uguale: 1 + eser3([Conti])  |
 +--------------------------------------------------------------+
 | RDA 1: gm = [Amato, general5]    diverso: eser3([Bianchi])   |
 +--------------------------------------------------------------+
 | RDA main: n = ?                                              |
 +--------------------------------------------------------------+
```

```text
FASE DI RITORNO (le RDA si chiudono dall'alto verso il basso)

RDA 6 restituisce 0
RDA 5 restituisce 0              (valore di eser3(NULL))
RDA 4 restituisce 1 + 0 = 1
RDA 3 restituisce 1 + 1 = 2
RDA 2 restituisce 1 + 2 = 3
RDA 1 restituisce 3              (valore di eser3([Bianchi]))
main:  n = 3
```

In ogni RDA `rank` punta sempre alla stessa stringa `"berretto"` del chiamante (si copia il puntatore, non la stringa).

## Traccia 3 (programma degli anni precedenti): "Marmotte sull'albero"

::: esercizio Testo (esempio 2, immatricolati 2024-25 e precedenti)
Stessi dati della traccia 2. I gradi possibili sono in un array globale di stringhe `gradi` = {"semplice", "marmotta", "berretto", "general0", ..., "general9", "mogol-00", ..., "mogol-99", "GR.mogol"}. A fine anno, per ogni medaglia la marmotta **sale** di un grado, per ogni reprimenda **scende** di un grado, senza superare "GR.mogol" né scendere sotto "semplice".
**Esercizio 2**: definire la struttura dati per rappresentare il reggimento come **albero**; scrivere `eser2()` che, ricevendo un albero del reggimento e un cognome e nome, aggiorni il record della marmotta (se c'è) con il bilancio delle medaglie e delle reprimende.
**Esercizio 3**: descrivere formalmente gli algoritmi di **visita** di un albero; esemplificarli su un albero di interi di almeno 9 nodi, con i record di attivazione.
:::

Scelgo un **albero binario di ricerca** ordinato per cognome e nome: la ricerca della marmotta scende a sinistra o a destra.

{{inc marmotte_albero.c tipi}}

{{inc marmotte_albero.c eser2}}

L'esercizio 3 è svolto nel capitolo 15 (tre visite, albero di 9 nodi, sequenze prodotte e pila delle RDA).

::: ricorda Da ricordare
- Le tracce si somigliano tutte: lista di struct, scansione con più risultati, modifica della lista.
- Per l'esercizio 3 servono **metodo + tabella motivata + esecuzione simulata**.
- Prova a rifare ogni traccia da solo, a tempo.
:::
