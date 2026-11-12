# Preparazione all'orale {#orale}

All'orale si **discute lo scritto** (sappi spiegare ogni riga che hai scritto e correggere da solo gli errori) e si fanno **domande sul programma**. Qui sotto le domande più probabili con una risposta breve: allenati a ripeterle **a voce**, con un disegno o un esempio.

## Architettura e rappresentazione

::: domanda Cos'è l'architettura di Von Neumann?
Uno schema di calcolatore in cui programma e dati stanno nella **stessa memoria** centrale; una **CPU** (unità di controllo, ALU, registri) preleva ed esegue le istruzioni una alla volta; memoria e periferiche sono collegate da un **bus**.
:::

::: domanda Cosa fanno PC e IR? Cos'è il ciclo fetch-decode-execute?
Il **PC** contiene l'indirizzo della prossima istruzione, l'**IR** l'istruzione in esecuzione. **Fetch**: si copia in IR l'istruzione all'indirizzo del PC e si incrementa il PC; **decode**: la CU riconosce il codice operativo; **execute**: si esegue. Un salto scrive un nuovo indirizzo nel PC.
:::

::: domanda Differenza tra compilatore, linker e interprete?
Il **compilatore** traduce tutto il programma sorgente in codice oggetto (linguaggio macchina), segnalando gli errori; il **linker** unisce il codice oggetto con quello delle librerie e produce l'eseguibile. Un **interprete** invece traduce ed esegue un'istruzione alla volta, senza produrre un eseguibile.
:::

::: domanda Perché si usa il complemento a due?
Ha **un solo zero**, rappresenta [-2<sup>n-1</sup>, 2<sup>n-1</sup>-1], e la **sottrazione diventa una somma** (N - M = N + (-M)), quindi basta un solo circuito sommatore.
:::

::: domanda Perché i float sono approssimati? Cos'è l'eccesso 127?
I bit sono finiti (23 di mantissa) e molte frazioni in binario sono **periodiche** (0.1, 0.37...): le cifre in più si perdono. L'esponente è memorizzato sommandogli 127, così con 8 bit senza segno (0-255) si rappresentano esponenti anche negativi.
:::

## Linguaggio C

::: domanda Cos'è un record di attivazione?
La zona di memoria (sulla pila) allocata **a ogni chiamata** di funzione: contiene parametri formali, variabili locali, valore e indirizzo di ritorno. Viene deallocata quando la funzione termina. Ogni chiamata ricorsiva ha il suo RDA.
:::

::: domanda Come si passano i parametri in C?
Sempre **per valore**: la funzione riceve una copia. Per modificare una variabile del chiamante si passa il suo **indirizzo** (parametro puntatore, "parametro di output"). Gli array sembrano passati per riferimento perché il loro nome è già l'indirizzo del primo elemento.
:::

::: domanda Differenza tra variabile locale, globale, static?
**Locale**: visibile nel blocco, vive durante l'attivazione. **Globale**: visibile ovunque dopo la dichiarazione, vive per tutto il programma. **Locale static**: visibile nella funzione ma conserva il valore tra le chiamate.
:::

::: domanda Che relazione c'è tra array e puntatori?
Il nome dell'array è l'indirizzo del primo elemento; `v[i]` equivale a `*(v+i)` (aritmetica dei puntatori: `+1` avanza di un elemento, non di un byte). Ma un array non si può riassegnare né incrementare; un puntatore sì.
:::

::: domanda Cos'è una stringa in C? Perché `malloc(strlen(s)+1)`?
Un array di char terminato da `'\0'`. `strlen` conta i caratteri **senza** il terminatore, quindi serve un posto in più per il `'\0'`.
:::

::: domanda Differenza tra allocazione statica e dinamica?
**Statica**: dimensione decisa nel codice, memoria gestita automaticamente (variabili locali nella pila, globali). **Dinamica**: memoria chiesta durante l'esecuzione con `malloc` nello **heap**, della dimensione che serve; resta finché non si chiama `free`. Rischi: `NULL` non controllato, memory leak, puntatori pendenti.
:::

::: domanda Cosa sono le stringhe "esatte" e perché si usano?
Stringhe allocate dinamicamente con esattamente `strlen + 1` caratteri: non si spreca memoria come con array sovradimensionati. Si legge in un buffer grande, si alloca la dimensione esatta, si copia.
:::

