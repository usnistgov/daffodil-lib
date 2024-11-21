#include <stdio.h>
#include <sys/mman.h>
#include <stdlib.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>

#include <errno.h>
#include <string.h>

#include <stdint.h>

#include "pgpio-lib.h"

#define barrier() __asm__ __volatile__("":::"memory")

#define BIT(n) 1 << n

//#define KERNEL_BYTE 0
//#define MUX_BYTE 4
//#define EVENT_BYTE 8

static int fd;
static volatile uint32_t* regs;

int col_en_base = 46;
int col_en_cnt = 25;
int row_en_base = 71;
int row_en_cnt = 25;
int dac_reset_n_pin_base = 40;
int dac_reset_n_pin_cnt = 5;
int dac_pd_pin_base = 4;
int dac_pd_pin_cnt = 1;
int dac_clr_n_pin_base = 5;
int dac_clr_n_pin_cnt = 5;
int dac_busy_n_pin = 39;
int dac_sync_n_pin_base = 10;
int dac_sync_n_pin_cnt = 5;
int dac_ldac_n_pin_base = 15;
int dac_ldac_n_pin_cnt = 5;
int ca_base = 37;
int ca_cnt = 2;
int ra_base = 35;
int ra_cnt = 2;
int en_in_c_pin = 34;
int et_mode_r_pin = 33;
int write_mode_r_pin = 32;
int compliance_control_lo_pin = 31;
int array_control_lsb_lo_pin = 30;
int array_control_msb_lo_pin = 29;
int ext_mode_G_pin = 28;
int write_mode_G_pin = 27;
int EN_IO_G_pin = 26;
int ext_mode_R_pin = 25;
int write_mode_R_pin = 24;
int EN_IO_R_pin = 23;
int ext_mode_C_pin = 22;
int write_mode_C_pin = 21;
int EN_IO_C_pin = 20;

int power_en_pin = 0; // daffodil 1
int power_en_pin_1 = 1; // daffodil 2
int power_en_pin_2 = 2; // daffodil 2

int gpio_data_offset = 0x1000;
int gpio_direction_offset = 0x2000;
int gpio_pulse_mode_offset = 0x3000;
int gpio_polarity_offset = 0x4000;
int gpio_hw_ctl_offset = 0x5000;
int gpio_input_offset = 0x6000;

int set_command_offset = 0x7000;
int reset_command_offset = 0x8000;

int sw_eigenvector_offset = 0x9000;
int sr_debug_input_offset = 0xA000;

int event_addr = 0x0;
int pulse_length_addr = 0x4;
int pulse_count_addr = 0x8;
int num_bits_addr = 0xC;
int timer_addr = 0x10;
int mux_select_addr = 0x14;
int command_length_addr = 0x20;
int sw_vector_valid_addr = 0x30;
int sw_vector_ready_addr = 0x34;
int vector_hw_ctl_addr = 0x38;
int ABI_magic_number_addr = 0x40;

int ABI_magic_number = 0x12340001;

int *read_files;
int *write_files;
int read_file_p;
int write_file_p;
char *tmp_static;

int open_write_file(char* fname) {
  int fd = open(fname, O_WRONLY);
  write_files[write_file_p++] = fd;
  return write_file_p - 1;
}

int open_read_file(char* fname) {
  int fd = open(fname, O_RDONLY);
  read_files[read_file_p++] = fd;
  return read_file_p - 1;
}
int read_static_file(int fnum) {
  lseek(read_files[fnum], 0, SEEK_SET);
  read(read_files[fnum], tmp_static, 8);
  return atoi(tmp_static);
}

void write_static_file(int fnum, int value) {
  sprintf(tmp_static, "%d\0", value);
  write(write_files[fnum], tmp_static, strlen(tmp_static));
  fsync(write_files[fnum]);
}

int read_int(char* fname) {
  int fd = open(fname, O_RDONLY);
  char* tmp = malloc(8);
  read(fd, tmp, 8);
//  printf("%s\n", tmp);
  close(fd);
  return atoi(tmp);
}

void write_int(char* fname, int value) {
  int fd = open(fname, O_WRONLY);
  char* tmp = malloc(8);
  sprintf(tmp, "%d\0", value);
  write(fd, tmp, strlen(tmp));
  fsync(fd);
  close(fd);
}

int open_mem() {
  if(regs) {
    return;
  }
//  fd = open("/dev/pgpio", O_RDWR);
  fd = open("/dev/mem", O_RDWR);
  if(fd<0) {
    printf("Error: %s\n", strerror(errno));
    return errno;
  }
  regs = (uint32_t*) mmap(0, 0x10000, PROT_READ | PROT_WRITE, MAP_SHARED, fd, 0x41010000); //0x00000000 additional offset, there is still the offset from the device tree
  printf("virtual addr: %d\n", regs);
  if(regs == NULL) {
    printf("Error: %s\n", strerror(errno));
    return errno;
  }
  return 0;
}

