/* >>> sol */
#include <stdio.h>

int main(void) {
  int n, d, somma = 0;
  printf("Intero positivo: ");
  scanf("%d", &n);
  for (d = 1; d < n; d++)
    if (n % d == 0)                     /* d e` un divisore            */
      somma += d;
  if (somma == n)
    printf("%d e` perfetto\n", n);
  else
    printf("%d non e` perfetto (somma divisori = %d)\n", n, somma);
  return 0;
}
/* <<< sol */
