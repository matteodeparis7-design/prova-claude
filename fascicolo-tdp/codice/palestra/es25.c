/* >>> sol */
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#define LUNGMAX 50

typedef struct nodo {
  char *parola;                         /* stringa esatta              */
  struct nodo *next;
} TipoNodo;
typedef TipoNodo *TipoLista;

/* inserimento in ordine alfabetico, senza doppioni:
   1 inserita, 0 gia` presente, -1 memoria esaurita                     */
int inserisci(TipoLista *pl, char *s) {
  TipoNodo *prec = NULL, *corr = *pl, *nuovo;
  while (corr != NULL && strcmp(corr->parola, s) < 0) {
    prec = corr;
    corr = corr->next;
  }
  if (corr != NULL && strcmp(corr->parola, s) == 0)
    return 0;
  nuovo = malloc(sizeof(TipoNodo));
  if (nuovo == NULL)
    return -1;
  nuovo->parola = malloc(strlen(s) + 1);
  if (nuovo->parola == NULL) {
    free(nuovo);
    return -1;
  }
  strcpy(nuovo->parola, s);
  nuovo->next = corr;
  if (prec == NULL)
    *pl = nuovo;
  else
    prec->next = nuovo;
  return 1;
}

int elimina(TipoLista *pl, char *s) {
  TipoNodo *prec = NULL, *corr = *pl;
  while (corr != NULL && strcmp(corr->parola, s) != 0) {
    prec = corr;
    corr = corr->next;
  }
  if (corr == NULL)
    return 0;
  if (prec == NULL)
    *pl = corr->next;
  else
    prec->next = corr->next;
  free(corr->parola);
  free(corr);
  return 1;
}

void stampa(TipoLista l) {
  for (; l != NULL; l = l->next)
    printf("  %s\n", l->parola);
}

void dealloca(TipoLista *pl) {
  TipoNodo *d;
  while (*pl != NULL) {
    d = *pl;
    *pl = d->next;
    free(d->parola);
    free(d);
  }
}

int main(void) {
  TipoLista dizionario = NULL;
  char buffer[LUNGMAX + 1];
  int scelta;
  do {
    printf("1 aggiungi, 2 elimina, 3 stampa, 0 fine: ");
    if (scanf("%d", &scelta) != 1)
      break;
    switch (scelta) {
      case 1:
        printf("parola: ");
        scanf("%50s", buffer);
        if (inserisci(&dizionario, buffer) != 1)
          printf("non inserita\n");
        break;
      case 2:
        printf("parola: ");
        scanf("%50s", buffer);
        if (!elimina(&dizionario, buffer))
          printf("non presente\n");
        break;
      case 3:
        stampa(dizionario);
        break;
    }
  } while (scelta != 0);
  dealloca(&dizionario);
  return 0;
}
/* <<< sol */
