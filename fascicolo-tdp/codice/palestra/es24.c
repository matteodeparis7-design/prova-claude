/* >>> sol */
#include <stdio.h>
#include <stdlib.h>

typedef struct nodo {
  int info;
  struct nodo *next;
} TipoNodo;
typedef TipoNodo *TipoLista;

/* quanti nodi hanno info maggiore della media; due scansioni */
int sopraMedia(TipoLista l) {
  TipoNodo *p;
  int n = 0, somma = 0, conta = 0;
  for (p = l; p != NULL; p = p->next) { /* 1a scansione: la media      */
    n++;
    somma += p->info;
  }
  for (p = l; p != NULL; p = p->next)   /* 2a scansione: il confronto  */
    if (p->info * n > somma)            /* info > somma/n              */
      conta++;
  return conta;
}

int main(void) {
  int v[] = {2, 8, 5, 9, 1}, i;
  TipoLista l = NULL;
  TipoNodo *n;
  for (i = 4; i >= 0; i--) {            /* costruisco 2 8 5 9 1        */
    n = malloc(sizeof(TipoNodo));
    n->info = v[i];
    n->next = l;
    l = n;
  }
  printf("sopra la media (5): %d\n", sopraMedia(l));   /* 8 e 9: 2  */
  while (l != NULL) { n = l; l = l->next; free(n); }
  return 0;
}
/* <<< sol */
