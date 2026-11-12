# Primi passi in C: algoritmi, variabili, tipi, espressioni {#cbasi}

*(slide lezioni 3-5; complementi lezioni 4 e 5; testo1 cap. 3, 5, 6, 8, app. B e C)*

## Algoritmo e programma

Un **algoritmo** è una sequenza **finita** di passi **precisi** (non ambigui) che risolve un problema in un tempo finito. Un **programma** è un algoritmo scritto in un linguaggio di programmazione. Prima si pensa l'algoritmo (anche con un diagramma a blocchi o in italiano), poi lo si traduce in C.

La **programmazione strutturata** (teorema di Böhm-Jacopini) dice che ogni algoritmo si può scrivere usando solo tre strutture: **sequenza**, **selezione** (`if`) e **iterazione** (`while`). Niente salti `goto`.

## Il primo programma

```c
#include <stdio.h>               /* libreria per input/output (printf, scanf) */

int main(void) {                 /* qui comincia l'esecuzione                 */
  int lato, area;                /* dichiarazione delle variabili             */

  printf("Lato del quadrato? ");
  scanf("%d", &lato);            /* & = "indirizzo di": scanf scrive in lato  */
  area = lato * lato;
  printf("Area = %d\n", area);
  return 0;                      /* 0 = "tutto bene" al sistema operativo     */
}
```

- Ogni istruzione finisce con `;`. I blocchi stanno tra `{ }`.
- I **commenti** in ANSI C si scrivono `/* ... */` (il `//` non è ANSI C89).
- In ANSI C le **dichiarazioni** stanno **all'inizio del blocco**, prima delle istruzioni.

## Variabili e tipi semplici

Una **variabile** è una locazione di memoria con un **nome**, un **tipo** e un **valore**. Il tipo dice quanti byte occupa e come interpretare i bit.

| Tipo | Cosa contiene | Dimensione tipica | Formato printf/scanf |
|---|---|---|---|
| `char` | un carattere (piccolo intero) | 1 byte | `%c` |
| `int` | intero | 4 byte | `%d` |
| `long` | intero più grande | 4 o 8 byte | `%ld` |
| `float` | reale, precisione singola | 4 byte | `%f` |
| `double` | reale, precisione doppia | 8 byte | `%f` in printf, **`%lf` in scanf** |

`sizeof(tipo)` dà la dimensione in byte (servirà con `malloc`).

**Costanti**: `#define MAX 100` (il preprocessore sostituisce `MAX` con `100` prima della compilazione; per convenzione in MAIUSCOLO). Costanti carattere tra apici `'A'`, stringhe tra virgolette `"ciao"`.

::: errore Variabili non inizializzate
Una variabile locale appena dichiarata contiene un valore **casuale** ("spazzatura"). `int somma; somma = somma + x;` è sbagliato: scrivi `int somma = 0;`. Vale per contatori, somme e per i puntatori (`TipoLista l = NULL;`).
:::

## Input e output formattato

```c
printf("x vale %d, y vale %.2f\n", x, y);  /* %.2f: due cifre decimali       */
scanf("%d %lf", &n, &d);                   /* & davanti alle variabili!     */
scanf("%s", parola);                       /* per le stringhe NIENTE &      */
```

Formati utili: `%5d` (larghezza 5), `%-10s` (allineato a sinistra), `%%` (il simbolo %). `\n` va a capo, `\t` tabulazione.

`scanf` **restituisce** quanti valori è riuscita a leggere: si usa per controllare l'input e, con i file, per sapere quando i dati finiscono.

## Espressioni e operatori

| Categoria | Operatori | Note |
|---|---|---|
| aritmetici | `+ - * / %` | `%` (resto) solo tra interi |
| relazionali | `< <= > >= == !=` | danno 1 (vero) o 0 (falso) |
| logici | `&& \|\| !` | AND, OR, NOT |
| assegnamento | `= += -= *= /= %=` | `x += 3` equivale a `x = x + 3` |
| incremento | `++ --` | prefisso o postfisso |
| condizionale | `c ? a : b` | vale `a` se `c` è vera, sennò `b` |

### Divisione intera: attenzione

{{inc basi.c espressioni}}

Se **entrambi** gli operandi sono interi, `/` fa la **divisione intera** (tronca verso lo zero). Per avere il risultato reale almeno un operando deve essere reale: `7 / 2.0` oppure il **cast** `(double) 7 / 2`.

### Conversioni di tipo

- **Implicite**: in un'espressione mista, il tipo "più piccolo" viene promosso (`int + double` diventa `double`). In un assegnamento il valore viene convertito nel tipo della variabile: `int i = 8.7;` mette **8** in `i` (tronca).
- **Esplicite** (cast): `(tipo) espressione`.

### Pre e post incremento

```c
int i = 5, a, b;
a = i++;     /* a = 5, poi i diventa 6 (POST: prima usa, poi incrementa) */
b = ++i;     /* i diventa 7, poi b = 7 (PRE: prima incrementa, poi usa)  */
```

### Precedenza (dalla più alta)

`!` `++` `--` `(cast)` → `*` `/` `%` → `+` `-` → `<` `<=` `>` `>=` → `==` `!=` → `&&` → `||` → `?:` → `=` `+=` ... Nel dubbio, **usa le parentesi**.

## Algebra di Boole ed espressioni logiche

In C **0 è falso** e **qualunque valore diverso da 0 è vero**.

| a | b | a && b | a \|\| b | !a |
|---|---|---|---|---|
| 0 | 0 | 0 | 0 | 1 |
| 0 | 1 | 0 | 1 | 1 |
| 1 | 0 | 0 | 1 | 0 |
| 1 | 1 | 1 | 1 | 0 |

**Leggi di De Morgan** (servono per negare le condizioni dei cicli):

- `!(a && b)` equivale a `!a || !b`
- `!(a || b)` equivale a `!a && !b`

Esempio: il contrario di "x è tra 1 e 10" `(x >= 1 && x <= 10)` è `(x < 1 || x > 10)`.

**Valutazione cortocircuitata**: in `a && b`, se `a` è falsa, `b` **non viene valutata**; in `a || b`, se `a` è vera, `b` non viene valutata. È fondamentale con le liste:

```c
while (p != NULL && p->info != x)   /* se p e` NULL, p->info NON viene valutato */
```

Scambiando l'ordine (`p->info != x && p != NULL`) il programma va in crash quando `p` è `NULL`.

::: errore = invece di ==
`if (x = 0)` **assegna** 0 a x e la condizione è sempre falsa. Per confrontare si usa `==`. Altro classico: `if (0 < x < 10)` non fa quello che sembra; si scrive `if (0 < x && x < 10)`.
:::

::: esercizio Esercizio 3.1 (esecuzione simulata)
Cosa stampa questo frammento?

```c
int a = 7, b = 2, c;
double d;
c = a / b + a % b;
d = a / b;
printf("%d %.1f %d\n", c, d, a > b && b > 3 || !0);
```
:::

::: soluzione
`a / b` = 3 (divisione intera), `a % b` = 1, quindi c = **4**. `d = a / b` calcola prima 3 (intero) e poi lo converte: d = **3.0**. L'ultima espressione: `a > b` è 1, `b > 3` è 0, quindi `1 && 0` = 0; poi `0 || !0` = `0 || 1` = **1** (`&&` ha precedenza su `||`). Stampa: `4 3.0 1`.
:::
