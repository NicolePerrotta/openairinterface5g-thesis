#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <pthread.h>
#include <signal.h>
#include "database.h"
#include "event.h"
#include "handler.h"
#include "logger/logger.h"
#include "utils.h"
#include "event_selector.h"
#include "config.h"

/* this function sends the activated traces to the nr-softmodem */
void activate_traces(int socket, int number_of_events, int *is_on)
{
  char t = 1;
  if (socket_send(socket, &t, 1) == -1 ||
      socket_send(socket, &number_of_events, sizeof(int)) == -1 ||
      socket_send(socket, is_on, number_of_events * sizeof(int)) == -1)
    abort();
}

void usage(void)
{
  printf(
"options:\n"
"    -d <database file>        this option is mandatory\n"
"    -ip <host>                connect to given IP address (default %s)\n"
"    -p <port>                 connect to given port (default %d)\n",
  DEFAULT_REMOTE_IP,
  DEFAULT_REMOTE_PORT
  );
  exit(1);
}

int main(int n, char **v)
{
  char *database_filename = NULL;
  void *database;
  char *ip = DEFAULT_REMOTE_IP;
  int port = DEFAULT_REMOTE_PORT;
  int *is_on;
  int number_of_events;
  int i;
  int socket;
  int ldpc_ok_id;
  database_event_format f;
  int segment;
  int nb_segments;
  int offset;
  int data;

  /* write on a socket fails if the other end is closed and we get SIGPIPE */
  if (signal(SIGPIPE, SIG_IGN) == SIG_ERR) abort();

  /* parse command line options */
  for (i = 1; i < n; i++) {
    if (!strcmp(v[i], "-h") || !strcmp(v[i], "--help")) usage();
    if (!strcmp(v[i], "-d"))
      { if (i > n-2) usage(); database_filename = v[++i]; continue; }
    if (!strcmp(v[i], "-ip")) { if (i > n-2) usage(); ip = v[++i]; continue; }
    if (!strcmp(v[i], "-p"))
      { if (i > n-2) usage(); port = atoi(v[++i]); continue; }
    usage();
  }

  if (database_filename == NULL) {
    printf("ERROR: provide a database file (-d)\n");
    exit(1);
  }

  /* load the database T_messages.txt */
  database = parse_database(database_filename);
  load_config_file(database_filename);

  /* an array of int for all the events defined in the database is needed */
  number_of_events = number_of_ids(database);
  is_on = calloc(number_of_events, sizeof(int));
  if (is_on == NULL) abort();

  /* activate the LDPC_OK trace in this array */
  on_off(database, "LDPC_OK", is_on, 1);

  /* connect to the nr-softmodem */
  socket = connect_to(ip, port);

  /* activate the trace LDPC_OK in the nr-softmodem */
  activate_traces(socket, number_of_events, is_on);

  free(is_on);
  /* get the format of the LDPC_OK trace */
  ldpc_ok_id = event_id_from_name(database, "LDPC_OK");
  f = get_format(database, ldpc_ok_id);

/* this macro looks for a particular element and checks its type */
#define G(var_name, var_type, var) \
  if (!strcmp(f.name[i], var_name)) { \
    if (strcmp(f.type[i], var_type)) { printf("bad type for %s\n", var_name); exit(1); } \
    var = i; \
    continue; \
  }
  /* get the elements of the LDPC_OK trace
   * the value is an index in the event, see below
   */
  for (i = 0; i < f.count; i++) {
    G("segment",     "int",    segment);
    G("nb_segments", "int",    nb_segments);
    G("offset",      "int",    offset);
    G("data",        "buffer", data);
  }

  /* a buffer needed to receive events from the nr-softmodem */
  OBUF ebuf = { .osize = 0, .omaxsize = 0, .obuf = NULL };

  /* read events */
  while (1) {
    event e;
    e = get_event(socket, &ebuf, database);
    if (e.type == -1) break;
    if (e.type == ldpc_ok_id) {
      /* this is how to access the elements of the LDPC_OK trace.
       * we use e.e[<element>] and then the correct suffix, here
       * it's .i for the integer and .b for the buffer and .bsize
       * for the buffer size
       * see in event.h the structure event_arg
       */
      unsigned char *buf = e.e[data].b;
      printf("get LDPC_OK event segment %d nb_segments %d offset %d buffer length %d = [",
             e.e[segment].i,
             e.e[nb_segments].i,
             e.e[offset].i,
             e.e[data].bsize);
      for (i = 0; i < e.e[data].bsize; i++)
        printf(" %2.2x", buf[i]);
      printf("]\n");
    }
  }

  return 0;
}