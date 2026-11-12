# Alberi binari (cenni) {#alberi}

*(slide e EG di fine corso; testo2 cap. 8, "limitatamente a quanto visto a lezione")*

Il programma prevede gli alberi come **cenni**. Nei testi d'esame per gli immatricolati dal 2025/26 non compaiono, ma in quelli degli anni precedenti sì (esercizi 2 e 3 della traccia "Giovani Marmotte"). Sappi almeno: definizione, tipi in C, visite ricorsive, funzioni ricorsive semplici.

## Definizione

Un **albero binario** è **vuoto**, oppure è formato da un nodo **radice** con due sottoalberi binari: il **sinistro** e il **destro**. È una definizione **ricorsiva**, come quella della lista.

```text
                 50              <- radice
               /    \
             30      70
            /  \    /  \
          20   40  60   80
              /      \
            35        65         <- foglie: 20, 35, 65, 80
```

Termini: **radice** (il nodo in cima), **figli** e **padre**, **foglia** (nodo senza figli), **altezza** (lunghezza del cammino più lungo dalla radice a una foglia: qui 3).

## I tipi in C

{{inc alberi.c tipi}}

## Le tre visite (in profondità)

**Visitare** un albero significa esaminare tutti i suoi nodi. Le tre visite ricorsive differiscono solo per **quando** si esamina la radice:

- **preordine** (anticipata): radice, poi sottoalbero sinistro, poi destro;
- **inordine** (simmetrica): sinistro, radice, destro;
- **postordine** (posticipata): sinistro, destro, radice.

{{inc alberi.c visite}}

Sull'albero disegnato sopra:

```text
preordine:  50 30 20 40 35 70 60 65 80
inordine:   20 30 35 40 50 60 65 70 80     <- ordinato! (e` un ABR)
postordine: 20 35 40 30 65 60 80 70 50
```

### Esecuzione simulata di una visita (con RDA)

`inordine` sul sottoalbero `30` (figli `20` e `40`, con `40` che ha il figlio sinistro `35`):

```text
inordine(30)
 +- inordine(20)
 |   +- inordine(NULL)  -> ritorna subito
 |   +- stampa 20
 |   +- inordine(NULL)  -> ritorna subito
 +- stampa 30
 +- inordine(40)
     +- inordine(35)
     |   +- inordine(NULL); stampa 35; inordine(NULL)
     +- stampa 40
     +- inordine(NULL)
stampato: 20 30 35 40
```

La pila delle RDA, nel momento in cui si stampa 35, contiene (dal basso): `main`, `inordine(50)`, `inordine(30)`, `inordine(40)`, `inordine(35)`.

## Funzioni ricorsive sugli alberi

Schema: caso base `a == NULL`; caso ricorsivo che combina la radice con i risultati sui due sottoalberi.

{{inc alberi.c funzioni}}

## Albero binario di ricerca (ABR)

Un **ABR** è un albero binario in cui, per ogni nodo, **tutti** i valori nel sottoalbero sinistro sono **minori** della sua info e quelli nel destro sono **maggiori o uguali**. Conseguenze: la **visita inordine dà i valori ordinati**; la **ricerca** scende a sinistra o a destra, come la ricerca binaria (su un albero bilanciato circa log<sub>2</sub> n passi).

{{inc alberi.c abr}}

Per **inserire** si passa `TipoAlbero *` perché, nel caso base, bisogna scrivere il nuovo nodo nel puntatore (radice o campo `sinistro`/`destro` del padre).

{{inc alberi.c dealloca}}

La deallocazione si fa in **postordine**: prima i figli, poi il nodo (dopo `free` non si potrebbero più raggiungere i figli).

::: esercizio Esercizio 15.1
Scrivi `int contaMaggiori(TipoAlbero a, int x)` che conta i nodi con info > x (albero binario qualsiasi), e `int massimoABR(TipoAlbero a)` che restituisce il massimo di un ABR non vuoto.
:::

::: soluzione
```c
int contaMaggiori(TipoAlbero a, int x) {
  if (a == NULL)
    return 0;
  return (a->info > x) + contaMaggiori(a->sinistro, x)
                       + contaMaggiori(a->destro, x);
}

int massimoABR(TipoAlbero a) {   /* in un ABR il massimo e` il nodo piu` a destra */
  while (a->destro != NULL)
    a = a->destro;
  return a->info;
}
```
`(a->info > x)` vale 1 o 0: un modo compatto per contare.
:::