int open_test() {
  regs = (uint32_t*) malloc(4 * 0x10000);
  if(regs == NULL) {
    printf("Error: %s\n", strerror(errno));
    return errno;
  }
  return 0;
}

uint32_t* get_regs() {
  return regs;
}

void close_mem() {
  munmap(regs, 0x10000);
  close(fd);
}

int init() {
  read_files = malloc(sizeof(int) * 28);
  write_files = malloc(sizeof(int) * 240);
  read_file_p = 0;
  write_file_p = 0;
  tmp_static = malloc(8);

  if(read_addr(ABI_magic_number_addr) != ABI_magic_number) {
    printf("ABI version mismatch\n");
  }
  raw_write(gpio_data_offset + 0, 0x00000000);
  raw_write(gpio_data_offset + 4, 0x00000000);
  raw_write(gpio_data_offset + 8, 0x00000000);

  
  write_bit(gpio_data_offset, dac_ldac_n_pin_base+0, 1);
  write_bit(gpio_data_offset, dac_ldac_n_pin_base+1, 1);
  write_bit(gpio_data_offset, dac_ldac_n_pin_base+2, 1);
  write_bit(gpio_data_offset, dac_ldac_n_pin_base+3, 1);
  write_bit(gpio_data_offset, dac_ldac_n_pin_base+4, 1);
  
  write_bit(gpio_data_offset, dac_pd_pin_base, 0);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+0, 0);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+1, 0);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+2, 0);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+3, 0);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+4, 0);

  // delay, can be replaced by time-based delay
  write_bit(gpio_data_offset, dac_pd_pin_base, 0);

  write_bit(gpio_data_offset, dac_reset_n_pin_base+0, 0);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+1, 0);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+2, 0);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+3, 0);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+4, 0);

  write_bit(gpio_data_offset, dac_clr_n_pin_base+0, 1);
  write_bit(gpio_data_offset, dac_clr_n_pin_base+1, 1);
  write_bit(gpio_data_offset, dac_clr_n_pin_base+2, 1);
  write_bit(gpio_data_offset, dac_clr_n_pin_base+3, 1);
  write_bit(gpio_data_offset, dac_clr_n_pin_base+4, 1);

  raw_write(gpio_direction_offset + 0, 0x00000000);
  raw_write(gpio_direction_offset + 4, 0x00000000);
  raw_write(gpio_direction_offset + 8, 0x00000000);

  raw_write(gpio_pulse_mode_offset + 0, 0x00000000);
  raw_write(gpio_pulse_mode_offset + 4, 0x00000000);
  raw_write(gpio_pulse_mode_offset + 8, 0x00000000);

  raw_write(gpio_polarity_offset + 0, 0x00000000);
  raw_write(gpio_polarity_offset + 4, 0x00000000);
  raw_write(gpio_polarity_offset + 8, 0x00000000);

  raw_write(gpio_hw_ctl_offset + 0, 0x00000000);
  raw_write(gpio_hw_ctl_offset + 4, 0x00000000);
  raw_write(gpio_hw_ctl_offset + 8, 0x00000000);


  write_bit_range(gpio_pulse_mode_offset, col_en_base, col_en_base + col_en_cnt, 1);
  write_bit_range(gpio_polarity_offset, col_en_base, col_en_base + col_en_cnt, 1);
  write_bit_range(gpio_pulse_mode_offset, row_en_base, row_en_base + row_en_cnt, 1);
  write_bit_range(gpio_polarity_offset, row_en_base, row_en_base + row_en_cnt, 1);

  write_bit(gpio_data_offset, power_en_pin, 1);
  write_bit(gpio_data_offset, power_en_pin_1, 1);
  write_bit(gpio_data_offset, power_en_pin_2, 1);


  write_bit(gpio_data_offset, dac_reset_n_pin_base+0, 1);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+1, 1);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+2, 1);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+3, 1);
  write_bit(gpio_data_offset, dac_reset_n_pin_base+4, 1);

  write_bit(gpio_data_offset, dac_sync_n_pin_base+0, 1);
  write_bit(gpio_data_offset, dac_sync_n_pin_base+1, 1);
  write_bit(gpio_data_offset, dac_sync_n_pin_base+2, 1);
  write_bit(gpio_data_offset, dac_sync_n_pin_base+3, 1);
  write_bit(gpio_data_offset, dac_sync_n_pin_base+4, 1);

  write_bit(gpio_data_offset, dac_clr_n_pin_base+0, 1);
  write_bit(gpio_data_offset, dac_clr_n_pin_base+1, 1);
  write_bit(gpio_data_offset, dac_clr_n_pin_base+2, 1);
  write_bit(gpio_data_offset, dac_clr_n_pin_base+3, 1);
  write_bit(gpio_data_offset, dac_clr_n_pin_base+4, 1);

  write_bit(gpio_data_offset, dac_ldac_n_pin_base+0, 1);
  write_bit(gpio_data_offset, dac_ldac_n_pin_base+1, 1);
  write_bit(gpio_data_offset, dac_ldac_n_pin_base+2, 1);
  write_bit(gpio_data_offset, dac_ldac_n_pin_base+3, 1);
  write_bit(gpio_data_offset, dac_ldac_n_pin_base+4, 1);


  raw_write(pulse_length_addr, 5); //default to something other than 0
  raw_write(command_length_addr, 5); //I think there are 5 dacs


