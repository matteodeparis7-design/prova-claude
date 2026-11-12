# Laboratorio: come si impara a programmare in C {#laboratorio}

Programmare si impara **programmando**, come si impara a nuotare in acqua. Leggere il fascicolo serve a capire; ma all'esame dovrai **scrivere** codice C corretto, su carta, da solo. Questo capitolo ti dice come allenarti, e alla fine del fascicolo trovi la [Palestra di programmazione](#palestra) con 25 esercizi graduati e risolti.

## 1. Prepara l'ambiente

Al corso si usa **Dev-C++** (Windows), un ambiente gratuito con editor, compilatore e debugger.

1. Scarica **Embarcadero Dev-C++** (la versione aggiornata) dal sito ufficiale e installalo.
2. Imposta lo standard ANSI C, come chiede il professore: menu *Strumenti → Opzioni di compilazione → Compilatore → Generazione di codice → Compilatore C → "Supporto programmi ANSI standard C" = Yes* (in inglese: *Tools → Compiler Options → Settings → C Compiler → Support all ANSI Standard C Programs*).
3. Per ogni esercizio: *File → Nuovo → File sorgente*, salva con estensione **`.c`** (non `.cpp`!), poi **F11** (compila ed esegui).

Alternative: su Mac o Linux il compilatore `gcc` dal terminale (`gcc -std=c89 -pedantic -Wall prova.c -o prova` e poi `./prova`); da telefono o da un PC qualsiasi, un compilatore online come OnlineGDB (scegli il linguaggio **C**).

::: nota Se la finestra si chiude subito
In alcune versioni di Dev-C++ la finestra del programma si chiude appena finisce. Esegui dal menu *Esegui* (che di solito aspetta un tasto) oppure aggiungi prima di `return 0;` le righe `printf("premi invio"); getchar(); getchar();`.
:::

## 2. Il ciclo di lavoro: scrivi, compila, esegui, prova

```text
   +----------+     +-----------+  errori   +----------------------+
   |  SCRIVI  | --> |  COMPILA  | --------> | leggi il PRIMO errore|
   |  il .c   |     |  (F9/F11) |           | correggi, ricompila  |
   +----------+     +-----------+           +----------------------+
                          | ok
                          v
                    +-----------+  output   +----------------------+
                    |  ESEGUI   | --------> | e` quello ATTESO?    |
                    | con dati  |  diverso  | no: DEBUGGING        |
                    | di prova  |           | si`: prova altri casi|
                    +-----------+           +----------------------+
```

Regola d'oro: **compila spesso**. Scrivi poche righe, compila, prova. Scrivere 100 righe e compilare alla fine produce 30 errori insieme e nessuna idea di dove cercarli.

## 3. Leggere gli errori del compilatore

Il compilatore ti dice **file:riga** e un messaggio (in inglese). Correggi **sempre il primo errore**: spesso gli altri sono conseguenze del primo. L'errore può essere sulla riga **prima** di quella indicata (tipicamente un `;` mancante).

| Messaggio (gcc / Dev-C++) | Cosa vuol dire di solito |
|---|---|
| `expected ';' before ...` | manca il punto e virgola alla fine della riga **precedente** |
| `'x' undeclared` | variabile non dichiarata, o scritta in modo diverso (il C distingue maiuscole e minuscole: `Somma` ≠ `somma`) |
| `implicit declaration of function 'f'` | funzione usata prima del suo prototipo, o `#include` mancante (es. `string.h` per `strlen`) |
| `expected declaration or statement at end of input` | manca una `}` di chiusura |
| `incompatible types` / `makes pointer from integer` | tipi sbagliati: ad esempio un `int` dove serve un puntatore, o dimenticato `*` o `&` |
| `too few arguments to function` | chiamata con meno parametri del prototipo |
| `format '%d' expects argument of type 'int *'` (warning) | in `scanf` manca la `&` |
| `control reaches end of non-void function` (warning) | in qualche caso la funzione non arriva a un `return` |

**Gli avvisi (warning) contano**: il programma compila, ma quasi sempre c'è un errore. Trattali come errori.

## 4. Quando il programma compila ma sbaglia: debugging

1. **Esecuzione simulata a mano**: prendi carta e penna e segui il codice riga per riga con i dati del test che fallisce, scrivendo i valori delle variabili in una tabella (capitolo 4).
2. **Metodo delle stampe**: aggiungi `printf` temporanee per vedere i valori, ad esempio `printf("DEBUG i=%d somma=%d\n", i, somma);` dentro il ciclo sospetto.
3. **Debugger di Dev-C++**: metti un *breakpoint* (clic sul numero di riga), avvia con *Debug*, esegui **passo passo** e aggiungi le variabili da osservare (*watch*). Sulla pagina del corso c'è un video di esempio.

Gli errori a **tempo di esecuzione** più comuni:

- il programma si blocca e va in crash: puntatore `NULL` o non inizializzato dereferenziato, indice fuori dall'array, `scanf` senza `&`;
- il programma non termina: ciclo infinito (manca l'avanzamento, condizione sbagliata);
- risultati strani: variabile non inizializzata, divisione intera, `=` al posto di `==`.

## 5. Un metodo per risolvere qualunque esercizio

È lo stesso metodo che il professore applica a lezione e nelle EG:

1. **Capisci il problema**: quali sono i dati di **INPUT**? Quale **OUTPUT** si vuole? Fai **un esempio a mano** con numeri piccoli.
2. **Scrivi l'algoritmo** in italiano a passi numerati (pseudocodice, capitolo 3). Cerca gli **schemi** che conosci: contatore, accumulatore, massimo, ricerca con flag, scansione di lista...
3. **Scegli le strutture dati**: variabili semplici? Un array? Una struct? Una lista?
4. **Dividi in funzioni**: ogni sottoproblema una funzione; scrivi prima il `main` con le chiamate, poi i prototipi.
5. **Traduci in C** un pezzo alla volta, compilando spesso; nei commenti indica il passo dell'algoritmo.
6. **Prova** con casi scelti con criterio (capitolo 13): caso normale, casi limite (zero elementi, un elemento), dati "strani".

## 6. Come allenarsi (il piano pratico)

- **Ogni volta che studi un capitolo**, ricopia ed esegui i programmi del capitolo (non incollarli: **riscriverli** a mano allena le dita e la memoria), poi **modificali**: cambia un dato, aggiungi una funzione, introduci un errore apposta e guarda cosa dice il compilatore.
- Fai gli **esercizi del capitolo** prima di aprire la soluzione. Se ti blocchi più di 20 minuti, guarda la soluzione, **chiudila**, e riscrivila da solo il giorno dopo.
- Fai la **Palestra** in ordine: ogni livello usa gli strumenti dei precedenti.
- Rifai le **EG** del corso (cartella "esercitazioni guidate" sul sito): sono esercizi pensati dal professore, con i suggerimenti passo passo.
- Dalle liste in poi, allenati **su carta**: all'esame non c'è il compilatore. Scrivi a mano, poi ricopia al computer e guarda se compila e funziona. Gli errori che il compilatore ti trova sono quelli che all'esame ti costerebbero punti.

::: esame Perché tutto questo conta all'esame
Lo scritto chiede di **scrivere codice** corretto in 2h30, senza compilatore. Chi ha scritto e fatto girare decine di programmi scrive giusto "di mano"; chi ha solo letto le soluzioni si blocca davanti al foglio bianco. Gli homework, obbligatori, servono proprio a questo: falli tu, fino in fondo.
:::
