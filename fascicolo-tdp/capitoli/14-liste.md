# Liste collegate {#liste}

*(slide lezioni 21-25, EG10 e EG11; testo2 cap. 6)*

::: obiettivi Cosa imparerai
- definire i tipi di una lista collegata
- scorrere, cercare, inserire (testa, coda, ordinato), eliminare, deallocare
- le tecniche dei due puntatori e del record generatore
:::

::: esame Il capitolo più importante
Gli esercizi 1 e 2 dello scritto (23 punti su 30) sono **sempre** sulle liste. Studia questo capitolo finché sai scrivere **a memoria e senza errori** tutte le funzioni qui sotto, disegnando i puntatori.
:::

## L'idea

Una **lista collegata** (o concatenata) è una sequenza di **nodi**. Ogni nodo è una struct allocata dinamicamente con:

- l'**informazione** (`info`): un intero, o una struct con tutti i dati dell'elemento;
- un **puntatore al nodo successivo** (`next`). L'ultimo nodo ha `next == NULL`.

La lista si identifica con il **puntatore al primo nodo** (la **testa**). La **lista vuota** è il puntatore `NULL`.

```text
  l
+---+     +------+---+     +------+---+     +------+------+
| o-+---> |  3   | o-+---> |  2   | o-+---> |  1   | NULL |
+---+     +------+---+     +------+---+     +------+------+
 testa      info  next
```

Rispetto all'array: la lista **cresce e si accorcia un nodo alla volta** (nessuna dimensione massima, nessuno spreco) e si inserisce/elimina **senza spostare** gli altri elementi; però per raggiungere il k-esimo elemento bisogna **scorrere** dall'inizio (niente accesso diretto `v[k]`).

## I tipi

{{inc liste.c tipi}}

- `struct nodo` contiene un puntatore a `struct nodo`: è una **struttura ricorsiva** (per questo serve il nome `struct nodo` e non basta il typedef, che non è ancora definito a quel punto).
- `TipoLista` è **un puntatore**. Una variabile lista si dichiara e **si inizializza sempre a `NULL`**: `TipoLista l = NULL;`.

::: nota Nomi e convenzioni
Il libro Calvanese et al. usa nomi come `TipoSCL` (Sequenza Collegata Lineare) e `TipoNodoSCL`; a lezione si usano anche nomi come `insTestaLista`. I nomi non contano: conta la struttura. All'esame, se il testo chiede un nome (es. `TipoReggimento`), **usa quello**.
:::

## Quando passare `TipoLista` e quando `TipoLista *`

| La funzione... | Parametro | Esempi |
|---|---|---|
| **legge** soltanto la lista | `TipoLista l` | stampa, lunghezza, ricerca, conteggi, massimo |
| può **cambiare la testa** | `TipoLista *pl` (si chiama con `&l`) | inserimento in testa/coda/ordinato, eliminazione, deallocazione |

Dentro la funzione con `TipoLista *pl`, la testa è `*pl`. Per passarla a una funzione che legge soltanto: `stampaLista(*pl)`.

## Scansione: stampa e lunghezza

Lo schema base: un puntatore **p** parte dalla testa e avanza con `p = p->next` finché diventa `NULL`.

{{inc liste.c stampa}}

{{inc liste.c lunghezza}}

`l` è un parametro passato per valore: spostarlo non modifica la lista del chiamante.

## Ricerca

{{inc liste.c cerca}}

L'ordine `l != NULL && l->info != x` è fondamentale: se `l` è `NULL` la seconda condizione non viene valutata (cortocircuito).

Variante con massimo e parametro di output (restituisce 0 se la lista è vuota):

{{inc liste.c maxLista}}

## Inserimento in testa

{{inc liste.c insTesta}}

```text
PRIMA:   *pl --> [2] --> [1] --> NULL

1. nuovo = malloc(...)            nuovo --> [ ? | ? ]
2. nuovo->info = 3                nuovo --> [ 3 | ? ]
3. nuovo->next = *pl              nuovo --> [ 3 | o-]--> [2] --> [1] --> NULL
4. *pl = nuovo                    *pl ----> [ 3 ] --> [2] --> [1] --> NULL
```

L'ordine dei passi 3 e 4 è importante: se facessi prima `*pl = nuovo`, perderei l'indirizzo del vecchio primo nodo.

Costruire una lista di n elementi con inserimenti in testa: gli elementi risultano in **ordine inverso** rispetto all'inserimento.

