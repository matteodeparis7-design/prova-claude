# File testuali e binari {#file}

*(lezione 9 con video, EG7; testo1 cap. 17)*

Le variabili vivono in RAM e spariscono a fine programma. Per conservare i dati servono i **file**, che stanno nella memoria di massa.

## Aprire e chiudere un file

```c
#include <stdio.h>

FILE *f;                          /* puntatore a una struttura che descrive il file */
f = fopen("dati.txt", "r");       /* nome del file, modo di apertura                */
if (f == NULL) {                  /* fopen restituisce NULL se fallisce             */
  printf("impossibile aprire il file\n");
  return 0;
}
...
fclose(f);                        /* SEMPRE: scarica i dati e libera la risorsa     */
```

| Modo | Significato |
|---|---|
| `"r"` | lettura; il file deve esistere |
| `"w"` | scrittura; crea il file o lo **svuota** se esiste |
| `"a"` | aggiunta in fondo (*append*) |
| `"r+"` | lettura e scrittura di un file esistente |
| `"rb"`, `"wb"`, `"ab"`... | come sopra, per file **binari** |

## File di testo: I/O formattato

Si usano come `printf`/`scanf`, ma con il file come primo argomento: `fprintf(f, ...)` e `fscanf(f, ...)`.

{{inc file.c scriviTesto}}

Per leggere "fino alla fine" si usa il **valore restituito da `fscanf`** (quanti dati ha letto): quando i dati finiscono restituisce `EOF` (un valore negativo) o comunque un numero diverso da quelli richiesti.

{{inc file.c leggiTesto}}

::: nota feof
Esiste anche `feof(f)`, che diventa vero **dopo** che una lettura ha provato a superare la fine. Il ciclo `while (!feof(f)) { fscanf(...); ... }` elabora l'ultimo dato **due volte** se il file finisce con un a capo. Il controllo sul valore di `fscanf` è più sicuro.
:::

Altre funzioni utili: `fgetc(f)` / `fputc(c, f)` per un carattere alla volta; `fgets(buffer, dim, f)` per una riga intera.

Lo **standard input** e **output** sono anch'essi file già aperti: `stdin`, `stdout`. `printf(...)` equivale a `fprintf(stdout, ...)`.

## File binari

Un file di testo contiene caratteri (il numero 1216 occupa 4 caratteri). Un file **binario** contiene i byte **così come sono in memoria** (un `int` occupa sempre `sizeof(int)` byte). È più compatto e veloce, ma non si legge con un editor di testo.

- `fwrite(indirizzo, dimensione_elemento, quanti, f)`: scrive `quanti` elementi presi dall'indirizzo dato; restituisce quanti ne ha scritti.
- `fread(indirizzo, dimensione_elemento, quanti, f)`: legge fino a `quanti` elementi; restituisce **quanti ne ha letti** (0 alla fine del file).
- `fseek(f, spostamento, origine)`: sposta la posizione corrente (accesso **diretto**, *random*). Origine: `SEEK_SET` (inizio), `SEEK_CUR` (posizione attuale), `SEEK_END` (fine).
- `ftell(f)`: posizione corrente in byte; `rewind(f)`: torna all'inizio.

{{inc file.c binari}}

Con un file binario di record tutti uguali si può leggere direttamente il k-esimo record, senza leggere quelli prima: è il vantaggio dell'accesso diretto.

::: errore Errori frequenti con i file
- Non controllare se `fopen` ha restituito `NULL`.
- Dimenticare `fclose` (i dati scritti possono restare nel buffer e andare persi).
- Aprire con `"w"` un file che si voleva solo leggere: lo si svuota.
- Salvare in un file binario una struct che contiene un puntatore (`char *descrizione`): si salva l'**indirizzo**, non la stringa! Al prossimo avvio quell'indirizzo non vale più nulla. Le stringhe esatte vanno salvate come testo, oppure scrivendo prima la lunghezza e poi i caratteri.
:::

::: esercizio Esercizio 7.1
Scrivi una funzione `int copiaPositivi(char *origine, char *destinazione)` che legge interi da un file di testo e scrive in un altro file solo i positivi, uno per riga. Restituisce quanti numeri ha copiato, oppure -1 se un file non si apre.
:::

::: soluzione
```c
int copiaPositivi(char *origine, char *destinazione) {
  FILE *fin, *fout;
  int x, copiati = 0;
  fin = fopen(origine, "r");
  if (fin == NULL)
    return -1;
  fout = fopen(destinazione, "w");
  if (fout == NULL) {
    fclose(fin);                    /* chiudo quello gia` aperto */
    return -1;
  }
  while (fscanf(fin, "%d", &x) == 1)
    if (x > 0) {
      fprintf(fout, "%d\n", x);
      copiati++;
    }
  fclose(fin);
  fclose(fout);
  return copiati;
}
```
:::
