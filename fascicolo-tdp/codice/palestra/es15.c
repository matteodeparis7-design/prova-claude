/* >>> sol */
#include <stdio.h>

int conta(int v[], int dim, int x) {
  int i, n = 0;
  for (i = 0; i < dim; i++)
    if (v[i] == x)
      n++;
  return n;
}

int main(void) {
  int v[] = {3, 7, 3, 1, 3, 7}, i, dim = 6;
  for (i = 0; i < dim; i++)               /* stampo ogni valore solo la  */
    if (conta(v, i, v[i]) == 0)           /* prima volta che compare     */
      printf("%d compare %d volte\n", v[i], conta(v, dim, v[i]));
  return 0;
}
/* <<< sol */
