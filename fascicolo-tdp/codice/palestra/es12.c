/* >>> sol */
#include <stdio.h>

long fattoriale(int n) {
  long f = 1;
  int i;
  for (i = 2; i <= n; i++)
    f = f * i;
  return f;
}

long binomiale(int n, int k) {          /* n! / (k! (n-k)!)            */
  return fattoriale(n) / (fattoriale(k) * fattoriale(n - k));
}

int main(void) {
  int n, k;
  printf("n e k: ");
  scanf("%d %d", &n, &k);
  printf("%d! = %ld, coefficiente binomiale = %ld\n",
         n, fattoriale(n), binomiale(n, k));
  return 0;
}
/* <<< sol */
