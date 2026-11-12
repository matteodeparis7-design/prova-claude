/* marmotte_albero.c - Traccia "Marmotte sull'Albero" (esempio d'esame per
   immatricolati 2024-25 e precedenti): reggimento come albero binario di
   ricerca ordinato per cognomeNome; aggiornamento del grado.
   Compilare con:  gcc -std=c89 -pedantic -Wall marmotte_albero.c          */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#define LUNGGRADO 8
#define NUMGRADI 114               /* semplice, marmotta, berretto,
                                      general0..9, mogol-00..99, GR.mogol */

char *gradi[NUMGRADI];             /* nel testo e` gia` inizializzato   */

/* >>> tipi */
typedef struct {
  char *cognomeNome;
  int associazione;
  char grado[LUNGGRADO + 1];
  int medaglie;
  int reprimende;
} TipoMarmotta;

struct nodoAlbMarmotta {
  TipoMarmotta info;
  struct nodoAlbMarmotta *sinistro, *destro;
};

typedef struct nodoAlbMarmotta TipoNodoAlbMarmotta;
typedef TipoNodoAlbMarmotta *TipoAlberoReggimento;
/* <<< tipi */

/* >>> eser2 */
/* posizione di un grado nell'array gradi (-1 se non c'e`) */
int indiceGrado(char *g) {
  int i;
  for (i = 0; i < NUMGRADI; i++)
    if (strcmp(gradi[i], g) == 0)
      return i;
  return -1;
}

/* cerca la marmotta cn nell'ABR e ne aggiorna il grado col bilancio
   medaglie - reprimende; restituisce 1 se trovata, 0 altrimenti        */
int eser2(TipoAlberoReggimento a, char *cn) {
  int c, pos;
  if (a == NULL)
    return 0;                                   /* non c'e`             */
  c = strcmp(cn, a->info.cognomeNome);
  if (c < 0)
    return eser2(a->sinistro, cn);              /* cerco a sinistra     */
  if (c > 0)
    return eser2(a->destro, cn);                /* cerco a destra       */

  /* trovata: calcolo il nuovo grado */
  pos = indiceGrado(a->info.grado);
  if (pos == -1)
    return 0;                                   /* grado non valido     */
  pos = pos + a->info.medaglie - a->info.reprimende;
  if (pos < 0)
    pos = 0;                                    /* non sotto "semplice" */
  if (pos > NUMGRADI - 1)
    pos = NUMGRADI - 1;                         /* non oltre "GR.mogol" */
  strcpy(a->info.grado, gradi[pos]);
  a->info.medaglie = 0;                         /* bilancio fatto       */
  a->info.reprimende = 0;
  return 1;
}
/* <<< eser2 */

int ins(TipoAlberoReggimento *pa, char *cn, char *grado, int med, int rep) {
  if (*pa == NULL) {
    *pa = malloc(sizeof(TipoNodoAlbMarmotta));
    if (*pa == NULL) return 0;
    (*pa)->info.cognomeNome = malloc(strlen(cn) + 1);
    strcpy((*pa)->info.cognomeNome, cn);
    (*pa)->info.associazione = 1;
    strcpy((*pa)->info.grado, grado);
    (*pa)->info.medaglie = med;
    (*pa)->info.reprimende = rep;
    (*pa)->sinistro = (*pa)->destro = NULL;
    return 1;
  }
  if (strcmp(cn, (*pa)->info.cognomeNome) < 0)
    return ins(&(*pa)->sinistro, cn, grado, med, rep);
  return ins(&(*pa)->destro, cn, grado, med, rep);
}

void dealloca(TipoAlberoReggimento *pa) {
  if (*pa != NULL) {
    dealloca(&(*pa)->sinistro);
    dealloca(&(*pa)->destro);
    free((*pa)->info.cognomeNome);
    free(*pa);
    *pa = NULL;
  }
}

int main(void) {
  TipoAlberoReggimento a = NULL;
  int i;
  static char nomi[NUMGRADI][LUNGGRADO + 1];

  /* costruzione dell'array gradi (nel testo e` gia` dato) */
  strcpy(nomi[0], "semplice"); strcpy(nomi[1], "marmotta"); strcpy(nomi[2], "berretto");
  for (i = 0; i < 10; i++) sprintf(nomi[3 + i], "general%d", i);
  for (i = 0; i < 100; i++) sprintf(nomi[13 + i], "mogol-%02d", i);
  strcpy(nomi[113], "GR.mogol");
  for (i = 0; i < NUMGRADI; i++) gradi[i] = nomi[i];

  ins(&a, "Neri Luca", "berretto", 4, 1);
  ins(&a, "Conti Leo", "marmotta", 0, 3);
  ins(&a, "Rossi Anna", "mogol-98", 9, 0);
  eser2(a, "Neri Luca");
  eser2(a, "Conti Leo");
  eser2(a, "Rossi Anna");
  printf("%s %s %s; assente: %d\n", a->info.grado, a->sinistro->info.grado,
         a->destro->info.grado, eser2(a, "Nessuno"));  /* general2 semplice GR.mogol 0 */
  dealloca(&a);
  return 0;
}
