/* alberi.c - Alberi binari (cenni): definizione, visite, funzioni ricorsive.
   Compilare con:  gcc -std=c89 -pedantic -Wall alberi.c -o alberi        */

#include <stdio.h>
#include <stdlib.h>

/* >>> tipi */
typedef int TipoInfo;

struct nodoAlbero {
  TipoInfo info;
  struct nodoAlbero *sinistro;     /* sottoalbero sinistro              */
  struct nodoAlbero *destro;       /* sottoalbero destro                */
};

typedef struct nodoAlbero TipoNodoAlbero;
typedef TipoNodoAlbero *TipoAlbero;   /* albero = puntatore alla radice */
/* <<< tipi */

/* >>> visite */
void preordine(TipoAlbero a) {     /* RADICE - sinistro - destro        */
  if (a != NULL) {
    printf("%d ", a->info);
    preordine(a->sinistro);
    preordine(a->destro);
  }
}

void inordine(TipoAlbero a) {      /* sinistro - RADICE - destro        */
  if (a != NULL) {
    inordine(a->sinistro);
    printf("%d ", a->info);
    inordine(a->destro);
  }
}

void postordine(TipoAlbero a) {    /* sinistro - destro - RADICE        */
  if (a != NULL) {
    postordine(a->sinistro);
    postordine(a->destro);
    printf("%d ", a->info);
  }
}
/* <<< visite */

/* >>> funzioni */
int contaNodi(TipoAlbero a) {
  if (a == NULL)
    return 0;
  return 1 + contaNodi(a->sinistro) + contaNodi(a->destro);
}

int sommaNodi(TipoAlbero a) {
  if (a == NULL)
    return 0;
  return a->info + sommaNodi(a->sinistro) + sommaNodi(a->destro);
}

int altezza(TipoAlbero a) {        /* albero vuoto: -1; solo radice: 0  */
  int hs, hd;
  if (a == NULL)
    return -1;
  hs = altezza(a->sinistro);
  hd = altezza(a->destro);
  return 1 + (hs > hd ? hs : hd);
}

int contaFoglie(TipoAlbero a) {
  if (a == NULL)
    return 0;
  if (a->sinistro == NULL && a->destro == NULL)
    return 1;                      /* foglia: nessun figlio             */
  return contaFoglie(a->sinistro) + contaFoglie(a->destro);
}
/* <<< funzioni */

/* >>> abr */
/* Albero Binario di Ricerca (ABR): a sinistra i valori minori della
   radice, a destra quelli maggiori (o uguali).                         */
int insABR(TipoAlbero *pa, TipoInfo x) {
  if (*pa == NULL) {               /* posto trovato: creo la foglia     */
    *pa = malloc(sizeof(TipoNodoAlbero));
    if (*pa == NULL)
      return 0;
    (*pa)->info = x;
    (*pa)->sinistro = NULL;
    (*pa)->destro = NULL;
    return 1;
  }
  if (x < (*pa)->info)
    return insABR(&((*pa)->sinistro), x);
  return insABR(&((*pa)->destro), x);
}

TipoNodoAlbero *cercaABR(TipoAlbero a, TipoInfo x) {
  if (a == NULL || a->info == x)
    return a;
  if (x < a->info)
    return cercaABR(a->sinistro, x);
  return cercaABR(a->destro, x);
}
/* <<< abr */

/* >>> dealloca */
void deallocaAlbero(TipoAlbero *pa) {   /* in POSTORDINE: prima i figli */
  if (*pa != NULL) {
    deallocaAlbero(&((*pa)->sinistro));
    deallocaAlbero(&((*pa)->destro));
    free(*pa);
    *pa = NULL;
  }
}
/* <<< dealloca */

int main(void) {
  TipoAlbero a = NULL;
  int valori[] = {50, 30, 70, 20, 40, 60, 80, 35, 65};
  int i;

  for (i = 0; i < 9; i++)
    insABR(&a, valori[i]);

  printf("preordine:  "); preordine(a);  printf("\n");
  printf("inordine:   "); inordine(a);   printf("\n");
  printf("postordine: "); postordine(a); printf("\n");
  printf("nodi %d, somma %d, altezza %d, foglie %d\n",
         contaNodi(a), sommaNodi(a), altezza(a), contaFoglie(a));
  printf("cerco 65: %s, cerco 66: %s\n",
         cercaABR(a, 65) ? "si" : "no", cercaABR(a, 66) ? "si" : "no");
  deallocaAlbero(&a);
  printf("dopo dealloca: %s\n", a == NULL ? "albero vuoto" : "?");
  return 0;
}
