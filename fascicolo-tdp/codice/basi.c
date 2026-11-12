/* basi.c - Frammenti dei primi capitoli (tipi, espressioni, controllo,
   funzioni, array, puntatori, stringhe, memoria dinamica, struct).
   Compilare con:  gcc -std=c89 -pedantic -Wall basi.c -o basi            */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define N 5

/* >>> scambio */
void scambioNO(int a, int b) {     /* SBAGLIATA: scambia due COPIE      */
  int t = a;
  a = b;
  b = t;
}

void scambio(int *pa, int *pb) {   /* GIUSTA: lavora sugli originali    */
  int t = *pa;
  *pa = *pb;
  *pb = t;
}
/* <<< scambio */

/* >>> mcd */
int mcd(int n, int m) {            /* algoritmo di Euclide per sottrazioni */
  while (n != m)
    if (m > n)
      m = m - n;
    else
      n = n - m;
  return n;
}
/* <<< mcd */

/* >>> arrayFun */
/* un array passato a una funzione e` l'indirizzo del suo primo elemento:
   la dimensione va passata a parte                                       */
int massimo(int v[], int dim) {
  int i, max = v[0];
  for (i = 1; i < dim; i++)
    if (v[i] > max)
      max = v[i];
  return max;
}

double media(int v[], int dim) {
  int i, somma = 0;
  for (i = 0; i < dim; i++)
    somma += v[i];
  return (double) somma / dim;     /* cast: altrimenti divisione intera! */
}

/* ricerca lineare con variabile "flag" (stile del corso):
   restituisce l'indice di x oppure -1                                   */
int indiceDi(int v[], int dim, int x) {
  int trovato = 0, i = 0;
  while (!trovato && i < dim)
    if (v[i] == x)
      trovato = 1;
    else
      i++;
  if (trovato)
    return i;
  return -1;
}
/* <<< arrayFun */

/* >>> minmax */
/* due risultati: uno con return? No: entrambi con parametri di output */
void minMax(int v[], int dim, int *pmin, int *pmax) {
  int i;
  *pmin = *pmax = v[0];
  for (i = 1; i < dim; i++) {
    if (v[i] < *pmin) *pmin = v[i];
    if (v[i] > *pmax) *pmax = v[i];
  }
}
/* <<< minmax */

/* >>> duplicato */
/* restituisce una copia "esatta" di s (NULL se manca memoria) */
char *duplicato(char *s) {
  char *nuova = malloc(strlen(s) + 1);   /* +1 per il '\0'!           */
  if (nuova != NULL)
    strcpy(nuova, s);
  return nuova;
}
/* <<< duplicato */

/* >>> mialen */
/* come lavora strlen: conta i caratteri fino al terminatore '\0' */
int miaStrlen(char *s) {
  int n = 0;
  while (s[n] != '\0')
    n++;
  return n;
}

/* versione con aritmetica dei puntatori */
int miaStrlenPunt(char *s) {
  char *p = s;
  while (*p != '\0')
    p++;
  return p - s;                    /* differenza tra puntatori          */
}
/* <<< mialen */

/* >>> arrayDinamico */
/* crea un array dinamico di n double, tutti inizializzati a val */
double *creaArray(int n, double val) {
  int i;
  double *a = malloc(n * sizeof(double));
  if (a == NULL)
    return NULL;
  for (i = 0; i < n; i++)
    a[i] = val;                    /* si usa come un array normale      */
  return a;                        /* la memoria SOPRAVVIVE alla funzione */
}
/* <<< arrayDinamico */

/* >>> struct */
struct punto {
  double x, y;
  char colore;                     /* 'R', 'G', 'B' ...                 */
};
typedef struct punto TipoPunto;

void stampaPunto(TipoPunto p) {    /* per valore: riceve una copia      */
  printf("(%.1f, %.1f) colore %c\n", p.x, p.y, p.colore);
}

void trasla(TipoPunto *pp, double dx, double dy) {  /* per indirizzo    */
  pp->x += dx;                     /* pp->x  equivale a  (*pp).x        */
  pp->y += dy;
}
/* <<< struct */

int main(void) {
  int a = 3, b = 7, mn, mx;
  int v[N] = {4, -2, 9, 0, 9};
  char parola[] = "POCO";
  char *copia;
  double *arr;
  TipoPunto p = {1.0, 2.0, 'R'};

  /* >>> espressioni */
  printf("%d %d %d\n", 7 / 2, 7 % 2, -7 / 2);   /* 3 1 -3              */
  printf("%.2f %.2f\n", 7 / 2.0, (double) 7 / 2); /* 3.50 3.50          */
  /* <<< espressioni */

  scambioNO(a, b);
  printf("dopo scambioNO: a=%d b=%d\n", a, b);   /* 3 7                 */
  scambio(&a, &b);
  printf("dopo scambio:   a=%d b=%d\n", a, b);   /* 7 3                 */

  printf("mcd(15,5)=%d mcd(12,18)=%d\n", mcd(15, 5), mcd(12, 18));
  printf("max=%d media=%.2f indice di 9: %d, di 5: %d\n",
         massimo(v, N), media(v, N), indiceDi(v, N, 9), indiceDi(v, N, 5));
  minMax(v, N, &mn, &mx);
  printf("min=%d max=%d\n", mn, mx);

  copia = duplicato(parola);
  if (copia != NULL) {
    printf("copia: %s (%d e %d caratteri)\n", copia,
           miaStrlen(copia), miaStrlenPunt(copia));
    free(copia);
  }

  arr = creaArray(3, 1.5);
  if (arr != NULL) {
    printf("arr: %.1f %.1f %.1f\n", arr[0], *(arr + 1), arr[2]);
    free(arr);
  }

  stampaPunto(p);
  trasla(&p, 0.5, -1.0);
  stampaPunto(p);
  return 0;
}
