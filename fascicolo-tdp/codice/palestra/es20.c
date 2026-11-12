/* >>> sol */
#include <stdio.h>

/* scambia nell'array il minimo e il massimo; in *pmin e *pmax le posizioni */
void scambiaMinMax(int v[], int dim, int *pmin, int *pmax) {
  int i, t;
  *pmin = 0;
  *pmax = 0;
  for (i = 1; i < dim; i++) {
    if (v[i] < v[*pmin]) *pmin = i;
    if (v[i] > v[*pmax]) *pmax = i;
  }
  t = v[*pmin];
  v[*pmin] = v[*pmax];
  v[*pmax] = t;
}

int main(void) {
  int v[] = {5, 9, 1, 7}, imin, imax, i;
  scambiaMinMax(v, 4, &imin, &imax);
  for (i = 0; i < 4; i++)
    printf("%d ", v[i]);                /* 5 1 9 7                     */
  printf("(min era in %d, max in %d)\n", imin, imax);
  return 0;
}
/* <<< sol */
