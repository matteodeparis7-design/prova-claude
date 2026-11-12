/* >>> sol */
#include <stdio.h>

int main(void) {
  double c, f;
  printf("Temperatura in gradi Celsius: ");
  scanf("%lf", &c);                    /* %lf per leggere un double  */
  f = c * 9 / 5 + 32;                  /* c e` double: niente divisione intera */
  printf("%.1f C = %.1f F\n", c, f);
  return 0;
}
/* <<< sol */
