/* ricorsione_ordinamento.c - Ricorsione, ricerca e ordinamento.
   Compilare con:  gcc -std=c89 -pedantic -Wall ricorsione_ordinamento.c   */

#include <stdio.h>
#include <string.h>

/* >>> fatt */
int fatt(int n) {
  if (n <= 1)                      /* caso base                         */
    return 1;
  return n * fatt(n - 1);          /* caso ricorsivo: problema piu` piccolo */
}
/* <<< fatt */

/* >>> invertiInput */
/* legge caratteri fino al '.' e li stampa al contrario (es. TOPI. -> IPOT) */
void leggiEInverti(void) {
  char ch;
  scanf("%c", &ch);
  if (ch != '.') {                 /* caso ricorsivo                    */
    leggiEInverti();               /* leggi e inverti il RESTO          */
    printf("%c", ch);              /* poi stampa questo carattere       */
  }                                /* caso base ('.'): non fare nulla   */
}
/* <<< invertiInput */

/* >>> palin */
/* 1 se la porzione p[i..j] e` palindroma, 0 altrimenti */
int palin(char p[], int i, int j) {
  if (i >= j)                      /* niente (o un solo car.) da controllare */
    return 1;
  if (p[i] != p[j])
    return 0;
  return palin(p, i + 1, j - 1);   /* controllo la parte interna        */
}
/* <<< palin */

/* >>> mcdRic */
int mcdRic(int n, int m) {
  if (n == m)
    return n;
  if (m > n)
    return mcdRic(n, m - n);
  return mcdRic(n - m, m);
}
/* <<< mcdRic */

/* >>> sommaArrayRic */
/* somma degli elementi v[0..n-1]: = v[n-1] + somma dei primi n-1 */
int sommaRic(int v[], int n) {
  if (n == 0)
    return 0;
  return v[n - 1] + sommaRic(v, n - 1);
}
/* <<< sommaArrayRic */

/* >>> ricercaBinaria */
/* l'array DEVE essere ordinato in modo crescente; restituisce indice o -1 */
int ricercaBinaria(int v[], int dim, int x) {
  int inizio = 0, fine = dim - 1, medio;
  while (inizio <= fine) {
    medio = (inizio + fine) / 2;
    if (v[medio] == x)
      return medio;
    if (x < v[medio])
      fine = medio - 1;            /* cerco nella meta` sinistra        */
    else
      inizio = medio + 1;          /* cerco nella meta` destra          */
  }
  return -1;
}
/* <<< ricercaBinaria */

/* >>> selection */
void selectionSort(int v[], int dim) {
  int i, j, iMin, t;
  for (i = 0; i < dim - 1; i++) {
    iMin = i;                      /* cerco il minimo in v[i..dim-1]    */
    for (j = i + 1; j < dim; j++)
      if (v[j] < v[iMin])
        iMin = j;
    t = v[i]; v[i] = v[iMin]; v[iMin] = t;   /* lo porto in posizione i */
  }
}
/* <<< selection */

/* >>> bubble */
void bubbleSort(int v[], int dim) {
  int i, t, scambiato = 1, limite = dim - 1;
  while (scambiato) {              /* ripeto finche' faccio scambi      */
    scambiato = 0;
    for (i = 0; i < limite; i++)
      if (v[i] > v[i + 1]) {       /* coppia in ordine sbagliato        */
        t = v[i]; v[i] = v[i + 1]; v[i + 1] = t;
        scambiato = 1;
      }
    limite--;                      /* l'ultimo e` ormai al suo posto    */
  }
}
/* <<< bubble */

/* >>> insertion */
void insertionSort(int v[], int dim) {
  int i, j, x;
  for (i = 1; i < dim; i++) {
    x = v[i];                      /* elemento da inserire              */
    j = i - 1;
    while (j >= 0 && v[j] > x) {   /* sposto a destra i maggiori di x   */
      v[j + 1] = v[j];
      j--;
    }
    v[j + 1] = x;                  /* inserisco x nel buco              */
  }
}
/* <<< insertion */

/* >>> merge */
/* merge sort (ricorsivo): divido a meta`, ordino le due meta`, le fondo */
void fondi(int v[], int inizio, int medio, int fine) {
  int aux[100];                    /* per semplicita`: dim <= 100       */
  int i = inizio, j = medio + 1, k = 0;
  while (i <= medio && j <= fine)
    if (v[i] <= v[j]) aux[k++] = v[i++];
    else              aux[k++] = v[j++];
  while (i <= medio) aux[k++] = v[i++];
  while (j <= fine)  aux[k++] = v[j++];
  for (k = 0; k <= fine - inizio; k++)
    v[inizio + k] = aux[k];
}

void mergeSort(int v[], int inizio, int fine) {
  int medio;
  if (inizio < fine) {             /* almeno 2 elementi                 */
    medio = (inizio + fine) / 2;
    mergeSort(v, inizio, medio);
    mergeSort(v, medio + 1, fine);
    fondi(v, inizio, medio, fine);
  }
}
/* <<< merge */

void stampa(int v[], int dim) {
  int i;
  for (i = 0; i < dim; i++)
    printf("%d ", v[i]);
  printf("\n");
}

int main(void) {
  int a[] = {29, 10, 14, 37, 13}, b[] = {29, 10, 14, 37, 13},
      c[] = {29, 10, 14, 37, 13}, d[] = {29, 10, 14, 37, 13};
  char s1[] = "radar", s2[] = "ingegnere";

  printf("fatt(5)=%d mcdRic(12,18)=%d sommaRic=%d\n",
         fatt(5), mcdRic(12, 18), sommaRic(a, 5));
  printf("palin(radar)=%d palin(ingegnere)=%d\n",
         palin(s1, 0, strlen(s1) - 1), palin(s2, 0, strlen(s2) - 1));
  selectionSort(a, 5); stampa(a, 5);
  bubbleSort(b, 5);    stampa(b, 5);
  insertionSort(c, 5); stampa(c, 5);
  mergeSort(d, 0, 4);  stampa(d, 5);
  printf("ricerca 37: %d, ricerca 15: %d\n",
         ricercaBinaria(a, 5, 37), ricercaBinaria(a, 5, 15));
  printf("scrivi una parola terminata da punto: ");
  leggiEInverti();
  printf("\n");
  return 0;
}
