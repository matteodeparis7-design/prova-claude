# Istruzioni di controllo {#controllo}

*(slide lezioni 4-6, EG1-EG3; testo1 cap. 4, 5, 7, 9)*

::: obiettivi Cosa imparerai
- usare if, switch, while, do-while e for
- progettare un ciclo (INIT, CHECK, USE, ADVANCE) che termina
- gli schemi fondamentali: contatore, accumulatore, massimo, sentinella, flag
:::

## Selezione: if / else

```c
if (voto >= 18)
  printf("promosso\n");
else
  printf("respinto\n");
```

Se in un ramo ci sono più istruzioni servono le graffe `{ }`. Con più casi si fanno catene `else if`:

```c
if (temp < 0)
  printf("gelo\n");
else if (temp < 20)
  printf("fresco\n");
else
  printf("caldo\n");
```

::: errore L'else "ambiguo" (dangling else)
Un `else` si attacca sempre all'**`if` più vicino** senza `else`, qualunque sia l'indentazione:

```c
if (a > 0)
  if (b > 0)
    printf("entrambi positivi\n");
else                       /* appartiene a  if (b > 0) , NON a  if (a > 0) */
  printf("a non positivo?\n");
```

Per attaccarlo al primo `if` servono le graffe: `if (a > 0) { if (b > 0) ... } else ...`. È un esercizio delle EG (`ambiguif.c`).
:::

## Selezione multipla: switch

```c
switch (scelta) {              /* scelta deve essere int o char      */
  case 1:
    stampaTabella(t);
    break;                     /* senza break si "cade" nel case dopo */
  case 2:
  case 3:                      /* 2 e 3 fanno la stessa cosa          */
    aggiungi(&t);
    break;
  default:                     /* tutti gli altri valori              */
    printf("opzione sbagliata\n");
}
```

Lo `switch` è tipico dei **menu** (vedi il programma dei voli nelle EG).

## Iterazione: while, do-while, for

```c
/* while: controlla PRIMA; il corpo puo` non essere mai eseguito */
while (condizione) {
  ...
}

/* do-while: controlla DOPO; il corpo e` eseguito ALMENO una volta */
do {
  printf("numero positivo? ");
  scanf("%d", &n);
} while (n <= 0);

/* for: comodo quando si conosce il numero di ripetizioni */
for (i = 0; i < n; i++) {
  ...
}
```

Il `for (inizializzazione; condizione; aggiornamento)` equivale a:

```c
inizializzazione;
while (condizione) {
  corpo;
  aggiornamento;
}
```

`break` esce subito dal ciclo; `continue` salta al prossimo giro. Usali poco: rendono i cicli più difficili da leggere.

## Come si progetta un ciclo: INIT, CHECK, USE, ADVANCE

Nelle slide della lezione 6 ogni ciclo si costruisce rispondendo a quattro domande:

| Parte | Domanda | Esempio: sommare i numeri da 1 a n |
|---|---|---|
| **INIT** (inizializzazione) | Che valori devono avere le variabili **prima** del ciclo? | `i = 1; somma = 0;` |
| **CHECK** (condizione) | Quando devo **ripetere**? (e quindi quando smetto?) | `i <= n` |
| **USE** (corpo) | Che lavoro faccio a ogni giro? | `somma = somma + i;` |
| **ADVANCE** (avanzamento) | Come mi **avvicino alla fine**? | `i = i + 1;` |

```c
i = 1;  somma = 0;            /* INIT    */
while (i <= n) {              /* CHECK   */
  somma = somma + i;          /* USE     */
  i = i + 1;                  /* ADVANCE */
}
```

Nel `for` le quattro parti sono tutte visibili: `for (INIT; CHECK; ADVANCE) USE`.

### Terminazione

Un ciclo deve **terminare**: l'ADVANCE deve far diventare prima o poi falsa la condizione. Se nel corpo nessuna istruzione modifica le variabili della condizione, il ciclo è **infinito**:

```c
i = 1;
while (i <= 10)
  printf("%d\n", i);          /* manca i++ : ciclo infinito */
