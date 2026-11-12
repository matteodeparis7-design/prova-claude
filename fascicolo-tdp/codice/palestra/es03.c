/* >>> sol */
#include <stdio.h>

int main(void) {
  int n;
  printf("Numero intero: ");
  scanf("%d", &n);
  if (n % 2 == 0)
    printf("%d e` pari\n", n);
  else
    printf("%d e` dispari\n", n);
  if (n > 0)
    printf("ed e` positivo\n");
  else if (n < 0)
    printf("ed e` negativo\n");
  else
    printf("ed e` zero\n");
  return 0;
}
/* <<< sol */
