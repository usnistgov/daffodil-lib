#include <stdlib.h>
#include <stdio.h>

#include "pgpio-lib.h"

int main(int argc, char** argv) {
  if(argc != 4) {
    printf("usage: pgpio-set bit data tristate\n");
    return 0;
  }
  open_mem(); //always do this first
  write_bit(gpio_data_offset, atoi(argv[1]), atoi(argv[2]));
  write_bit(gpio_direction_offset, atoi(argv[1]), atoi(argv[3]));
  close_mem(); //always end with this
}