::: domanda Differenza tra file di testo e file binario?
Il file di testo contiene caratteri (leggibili, `fprintf`/`fscanf`); il binario contiene i byte come sono in memoria (`fwrite`/`fread`), è più compatto e permette l'accesso diretto con `fseek` a record di dimensione fissa.
:::

::: domanda Struct per valore o per indirizzo?
Per valore la funzione lavora su una copia (e copiare una struct grande costa); per indirizzo può modificare l'originale e si usa la freccia `p->campo`.
:::

## Metodologia e strutture dati

::: domanda Cos'è la ricorsione? Cosa serve perché termini?
Una funzione che chiama se stessa. Servono un **caso base** risolto direttamente e un **caso ricorsivo** che si riduce a un problema più piccolo, avvicinandosi al caso base.
:::

::: domanda Ricorsione o iterazione?
Sono equivalenti in potenza. La ricorsione è più naturale per strutture ricorsive (liste, alberi) e per il divide et impera, ma costa un RDA per chiamata (tempo e memoria, rischio di stack overflow).
:::

::: domanda Come funzionano selection, bubble e insertion sort? Quanto costano?
Selection: cerca il minimo del resto e lo scambia in posizione. Bubble: confronta e scambia vicini, il più grande sale in fondo. Insertion: inserisce ogni elemento al suo posto nella parte ordinata. Tutti circa n² confronti nel caso peggiore; merge sort n log n.
:::

::: domanda Quando si può usare la ricerca binaria?
Solo su dati **ordinati** e con accesso diretto (array). Dimezza lo spazio di ricerca a ogni passo: circa log<sub>2</sub> n confronti.
:::

::: domanda Scatola nera e scatola trasparente: differenze?
Nera: test scelti dalla **specifica** (classi di equivalenza dell'input, casi limite), senza guardare il codice. Trasparente: test scelti **guardando il codice** per coprire istruzioni, decisioni, condizioni, valori limite. Nessuno dei due garantisce l'assenza di errori.
:::

::: domanda Cos'è il test top-down? Cos'è uno stub?
Test incrementale di un programma modulare: si prova una funzione alla volta partendo dal main; le funzioni non ancora provate sono sostituite da **stub** (versioni finte che danno il risultato giusto per il test).
:::

::: domanda Cos'è un tipo di dato astratto?
Un tipo definito dalle **operazioni** che si possono fare sui dati e dal loro significato, indipendentemente dalla **rappresentazione concreta** (array, lista...). Esempi: tabella, lista.
:::

::: domanda Lista o array: vantaggi e svantaggi?
Lista: dimensione dinamica, inserimenti ed eliminazioni senza spostare elementi, nessuno spreco; ma niente accesso diretto (per il k-esimo bisogna scorrere) e un puntatore in più per nodo. Array: accesso diretto `v[k]`, ricerca binaria possibile; ma dimensione fissa (o costose `realloc`) e spostamenti per inserire in mezzo.
:::

::: domanda Perché alcune funzioni sulle liste ricevono `TipoLista *`?
Perché possono **cambiare la testa** (inserimento in testa o ordinato, eliminazione del primo): per modificare il puntatore di testa del chiamante bisogna riceverne l'indirizzo.
:::

::: domanda Cos'è il record generatore?
Un nodo fittizio messo davanti al primo nodo vero: così ogni nodo ha un predecessore e gli inserimenti/eliminazioni non hanno il caso speciale della testa. Alla fine la testa è `rg.next`.
:::

::: domanda Cosa sono le visite di un albero?
Algoritmi ricorsivi che esaminano tutti i nodi: preordine (radice, sinistro, destro), inordine (sinistro, radice, destro), postordine (sinistro, destro, radice). In un albero binario di ricerca l'inordine dà i valori ordinati.
:::

## Discutere il tuo scritto

Porta all'orale una copia (o la memoria) di cosa hai scritto. Prima dell'orale **riscrivi a casa la tua soluzione corretta** e provala al computer: se all'orale sai dire "qui avevo sbagliato, la versione giusta è questa, e il motivo è questo", fai una buona impressione e recuperi punti.
