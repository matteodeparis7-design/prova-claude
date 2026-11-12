# Palestra di programmazione {#palestra}

25 esercizi **graduati**, dal primo programma alle liste. Tutte le soluzioni sono programmi completi, compilati ed eseguiti. Come usarli:

1. leggi il testo e **scrivi la tua soluzione al computer** (o su carta, dai livelli 6-7);
2. compila e prova con l'esempio indicato e con altri dati scelti da te;
3. solo dopo apri la soluzione e **confrontala** con la tua: ci sono tanti modi giusti di scrivere un programma, ma controlla di non aver dimenticato casi;
4. dopo qualche giorno **rifai** gli esercizi in cui ti eri bloccato.

## Livello 1: input, output, espressioni

::: esercizio Esercizio P01. Da Celsius a Fahrenheit
Leggi una temperatura in gradi Celsius (anche con decimali) e stampala in Fahrenheit: F = C × 9/5 + 32.
:::

::: soluzione
{{inc palestra/es01.c sol}}

Input `36.6` → `36.6 C = 97.9 F`. Attenzione: se `c` fosse `int`, `c * 9 / 5` farebbe una divisione intera e perderebbe i decimali; e scrivere `9 / 5 * c` darebbe sempre `c` (perché `9 / 5` vale 1).
:::

::: esercizio Esercizio P02. Secondi in ore, minuti, secondi
Leggi un numero di secondi e stampalo come ore, minuti e secondi.
:::

::: soluzione
{{inc palestra/es02.c sol}}

Input `3725` → `1 h 2 min 5 s`. Divisione intera `/` e resto `%` sono la coppia perfetta per questi problemi.
:::

::: esercizio Esercizio P03. Pari o dispari, positivo o negativo
Leggi un intero e di' se è pari o dispari, e se è positivo, negativo o zero.
:::

::: soluzione
{{inc palestra/es03.c sol}}

Input `-7` → `-7 e` dispari`, `ed e` negativo`. Nota la catena `if / else if / else`.
:::

::: esercizio Esercizio P04. Equazione di secondo grado
Leggi a, b, c e stampa le soluzioni reali di ax² + bx + c = 0 (gestisci a = 0 e il discriminante negativo).
:::

::: soluzione
{{inc palestra/es04.c sol}}

Input `1 -3 2` → `x1 = 2.000  x2 = 1.000`. Con gcc da terminale serve `-lm` per `sqrt`; Dev-C++ lo fa da solo.
:::

## Livello 2: cicli

::: esercizio Esercizio P05. Tabellina
Leggi n e stampa la sua tabellina da 1 a 10, ben incolonnata.
:::

::: soluzione
{{inc palestra/es05.c sol}}

`%2d` e `%3d` riservano 2 o 3 spazi: le colonne restano allineate.
:::

::: esercizio Esercizio P06. Somma e media di n numeri
Leggi quanti numeri verranno dati, poi leggili e stampa somma e media.
:::

::: soluzione
{{inc palestra/es06.c sol}}

Input `3`, poi `1.5 2.5 5` → `somma 9.00, media 3.00`. Schema **accumulatore**.
:::

::: esercizio Esercizio P07. Massimo con sentinella
Leggi numeri positivi finché arriva 0; stampa quanti sono e il massimo.
:::

::: soluzione
{{inc palestra/es07.c sol}}

Input `4 9 2 0` → `letti 3 numeri, massimo 9`. Schema **sentinella** + **massimo** (il candidato parte dal primo valore letto).
:::

::: esercizio Esercizio P08. Cifre di un numero
Leggi un intero positivo; stampalo con le cifre al contrario e stampa la somma delle cifre.
:::

::: soluzione
{{inc palestra/es08.c sol}}

Input `1234` → `4321`, somma `10`. `n % 10` è l'ultima cifra, `n / 10` la toglie.
:::

::: esercizio Esercizio P09. Triangolo di asterischi
Leggi n e disegna un triangolo di n righe: la riga i ha i asterischi.
:::

::: soluzione
{{inc palestra/es09.c sol}}

Due cicli **annidati**: quello esterno conta le righe, quello interno stampa gli asterischi della riga.
:::

::: esercizio Esercizio P10. Numero perfetto
Un numero è perfetto se è uguale alla somma dei suoi divisori minori di lui (6 = 1+2+3). Verifica se n è perfetto.
:::

::: soluzione
{{inc palestra/es10.c sol}}

Input `28` → perfetto (1+2+4+7+14).
:::

## Livello 3: funzioni

::: esercizio Esercizio P11. Funzione primo
Scrivi `int primo(int n)` e usala per stampare i primi in un intervallo [a, b].
:::

::: soluzione
{{inc palestra/es11.c sol}}

Input `10 30` → `11 13 17 19 23 29`. Il `return 0` dentro il ciclo termina subito la funzione.
:::

::: esercizio Esercizio P12. Fattoriale e coefficiente binomiale
Scrivi `long fattoriale(int n)` e usala per calcolare il coefficiente binomiale n! / (k!(n-k)!).
:::

::: soluzione
{{inc palestra/es12.c sol}}

Input `5 2` → `5! = 120`, binomiale `10`. Una funzione usata per costruirne un'altra: **riuso**.
:::

