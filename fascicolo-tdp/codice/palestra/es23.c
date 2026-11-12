/* >>> sol */
#include <stdio.h>
#include <stdlib.h>

typedef struct nodo {
  int info;
  struct nodo *next;
} TipoNodo;
typedef TipoNodo *TipoLista;

int main(void) {
  TipoLista l = NULL;
  TipoNodo *ultimo = NULL, *nuovo, *p;
  int x;

  printf("Interi (0 per finire): ");
  scanf("%d", &x);
  while (x != 0) {
    nuovo = malloc(sizeof(TipoNodo));
    if (nuovo == NULL)
      return 1;
    nuovo->info = x;
    nuovo->next = NULL;
    if (l == NULL)                      /* primo nodo: e` la testa     */
      l = nuovo;
    else
      ultimo->next = nuovo;             /* attacco in coda             */
    ultimo = nuovo;                     /* tengo traccia dell'ultimo   */
    scanf("%d", &x);
  }
  for (p = l; p != NULL; p = p->next)   /* stampa nello stesso ordine  */
    printf("%d -> ", p->info);
  printf("NULL\n");
  while (l != NULL) {                   /* deallocazione               */
    p = l;
    l = l->next;
    free(p);
  }
  return 0;
}
/* <<< sol */