/*
  // also set up read/write mask + pulse mask
  write_bit_range(gpio_direction_offset, col_en_base, col_en_base + col_en_cnt, 1);
  write_bit_range(gpio_pulse_mode_offset, col_en_base, col_en_base + col_en_cnt, 1);
  write_bit_range(gpio_polarity_offset, col_en_base, col_en_base + col_en_cnt, 1);
  write_bit_range(gpio_hw_ctl_offset, col_en_base, col_en_base + col_en_cnt, 1);

  write_bit_range(gpio_direction_offset, row_en_base, row_en_base + row_en_cnt, 1);
  write_bit_range(gpio_pulse_mode_offset, row_en_base, row_en_base + row_en_cnt, 1);
  write_bit_range(gpio_polarity_offset, row_en_base, row_en_base + row_en_cnt, 1);
  write_bit_range(gpio_hw_ctl_offset, row_en_base, row_en_base + row_en_cnt, 1);


  raw_write(set_command_offset + 0,  0b00000111000000000000000000000000); //For now just fill in blank commands, we'll work out the details later
  raw_write(set_command_offset + 4,  0b00001000000000000000000000000000);
  raw_write(set_command_offset + 8,  0b00001001000000000000000000000000);
  raw_write(set_command_offset + 12, 0b00001010000000000000000000000000);
  raw_write(set_command_offset + 16, 0b00001011000000000000000000000000);

  raw_write(reset_command_offset + 0,  0b00000111000000000000000000000000);
  raw_write(reset_command_offset + 4,  0b00001000000000000000000000000000);
  raw_write(reset_command_offset + 8,  0b00001001000000000000000000000000);
  raw_write(reset_command_offset + 12, 0b00001010000000000000000000000000);
  raw_write(reset_command_offset + 16, 0b00001011000000000000000000000000);
*/
  return 0;
}

inline void raw_write(unsigned int addr, uint32_t data) {
  regs[addr/4] = data;
}

inline void masked_write(unsigned int addr, uint32_t write_mask, uint32_t data) {
  uint32_t tmp = regs[addr/4];
  barrier();
  regs[addr/4] = (tmp & ~write_mask) | (data & write_mask);
}

inline void write_bit(unsigned int addr, unsigned int bit, unsigned int value) {
  masked_write(addr + ((bit/32) * 4), BIT(bit % 32), value << (bit % 32));
}

inline void write_bit_range_raw(unsigned int addr, unsigned int low_bit, unsigned int high_bit, unsigned int value) { //low_bit is the lowest bit to write, high_bit is the lowest bit NOT to write
  uint32_t mask = (1ULL << high_bit) - (1ULL << low_bit);
  uint32_t data = 0 - value; //all 0s for 0, all 1s for 1
  masked_write(addr, mask, data);
}

void write_bit_range(unsigned int addr, unsigned int low_bit, unsigned int high_bit, unsigned int value) { //low_bit is the lowest bit to write, high_bit is the lowest bit NOT to write, addr points to base address
  if(high_bit < low_bit) {
    return;
  }
  int low_offset = low_bit/32;
  int high_offset = high_bit/32;
  if(low_offset == high_offset) {
    write_bit_range_raw(addr + low_offset * 4, low_bit - 32*low_offset, high_bit - 32*low_offset, value);
    return;
  }
  write_bit_range_raw(addr + low_offset * 4, low_bit - 32*low_offset, 32, value);
  for(int i = low_offset + 1; i<high_offset; i++) {
    masked_write(addr + i * 4, -1, -value); //write full 32 bits (-1 is all 1s)
  }
  write_bit_range_raw(addr + high_offset * 4, 0, high_bit - 32*high_offset, value);
  return;
}

inline uint32_t read_addr(unsigned int addr) {
  return regs[addr/4];
}

inline int read_bit_raw(unsigned int addr, unsigned int bit) {
  return (read_addr(addr) >> bit) & 1u; //only get the LSB after shift, 1u is unsigned 1
}

inline int read_bit(unsigned int addr, unsigned int bit) {
  return read_bit_raw(addr + 4 * (bit / 32), bit%32);
}
