/* >>> sol */
#include <stdio.h>
#define MAX 100

typedef struct {
  char nome[21];
  int voto;
} TipoStudente;

int salva(char *nomeFile, TipoStudente v[], int n) {
  int i;
  FILE *f = fopen(nomeFile, "w");
  if (f == NULL)
    return 0;
  for (i = 0; i < n; i++)
    fprintf(f, "%s %d\n", v[i].nome, v[i].voto);
  fclose(f);
  return 1;
}

int carica(char *nomeFile, TipoStudente v[], int max) {
  int n = 0;
  FILE *f = fopen(nomeFile, "r");
  if (f == NULL)
    return 0;
  while (n < max && fscanf(f, "%20s %d", v[n].nome, &v[n].voto) == 2)
    n++;
  fclose(f);
  return n;
}

int main(void) {
  TipoStudente a[3] = {{"Anna", 28}, {"Luca", 24}, {"Sara", 30}}, b[MAX];
  int n, i;
  salva("studenti.txt", a, 3);
  n = carica("studenti.txt", b, MAX);
  for (i = 0; i < n; i++)
    printf("%s %d\n", b[i].nome, b[i].voto);
  return 0;
}
/* <<< sol */