::: esercizio Esercizio P13. Calcolatrice con switch
Leggi operazioni come `3 * 4` finché arriva `0 x 0`; una funzione calcola il risultato e segnala con un **parametro di output** le operazioni non valide (operatore sconosciuto, divisione per zero).
:::

::: soluzione
{{inc palestra/es13.c sol}}

Input `3 * 4`, `8 / 0`, `9 - 2.5` → `= 12`, `operazione non valida`, `= 6.5`. Lo spazio in `" %c"` fa saltare gli spazi prima dell'operatore.
:::

## Livello 4: array

::: esercizio Esercizio P14. Al contrario
Leggi 5 interi in un array e stampali in ordine inverso.
:::

::: soluzione
{{inc palestra/es14.c sol}}

Ricorda: gli indici vanno da 0 a N-1; il ciclo all'indietro parte da `N - 1`.
:::

::: esercizio Esercizio P15. Quante volte compare
Dato un array, stampa per ogni valore distinto quante volte compare.
:::

::: soluzione
{{inc palestra/es15.c sol}}

Trucco: stampo un valore solo se **non compare prima** della sua posizione (`conta(v, i, v[i]) == 0`), riusando la stessa funzione su una parte dell'array.
:::

::: esercizio Esercizio P16. Togliere i doppioni
Da un array **ordinato** elimina i valori ripetuti, compattando; restituisci la nuova dimensione.
:::

::: soluzione
{{inc palestra/es16.c sol}}

`{1,1,2,4,4,4,7,9,9}` → `1 2 4 7 9`. Stessa idea di `condensa` (capitolo 6).
:::

::: esercizio Esercizio P17. Matrice trasposta
Calcola la trasposta di una matrice 2×3 (le righe diventano colonne) e stampala.
:::

::: soluzione
{{inc palestra/es17.c sol}}

Output: `1 4 / 2 5 / 3 6`.
:::

## Livello 5: stringhe e puntatori

::: esercizio Esercizio P18. Maiuscolo e palindromo
Leggi una parola, trasformala in maiuscolo e di' se è palindroma (versione iterativa, con due indici).
:::

::: soluzione
{{inc palestra/es18.c sol}}

Input `Radar` → `RADAR e` palindroma`. `%50s` impedisce di leggere più caratteri di quanti l'array ne contenga.
:::

::: esercizio Esercizio P19. strcmp e strcpy fatte a mano
Scrivi le tue versioni di `strcmp` e `strcpy`.
:::

::: soluzione
{{inc palestra/es19.c sol}}

Il cuore delle stringhe C: si scorre fino al `'\0'`, che va sempre copiato.
:::

::: esercizio Esercizio P20. Scambia minimo e massimo
Scrivi una funzione che scambia di posto minimo e massimo di un array e restituisce le loro posizioni con due parametri di output.
:::

::: soluzione
{{inc palestra/es20.c sol}}

`{5,9,1,7}` → `5 1 9 7`, min era in 2, max in 1.
:::

## Livello 6: struct, memoria dinamica, file

::: esercizio Esercizio P21. Classe dinamica
Leggi n, alloca dinamicamente un array di n studenti (nome come stringa esatta, voto), calcola la media e stampa chi sta sopra la media. Libera tutto alla fine.
:::

::: soluzione
{{inc palestra/es21.c sol}}

Input `3`, `anna 28`, `luca 22`, `sara 30` → media `26.67`, sopra: `anna sara`. Prima si liberano le stringhe, poi l'array.
:::

::: esercizio Esercizio P22. Salva e ricarica
Salva un array di studenti su un file di testo e ricaricalo in un altro array.
:::

::: soluzione
{{inc palestra/es22.c sol}}

Il ciclo di lettura si ferma quando `fscanf` non legge più 2 valori (o l'array è pieno).
:::

## Livello 7: liste

::: esercizio Esercizio P23. Costruisci una lista dall'input
Leggi interi fino allo 0 e costruisci una lista **nello stesso ordine** di input; stampala e deallocala.
:::

::: soluzione
{{inc palestra/es23.c sol}}

Input `5 3 8 0` → `5 -> 3 -> 8 -> NULL`. Tenere un puntatore all'**ultimo** nodo evita di riscorrere la lista a ogni inserimento.
:::

::: esercizio Esercizio P24. Sopra la media
Conta i nodi di una lista con valore maggiore della media dei valori.
:::

::: soluzione
{{inc palestra/es24.c sol}}

Servono **due scansioni**: la prima calcola la media, la seconda conta. Lista `2 8 5 9 1` → 2.
:::

::: esercizio Esercizio P25. Dizionario ordinato (programma completo)
Programma con menu: aggiungi una parola (in ordine alfabetico, senza doppioni, come stringa esatta), elimina una parola, stampa il dizionario. Alla fine dealloca tutto.
:::

::: soluzione
{{inc palestra/es25.c sol}}

È un piccolo "homework": tipi, inserimento ordinato con `strcmp`, eliminazione, stampa, deallocazione e un menu con `switch`. Se lo sai scrivere da solo, sei pronto per gli esercizi 1 e 2 dello scritto.
:::

## E adesso?

Hai finito la palestra? Passa alle [tracce di esercitazione](#esercitazione) e alle [tracce del professore](#tracce), **su carta e a tempo**. Poi rifai i tre esercizi più difficili per te senza guardare nulla.
