# Tracce di esercitazione (nuove, stile esame) {#esercitazione}

Le ho scritte sul modello delle tracce del professore. **Usale come simulazione d'esame**: carta e penna, 2 ore e 30, niente fascicolo aperto. Poi correggi con le soluzioni e prova il codice al computer.

## Traccia A: "Biblioteca di quartiere"

::: esercizio Testo
**Esercizio 1** (0-13 punti). Una biblioteca di quartiere tiene il catalogo dei libri. Ogni libro ha: **titolo** (stringa di lunghezza non nota a priori); **ISBN** (stringa di 13 caratteri); **anno** di pubblicazione (intero); **copie** disponibili (intero); **genere** (carattere: R romanzo, S saggio, F fumetto).
Definire i tipi per rappresentare il catalogo come lista (record e puntatori). Scrivere `eser1` che, ricevendo (almeno) il catalogo e un anno, restituisca il **puntatore al libro più vecchio**, il **numero di libri pubblicati prima di quell'anno** e il **totale delle copie disponibili**.

**Esercizio 2** (10 punti). Scrivere `eser2` che **elimini dal catalogo tutti i libri con zero copie disponibili** e restituisca quanti libri ha eliminato.

**Esercizio 3** (da -1 a 7 punti). Rappresentare in floating point su 32 bit il numero **-45.625**, descrivendo tutti i passaggi. Poi rappresentare in complemento a due con il minimo numero di bit **-300** e **125**, e calcolarne la somma su 16 bit.
:::

::: soluzione
**Tipi**

{{inc biblioteca.c tipi}}

**eser1**

{{inc biblioteca.c eser1}}

**eser2**: eliminare **più** nodi è più delicato che eliminarne uno. Con il record generatore ogni nodo ha un predecessore; quando elimino `prec->next` **non avanzo** `prec`, perché il nuovo `prec->next` deve ancora essere controllato (potrebbero esserci due libri da eliminare consecutivi).

{{inc biblioteca.c eser2}}

Prova (`biblioteca.c`): con 5 libri, di cui 3 con zero copie (in testa, in mezzo e in coda), `eser2` restituisce 3 e restano i 2 libri con copie.

**Esercizio 3**

*Floating point di -45.625*: segno negativo, s = 1. 45 = `101101` (32+8+4+1); 0.625: 0.625×2 = 1.25 → 1; 0.25×2 = 0.5 → 0; 0.5×2 = 1.0 → 1; quindi `.101`. Numero: `101101.101` = `1.01101101` × 2<sup>5</sup>. E = 5 + 127 = 132 = `10000100`. M = `01101101` + 15 zeri.

```text
-45.625 = 1 10000100 01101101000000000000000
```
Verifica: 1.01101101 × 2<sup>5</sup> = 101101.101 = 45.625, col segno meno. La rappresentazione è **esatta** (la parte frazionaria finisce).

*Complemento a due*: -300 sta in [-512, 511], quindi servono **10 bit**: 300 = `0100101100`, invertito `1011010011`, +1 = `1011010100`. 125 sta in [-128, 127]: **8 bit**, `01111101`.
Somma su 16 bit (estensione del segno): `1111111011010100` + `0000000001111101` = `1111111101010001`, che è -175 (2<sup>16</sup> - 175 = 65361 = `1111111101010001`). Ok.
:::

## Traccia B: "Officina"

::: esercizio Testo
**Esercizio 1** (0-13 punti). Un'officina registra le riparazioni. Ogni riparazione ha: **targa** (stringa di 7 caratteri); **descrizione** del lavoro (stringa di lunghezza non nota a priori); **costo** (reale); **ore** di lavoro (intero); **stato** (carattere: A aperta, C chiusa).
Definire i tipi per una lista di riparazioni. Scrivere `eser1` che, ricevendo (almeno) la lista, restituisca il **numero di riparazioni aperte**, il **costo totale** delle riparazioni aperte e la **media (reale) delle ore** delle riparazioni aperte.

**Esercizio 2** (10 punti). Scrivere `eser2` che, ricevendo la lista e i dati di una nuova riparazione (targa, descrizione, costo, ore), la **aggiunga in coda** come riparazione aperta, **ma solo se** per quella targa non c'è già una riparazione aperta. Restituire 1 se aggiunta, 0 se già presente.

**Esercizio 3** (da -1 a 7 punti). Scrivere una funzione **ricorsiva** `eser3` che restituisca il costo totale di tutte le riparazioni (aperte e chiuse) di una targa data. Mostrare un'esecuzione simulata con i record di attivazione su una lista di almeno 4 riparazioni.
:::

::: soluzione
**Tipi**

{{inc officina.c tipi}}

**eser1**: un risultato col `return`, due come parametri di output. Media **reale**: serve il cast.

{{inc officina.c eser1}}

