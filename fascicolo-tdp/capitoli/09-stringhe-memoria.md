# Stringhe e allocazione dinamica della memoria {#stringhe}

*(slide lezioni 15 e 16, EG5, video "ArrayDouble"; testo1 cap. 13, 14, app. B)*

::: obiettivi Cosa imparerai
- come sono fatte le stringhe in C e le funzioni di string.h
- allocare e liberare memoria con malloc e free
- le stringhe "esatte", richieste in ogni traccia d'esame
:::

## Le stringhe in C

Una **stringa** è un **array di `char` terminato dal carattere `'\0'`** (codice 0). Il `'\0'` segna la fine: per questo una stringa di k caratteri occupa **k+1** caratteri.

```c
char s[10] = "POCO";        /* 10 posti, ne usa 5: P O C O \0 */
```

```text
indice:  0   1   2   3   4    5   6   7   8   9
       +---+---+---+---+----+---+---+---+---+---+
   s   | P | O | C | O | \0 | ? | ? | ? | ? | ? |
       +---+---+---+---+----+---+---+---+---+---+
```

Lettura e stampa: `scanf("%s", s);` (senza `&`, perché `s` è già un indirizzo; legge fino al primo spazio) e `printf("%s", s);`. Per leggere una riga con spazi: `fgets(s, 10, stdin);` (che però tiene anche il `'\n'` finale).

### Le funzioni di `string.h`

| Funzione | Cosa fa |
|---|---|
| `strlen(s)` | numero di caratteri **escluso** il `'\0'` |
| `strcpy(dest, src)` | copia `src` in `dest` (dest deve avere spazio!) |
| `strncpy(dest, src, n)` | copia al massimo n caratteri (può non mettere il `'\0'`) |
| `strcmp(a, b)` | **0** se uguali, **< 0** se a viene prima in ordine alfabetico, **> 0** se dopo |
| `strcat(dest, src)` | aggiunge `src` in fondo a `dest` |

