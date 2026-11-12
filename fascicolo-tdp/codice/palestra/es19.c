/* >>> sol */
#include <stdio.h>

/* come strcmp: <0, 0, >0 */
int mioStrcmp(char *a, char *b) {
  int i = 0;
  while (a[i] != '\0' && a[i] == b[i])  /* avanzo finche' sono uguali  */
    i++;
  return a[i] - b[i];                   /* differenza dei primi diversi */
}

/* copia src in dest (dest deve essere abbastanza grande) */
void mioStrcpy(char *dest, char *src) {
  while (*src != '\0') {
    *dest = *src;
    dest++;
    src++;
  }
  *dest = '\0';                         /* non dimenticare il terminatore */
}

int main(void) {
  char a[20];
  mioStrcpy(a, "mela");
  printf("%s %d %d %d\n", a, mioStrcmp(a, "mela") == 0,
         mioStrcmp("mela", "pera") < 0, mioStrcmp("pera", "pe") > 0);
  return 0;
}
/* <<< sol */
