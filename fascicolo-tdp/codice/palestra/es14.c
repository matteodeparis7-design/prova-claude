/* >>> sol */
#include <stdio.h>
#define N 5

int main(void) {
  int v[N], i;
  for (i = 0; i < N; i++) {
    printf("v[%d] = ", i);
    scanf("%d", &v[i]);                 /* & davanti a v[i]            */
  }
  printf("al contrario:");
  for (i = N - 1; i >= 0; i--)
    printf(" %d", v[i]);
  printf("\n");
  return 0;
}
/* <<< sol */