```

Altro caso classico: `while (x != 0) x = x - 2;` termina solo se x parte pari e positivo. Quando scrivi un ciclo chiediti sempre: **"perché sono sicuro che finisce?"**. Nell'esempio del MCD del capitolo 3 la risposta è: ris scende di 1 a ogni giro e quando arriva a 1 la condizione è sicuramente falsa (1 divide tutto).

### Variabili contatore e variabili "flag"

- Una variabile **contatore** conta le iterazioni (o gli eventi) e spesso decide quando fermarsi (`for (i = 0; i < 5; i++)` per ripetere 5 volte).
- Una variabile **flag** ("bandiera", detta anche sentinella) vale 0 finché non accade un evento, poi viene "alzata" a 1; la condizione del ciclo la controlla (`while (!trovato && ...)`). Serve per **fermarsi appena** si trova quello che si cerca.

## Gli schemi di ciclo da sapere a memoria

Quasi tutti gli esercizi sono combinazioni di questi schemi. All'esame, sulle liste, li userai identici.

**Contatore**: quanti elementi soddisfano una condizione.

```c
conta = 0;
for (i = 0; i < n; i++)
  if (v[i] > soglia)
    conta++;
```

**Accumulatore**: somma (o prodotto) di valori.

```c
somma = 0;                     /* per un prodotto: prod = 1 */
for (i = 0; i < n; i++)
  somma += v[i];
media = (double) somma / n;    /* attenzione: n > 0 ! */
```

**Massimo / minimo**: si parte dal **primo elemento**, non da 0 (se tutti i valori fossero negativi, 0 sarebbe sbagliato).

```c
max = v[0];
for (i = 1; i < n; i++)
  if (v[i] > max)
    max = v[i];
```

**Sentinella**: si leggono dati finché arriva un valore speciale.

```c
scanf("%d", &x);
while (x != 0) {               /* 0 = sentinella: fine dei dati */
  ...elabora x...
  scanf("%d", &x);             /* lettura del prossimo */
}
```

**Ricerca con variabile flag** (stile del corso): ci si ferma appena si trova.

```c
trovato = 0;
i = 0;
while (!trovato && i < n)
  if (v[i] == x)
    trovato = 1;
  else
    i++;
/* qui: se trovato, i e` la posizione */
```

## Esecuzione simulata

All'esame e all'orale ti può essere chiesto di "eseguire a mano" un programma. Si fa una **tabella**: una colonna per variabile, una riga per ogni passo in cui qualcosa cambia.

```c
int i, s = 0;
for (i = 1; i <= 4; i++)
  if (i % 2 == 0)
    s = s + i;
printf("%d\n", s);
```

| passo | i | i % 2 == 0 ? | s |
|---|---|---|---|
| inizio | - | - | 0 |
| 1 | 1 | no | 0 |
| 2 | 2 | sì | 2 |
| 3 | 3 | no | 2 |
| 4 | 4 | sì | 6 |
| fine | 5 (esce) | - | 6 → stampa **6** |

::: esercizio Esercizio 4.1
Scrivi un programma che legge una sequenza di interi terminata da 0 e stampa quanti sono positivi, quanti negativi e la media dei positivi (con due decimali).
:::

::: soluzione
```c
#include <stdio.h>

int main(void) {
  int x, pos = 0, neg = 0, sommaPos = 0;

  printf("numero (0 per finire): ");
  scanf("%d", &x);
  while (x != 0) {
    if (x > 0) {
      pos++;
      sommaPos += x;
    } else
      neg++;
    printf("numero (0 per finire): ");
    scanf("%d", &x);
  }
  printf("positivi %d, negativi %d\n", pos, neg);
  if (pos > 0)
    printf("media positivi %.2f\n", (double) sommaPos / pos);
  return 0;
}
```
Nota il controllo `pos > 0` prima della divisione e il cast a `double`.
:::

::: esercizio Esercizio 4.2
Scrivi un ciclo che stampa i numeri primi minori di 100 (come `primiCento.c` delle EG).
:::

::: soluzione
```c
int n, d, primo;
for (n = 2; n < 100; n++) {
  primo = 1;                          /* flag: suppongo che sia primo */
  for (d = 2; d * d <= n && primo; d++)
    if (n % d == 0)
      primo = 0;                      /* trovato un divisore          */
  if (primo)
    printf("%d ", n);
}
```
Basta provare i divisori fino a √n (`d * d <= n`) e fermarsi al primo divisore trovato.
:::

::: ricorda Da ricordare
- L'`else` si lega all'**`if` più vicino**.
- Ogni ciclo deve avvicinarsi alla fine: chiediti **perché termina**.
- Il massimo parte dal **primo elemento**, non da 0.
:::
