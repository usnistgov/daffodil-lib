#include <stdio.h>
#include "pgpio-lib.h"

int main() {
  open_mem();
  if(read_addr(ABI_magic_number_addr) != ABI_magic_number) {
    printf("ABI version mismatch\n");
  } else {
    printf("ABI version match\n");
  }
  close_mem();
}
