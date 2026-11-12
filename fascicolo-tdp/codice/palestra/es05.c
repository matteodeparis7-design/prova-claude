/* >>> sol */
#include <stdio.h>

int main(void) {
  int n, i;
  printf("Tabellina del: ");
  scanf("%d", &n);
  for (i = 1; i <= 10; i++)
    printf("%2d x %2d = %3d\n", n, i, n * i);
  return 0;
}
/* <<< sol */
