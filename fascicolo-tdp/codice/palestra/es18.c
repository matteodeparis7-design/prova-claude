/* >>> sol */
#include <stdio.h>
#include <string.h>

int palindroma(char s[]) {
  int i = 0, j = strlen(s) - 1;
  while (i < j) {
    if (s[i] != s[j])
      return 0;
    i++;
    j--;
  }
  return 1;
}

void maiuscolo(char s[]) {
  int i;
  for (i = 0; s[i] != '\0'; i++)
    if (s[i] >= 'a' && s[i] <= 'z')
      s[i] = s[i] - 32;                 /* 'a' - 'A' == 32             */
}

int main(void) {
  char parola[51];
  printf("Parola: ");
  scanf("%50s", parola);                /* al massimo 50 caratteri     */
  maiuscolo(parola);
  printf("%s %s palindroma\n", parola, palindroma(parola) ? "e`" : "non e`");
  return 0;
}
/* <<< sol */
