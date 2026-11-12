/* file.c - File testuali e binari in C.
   Compilare con:  gcc -std=c89 -pedantic -Wall file.c -o file            */

#include <stdio.h>
#include <stdlib.h>

typedef struct {
  char codice[6];
  int posti;
  double prezzo;
} TipoVolo;

/* >>> scriviTesto */
/* scrive n interi su un file di testo, uno per riga */
int scriviNumeri(char *nomeFile, int v[], int n) {
  FILE *f;
  int i;
  f = fopen(nomeFile, "w");        /* "w": crea o SVUOTA il file        */
  if (f == NULL)
    return 0;                      /* SEMPRE controllare l'apertura!    */
  for (i = 0; i < n; i++)
    fprintf(f, "%d\n", v[i]);
  fclose(f);
  return 1;
}
/* <<< scriviTesto */

/* >>> leggiTesto */
/* legge interi da un file di testo finche' ce ne sono; ne restituisce la somma */
int sommaDaFile(char *nomeFile, int *pquanti) {
  FILE *f;
  int x, somma = 0;
  *pquanti = 0;
  f = fopen(nomeFile, "r");
  if (f == NULL)
    return 0;
  while (fscanf(f, "%d", &x) == 1) { /* fscanf restituisce quanti dati ha letto */
    somma += x;
    (*pquanti)++;
  }
  fclose(f);
  return somma;
}
/* <<< leggiTesto */

/* >>> binari */
/* file binari: si scrivono/leggono BLOCCHI di byte, cosi` come sono in memoria */
int salvaVoli(char *nomeFile, TipoVolo voli[], int n) {
  FILE *f = fopen(nomeFile, "wb");
  int scritti;
  if (f == NULL)
    return 0;
  scritti = fwrite(voli, sizeof(TipoVolo), n, f);  /* n elementi in un colpo */
  fclose(f);
  return scritti == n;
}

int caricaVoli(char *nomeFile, TipoVolo voli[], int max) {
  FILE *f = fopen(nomeFile, "rb");
  int letti;
  if (f == NULL)
    return 0;
  letti = fread(voli, sizeof(TipoVolo), max, f);   /* restituisce quanti ne ha letti */
  fclose(f);
  return letti;
}

/* accesso diretto: leggo SOLO il k-esimo volo (k da 0) */
int leggiVoloK(char *nomeFile, int k, TipoVolo *pv) {
  FILE *f = fopen(nomeFile, "rb");
  int ok;
  if (f == NULL)
    return 0;
  fseek(f, (long) k * sizeof(TipoVolo), SEEK_SET);  /* salto k record   */
  ok = fread(pv, sizeof(TipoVolo), 1, f) == 1;
  fclose(f);
  return ok;
}
/* <<< binari */

int main(void) {
  int v[] = {3, 8, -1, 10}, quanti, s;
  TipoVolo voli[3] = {{"AZ123", 10, 99.5}, {"FR777", 0, 19.9}, {"LH400", 5, 150.0}};
  TipoVolo letti[10], uno;
  char *ft = "numeri.txt";
  char *fb = "voli.dat";
  int n;

  scriviNumeri(ft, v, 4);
  s = sommaDaFile(ft, &quanti);
  printf("letti %d numeri, somma %d\n", quanti, s);   /* 4, 20         */

  salvaVoli(fb, voli, 3);
  n = caricaVoli(fb, letti, 10);
  printf("caricati %d voli, il secondo e` %s\n", n, letti[1].codice);
  if (leggiVoloK(fb, 2, &uno))
    printf("volo di indice 2: %s %d %.1f\n", uno.codice, uno.posti, uno.prezzo);
  return 0;
}
