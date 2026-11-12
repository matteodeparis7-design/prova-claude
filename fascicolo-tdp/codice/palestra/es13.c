/* >>> sol */
#include <stdio.h>

double calcola(double a, char op, double b, int *errore) {
  *errore = 0;
  switch (op) {
    case '+': return a + b;
    case '-': return a - b;
    case '*': return a * b;
    case '/':
      if (b == 0) {
        *errore = 1;                    /* parametro di output         */
        return 0;
      }
      return a / b;
    default:
      *errore = 1;
      return 0;
  }
}

int main(void) {
  double a, b, r;
  char op;
  int err;
  printf("Operazione (es. 3 * 4, oppure 0 x 0 per finire): ");
  scanf("%lf %c %lf", &a, &op, &b);     /* lo spazio prima di %c salta gli spazi */
  while (op != 'x') {
    r = calcola(a, op, b, &err);
    if (err)
      printf("operazione non valida\n");
    else
      printf("= %g\n", r);
    printf("Operazione: ");
    scanf("%lf %c %lf", &a, &op, &b);
  }
  return 0;
}
/* <<< sol */
