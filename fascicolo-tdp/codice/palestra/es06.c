/* >>> sol */
#include <stdio.h>

int main(void) {
  int n, i;
  double x, somma = 0;                  /* accumulatore inizializzato! */
  printf("Quanti numeri? ");
  scanf("%d", &n);
  for (i = 1; i <= n; i++) {
    printf("numero %d: ", i);
    scanf("%lf", &x);
    somma = somma + x;
  }
  if (n > 0)
    printf("somma %.2f, media %.2f\n", somma, somma / n);
  return 0;
}
/* <<< sol */
