#include <stdlib.h>
#include <stdio.h>

#include "pgpio-lib.h"

#define barrier() __asm__ __volatile__("":::"memory")

int main(int argc, char** argv) {
  if(argc != 2) {
    printf("usage: pgpio-read bit\n");
    return 0;
  }
  open_mem(); //always do this first
  write_bit(gpio_direction_offset, atoi(argv[1]), 1);
  barrier();
  printf("%d\n", read_bit(gpio_data_offset, atoi(argv[1])));
  close_mem(); //always end with this
}
