/* >>> sol */
#include <stdio.h>
#include <math.h>                       /* sqrt (con gcc: aggiungere -lm) */

int main(void) {
  double a, b, c, delta;
  printf("Coefficienti a b c: ");
  scanf("%lf %lf %lf", &a, &b, &c);
  if (a == 0)
    printf("Non e` di secondo grado\n");
  else {
    delta = b * b - 4 * a * c;
    if (delta > 0)
      printf("x1 = %.3f  x2 = %.3f\n", (-b + sqrt(delta)) / (2 * a),
             (-b - sqrt(delta)) / (2 * a));
    else if (delta == 0)
      printf("x1 = x2 = %.3f\n", -b / (2 * a));
    else
      printf("Nessuna soluzione reale\n");
  }
  return 0;
}
/* <<< sol */