```c
TipoLista l = NULL;
for (i = 1; i <= 3; i++)
  insTesta(&l, i);         /* l: 3 -> 2 -> 1 -> NULL */
```

## Inserimento in coda

Bisogna arrivare all'**ultimo** nodo (quello con `next == NULL`) e attaccargli il nuovo. Caso speciale: se la lista è vuota, il nuovo nodo diventa la testa.

{{inc liste.c insCoda}}

Attenzione alla condizione `while (p->next != NULL)`: ci si ferma **sull'ultimo** nodo, non dopo (con `while (p != NULL)` si uscirebbe con `p == NULL` e non si saprebbe più a chi attaccare il nuovo nodo).

### La tecnica del record generatore (RG)

Il caso speciale "lista vuota / primo nodo" esiste perché il primo nodo non ha un predecessore. Il **record generatore** è un nodo **fittizio** messo davanti alla lista: così **ogni** nodo vero ha un predecessore e il caso speciale sparisce. Alla fine la testa vera è `rg.next`.

{{inc liste.c insCodaRG}}

```text
rg (finto)       nodi veri
+---+---+       +---+---+     +---+------+
| ? | o-+-----> | 3 | o-+---> | 2 | NULL |
+---+---+       +---+---+     +---+------+
  ^ p parte da qui, quindi p non e` mai NULL
```

Il RG è comodo in **tutte** le operazioni in cui serve il predecessore: inserimento in coda, inserimento ordinato, eliminazione (anche di più nodi, vedi capitolo 18).

## Inserimento ordinato

Lista ordinata in modo crescente: bisogna trovare il **primo nodo con info ≥ x** e inserire il nuovo nodo **prima** di lui. Per inserire "prima" serve il nodo **precedente**: si scorre con **due puntatori**, `prec` e `corr`.

{{inc liste.c insOrdinato}}

```text
inserisco 6 in   *pl --> [1] --> [5] --> [7] --> [9] --> NULL

scansione:  prec=NULL corr=[1]   1 < 6, avanzo
            prec=[1]  corr=[5]   5 < 6, avanzo
            prec=[5]  corr=[7]   7 >= 6, mi fermo

aggancio:   nuovo->next = corr  ([6] -> [7])
            prec->next  = nuovo ([5] -> [6])

DOPO:       *pl --> [1] --> [5] --> [6] --> [7] --> [9] --> NULL
```

I casi da controllare: lista vuota (`prec` resta `NULL`: nuova testa), x più piccolo di tutti (`prec == NULL`: nuova testa), x più grande di tutti (`corr == NULL`: in coda), x in mezzo.

Per le stringhe la condizione diventa `strcmp(corr->info.nome, nome) < 0`.

## Eliminazione di un elemento

Stessa tecnica dei due puntatori: si cerca il nodo da eliminare **ricordando il precedente**, poi lo si "scavalca" e si libera la memoria.

{{inc liste.c elimina}}

```text
elimino 5 da   *pl --> [1] --> [5] --> [7] --> NULL

prec=[1] corr=[5]          prec->next = corr->next      free(corr)

               *pl --> [1] ----------> [7] --> NULL
                            [5] (liberato)
```

::: errore Errori tipici nelle eliminazioni
- `free(corr)` **prima** di aver collegato `prec->next = corr->next`: dopo la `free` non si può più leggere `corr->next`.
- Dimenticare il caso "elimino il primo nodo": va cambiata la testa (`*pl = corr->next`), quindi il parametro deve essere `TipoLista *`.
- Se il nodo contiene stringhe esatte, liberarle **prima** del nodo: `free(corr->info.nome); free(corr);`. Altrimenti è un memory leak.
:::

## Deallocazione di tutta la lista

{{inc liste.c dealloca}}

Bisogna salvare il nodo da liberare, **avanzare**, e poi liberare: dopo `free` non si può più seguire il suo `next`.

## Funzioni ricorsive sulle liste

Una lista è **vuota** oppure è **un nodo seguito da una lista**. Le funzioni ricorsive seguono tutte lo stesso schema: caso base `l == NULL`, caso ricorsivo che usa `l->info` e chiama la funzione su `l->next`.

{{inc liste.c ricorsive}}

Esecuzione simulata di `contaRic(l, 1)` su `l: 1 -> 4 -> 1 -> NULL`:

```text
RDA contaRic  l=NULL          caso base                      -> 0
RDA contaRic  l=[1]->NULL     info==1:  1 + contaRic(NULL)   -> 1 + 0 = 1
RDA contaRic  l=[4]->...      info!=1:  contaRic([1])        -> 1
RDA contaRic  l=[1]->...      info==1:  1 + contaRic([4])    -> 1 + 1 = 2
RDA main                      riceve 2
```

## Il programma di prova completo

Tutte le funzioni di questo capitolo stanno in `liste.c`, con questo `main` di prova:

{{inc liste.c main}}

Output reale:

```text
3 -> 2 -> 1 -> NULL
3 -> 2 -> 1 -> 10 -> 20 -> NULL
lunghezza: 5 (ricorsiva: 5)
2 -> 1 -> 20 -> NULL
massimo: 20
contrario: 20 1 2
1 -> 1 -> 5 -> 7 -> 9 -> NULL
quanti 1: 2
cerco 7: trovato
dopo dealloca: NULL
```

## Liste di struct (come all'esame)

All'esame l'informazione del nodo non è un `int` ma una **struct** con i dati dell'elemento. Lo schema è sempre questo:

```c
typedef struct {
  char *nome;                  /* stringa di lunghezza ignota: esatta   */
  char codice[9 + 1];          /* stringa di 9 caratteri                */
  int quantita;
  char tipo;
} TipoElemento;

