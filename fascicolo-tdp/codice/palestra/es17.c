/* >>> sol */
#include <stdio.h>
#define R 2
#define C 3

int main(void) {
  int m[R][C] = {{1, 2, 3}, {4, 5, 6}}, t[C][R], i, j;
  for (i = 0; i < R; i++)
    for (j = 0; j < C; j++)
      t[j][i] = m[i][j];                /* la riga i diventa colonna i */
  for (i = 0; i < C; i++) {
    for (j = 0; j < R; j++)
      printf("%3d", t[i][j]);
    printf("\n");
  }
  return 0;
}
/* <<< sol */
