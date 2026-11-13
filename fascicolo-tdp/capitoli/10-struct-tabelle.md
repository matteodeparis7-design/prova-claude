# Struct, typedef e tabelle {#struct}

*(slide lezioni 18 e 19, EG6 e EG9; testo1 cap. 20; testo2 cap. 1-2)*

::: obiettivi Cosa imparerai
- raggruppare dati diversi in una struct e usare typedef
- accedere ai campi con `.` e con `->`
- realizzare una tabella con chiave di ricerca e le sue operazioni
:::

## Struct: il record

Un **array** raccoglie dati **dello stesso tipo**. Una **struct** (record) raccoglie dati di **tipi diversi** che descrivono **una cosa sola**. Ogni componente si chiama **campo**.

```c
struct ora {
  int ore, minuti;
};

struct volo {
  char codice[6];              /* 5 caratteri + '\0': lunghezza fissa  */
  char *destinazione;          /* stringa esatta: lunghezza ignota     */
  struct ora oraPartenza;      /* struct dentro una struct             */
  int postiLiberi;
};
```

Accesso ai campi con il **punto**:

```c
struct volo v;
strcpy(v.codice, "AZ123");
v.oraPartenza.ore = 10;
v.oraPartenza.minuti = 35;
v.postiLiberi = 120;
```

A differenza degli array, le struct **si possono assegnare** con `=` (si copiano tutti i campi) e **passare/restituire per valore**. Non si possono però confrontare con `==`.

::: nota Copia di una struct con un puntatore dentro
Se `a` e `b` sono `struct volo`, `b = a;` copia il **puntatore** `destinazione`, non la stringa: dopo l'assegnamento `a.destinazione` e `b.destinazione` puntano alla **stessa** stringa. Se poi fai `free` di una delle due, l'altra resta con un puntatore non valido.
:::

## typedef: dare un nome ai tipi

`typedef tipo_esistente NuovoNome;` crea un **sinonimo** di tipo. Il corso lo usa sempre, con nomi che iniziano per `Tipo`:

```c
typedef struct volo TipoVolo;

typedef struct {               /* struct "anonima" con nome dato dal typedef */
  double x, y;
  char colore;
} TipoPunto;
```

## Struct e funzioni

{{inc basi.c struct}}

- **Per valore** (`TipoPunto p`): la funzione riceve una **copia**. Va bene per leggere i dati.
- **Per indirizzo** (`TipoPunto *pp`): la funzione può **modificare** l'originale. Si accede ai campi con la **freccia**: `pp->x` equivale a `(*pp).x` (le parentesi servono perché il punto ha precedenza sull'asterisco).

## Tabelle: array di struct

Una **tabella** è una struttura dati che rappresenta un **archivio** del mondo reale: una collezione di elementi dello stesso tipo (record). Le operazioni tipiche sono:

- **aggiunta** di un elemento;
- **eliminazione** di un elemento;
- **modifica** dei dati di un elemento;
- **ricerca** di un elemento tramite la sua **chiave**.

La **chiave di ricerca** è il campo che identifica un elemento in modo univoco (codice del volo, matricola, codice fiscale).

### La tabella dei voli (EG9)

Realizzazione con array parzialmente riempito: un **sostegno** di `MAXVOLI` elementi e un contatore.

```c
#define MAXVOLI 10

typedef struct {
  TipoVolo arrayVoli[MAXVOLI];   /* sostegno di memoria                  */
  int quantiVoli;                /* quanti voli sono davvero in tabella  */
} TipoTabella;
```

I voli presenti sono sempre i primi `quantiVoli`; ogni scansione va da 0 a `quantiVoli - 1`.

