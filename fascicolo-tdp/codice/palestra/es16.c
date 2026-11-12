/* >>> sol */
#include <stdio.h>

/* array ORDINATO: elimina i doppioni, restituisce la nuova dimensione */
int togliDoppioni(int v[], int dim) {
  int i, k;
  if (dim == 0)
    return 0;
  k = 1;                                /* v[0..k-1] senza doppioni    */
  for (i = 1; i < dim; i++)
    if (v[i] != v[k - 1]) {             /* diverso dall'ultimo tenuto  */
      v[k] = v[i];
      k++;
    }
  return k;
}

int main(void) {
  int v[] = {1, 1, 2, 4, 4, 4, 7, 9, 9}, n, i;
  n = togliDoppioni(v, 9);
  for (i = 0; i < n; i++)
    printf("%d ", v[i]);                /* 1 2 4 7 9                   */
  printf("\n");
  return 0;
}
/* <<< sol */