**eser2**: con il record generatore si scorre fino all'ultimo nodo e, **nello stesso ciclo**, si controlla se la targa ha già una riparazione aperta. Il controllo va fatto **prima** di allocare, così in caso di duplicato non c'è niente da liberare.

{{inc officina.c eser2}}

**eser3**

{{inc officina.c eser3}}

Esecuzione simulata: lista `[AB123CD 120.0 C] -> [EF456GH 300.0 A] -> [AB123CD 250.0 A] -> [IL789MN 800.0 A] -> NULL`, chiamata `t = eser3(l, "AB123CD");`

```text
RDA 5: l = NULL                    caso base                 -> 0
RDA 4: l = [IL789MN 800]           targa diversa: eser3(NULL) -> 0
RDA 3: l = [AB123CD 250]           uguale: 250 + eser3(...)  -> 250 + 0   = 250
RDA 2: l = [EF456GH 300]           diversa: eser3(...)       -> 250
RDA 1: l = [AB123CD 120]           uguale: 120 + eser3(...)  -> 120 + 250 = 370
RDA main: t = 370
```

Il programma di prova `officina.c` stampa infatti `totale AB123CD: 370.00`.
:::

## Esercizi brevi in più, sulle liste

::: esercizio Esercizio 18.1
Lista di interi. Scrivi `int eliminaTutti(TipoLista *pl, int x)` che elimina **tutte** le occorrenze di x e restituisce quante ne ha eliminate (senza record generatore, gestendo la testa a parte).
:::

::: soluzione
```c
int eliminaTutti(TipoLista *pl, int x) {
  TipoNodo *corr, *prec, *d;
  int n = 0;
  while (*pl != NULL && (*pl)->info == x) {   /* 1. elimino in testa finche' serve */
    d = *pl;
    *pl = d->next;
    free(d);
    n++;
  }
  if (*pl == NULL)
    return n;
  prec = *pl;                                 /* 2. ora la testa e` sicuramente != x */
  corr = prec->next;
  while (corr != NULL)
    if (corr->info == x) {
      prec->next = corr->next;
      free(corr);
      corr = prec->next;                      /* prec NON avanza */
      n++;
    } else {
      prec = corr;
      corr = corr->next;
    }
  return n;
}
```
:::

::: esercizio Esercizio 18.2
Scrivi `int inserisciDopo(TipoLista l, int dopo, int x)` che inserisce un nodo con x **subito dopo** il primo nodo che contiene `dopo`. Restituisce 0 se `dopo` non c'è. Perché qui basta `TipoLista` e non `TipoLista *`?
:::

::: soluzione
```c
int inserisciDopo(TipoLista l, int dopo, int x) {
  TipoNodo *p = l, *nuovo;
  while (p != NULL && p->info != dopo)
    p = p->next;
  if (p == NULL)
    return 0;
  nuovo = malloc(sizeof(TipoNodo));
  if (nuovo == NULL)
    return 0;
  nuovo->info = x;
  nuovo->next = p->next;
  p->next = nuovo;
  return 1;
}
```
Basta `TipoLista` perché la testa **non cambia mai**: il nuovo nodo va sempre dopo un nodo esistente. Si modificano i nodi (che sono nello heap, condivisi), non il puntatore di testa del chiamante.
:::

::: esercizio Esercizio 18.3
Due liste di interi ordinate in modo crescente. Scrivi `TipoLista fondiListe(TipoLista a, TipoLista b)` che crea una **nuova** lista ordinata con tutti gli elementi delle due (le liste originali restano intatte).
:::

::: soluzione
Uso il record generatore e un puntatore `coda` all'ultimo nodo della lista risultato, così ogni inserimento in coda costa un solo passo.
```c
TipoLista fondiListe(TipoLista a, TipoLista b) {
  TipoNodo rg, *coda = &rg, *n;
  int x;
  rg.next = NULL;
  while (a != NULL || b != NULL) {
    if (b == NULL || (a != NULL && a->info <= b->info)) {
      x = a->info;
      a = a->next;
    } else {
      x = b->info;
      b = b->next;
    }
    n = malloc(sizeof(TipoNodo));
    if (n == NULL)
      break;                    /* memoria finita: restituisco quanto fatto */
    n->info = x;
    n->next = NULL;
    coda->next = n;
    coda = n;
  }
  return rg.next;
}
```
:::

::: esercizio Esercizio 18.4 (ricorsione + stringhe)
Lista di struct con un campo `char *nome` (stringa esatta). Scrivi una funzione **ricorsiva** `TipoNodoElem *cercaNome(TipoListaElem l, char *nome)` che restituisce il puntatore al nodo con quel nome, o `NULL`.
:::

::: soluzione
```c
TipoNodoElem *cercaNome(TipoListaElem l, char *nome) {
  if (l == NULL)
    return NULL;                               /* non trovato   */
  if (strcmp(l->info.nome, nome) == 0)
    return l;                                  /* trovato       */
  return cercaNome(l->next, nome);             /* cerca nel resto */
}
```
:::
