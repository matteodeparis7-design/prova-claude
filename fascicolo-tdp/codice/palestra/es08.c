/* >>> sol */
#include <stdio.h>

int main(void) {
  int n, invertito = 0, somma = 0;
  printf("Intero positivo: ");
  scanf("%d", &n);
  while (n > 0) {
    somma += n % 10;                    /* ultima cifra                */
    invertito = invertito * 10 + n % 10;
    n = n / 10;                         /* tolgo l'ultima cifra        */
  }
  printf("al contrario: %d, somma delle cifre: %d\n", invertito, somma);
  return 0;
}
/* <<< sol */
