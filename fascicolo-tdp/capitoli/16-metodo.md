# Il metodo per lo scritto {#metodo}

::: obiettivi Cosa imparerai
- come gestire le 2h30 dello scritto
- come impostare tipi, eser1, eser2 ed esercizio 3
- la checklist degli errori da controllare prima di consegnare
:::

Qui metto insieme tutto in una procedura da seguire in aula. Leggila prima di ogni traccia di esercitazione, finché non diventa automatica.

## Gestione del tempo (2 ore e 30)

| Tempo | Cosa fare |
|---|---|
| 0-10 min | Leggere **tutto** il testo. Sottolineare: campi e loro tipi, cosa riceve e cosa restituisce ogni funzione, se la lista è ordinata. |
| 10-25 min | **Tipi** (esercizio 1, prima parte). Sono la base di tutto: se sono sbagliati, sono sbagliati anche gli esercizi 1 e 2. |
| 25-60 min | `eser1` |
| 60-100 min | `eser2` |
| 100-135 min | Esercizio 3 |
| 135-150 min | **Rilettura**: punti e virgola, `*` nei parametri di output, `NULL`, `free`, `strcmp`. |

## Esercizio 1, prima parte: i tipi

Per ogni dato del testo scegli il tipo:

| Il testo dice... | In C |
|---|---|
| "stringa di lunghezza non nota a priori / non prefissata" | `char *campo;` (stringa **esatta**, allocata con `malloc`) |
| "stringa di k caratteri" | `char campo[k + 1];` (+1 per il `'\0'`) |
| "un carattere (R o A...)" | `char campo;` |
| "un intero", "numero di...", "anni" | `int campo;` |
| "prezzo", "costo", "media reale" | `double campo;` |
| "data", "ora" | una piccola struct (`struct data { int g, m, a; };`) |

Poi lo schema fisso (adatta i nomi al testo):

```c
#define LUNGCOD 9

typedef struct {
  /* ...i campi... */
} TipoElemento;

struct nodoElemento {
  TipoElemento info;
  struct nodoElemento *next;
};

typedef struct nodoElemento TipoNodoElemento;
typedef TipoNodoElemento *TipoLista;   /* usa il nome chiesto dal testo! */
```

Aggiungi un commento per ogni campo con il significato: mostra che hai capito il testo.

## Esercizio 1, seconda parte: la funzione eser1

1. **Intestazione**. "Restituisca A, B e C": scegli **uno** dei risultati per il `return` (di solito il puntatore o il conteggio) e gli **altri come parametri puntatore**. "Ricevendo (almeno) una lista e un valore": i parametri sono la lista (**`TipoLista`**, perché la funzione legge soltanto) e il valore.
2. **Inizializza** subito i parametri di output (`*conta = 0;`).
3. **Scansione** con lo schema `for (p = l; p != NULL; p = p->next)`.
4. Dentro: contatori `(*conta)++`, accumulatori, confronti con `strcmp`, ricerca del massimo (il candidato parte dal **primo nodo**, non da 0).
5. **Dopo il ciclo**: le medie (attenzione alla divisione per zero e alla divisione intera), il `return`.
6. Gestisci la **lista vuota** (restituisci `NULL` o 0 e dillo in un commento).

## Esercizio 2: modificare la lista

1. Il parametro è **`TipoLista *pl`** se la testa può cambiare (quasi sempre).
2. Per inserire o eliminare in mezzo serve il **predecessore**: due puntatori `prec`/`corr`, oppure il **record generatore**.
3. Considera **sempre** questi casi e prova mentalmente il codice su ciascuno:
   - lista **vuota**;
   - l'elemento interessato è il **primo**;
   - è l'**ultimo**;
   - è **in mezzo**;
   - (per le ricerche) **non c'è**.
4. **Inserimento**: `malloc` del nodo (controlla `NULL`), `malloc` + `strcpy` delle stringhe esatte, riempimento di tutti i campi, aggancio (`nuovo->next = corr; prec->next = nuovo;` oppure nuova testa).
5. **Eliminazione**: scavalca (`prec->next = corr->next;` oppure `*pl = corr->next;`), poi `free` delle stringhe esatte, poi `free` del nodo.
6. Restituisci un esito (1 = fatto, 0 = non fatto) anche se il testo non lo chiede: è robustezza.

## Esercizio 3

- **Test (scatola nera / trasparente)**: segui lo schema del capitolo 13 (descrizione del metodo, tabella dei test motivati con dati concreti, esecuzione simulata).
- **Floating point**: i 5 passi del capitolo 2, mostrando **tutti** i calcoli (divisioni, moltiplicazioni, normalizzazione, eccesso 127) e una verifica finale.
- **Funzione ricorsiva con RDA**: caso base + caso ricorsivo, poi la pila delle RDA su un esempio concreto (capitolo 11), con l'andata e il ritorno dei valori.
- **Visite di albero**: definizione delle tre visite, codice, esempio su un albero di almeno 9 nodi, sequenze prodotte, RDA (capitolo 15).

## Checklist finale (rileggi così)

::: errore Gli errori che costano più punti
- [ ] Stringhe confrontate con `==` invece di `strcmp(...) == 0`, o copiate con `=` invece di `strcpy`.
- [ ] `malloc(strlen(s))` senza il **+1** per il `'\0'`.
- [ ] Parametro di output usato senza `*` (`conta++` invece di `(*conta)++`).
- [ ] Funzione che cambia la testa ma riceve `TipoLista` invece di `TipoLista *`.
- [ ] `p->next` usato quando `p` può essere `NULL` (ordine delle condizioni nei `while`).
- [ ] `free(nodo)` prima di aver salvato o collegato `nodo->next`.
- [ ] Stringa esatta non liberata prima del nodo.
- [ ] Massimo inizializzato a 0 invece che al primo elemento.
- [ ] Media calcolata con divisione intera quando il testo vuole un reale (o viceversa) e divisione per zero.
- [ ] Lista vuota non gestita.
- [ ] Variabili non inizializzate (contatori, `TipoLista l = NULL`).
:::

::: nota Scrivere bene conta
Il codice su carta viene letto da una persona: indenta, usa nomi chiari (`prec`, `corr`, `nuovo`), scrivi due righe di commento con l'algoritmo prima del codice. Se non ricordi il nome di una funzione di libreria, scrivi un commento che dica cosa fa: è meglio di un'invenzione.
:::

::: ricorda Da ricordare
- Prima i **tipi**, poi eser1, eser2, esercizio 3, infine la **rilettura**.
- Più risultati: uno col `return`, gli altri con **parametri puntatore**.
- Rileggi con la checklist: `strcmp`, `+1`, `*`, `NULL`, `free`.
:::
