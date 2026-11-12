# Ricerca e ordinamento {#ordinamento}

*(slide lezione 20 e filmati sugli algoritmi di ordinamento; testo1 cap. 11, 12, caso di studio I; testo2 cap. 1-2)*

## Ricerca lineare (sequenziale)

Si scorre l'array dall'inizio finché si trova l'elemento o si arriva in fondo. Funziona **sempre**, anche se l'array non è ordinato. Nel caso peggiore fa **n** confronti.

{{inc basi.c arrayFun}}

## Ricerca binaria (dicotomica)

Funziona **solo su array ordinati**. Si guarda l'elemento **centrale**: se è quello cercato, fatto; se il cercato è più piccolo si continua nella metà sinistra, altrimenti nella destra. A ogni passo **si dimezza** lo spazio di ricerca: al massimo circa **log<sub>2</sub> n** confronti (per n = 1000, circa 10 invece di 1000).

{{inc ricorsione_ordinamento.c ricercaBinaria}}

```text
cerco 37 in  [10 13 14 29 37]
   inizio=0 fine=4  medio=2  v[2]=14 < 37  -> inizio=3
   inizio=3 fine=4  medio=3  v[3]=29 < 37  -> inizio=4
   inizio=4 fine=4  medio=4  v[4]=37       -> trovato, indice 4
```

## Algoritmi di ordinamento

Ordinare = disporre gli elementi in ordine (di solito crescente). Esempio usato qui sotto: `29 10 14 37 13`.

### Selection sort (ordinamento per selezione)

A ogni passo **seleziono il minimo** della parte non ancora ordinata e lo **scambio** con il primo elemento di quella parte.

{{inc ricorsione_ordinamento.c selection}}

```text
29 10 14 37 13    minimo di tutto = 10, scambio con 29
10|29 14 37 13    minimo del resto = 13, scambio con 29
10 13|14 37 29    minimo = 14, gia` al suo posto
10 13 14|37 29    minimo = 29, scambio con 37
10 13 14 29 37    fine
```

### Bubble sort (ordinamento a bolle)

Scorro l'array confrontando **coppie di elementi vicini** e le scambio se sono in ordine sbagliato. Dopo ogni passata il più grande "sale come una bolla" in fondo. Mi fermo quando una passata non fa scambi.

{{inc ricorsione_ordinamento.c bubble}}

```text
passata 1:  29 10 14 37 13 -> 10 29 14 37 13 -> 10 14 29 37 13 -> 10 14 29 37 13 -> 10 14 29 13 37
passata 2:  10 14 29 13|37 -> ... -> 10 14 13 29|37
passata 3:  10 14 13|29 37 -> 10 13 14|29 37
passata 4:  nessuno scambio: fine
```

### Insertion sort (ordinamento per inserimento)

Come quando si ordinano le carte in mano: prendo un elemento alla volta e lo **inserisco al posto giusto** nella parte già ordinata a sinistra, spostando a destra quelli più grandi.

{{inc ricorsione_ordinamento.c insertion}}

```text
29|10 14 37 13    inserisco 10: 10 29
10 29|14 37 13    inserisco 14: 10 14 29
10 14 29|37 13    inserisco 37: resta li`
10 14 29 37|13    inserisco 13: 10 13 14 29 37
```

### Merge sort (cenni)

**Divide et impera**, ricorsivo: divido l'array a metà, ordino ricorsivamente le due metà, poi le **fondo** (*merge*) in un'unica sequenza ordinata, confrontando ogni volta i primi elementi delle due metà.

{{inc ricorsione_ordinamento.c merge}}

## Quanto costano (complessità, cenni)

L'**efficienza** di un algoritmo si misura con il numero di operazioni in funzione della dimensione n dei dati (nel caso peggiore).

| Algoritmo | Caso peggiore | Note |
|---|---|---|
| Ricerca lineare | proporzionale a n | anche su dati non ordinati |
| Ricerca binaria | proporzionale a log n | solo su dati ordinati |
| Selection sort | proporzionale a n² | fa sempre gli stessi confronti |
| Bubble sort | proporzionale a n² | veloce se l'array è quasi ordinato |
| Insertion sort | proporzionale a n² | veloce se l'array è quasi ordinato |
| Merge sort | proporzionale a n log n | serve memoria aggiuntiva |

::: nota I filmati della lezione 20
A lezione sono stati proposti quattro filmati (SORTING-ALG_A ... D) in cui persone "eseguono" gli algoritmi: guardali e prova a riconoscere l'algoritmo, poi controlla con le soluzioni sul sito. Un indizio: nel selection si cerca sempre il minimo e lo si scambia; nel bubble si confrontano solo vicini; nell'insertion si fa "scorrere" un elemento a sinistra.
:::

::: esercizio Esercizio 12.1
Applica a mano selection sort, bubble sort e insertion sort all'array `5 1 4 2 8`, scrivendo l'array dopo ogni passo.
:::

::: soluzione
**Selection**: `1|5 4 2 8` → `1 2|4 5 8` → `1 2 4|5 8` → `1 2 4 5|8`.

**Bubble**: passata 1: `1 5 4 2 8` → `1 4 5 2 8` → `1 4 2 5 8` → (5 e 8 ok) `1 4 2 5 8`; passata 2: `1 2 4 5 8`; passata 3: nessuno scambio, fine.

**Insertion**: inserisco 1 → `1 5|4 2 8`; inserisco 4 → `1 4 5|2 8`; inserisco 2 → `1 2 4 5|8`; inserisco 8 → `1 2 4 5 8`.
:::

::: esercizio Esercizio 12.2
Adatta il selection sort per ordinare la tabella dei voli (capitolo 10) per **codice** crescente.
:::

::: soluzione
```c
void ordinaPerCodice(TipoTabella *t) {
  int i, j, iMin;
  TipoVolo tmp;
  for (i = 0; i < t->quantiVoli - 1; i++) {
    iMin = i;
    for (j = i + 1; j < t->quantiVoli; j++)
      if (strcmp(t->arrayVoli[j].codice, t->arrayVoli[iMin].codice) < 0)
        iMin = j;
    tmp = t->arrayVoli[i];                 /* le struct si assegnano con = */
    t->arrayVoli[i] = t->arrayVoli[iMin];
    t->arrayVoli[iMin] = tmp;
  }
}
```
:::
