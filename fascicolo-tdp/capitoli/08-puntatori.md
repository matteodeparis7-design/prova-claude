# Puntatori {#puntatori}

*(slide lezioni 13 e 14, complementi lezione 13; testo1 cap. 14)*

I puntatori sono **l'argomento chiave** del corso: senza di loro non si fanno né i parametri di output né le liste. Vale la pena studiarli con calma e con tanti disegni.

## Indirizzi e puntatori

Ogni variabile occupa una locazione di memoria che ha un **indirizzo**. Un **puntatore** è una variabile che **contiene un indirizzo**.

```c
int x = 5;
int *p;          /* p e` un "puntatore a int": puo` contenere l'indirizzo di un int */
p = &x;          /* &x = indirizzo di x: ora p "punta a" x                         */
*p = 8;          /* *p = "la variabile puntata da p", cioe` x: ora x vale 8        */
```

```text
     indirizzo 1000            indirizzo 2000
     +-----------+             +-----------+
  x  |  5 -> 8   |   <------   |   1000    |  p
     +-----------+             +-----------+
```

- `&` (**indirizzo di**): applicato a una variabile, dà il suo indirizzo.
- `*` (**dereferenziazione**): applicato a un puntatore, dà la variabile puntata.
- Nella **dichiarazione** `int *p;` l'asterisco dice solo che `p` è un puntatore.
- `NULL` (definito in `stdio.h` e `stdlib.h`) è il puntatore che **non punta a niente**. Dereferenziare `NULL` fa andare in crash il programma.

::: errore Puntatore non inizializzato
`int *p; *p = 3;` scrive in un indirizzo casuale. Un puntatore va **sempre** inizializzato: a `NULL`, all'indirizzo di una variabile, o al risultato di `malloc`.
:::

## Parametri di output (passaggio per indirizzo)

Per permettere a una funzione di **modificare una variabile del chiamante**, le si passa l'**indirizzo** della variabile. La funzione lavora con `*parametro`.

{{inc basi.c scambio}}

```text
chiamata scambio(&a, &b) con a = 3, b = 7:

  RDA scambio:  pa = &a    pb = &b    t = 3
                 |          |
                 v          v
  RDA main:     a: 3 -> 7   b: 7 -> 3
```

È lo stesso meccanismo di `scanf("%d", &x)`: `scanf` deve scrivere dentro `x`, quindi le serve il suo indirizzo.

**Schema per gli esercizi d'esame** ("la funzione restituisca A, B e C"): uno dei risultati con `return`, gli altri come parametri puntatore.

```c
/* restituisce quanti; in *media e *massimo gli altri due risultati */
int analizza(TipoLista l, int soglia, double *media, int *massimo);

/* nel chiamante: */
n = analizza(lista, 10, &m, &mx);
```

::: errore Parentesi con ++
Dentro la funzione, per incrementare un contatore di output scrivi `(*conta)++;`. Senza parentesi `*conta++` incrementa il **puntatore** (precedenza di `++`) e non il valore. In alternativa: `*conta = *conta + 1;`.
:::

## Puntatori e array

Il **nome di un array** è l'indirizzo del suo primo elemento: `v` equivale a `&v[0]`.

**Aritmetica dei puntatori**: se `p` punta a un elemento di un array, `p + 1` punta all'elemento **successivo** (il compilatore aggiunge `sizeof(tipo)` byte, non 1). Quindi:

| Notazione con indice | Notazione con puntatori |
|---|---|
| `v[i]` | `*(v + i)` |
| `&v[i]` | `v + i` |

```c
int v[5] = {10, 20, 30, 40, 50};
int *p;
for (p = v; p < v + 5; p++)     /* scansione con un puntatore */
  printf("%d ", *p);
