# Ricorsione {#ricorsione}

*(slide lezione 17, EG8, complementi lezione 8 sui record di attivazione; testo1 cap. 15)*

## L'idea

Una funzione è **ricorsiva** quando **chiama se stessa**. Funziona se:

1. c'è almeno un **caso base**, che si risolve **direttamente**, senza chiamate ricorsive;
2. il **caso ricorsivo** riduce il problema a uno **dello stesso tipo ma più piccolo**, e si avvicina sempre al caso base.

Il modo di pensare: "**supponiamo** che la funzione sappia già risolvere il problema più piccolo; come uso quel risultato per risolvere il problema grande?"

## Il fattoriale

n! = n × (n-1) × ... × 1, e per definizione 0! = 1. Ma n! = n × (n-1)! : ecco la ricorsione.

{{inc ricorsione_ordinamento.c fatt}}

Versione **iterativa**, per confronto:

```c
int fattIter(int n) {
  int i, prod = 1;
  for (i = 2; i <= n; i++)
    prod *= i;
  return prod;
}
```

Con `int` il fattoriale va in overflow già con n = 13 (13! supera 2<sup>31</sup>-1); con `long` a 64 bit si arriva a 20.

## Visualizzare la ricorsione con i record di attivazione

Ogni chiamata ricorsiva crea un **nuovo RDA**, con **i suoi** parametri e **le sue** variabili locali. Le RDA si impilano; quando si arriva al caso base, le chiamate terminano una alla volta **in ordine inverso**, ciascuna restituendo il valore alla precedente.

```text
x = fatt(3)          FASE DI ANDATA (chiamate)          FASE DI RITORNO

                    +------------------+
                    | RDA fatt  n = 1  |  caso base ---> restituisce 1
                    +------------------+
                    | RDA fatt  n = 2  |  aspetta fatt(1) ---> 2 * 1 = 2
                    +------------------+
                    | RDA fatt  n = 3  |  aspetta fatt(2) ---> 3 * 2 = 6
                    +------------------+
                    | RDA main  x = ?  |  ---> x = 6
                    +------------------+
```

**Visualizzazione logica** (albero delle chiamate), altrettanto valida all'esame:

```text
fatt(3) = 3 * fatt(2)
              fatt(2) = 2 * fatt(1)
                            fatt(1) = 1          (caso base)
              fatt(2) = 2 * 1 = 2
fatt(3) = 3 * 2 = 6
```

::: esame Come si presenta un'esecuzione simulata con RDA
1. Scrivi la chiamata iniziale e i valori dei parametri.
2. Disegna una RDA per ogni chiamata, impilandole, con **parametri**, **variabili locali** e **punto di ritorno** ("aspetta il risultato di ...").
3. Segna il **caso base** e il valore che restituisce.
4. Ripercorri la pila **all'indietro** scrivendo il valore restituito da ogni RDA e cancellando quelle terminate.
5. Scrivi il risultato finale.

Nelle tracce "Giovani Marmotte" (esercizio 3) è richiesto esattamente questo su una lista di 5 elementi: vedi il capitolo 17.
:::

## Inversione dell'input (EG8)

Leggere caratteri fino al punto e stamparli al contrario (`TOPI.` → `IPOT`). L'idea: leggo un carattere; **se non è il punto**, faccio leggere e invertire **il resto** e **poi** stampo il carattere letto.

{{inc ricorsione_ordinamento.c invertiInput}}

Ogni RDA conserva **il suo** `ch`: è la pila delle RDA a "ricordare" i caratteri, senza bisogno di un array.

```text
input: T O P I .
RDA 1: ch='T'  chiama RDA 2 ... poi stampa T  (per ultimo)
RDA 2: ch='O'  chiama RDA 3 ... poi stampa O
RDA 3: ch='P'  chiama RDA 4 ... poi stampa P
RDA 4: ch='I'  chiama RDA 5 ... poi stampa I  (per primo)
RDA 5: ch='.'  caso base: non fa nulla e termina
output: I P O T
```

## Palindromi (EG8)

Una parola è palindroma (radar, anna, ingegni) se si legge uguale nei due sensi. La porzione `p[i..j]` è palindroma se `p[i] == p[j]` **e** la porzione interna `p[i+1..j-1]` è palindroma. Caso base: `i >= j` (zero o un carattere: palindroma).

{{inc ricorsione_ordinamento.c palin}}

## Altri esempi

{{inc ricorsione_ordinamento.c mcdRic}}

{{inc ricorsione_ordinamento.c sommaArrayRic}}

## Ricorsione sulle liste

Una lista è **vuota**, oppure è **un nodo seguito da una lista**. Per questo le funzioni ricorsive sulle liste sono naturali: caso base `l == NULL`, caso ricorsivo "faccio qualcosa col primo nodo e chiamo la funzione su `l->next`". Le trovi nel capitolo 14.

## Ricorsione o iterazione?

- Tutto quello che si fa con la ricorsione si può fare con i cicli, e viceversa.
- La ricorsione è spesso **più semplice da scrivere e da capire** quando il problema è ricorsivo per natura (liste, alberi, divide et impera).
- Costa di più: ogni chiamata alloca un RDA (tempo e memoria). Con troppe chiamate annidate la pila si esaurisce (*stack overflow*).
- Esempio da evitare: Fibonacci "ingenuo" `fib(n) = fib(n-1) + fib(n-2)` ricalcola gli stessi valori un numero esponenziale di volte.

::: errore Errori tipici
- **Manca il caso base**, o il caso ricorsivo non si avvicina al caso base: ricorsione infinita, il programma va in crash.
- Dimenticare `return` davanti alla chiamata ricorsiva: `return 1 + conta(l->next);` e non solo `conta(l->next);`.
- Usare una variabile locale "per accumulare" tra le chiamate: ogni RDA ha la **sua** copia; il risultato si costruisce con i valori restituiti.
:::

::: esercizio Esercizio 11.1
Scrivi una funzione ricorsiva `int contaCifre(int n)` (n ≥ 0) che restituisce il numero di cifre decimali di n, e mostra le RDA per `contaCifre(472)`.
:::

::: soluzione
```c
int contaCifre(int n) {
  if (n < 10)                    /* caso base: una sola cifra */
    return 1;
  return 1 + contaCifre(n / 10); /* tolgo l'ultima cifra       */
}
```
```text
RDA contaCifre n=4    caso base           -> 1
RDA contaCifre n=47   1 + contaCifre(4)   -> 1 + 1 = 2
RDA contaCifre n=472  1 + contaCifre(47)  -> 1 + 2 = 3
RDA main                                  -> riceve 3
```
:::

::: esercizio Esercizio 11.2
Scrivi una funzione ricorsiva `int maxArray(int v[], int n)` che restituisce il massimo dei primi n elementi (n ≥ 1).
:::

::: soluzione
```c
int maxArray(int v[], int n) {
  int m;
  if (n == 1)
    return v[0];                 /* un solo elemento: e` lui il massimo */
  m = maxArray(v, n - 1);        /* massimo dei primi n-1               */
  if (v[n - 1] > m)
    return v[n - 1];
  return m;
}
```
:::
