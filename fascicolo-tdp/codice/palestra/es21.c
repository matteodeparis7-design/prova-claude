/* >>> sol */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define LUNGMAX 50

typedef struct {
  char *nome;                           /* stringa esatta              */
  int voto;
} TipoStudente;

int main(void) {
  TipoStudente *classe;                 /* array dinamico di struct    */
  char buffer[LUNGMAX + 1];
  int n, i, somma = 0;

  printf("Quanti studenti? ");
  scanf("%d", &n);
  classe = malloc(n * sizeof(TipoStudente));
  if (classe == NULL)
    return 1;
  for (i = 0; i < n; i++) {
    printf("nome e voto: ");
    scanf("%s %d", buffer, &classe[i].voto);
    classe[i].nome = malloc(strlen(buffer) + 1);
    if (classe[i].nome == NULL)
      return 1;
    strcpy(classe[i].nome, buffer);
    somma += classe[i].voto;
  }
  if (n > 0) {
    printf("media %.2f; sopra la media:", (double) somma / n);
    for (i = 0; i < n; i++)
      if (classe[i].voto * n > somma)   /* voto > somma/n, senza divisioni */
        printf(" %s", classe[i].nome);
    printf("\n");
  }
  for (i = 0; i < n; i++)
    free(classe[i].nome);               /* prima le stringhe ...       */
  free(classe);                         /* ... poi l'array             */
  return 0;
}
/* <<< sol */
