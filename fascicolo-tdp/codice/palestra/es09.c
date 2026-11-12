/* >>> sol */
#include <stdio.h>

int main(void) {
  int n, riga, col;
  printf("Altezza: ");
  scanf("%d", &n);
  for (riga = 1; riga <= n; riga++) {   /* ciclo esterno: le righe     */
    for (col = 1; col <= riga; col++)   /* ciclo interno: riga asterischi */
      printf("*");
    printf("\n");
  }
  return 0;
}
/* <<< sol */