```

Differenze tra puntatori allo stesso array danno il numero di elementi tra loro (`p - v`). Ecco come lavora `strlen`:

{{inc basi.c mialen}}

**Differenza importante**: un puntatore è una variabile e si può spostare (`p++`); il nome di un array è un indirizzo costante (`v++` è un errore).

**Riuso di una funzione su una parte di array** (lezione 14): poiché una funzione su array riceve solo un indirizzo e una dimensione, le si può passare **un pezzo** dell'array. Con `int v[10]` e la funzione `massimo(int v[], int dim)`:

```c
massimo(v, 10);        /* massimo di tutto l'array              */
massimo(v, 5);         /* massimo dei primi 5 elementi          */
massimo(v + 5, 5);     /* massimo degli ultimi 5: v[5] ... v[9] */
massimo(&v[3], 4);     /* massimo di v[3] ... v[6]              */
```

Dentro la funzione, `v[0]` è l'elemento da cui si è partiti.

## Funzioni che restituiscono puntatori

Una funzione può restituire un indirizzo, ad esempio quello di un elemento trovato in un array, o `NULL` se non lo trova:

```c
int *cercaPrimoNegativo(int v[], int dim) {
  int i;
  for (i = 0; i < dim; i++)
    if (v[i] < 0)
      return &v[i];             /* indirizzo di un elemento dell'array del chiamante: ok */
  return NULL;
}
```

Va bene restituire l'indirizzo di qualcosa che **sopravvive** alla funzione (un elemento dell'array del chiamante, memoria allocata con `malloc`), **mai** quello di una variabile locale.

## Puntatori a struct

Con le struct (capitolo 10) e le liste userai continuamente l'operatore **freccia**:

```c
p->campo      /* equivale a  (*p).campo  : il campo della struct puntata da p */
```

## Puntatori a puntatori

Se una funzione deve **modificare un puntatore** del chiamante (ad esempio la testa di una lista), le si passa l'indirizzo del puntatore: un **puntatore a puntatore**.

```c
void azzera(int **pp) {
  *pp = NULL;                  /* modifica il puntatore del chiamante */
}

int *q = &x;
azzera(&q);                    /* ora q vale NULL */
```

Con le liste, `TipoLista *pl` è proprio questo: `TipoLista` è già un puntatore, `TipoLista *` è l'indirizzo di quel puntatore (capitolo 14).

::: esame La regola d'oro dei parametri
Se una funzione deve **cambiare** una variabile del chiamante, ricevi **l'indirizzo** di quella variabile. Una lista di cui cambia la **testa** (inserimento in testa, eliminazione del primo, inserimento ordinato) si passa come `TipoLista *`. Una lista che si **legge soltanto**, o di cui si modificano solo i nodi interni, si passa come `TipoLista`.
:::

::: esercizio Esercizio 8.1 (esecuzione simulata)
Cosa stampa?

```c
int a = 1, b = 2, *p, *q;
p = &a;
q = &b;
*p = *q + 10;
p = q;
*p = *p * 3;
printf("%d %d %d %d\n", a, b, *p, *q);
```
:::

::: soluzione
`*p = *q + 10` mette in `a` il valore 2 + 10 = 12. Poi `p = q`: ora anche `p` punta a `b`. `*p = *p * 3` mette in `b` il valore 6. Stampa: `12 6 6 6`.
:::

::: esercizio Esercizio 8.2
Scrivi `void statistiche(int v[], int dim, int *somma, int *pari, double *media)` che calcola somma, numero di elementi pari e media dell'array.
:::

::: soluzione
```c
void statistiche(int v[], int dim, int *somma, int *pari, double *media) {
  int i;
  *somma = 0;
  *pari = 0;
  for (i = 0; i < dim; i++) {
    *somma += v[i];
    if (v[i] % 2 == 0)
      (*pari)++;
  }
  if (dim > 0)
    *media = (double) *somma / dim;
  else
    *media = 0;
}
/* chiamata:  statistiche(v, N, &s, &np, &m); */
```
:::
