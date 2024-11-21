#include <stdlib.h>
#include <stdio.h>

#include "pgpio-lib.h"

int main(int argc, char** argv) {
  if(argc != 6) {
    printf("usage: pgpio-pulse bit data tristate polarity pulse_length\n");
    return 0;
  }
  open_mem(); //always do this first
  write_bit(gpio_data_offset, atoi(argv[1]), atoi(argv[2]));
  write_bit(gpio_direction_offset, atoi(argv[1]), atoi(argv[3]));
  write_bit(gpio_polarity_offset, atoi(argv[1]), atoi(argv[4]));
  raw_write(pulse_length_addr, atoi(argv[5]));
  raw_write(event_addr, 1);
  close_mem(); //always end with this
}