::: errore Le stringhe non si confrontano con == e non si copiano con =
`if (s1 == s2)` confronta gli **indirizzi**, non il contenuto: si usa `strcmp(s1, s2) == 0`. E `s1 = s2;` tra array non compila (oppure, tra puntatori, copia l'indirizzo e non i caratteri): si usa `strcpy`. Questo errore all'esame costa caro, perché i testi chiedono sempre di cercare per nome, codice o grado.
:::

## Allocazione statica e dinamica

- **Statica / automatica**: la dimensione è decisa **quando scrivi il programma** (`int v[100];`). Le variabili locali vivono nell'RDA e muoiono con la funzione.
- **Dinamica**: la memoria si chiede **durante l'esecuzione**, quando si sa quanta ne serve, in una zona chiamata **heap**. Rimane allocata finché non la liberi tu con `free`, **anche dopo la fine della funzione** che l'ha chiesta.

Funzioni di `stdlib.h`:

| Funzione | Cosa fa |
|---|---|
| `malloc(nbyte)` | alloca `nbyte` byte e restituisce l'indirizzo (contenuto casuale), **`NULL`** se non c'è memoria |
| `calloc(n, dim)` | alloca n elementi di `dim` byte e li azzera |
| `realloc(p, nuovaDim)` | cambia la dimensione del blocco puntato da p (può spostarlo: usa l'indirizzo restituito) |
| `free(p)` | restituisce al sistema il blocco puntato da p |

```c
int *v;
int n;
scanf("%d", &n);
v = malloc(n * sizeof(int));     /* array dinamico di n interi          */
if (v == NULL) {                 /* SEMPRE controllare ("test sull'allocazione") */
  printf("memoria esaurita\n");
  return 0;
}
v[0] = 3;                        /* si usa come un array normale         */
...
free(v);                         /* quando non serve piu`                */
```

{{inc basi.c arrayDinamico}}

::: errore I tre errori della memoria dinamica
1. **Non controllare `NULL`** dopo `malloc`.
2. **Memory leak**: perdere l'ultimo puntatore a un blocco senza averlo liberato (la memoria resta occupata fino alla fine del programma).
3. **Usare memoria già liberata** (*dangling pointer*): dopo `free(p)`, `p` contiene ancora il vecchio indirizzo ma la memoria non è più tua. Se serve, scrivi `p = NULL;` subito dopo.
:::

## Stringhe "esatte"

Una **stringa esatta** è allocata con **esattamente** lo spazio necessario: `strlen + 1` caratteri. Nessuno spreco. È **la tecnica richiesta in tutti i testi d'esame** per i campi "stringa di lunghezza non nota a priori".

### Duplicato esatto di una stringa

{{inc basi.c duplicato}}

```text
prima:    str ---> | P | O | C | O | \0 | ? | ? | ? | ? |   (array di 10)

malloc(strlen(s)+1) = malloc(5):
          nuova -> | ? | ? | ? | ? | ?  |

strcpy:   nuova -> | P | O | C | O | \0 |   5 caratteri, nessuno sprecato
```

La memoria allocata con `malloc` **sopravvive** alla fine di `duplicato`: l'RDA sparisce (con la variabile `nuova`), ma il blocco resta, e il suo indirizzo è stato restituito al chiamante.

### Lo schema con il buffer

Per leggere una stringa di lunghezza ignota:

1. si legge in un **buffer** abbastanza grande (`char buffer[LUNGMAX+1]`);
2. si alloca con `malloc(strlen(buffer) + 1)`;
3. si copia con `strcpy`;
4. il buffer si riusa per la prossima lettura.

```c
#define LUNGMAX 80
char buffer[LUNGMAX + 1];
char *nome;

scanf("%s", buffer);
nome = malloc(strlen(buffer) + 1);
if (nome != NULL)
  strcpy(nome, buffer);
```

## Array di stringhe

Un **array di stringhe** è un **array di puntatori a char**: ogni elemento punta a una stringa esatta allocata a parte.

```c
#define N 6
char *arrStr[N];           /* 6 puntatori; le stringhe vanno allocate */
```

```text
arrStr
 [0] ---> | P | O | C | O | \0 |
 [1] ---> | O | R | O | \0 |
 [2] ---> | R | E | S | T | O | \0 |
 ...
 [5] ---> | P | R | O | M | O | Z | i | o | n | \0 |
```

Lettura di N stringhe esatte (dalle slide della lezione 16):

```c
void costruisciArrayStringhe(char *v[], int n) {
  char buffer[LUNGMAX + 1];
  int i;
  for (i = 0; i < n; i++) {
    printf("scrivi una stringa: ");
    scanf("%s", buffer);
    v[i] = malloc(strlen(buffer) + 1);
    if (v[i] != NULL)
      strcpy(v[i], buffer);
    else {
      printf("memoria esaurita\n");
      break;
    }
  }
}
```

Ricerca in un array di stringhe (con flag, fermandosi appena trovata):

```c
int presenteIn(char *cercata, char **v, int dim) {   /* char *v[] == char **v */
  int trovata = 0, i;
  for (i = 0; i < dim && trovata == 0; i++)
    if (strcmp(cercata, v[i]) == 0)
      trovata = 1;
  return trovata;
}
```

Nel **tipo** dei parametri, `char v[]` equivale a `char *v`, e quindi `char *v[]` equivale a `char **v`.

## Array dinamici che crescono: realloc

Se un array dinamico è pieno, lo si può ingrandire (è la tecnica di `voli6.c` nelle EG):

```c
int *nuovo = realloc(v, 2 * dim * sizeof(int));  /* raddoppio */
if (nuovo != NULL) {
  v = nuovo;          /* uso il nuovo indirizzo (il blocco puo` essersi spostato) */
  dim = 2 * dim;
}                     /* se fallisce, v e` ancora valido e intatto */
```

::: esercizio Esercizio 9.1
Scrivi `char *concatenaEsatta(char *a, char *b)` che restituisce una **nuova** stringa esatta contenente a seguita da b (le due stringhe originali non vanno toccate).
:::

::: soluzione
```c
char *concatenaEsatta(char *a, char *b) {
  char *r = malloc(strlen(a) + strlen(b) + 1);   /* un solo '\0' */
  if (r != NULL) {
    strcpy(r, a);
    strcat(r, b);
  }
  return r;
}
```
:::

::: esercizio Esercizio 9.2
Scrivi `int contaVocali(char *s)` senza usare `strlen` (scorri fino al `'\0'`).
:::

::: soluzione
```c
int contaVocali(char *s) {
  int i, n = 0;
  char c;
  for (i = 0; s[i] != '\0'; i++) {
    c = s[i];
    if (c >= 'A' && c <= 'Z')
      c = c + 32;                     /* in minuscolo */
    if (c == 'a' || c == 'e' || c == 'i' || c == 'o' || c == 'u')
      n++;
  }
  return n;
}
```
:::

::: ricorda Da ricordare
- Stringa = array di char che finisce con **'\0'**.
- Confronta con **`strcmp`**, copia con **`strcpy`** (mai `==` e `=`).
- Stringa esatta: `malloc(strlen(s) + 1)`, controllo NULL, `strcpy`; poi `free`.
:::
