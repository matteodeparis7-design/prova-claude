/* >>> sol */
#include <stdio.h>

int main(void) {
  int totale, ore, minuti, secondi;
  printf("Secondi: ");
  scanf("%d", &totale);
  ore = totale / 3600;                 /* divisione intera            */
  minuti = (totale % 3600) / 60;       /* quel che resta, in minuti   */
  secondi = totale % 60;
  printf("%d h %d min %d s\n", ore, minuti, secondi);
  return 0;
}
/* <<< sol */
