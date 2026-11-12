/* biblioteca.c - Traccia d'esercitazione A ("Biblioteca di quartiere"),
   scritta sul modello delle prove d'esame del corso.
   Compilare con:  gcc -std=c89 -pedantic -Wall biblioteca.c -o biblioteca */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* >>> tipi */
#define LUNGISBN 13

typedef struct {
  char *titolo;                    /* stringa esatta                    */
  char isbn[LUNGISBN + 1];
  int anno;
  int copie;                       /* copie disponibili                 */
  char genere;                     /* 'R' romanzo, 'S' saggio, 'F' fumetto */
} TipoLibro;

struct nodoLibro {
  TipoLibro info;
  struct nodoLibro *next;
};

typedef struct nodoLibro TipoNodoLibro;
typedef TipoNodoLibro *TipoCatalogo;
/* <<< tipi */

/* >>> eser1 */
/* restituisce il puntatore al libro piu` vecchio (NULL se catalogo vuoto);
   in *prima: quanti libri sono stati pubblicati prima di anno;
   in *totCopie: il totale delle copie disponibili                       */
TipoNodoLibro *eser1(TipoCatalogo c, int anno, int *prima, int *totCopie) {
  TipoNodoLibro *vecchio = c;
  *prima = 0;
  *totCopie = 0;
  while (c != NULL) {
    if (c->info.anno < anno)
      (*prima)++;
    *totCopie += c->info.copie;
    if (c->info.anno < vecchio->info.anno)
      vecchio = c;
    c = c->next;
  }
  return vecchio;
}
/* <<< eser1 */

/* >>> eser2 */
/* elimina TUTTI i libri con 0 copie; restituisce quanti ne ha eliminati.
   Uso il record generatore: cosi` anche il primo nodo ha un "precedente". */
int eser2(TipoCatalogo *pc) {
  TipoNodoLibro rg, *prec, *daEliminare;
  int eliminati = 0;

  rg.next = *pc;
  prec = &rg;
  while (prec->next != NULL) {
    if (prec->next->info.copie == 0) {
      daEliminare = prec->next;
      prec->next = daEliminare->next;   /* scavalco                     */
      free(daEliminare->info.titolo);
      free(daEliminare);
      eliminati++;                       /* NON avanzo prec: il nuovo    */
    } else                               /* prec->next va ancora controllato */
      prec = prec->next;
  }
  *pc = rg.next;
  return eliminati;
}
/* <<< eser2 */

int aggiungiLibro(TipoCatalogo *pc, char *titolo, char *isbn, int anno,
                  int copie, char genere) {
  TipoNodoLibro *n = malloc(sizeof(TipoNodoLibro));
  if (n == NULL) return 0;
  n->info.titolo = malloc(strlen(titolo) + 1);
  if (n->info.titolo == NULL) { free(n); return 0; }
  strcpy(n->info.titolo, titolo);
  strncpy(n->info.isbn, isbn, LUNGISBN);
  n->info.isbn[LUNGISBN] = '\0';
  n->info.anno = anno;
  n->info.copie = copie;
  n->info.genere = genere;
  n->next = *pc;
  *pc = n;
  return 1;
}

void stampaCatalogo(TipoCatalogo c) {
  for (; c != NULL; c = c->next)
    printf("  %-28s %d  copie %d\n", c->info.titolo, c->info.anno, c->info.copie);
}

void deallocaCatalogo(TipoCatalogo *pc) {
  TipoNodoLibro *d;
  while (*pc != NULL) {
    d = *pc;
    *pc = d->next;
    free(d->info.titolo);
    free(d);
  }
}

int main(void) {
  TipoCatalogo c = NULL;
  TipoNodoLibro *v;
  int prima, tot;

  aggiungiLibro(&c, "Il nome della rosa", "9788845292613", 1980, 0, 'R');
  aggiungiLibro(&c, "Linguaggio C", "9788838668227", 2007, 2, 'S');
  aggiungiLibro(&c, "I promessi sposi", "9788804668237", 1827, 0, 'R');
  aggiungiLibro(&c, "Fumetto a caso", "9781234567897", 2019, 5, 'F');
  aggiungiLibro(&c, "Strutture dati in C", "9788887331123", 2004, 0, 'S');
  stampaCatalogo(c);

  v = eser1(c, 2000, &prima, &tot);
  printf("piu` vecchio: %s; prima del 2000: %d; copie: %d\n",
         v->info.titolo, prima, tot);             /* promessi sposi 2 7 */
  printf("eliminati: %d\n", eser2(&c));           /* 3                 */
  stampaCatalogo(c);
  deallocaCatalogo(&c);
  return 0;
}
