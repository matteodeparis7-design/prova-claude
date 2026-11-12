/* >>> sol */
#include <stdio.h>

int main(void) {
  int x, max, quanti = 0;
  printf("Numeri positivi (0 per finire): ");
  scanf("%d", &x);
  max = x;                              /* il primo e` il candidato    */
  while (x != 0) {                      /* 0 = sentinella              */
    quanti++;
    if (x > max)
      max = x;
    scanf("%d", &x);                    /* lettura del prossimo        */
  }
  if (quanti > 0)
    printf("letti %d numeri, massimo %d\n", quanti, max);
  else
    printf("nessun numero\n");
  return 0;
}
/* <<< sol */