**Ricerca** per chiave (restituisce l'indice, o -1):

```c
int indiceVolo(TipoTabella t, char cod[]) {
  int trovato = 0, i = 0;
  while (!trovato && i < t.quantiVoli)
    if (strcmp(t.arrayVoli[i].codice, cod) == 0)
      trovato = 1;
    else
      i++;
  if (trovato)
    return i;
  return -1;
}
```

**Aggiunta** (la tabella cambia: si passa per indirizzo):

```c
int aggiungiVolo(TipoTabella *t, TipoVolo v) {
  if (t->quantiVoli == MAXVOLI)          /* tabella piena                 */
    return 0;
  if (indiceVolo(*t, v.codice) != -1)    /* chiave gia` presente          */
    return 0;
  t->arrayVoli[t->quantiVoli] = v;       /* nel primo posto libero        */
  t->quantiVoli++;
  return 1;
}
```

**Eliminazione**: si cerca l'indice k; si può spostare indietro di un posto tutti gli elementi dopo k, oppure (se l'ordine non conta) mettere l'**ultimo** al posto di k. Si libera la stringa esatta dell'eliminato.

```c
int eliminaVolo(TipoTabella *t, char cod[]) {
  int k = indiceVolo(*t, cod);
  if (k == -1)
    return 0;
  free(t->arrayVoli[k].destinazione);                     /* stringa esatta */
  t->arrayVoli[k] = t->arrayVoli[t->quantiVoli - 1];      /* l'ultimo al suo posto */
  t->quantiVoli--;
  return 1;
}
```

::: nota Limiti della tabella con array (e perché arrivano le liste)
Con l'array il numero massimo di elementi è fissato (`MAXVOLI`): o si spreca memoria o si rischia di riempirla. Con un **array dinamico** e `realloc` si può farla crescere (`voli6.c`), ma ogni ingrandimento copia tutto. Inserire o togliere in mezzo richiede di **spostare** molti elementi. La **lista collegata** (capitolo 14) risolve questi problemi: cresce un nodo alla volta e si inserisce o elimina **senza spostare nulla**. Per questo all'esame la "tabella" va sempre realizzata come **lista**.
:::

## Tipi di dato astratti (ADT)

Un **tipo di dato astratto** si definisce dicendo **che cosa** si può fare con i dati (le operazioni e il loro significato), **senza dire come** sono memorizzati. Esempio: l'ADT *Tabella* ha le operazioni aggiungi, elimina, cerca, modifica. Poi si sceglie una **rappresentazione concreta**: array di struct, array dinamico, lista collegata... Il resto del programma usa solo le funzioni, quindi si può cambiare la rappresentazione senza riscrivere tutto.

L'ADT **Lista** è una sequenza di elementi con operazioni come: crea lista vuota, è vuota?, inserisci in testa/in coda/in ordine, elimina, cerca, lunghezza. Si può rappresentare con un array (cenni a lezione) o con **struct e puntatori** (la rappresentazione che usiamo).

::: esame All'orale
"Che cos'è una tabella e quali operazioni ha?" "Che cos'è una chiave?" "Che differenza c'è tra tipo astratto e rappresentazione concreta?" "Quali sono i limiti di una tabella realizzata con array?"
:::

::: esercizio Esercizio 10.1
Usando `TipoTabella` dei voli, scrivi `int prenota(TipoTabella *t, char cod[], int k)` che prenota k posti sul volo indicato se ci sono abbastanza posti liberi. Restituisce 1 se riesce, 0 altrimenti.
:::

::: soluzione
```c
int prenota(TipoTabella *t, char cod[], int k) {
  int i = indiceVolo(*t, cod);
  if (i == -1 || t->arrayVoli[i].postiLiberi < k)
    return 0;
  t->arrayVoli[i].postiLiberi -= k;
  return 1;
}
```
:::

::: ricorda Da ricordare
- `p->campo` equivale a `(*p).campo`.
- Una struct si passa **per indirizzo** se va modificata.
- Tabella: aggiungi, elimina, modifica, cerca per **chiave**; con l'array ha limiti che la lista supera.
:::
