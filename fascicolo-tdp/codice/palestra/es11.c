/* >>> sol */
#include <stdio.h>

int primo(int n);                       /* prototipo                   */

int main(void) {
  int a, b, x;
  printf("Intervallo a b: ");
  scanf("%d %d", &a, &b);
  for (x = a; x <= b; x++)
    if (primo(x))
      printf("%d ", x);
  printf("\n");
  return 0;
}

/* restituisce 1 se n e` primo, 0 altrimenti */
int primo(int n) {
  int d;
  if (n < 2)
    return 0;
  for (d = 2; d * d <= n; d++)
    if (n % d == 0)
      return 0;                         /* trovato un divisore         */
  return 1;
}
/* <<< sol */
