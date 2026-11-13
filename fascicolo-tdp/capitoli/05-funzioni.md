# Funzioni e record di attivazione {#funzioni}

*(slide lezioni 8 e 10, complemento "Record di attivazione"; testo1 cap. 11)*

::: obiettivi Cosa imparerai
- dichiarare, definire e chiamare una funzione
- cosa succede in memoria a ogni chiamata (record di attivazione)
- visibilità e durata delle variabili
:::

## Perché le funzioni

Una funzione è un **sottoprogramma** con un nome, che risolve un sottoproblema. Serve a non ripetere codice, a dividere un problema grande in pezzi (**modularizzazione**, progettazione *top-down*) e a provare ogni pezzo separatamente.

## Dichiarazione, definizione, chiamata

```c
#include <stdio.h>

int mcd(int, int);                /* 1. DICHIARAZIONE (prototipo): prima del main */

int main(void) {
  int a = 15, b = 5, m;
  m = mcd(a, b);                  /* 2. CHIAMATA: a e b sono i parametri ATTUALI */
  printf("%d\n", m);
  return 0;
}
```

{{inc basi.c mcd}}

- **Prototipo**: tipo restituito, nome, tipi dei parametri. Permette al compilatore di controllare le chiamate.
- **Definizione**: intestazione + corpo. `n` e `m` sono i **parametri formali**.
- **Chiamata**: i parametri **attuali** sono **espressioni**: il loro **valore** viene **copiato** nei parametri formali.
- `return espressione;` termina la funzione e restituisce il valore al chiamante. Una funzione `void` non restituisce nulla.

## Passaggio dei parametri per valore

In C **i parametri passano sempre per valore**: la funzione riceve una **copia**. Modificare un parametro formale **non cambia** la variabile del chiamante.

{{inc basi.c scambio}}

`scambioNO(a, b)` scambia solo le copie: dopo la chiamata `a` e `b` sono uguali a prima. Per modificare una variabile del chiamante bisogna passarne l'**indirizzo** (`scambio(&a, &b)`): lo vedremo bene con i puntatori (capitolo 8). È il meccanismo dei **parametri di output**, che userai in ogni esercizio 1 d'esame.

## Il record di attivazione (RDA)

Ogni volta che una funzione viene **chiamata** succede questo:

1. l'esecuzione del chiamante si **sospende**;
2. viene allocata in memoria (sulla **pila**, *stack*) una zona chiamata **record di attivazione** (RDA). Contiene:
   - i **parametri formali**, riempiti con le copie dei valori dei parametri attuali;
   - le **variabili locali**;
   - il **valore di ritorno** e l'**indirizzo di ritorno** (dove riprendere nel chiamante);
3. si esegue il corpo della funzione, usando le locazioni del suo RDA;
4. con `return` il valore torna al chiamante, l'RDA viene **deallocato** (sparisce) e il chiamante riprende.

```text
chiamata m = mcd(15, 5) dentro main:

        PILA (cresce verso l'alto)
   +-------------------------------+
   | RDA mcd                       |  <- in cima: la funzione in esecuzione
   |   parametri:  n = 15  m = 5   |
   |   ritorno a:  main, riga "m=" |
   +-------------------------------+
   | RDA main                      |
   |   variabili:  a=15 b=5 m=?    |
   +-------------------------------+

dopo il return: l'RDA di mcd sparisce, in main  m = 5
```

Le RDA si impilano: se `main` chiama `f` e `f` chiama `g`, sulla pila ci sono main, f, g; quando `g` finisce si torna a `f`. Questa pila diventa fondamentale per capire la **ricorsione** (capitolo 11).

## Visibilità e ciclo di vita delle variabili

- **Variabili locali** (dichiarate in una funzione o in un blocco): **visibili solo lì**; **nascono** quando la funzione viene attivata e **muoiono** quando termina (vivono nell'RDA). Due funzioni possono avere variabili locali con lo stesso nome: sono variabili diverse.
- **Variabili globali** (dichiarate fuori da ogni funzione): visibili in tutte le funzioni dopo la dichiarazione; vivono per tutto il programma. Da usare il meno possibile (rendono difficile capire chi modifica cosa).
- Variabili locali **`static`**: visibili solo nella funzione, ma **conservano il valore** tra una chiamata e l'altra.
- Una variabile locale **nasconde** una globale con lo stesso nome (*shadowing*).

```c
int contatore = 0;                 /* globale                          */

void f(void) {
  static int chiamate = 0;         /* inizializzata una volta sola     */
  int locale = 0;                  /* ricreata a ogni chiamata         */
  chiamate++;
  locale++;
  contatore++;
  printf("%d %d %d\n", chiamate, locale, contatore);
}
/* chiamando f() tre volte stampa: 1 1 1, poi 2 1 2, poi 3 1 3 */
```

::: errore Restituire l'indirizzo di una variabile locale
```c
int *sbagliata(void) {
  int x = 5;
  return &x;        /* x muore con l'RDA: il puntatore restituito non vale piu` */
}
```
Per restituire memoria che "sopravvive" alla funzione si usa `malloc` (capitolo 9).
:::

## Progettare con le funzioni (il metodo del corso)

Nelle lezioni e nelle EG il professore procede sempre in **fasi**:

1. **ambiente di calcolo**: scrivo il `main` con le variabili e le **chiamate** delle funzioni che mi servono, come se esistessero già;
2. **prototipi**: scrivo le dichiarazioni (che cosa riceve, che cosa restituisce ogni funzione);
3. **algoritmo** di ogni funzione, in italiano;
4. **definizione** in C;
5. **test** (capitolo 13).

All'esame fai lo stesso per ogni `eserN`: prima l'intestazione (cosa riceve, cosa restituisce, quali sono i parametri di output), poi l'algoritmo in due righe di commento, poi il codice.

::: esame Domande d'orale
"Che cos'è un record di attivazione e cosa contiene?" "Differenza tra parametro formale e attuale?" "Perché `scambioNO` non funziona?" "Cosa vuol dire che il passaggio è per valore?" "Differenza tra variabile locale, globale e static?"
:::

::: esercizio Esercizio 5.1
Scrivi una funzione `int potenza(int base, int esp)` che calcola base<sup>esp</sup> (esp ≥ 0) senza usare librerie, e disegna la pila delle RDA durante la chiamata `x = potenza(2, 3);` fatta dal `main`.
:::

::: soluzione
```c
int potenza(int base, int esp) {
  int i, risultato = 1;
  for (i = 0; i < esp; i++)
    risultato *= base;
  return risultato;
}
```
```text
   +----------------------------------------+
   | RDA potenza                            |
   |  par:  base = 2   esp = 3              |
   |  loc:  i = 0,1,2,3   risultato = 1,2,4,8 |
   +----------------------------------------+
   | RDA main:  x = ?                       |
   +----------------------------------------+
al return l'RDA di potenza sparisce e in main x = 8
```
:::

::: ricorda Da ricordare
- I parametri passano **per valore**: la funzione riceve copie.
- Ogni chiamata crea un **RDA** (parametri, variabili locali, ritorno) che sparisce al termine.
- Mai restituire l'indirizzo di una variabile locale.
:::
