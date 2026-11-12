/* marmotte.c - Soluzione della traccia d'esame "Giovani Marmotte"
   (esempi 2 e 3 di prova scritta, A.A. immatricolazione 2025-26 e successivi)
   Compilare con:  gcc -std=c89 -pedantic -Wall marmotte.c -o marmotte    */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* >>> tipi */
#define LUNGGRADO 8

typedef struct {
  char *cognomeNome;               /* stringa esatta                    */
  int associazione;                /* anni di presenza nel reggimento   */
  char grado[LUNGGRADO + 1];       /* 8 caratteri + '\0'                */
  int medaglie;
  int reprimende;
} TipoMarmotta;

struct nodoMarmotta {
  TipoMarmotta info;
  struct nodoMarmotta *next;
};

typedef struct nodoMarmotta TipoNodoMarmotta;
typedef TipoNodoMarmotta *TipoReggimento;
/* <<< tipi */

/* >>> eser1 */
/* Restituisce quante marmotte hanno grado rank; in *mediaMed e *mediaRep
   le medie (intere) di medaglie e reprimende di quelle marmotte.
   Se non ce ne sono, le medie valgono 0 (evito la divisione per zero). */
int eser1(TipoReggimento gm, char *rank, int *mediaMed, int *mediaRep) {
  int quante = 0, sommaMed = 0, sommaRep = 0;

  while (gm != NULL) {
    if (strcmp(gm->info.grado, rank) == 0) {
      quante++;
      sommaMed += gm->info.medaglie;
      sommaRep += gm->info.reprimende;
    }
    gm = gm->next;
  }
  if (quante > 0) {
    *mediaMed = sommaMed / quante;     /* divisione intera: media intera */
    *mediaRep = sommaRep / quante;
  } else {
    *mediaMed = 0;
    *mediaRep = 0;
  }
  return quante;
}
/* <<< eser1 */

/* >>> eser2 */
/* Inserisce una nuova marmotta mantenendo l'ordine crescente di cognomeNome.
   Restituisce 1 se l'inserimento riesce, 0 se manca memoria.           */
int eser2(TipoReggimento *pgm, char *cn, int ass, char *grado,
          int med, int rep) {
  TipoNodoMarmotta *nuovo, *prec, *corr;

  /* 1. creo e riempio il nuovo nodo */
  nuovo = malloc(sizeof(TipoNodoMarmotta));
  if (nuovo == NULL)
    return 0;
  nuovo->info.cognomeNome = malloc(strlen(cn) + 1);
  if (nuovo->info.cognomeNome == NULL) {
    free(nuovo);
    return 0;
  }
  strcpy(nuovo->info.cognomeNome, cn);
  nuovo->info.associazione = ass;
  strncpy(nuovo->info.grado, grado, LUNGGRADO);
  nuovo->info.grado[LUNGGRADO] = '\0';
  nuovo->info.medaglie = med;
  nuovo->info.reprimende = rep;

  /* 2. cerco la posizione: il primo nodo con cognomeNome >= cn */
  prec = NULL;
  corr = *pgm;
  while (corr != NULL && strcmp(corr->info.cognomeNome, cn) < 0) {
    prec = corr;
    corr = corr->next;
  }

  /* 3. aggancio */
  nuovo->next = corr;
  if (prec == NULL)
    *pgm = nuovo;                  /* nuova testa                       */
  else
    prec->next = nuovo;
  return 1;
}
/* <<< eser2 */

/* >>> eser3 */
/* Versione ricorsiva: quante marmotte di grado rank nel reggimento gm */
int eser3(TipoReggimento gm, char *rank) {
  if (gm == NULL)                                  /* caso base         */
    return 0;
  if (strcmp(gm->info.grado, rank) == 0)           /* caso ricorsivo 1  */
    return 1 + eser3(gm->next, rank);
  return eser3(gm->next, rank);                    /* caso ricorsivo 2  */
}
/* <<< eser3 */

void stampaReggimento(TipoReggimento gm) {
  for (; gm != NULL; gm = gm->next)
    printf("  %-20s %-8s anni %d  med %d  rep %d\n", gm->info.cognomeNome,
           gm->info.grado, gm->info.associazione, gm->info.medaglie,
           gm->info.reprimende);
}

void deallocaReggimento(TipoReggimento *pgm) {
  TipoNodoMarmotta *d;
  while (*pgm != NULL) {
    d = *pgm;
    *pgm = (*pgm)->next;
    free(d->info.cognomeNome);
    free(d);
  }
}

int main(void) {
  TipoReggimento gm = NULL;
  int n, mm, mr;

  n = eser1(gm, "berretto", &mm, &mr);
  printf("vuoto: %d marmotte, medie %d %d; ricorsiva: %d\n", n, mm, mr,
         eser3(gm, "berretto"));

  eser2(&gm, "Neri Luca", 3, "berretto", 4, 1);
  eser2(&gm, "Rossi Anna", 2, "marmotta", 1, 0);
  eser2(&gm, "Bianchi Ugo", 3, "berretto", 7, 2);
  eser2(&gm, "Amato Sara", 9, "general5", 10, 0);   /* in testa          */
  eser2(&gm, "Verdi Ida", 1, "semplice", 0, 9); /* in coda           */
  eser2(&gm, "Conti Leo", 4, "berretto", 2, 6);
  stampaReggimento(gm);

  n = eser1(gm, "berretto", &mm, &mr);
  printf("berretto: %d marmotte, media medaglie %d, media reprimende %d\n",
         n, mm, mr);                               /* 3, 13/3=4, 9/3=3  */
  printf("ricorsiva berretto: %d, general5: %d, mogol-00: %d\n",
         eser3(gm, "berretto"), eser3(gm, "general5"), eser3(gm, "mogol-00"));
  deallocaReggimento(&gm);
  return 0;
}
