/* officina.c - Traccia d'esercitazione B ("Officina"),
   scritta sul modello delle prove d'esame del corso.
   Compilare con:  gcc -std=c89 -pedantic -Wall officina.c -o officina    */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* >>> tipi */
#define LUNGTARGA 7

typedef struct {
  char targa[LUNGTARGA + 1];
  char *descrizione;               /* stringa esatta                    */
  double costo;
  int ore;
  char stato;                      /* 'A' aperta, 'C' chiusa            */
} TipoRiparazione;

struct nodoRip {
  TipoRiparazione info;
  struct nodoRip *next;
};

typedef struct nodoRip TipoNodoRip;
typedef TipoNodoRip *TipoListaRip;
/* <<< tipi */

/* >>> eser1 */
/* restituisce il numero di riparazioni aperte; in *costoAperte il loro
   costo totale e in *oreMedie la media (reale) delle loro ore          */
int eser1(TipoListaRip l, double *costoAperte, double *oreMedie) {
  int aperte = 0, oreTot = 0;
  *costoAperte = 0;
  for (; l != NULL; l = l->next)
    if (l->info.stato == 'A') {
      aperte++;
      *costoAperte += l->info.costo;
      oreTot += l->info.ore;
    }
  if (aperte > 0)
    *oreMedie = (double) oreTot / aperte;
  else
    *oreMedie = 0;
  return aperte;
}
/* <<< eser1 */

/* >>> eser2 */
/* aggiunge in CODA una nuova riparazione aperta, ma solo se per quella
   targa non c'e` gia` una riparazione aperta.
   Restituisce 1 se aggiunta, 0 se gia` presente, -1 se manca memoria.   */
int eser2(TipoListaRip *pl, char *targa, char *descr, double costo, int ore) {
  TipoNodoRip rg, *p, *nuovo;

  rg.next = *pl;
  p = &rg;
  while (p->next != NULL) {        /* scorro fino all'ultimo nodo e     */
    if (strcmp(p->next->info.targa, targa) == 0 && p->next->info.stato == 'A')
      return 0;                    /* intanto controllo i duplicati     */
    p = p->next;
  }
  nuovo = malloc(sizeof(TipoNodoRip));
  if (nuovo == NULL)
    return -1;
  nuovo->info.descrizione = malloc(strlen(descr) + 1);
  if (nuovo->info.descrizione == NULL) {
    free(nuovo);
    return -1;
  }
  strcpy(nuovo->info.descrizione, descr);
  strncpy(nuovo->info.targa, targa, LUNGTARGA);
  nuovo->info.targa[LUNGTARGA] = '\0';
  nuovo->info.costo = costo;
  nuovo->info.ore = ore;
  nuovo->info.stato = 'A';
  nuovo->next = NULL;
  p->next = nuovo;                 /* p e` l'ultimo (o il RG)           */
  *pl = rg.next;
  return 1;
}
/* <<< eser2 */

/* >>> eser3 */
/* ricorsiva: costo totale di tutte le riparazioni (aperte o chiuse) di una targa */
double eser3(TipoListaRip l, char *targa) {
  if (l == NULL)
    return 0;
  if (strcmp(l->info.targa, targa) == 0)
    return l->info.costo + eser3(l->next, targa);
  return eser3(l->next, targa);
}
/* <<< eser3 */

void dealloca(TipoListaRip *pl) {
  TipoNodoRip *d;
  while (*pl != NULL) {
    d = *pl;
    *pl = d->next;
    free(d->info.descrizione);
    free(d);
  }
}

int main(void) {
  TipoListaRip l = NULL;
  double costo, oreMed;
  int n;

  printf("%d ", eser2(&l, "AB123CD", "tagliando", 120.0, 2));
  printf("%d ", eser2(&l, "EF456GH", "freni", 300.0, 5));
  printf("%d ", eser2(&l, "AB123CD", "gomme", 250.0, 1));    /* 0: dup */
  l->info.stato = 'C';                                        /* chiudo la 1a */
  printf("%d ", eser2(&l, "AB123CD", "gomme", 250.0, 1));    /* ora si`  */
  printf("%d\n", eser2(&l, "IL789MN", "frizione", 800.0, 8));
  n = eser1(l, &costo, &oreMed);
  printf("aperte %d, costo %.2f, ore medie %.2f\n", n, costo, oreMed);
  printf("totale AB123CD: %.2f\n", eser3(l, "AB123CD"));     /* 370.00 */
  dealloca(&l);
  return 0;
}
