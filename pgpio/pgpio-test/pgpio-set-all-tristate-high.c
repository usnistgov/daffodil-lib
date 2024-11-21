#include "pgpio-lib.h"

int main() {
  open_mem(); //always do this first
  write_bit_range(gpio_direction_offset, 0, 96, 1); //write bits [0, 96) to value one
  close_mem(); //always end with this
}