struct nodoElem {
  TipoElemento info;
  struct nodoElem *next;
};

typedef struct nodoElem TipoNodoElem;
typedef TipoNodoElem *TipoListaElem;
```

L'accesso ai campi diventa `p->info.quantita`, `p->info.nome`, `strcmp(p->info.codice, cod)`.

::: esercizio Esercizio 14.1
Scrivi `int sommaPari(TipoLista l)` (somma dei valori pari) in versione iterativa e ricorsiva.
:::

::: soluzione
```c
int sommaPari(TipoLista l) {
  int s = 0;
  for (; l != NULL; l = l->next)
    if (l->info % 2 == 0)
      s += l->info;
  return s;
}

int sommaPariRic(TipoLista l) {
  if (l == NULL)
    return 0;
  if (l->info % 2 == 0)
    return l->info + sommaPariRic(l->next);
  return sommaPariRic(l->next);
}
```
:::

::: esercizio Esercizio 14.2
Scrivi `int eliminaUltimo(TipoLista *pl)` che elimina l'ultimo nodo e restituisce 1, oppure 0 se la lista è vuota.
:::

::: soluzione
```c
int eliminaUltimo(TipoLista *pl) {
  TipoNodo *prec = NULL, *corr = *pl;
  if (corr == NULL)
    return 0;
  while (corr->next != NULL) {     /* mi fermo sull'ultimo */
    prec = corr;
    corr = corr->next;
  }
  if (prec == NULL)                /* c'era un solo nodo   */
    *pl = NULL;
  else
    prec->next = NULL;
  free(corr);
  return 1;
}
```
:::

::: esercizio Esercizio 14.3
Scrivi `TipoLista copiaLista(TipoLista l)` che crea e restituisce una **copia** della lista, con gli elementi nello stesso ordine.
:::

::: soluzione
Versione ricorsiva (la più semplice): la copia di una lista vuota è vuota; altrimenti creo un nodo con la stessa info e gli attacco la copia del resto.
```c
TipoLista copiaLista(TipoLista l) {
  TipoNodo *n;
  if (l == NULL)
    return NULL;
  n = malloc(sizeof(TipoNodo));
  if (n == NULL)
    return NULL;
  n->info = l->info;
  n->next = copiaLista(l->next);
  return n;
}
```
:::

::: esercizio Esercizio 14.4
Scrivi `void invertiLista(TipoLista *pl)` che inverte la lista **senza allocare** nuovi nodi (cambiando solo i `next`).
:::

::: soluzione
```c
void invertiLista(TipoLista *pl) {
  TipoNodo *prec = NULL, *corr = *pl, *succ;
  while (corr != NULL) {
    succ = corr->next;     /* salvo il resto della lista     */
    corr->next = prec;     /* giro la freccia                */
    prec = corr;           /* avanzo i due puntatori         */
    corr = succ;
  }
  *pl = prec;              /* l'ultimo nodo e` la nuova testa */
}
```
:::

::: ricorda Da ricordare
- Lista = puntatore al primo nodo; vuota = **NULL**.
- Per inserire o eliminare in mezzo serve il **predecessore** (`prec`/`corr` o record generatore).
- Prova sempre: lista vuota, primo, ultimo, in mezzo, assente.
:::
