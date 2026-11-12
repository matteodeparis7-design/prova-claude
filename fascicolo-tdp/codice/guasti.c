/* guasti.c - Soluzione della traccia d'esame "Segnala un guasto!"
   (esempio 1 di prova scritta, A.A. immatricolazione 2025-26 e successivi)
   Compilare con:  gcc -std=c89 -pedantic -Wall guasti.c -o guasti        */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

/* >>> tipi */
#define LUNGCOD 9                  /* codice utente: 9 caratteri         */

typedef struct {
  char *descrizione;               /* stringa "esatta" (lunghezza ignota) */
  int tipologia;                   /* 1 lieve, 2 interruzione, 3 ragguard. */
  char servizio;                   /* 'R' oppure 'A'                     */
  char codiceUtente[LUNGCOD + 1];  /* 9 caratteri + '\0'                 */
  int numOrdine;                   /* numero d'ordine della chiamata     */
} TipoGuasto;

struct nodoGuasto {
  TipoGuasto info;
  struct nodoGuasto *next;
};

typedef struct nodoGuasto TipoNodoGuasto;
typedef TipoNodoGuasto *TipoListaGuasti;   /* la "tabella" dei guasti   */
/* <<< tipi */

/* >>> importanza */
int importanza(TipoGuasto g) {
  return g.tipologia * 11 - g.numOrdine;
}
/* <<< importanza */

/* >>> eser1 */
/* Restituisce il puntatore al nodo col guasto piu` importante (NULL se la
   lista e` vuota). Tramite i parametri di output *piuImp e *menoImp
   restituisce quanti guasti hanno importanza > imp e < imp.            */
TipoNodoGuasto *eser1(TipoListaGuasti lista, int imp, int *piuImp, int *menoImp) {
  TipoNodoGuasto *max = lista;     /* candidato: il primo (o NULL)      */
  TipoNodoGuasto *p;
  int i;

  *piuImp = 0;                     /* inizializzo i contatori di output */
  *menoImp = 0;
  for (p = lista; p != NULL; p = p->next) {
    i = importanza(p->info);
    if (i > imp)
      (*piuImp)++;                 /* attenzione alle parentesi!        */
    else if (i < imp)
      (*menoImp)++;
    if (i > importanza(max->info)) /* qui max != NULL perche' p != NULL */
      max = p;
  }
  return max;
}
/* <<< eser1 */

/* >>> eser2 */
/* Elimina dalla lista il guasto piu` importante.
   Restituisce 1 se ha eliminato qualcosa, 0 se la lista era vuota.     */
int eser2(TipoListaGuasti *plista) {
  TipoNodoGuasto *prec, *corr;     /* scansione                         */
  TipoNodoGuasto *precMax, *max;   /* il massimo e il suo predecessore  */

  if (*plista == NULL)
    return 0;

  precMax = NULL;
  max = *plista;
  prec = *plista;
  corr = (*plista)->next;
  while (corr != NULL) {
    if (importanza(corr->info) > importanza(max->info)) {
      max = corr;
      precMax = prec;
    }
    prec = corr;
    corr = corr->next;
  }

  if (precMax == NULL)             /* il massimo e` il primo nodo       */
    *plista = max->next;
  else
    precMax->next = max->next;     /* scavalco il nodo da eliminare     */

  free(max->info.descrizione);     /* prima la stringa allocata ...     */
  free(max);                       /* ... poi il nodo                   */
  return 1;
}
/* <<< eser2 */

/* ---- funzioni di servizio per provare la soluzione (non richieste) ---- */

/* >>> aggiungi */
/* aggiunge in testa un guasto; la descrizione viene duplicata "esattamente" */
int aggiungiGuasto(TipoListaGuasti *plista, char *descr, int tipo, char serv,
                   char *cod, int ordine) {
  TipoNodoGuasto *nuovo = malloc(sizeof(TipoNodoGuasto));
  if (nuovo == NULL)
    return 0;
  nuovo->info.descrizione = malloc(strlen(descr) + 1);   /* esatta!     */
  if (nuovo->info.descrizione == NULL) {
    free(nuovo);
    return 0;
  }
  strcpy(nuovo->info.descrizione, descr);
  nuovo->info.tipologia = tipo;
  nuovo->info.servizio = serv;
  strncpy(nuovo->info.codiceUtente, cod, LUNGCOD);
  nuovo->info.codiceUtente[LUNGCOD] = '\0';
  nuovo->info.numOrdine = ordine;
  nuovo->next = *plista;
  *plista = nuovo;
  return 1;
}
/* <<< aggiungi */

void stampaGuasti(TipoListaGuasti l) {
  for (; l != NULL; l = l->next)
    printf("  [%d] tipo %d imp %3d  %s (%c, %s)\n", l->info.numOrdine,
           l->info.tipologia, importanza(l->info), l->info.descrizione,
           l->info.servizio, l->info.codiceUtente);
}

void deallocaGuasti(TipoListaGuasti *pl) {
  TipoNodoGuasto *d;
  while (*pl != NULL) {
    d = *pl;
    *pl = (*pl)->next;
    free(d->info.descrizione);
    free(d);
  }
}

int main(void) {
  TipoListaGuasti lista = NULL;
  TipoNodoGuasto *pm;
  int piu, meno;

  /* test: lista vuota */
  pm = eser1(lista, 0, &piu, &meno);
  printf("vuota: max=%s piu=%d meno=%d\n", pm == NULL ? "NULL" : "?", piu, meno);
  printf("eser2 su vuota: %d\n", eser2(&lista));

  aggiungiGuasto(&lista, "perdita contatore", 1, 'A', "ABC123456", 1);  /* imp 10 */
  aggiungiGuasto(&lista, "caldaia ferma", 2, 'R', "XYZ987654", 2);      /* imp 20 */
  aggiungiGuasto(&lista, "odore di gas in cantina", 3, 'R', "QWE111222", 3); /* 30 */
  aggiungiGuasto(&lista, "niente acqua calda", 2, 'A', "RTY333444", 4); /* imp 18 */
  stampaGuasti(lista);

  pm = eser1(lista, 18, &piu, &meno);
  printf("eser1(imp=18): max='%s' piu=%d meno=%d\n",
         pm->info.descrizione, piu, meno);           /* 'odore..' 2 1 */

  eser2(&lista);                   /* elimina "odore di gas" (in mezzo) */
  printf("dopo eser2:\n");
  stampaGuasti(lista);
  eser2(&lista);                   /* elimina "caldaia ferma" (in mezzo) */
  eser2(&lista);                   /* elimina "niente acqua calda" (testa) */
  printf("dopo altre due eser2:\n");
  stampaGuasti(lista);
  deallocaGuasti(&lista);
  return 0;
}
