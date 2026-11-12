# Array {#array}

*(slide lezioni 10 e 11, complementi lezioni 10 e 11, EG4; testo1 cap. 10)*

## Che cos'è un array

Un **array** è una sequenza di **N elementi dello stesso tipo**, in locazioni **consecutive** di memoria, a cui si accede con un **indice** da **0 a N-1**.

```c
#define N 5
int v[N];                       /* 5 interi: v[0] ... v[4]            */
int w[N] = {4, -2, 9, 0, 9};    /* inizializzazione                   */
double temp[] = {1.5, 2.0};     /* dimensione dedotta: 2               */
```

```text
indice:    0     1     2     3     4
        +-----+-----+-----+-----+-----+
   w    |  4  | -2  |  9  |  0  |  9  |
        +-----+-----+-----+-----+-----+
```

- La dimensione deve essere una **costante** (in ANSI C), per questo si usa `#define`.
- Gli array **non si copiano** con `=` e **non si confrontano** con `==`: si lavora elemento per elemento con un ciclo.

::: errore Uscire dall'array
`v[N]` **non esiste** (l'ultimo è `v[N-1]`). Il C **non controlla** gli indici: scrivere fuori dall'array rovina altre variabili o fa andare in crash il programma, senza messaggi. Controlla sempre la condizione dei cicli: `i < N`, non `i <= N`.
:::

## Array e funzioni

Quando passi un array a una funzione, **passi l'indirizzo del suo primo elemento** (non una copia!). Conseguenze:

- la funzione **può modificare** l'array originale;
- la funzione **non conosce la dimensione**: va passata come parametro.

{{inc basi.c arrayFun}}

L'intestazione `int massimo(int v[], int dim)` è equivalente a `int massimo(int *v, int dim)` (capitolo 8).

Una funzione non può restituire due valori con `return`. Per minimo **e** massimo si usano **parametri di output**:

{{inc basi.c minmax}}

Si chiama così: `minMax(v, N, &mn, &mx);`

## Array parzialmente riempito

Spesso non si sa quanti dati ci saranno. Si alloca un array "abbastanza grande" (il **sostegno**) e si tiene in una variabile **quanti elementi sono davvero usati**. Gli elementi validi sono sempre i primi, da `0` a `quanti-1`.

```c
#define MAX 100
int v[MAX];
int quanti = 0;              /* all'inizio l'array e` vuoto */

/* aggiunta in fondo */
if (quanti < MAX) {
  v[quanti] = x;
  quanti++;
}

/* eliminazione dell'elemento di indice k: sposto indietro quelli dopo */
for (i = k; i < quanti - 1; i++)
  v[i] = v[i + 1];
quanti--;
```

Questa è proprio l'idea della **tabella** (capitolo 10): un array di struct più un intero `quanti`.

## Matrici (array a due dimensioni)

```c
#define R 3
#define C 4
int m[R][C];                 /* 3 righe, 4 colonne */

for (i = 0; i < R; i++)      /* scorro le righe            */
  for (j = 0; j < C; j++)    /* e dentro ogni riga le colonne */
    m[i][j] = i * j;
```

In memoria la matrice è memorizzata **per righe**, una riga dopo l'altra. Passandola a una funzione, il numero di **colonne** va scritto: `void stampaMat(int m[][C], int righe)`.

**Somma di matrici**: `s[i][j] = a[i][j] + b[i][j]`. **Prodotto** (A di dimensione R×K, B di dimensione K×C):

```c
for (i = 0; i < R; i++)
  for (j = 0; j < C; j++) {
    p[i][j] = 0;
    for (k = 0; k < K; k++)
      p[i][j] += a[i][k] * b[k][j];
  }
```

::: esercizio Esercizio 6.1
Scrivi una funzione `int condensa(int v[], int dim)` che elimina dall'array tutti gli zeri, compattando gli altri elementi all'inizio, e restituisce quanti elementi restano. Esempio: `{3,0,0,5,0,7}` diventa `{3,5,7}` e restituisce 3.
:::

::: soluzione
```c
int condensa(int v[], int dim) {
  int i, k = 0;               /* k = prossima posizione libera */
  for (i = 0; i < dim; i++)
    if (v[i] != 0) {
      v[k] = v[i];
      k++;
    }
  return k;
}
```
Un solo ciclo: è più efficiente che spostare tutto indietro a ogni zero trovato.
:::

::: esercizio Esercizio 6.2
Scrivi una funzione che riceve una matrice quadrata N×N e restituisce 1 se è simmetrica (`m[i][j] == m[j][i]` per ogni i, j), 0 altrimenti.
:::

::: soluzione
```c
int simmetrica(int m[][N]) {
  int i, j;
  for (i = 0; i < N; i++)
    for (j = i + 1; j < N; j++)       /* basta la parte sopra la diagonale */
      if (m[i][j] != m[j][i])
        return 0;                     /* trovato un controesempio          */
  return 1;
}
```
:::
