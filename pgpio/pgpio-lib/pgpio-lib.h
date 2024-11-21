#include <stdint.h>

extern int col_en_base;
extern int col_en_cnt;
extern int row_en_base;
extern int row_en_cnt;
extern int dac_reset_n_pin;
extern int dac_pd_pin;
extern int dac_clr_n_pin;
extern int dac_busy_n_pin;
extern int dac_ldac_n_base;
extern int dac_ldac_n_cnt;
extern int ca_base;
extern int ca_cnt;
extern int ra_base;
extern int ra_cnt;
extern int en_in_c_pin;
extern int et_mode_r_pin;
extern int write_mode_r_pin;
extern int compliance_control_lo_pin;
extern int array_control_lsb_lo_pin;
extern int array_control_msb_lo_pin;
extern int ext_mode_G_pin;
extern int write_mode_G_pin;
extern int EN_IO_G_pin;
extern int ext_mode_R_pin;
extern int write_mode_R_pin;
extern int EN_IO_R_pin;
extern int ext_mode_C_pin;
extern int write_mode_C_pin;
extern int EN_IO_C_pin;
extern int power_en_pin;
extern int power_en_pin_1;
extern int power_en_pin_2;

extern int gpio_data_offset;
extern int gpio_direction_offset;
extern int gpio_pulse_mode_offset;
extern int gpio_polarity_offset;
extern int gpio_hw_ctl_offset;
extern int gpio_input_offset;

extern int set_command_offset;
extern int reset_command_offset;

extern int sw_eigenvector_offset;
extern int sr_debug_input_offset;

extern int event_addr;
extern int pulse_length_addr;
extern int pulse_count_addr;
extern int num_bits_addr;
extern int timer_addr;
extern int mux_select_addr;
extern int command_length_addr;
extern int sw_vector_valid_addr;
extern int sw_vector_ready_addr;
extern int vector_hw_ctl_addr;
extern int ABI_magic_number_addr;
extern int ABI_magic_number;

extern int open_mem();
extern void close_mem();

extern int init();

extern inline void raw_write(unsigned int, uint32_t);
extern inline void masked_write(unsigned int, uint32_t, uint32_t);
extern inline void write_bit(unsigned int, unsigned int, unsigned int);
extern inline void write_bit_range_raw(unsigned int, unsigned int, unsigned int, unsigned int);
extern void write_bit_range(unsigned int, unsigned int, unsigned int, unsigned int);

extern inline uint32_t read_addr(unsigned int);
extern inline int read_bit_raw(unsigned int, unsigned int);
extern inline int read_bit(unsigned int, unsigned int);

extern int read_int(char*);
extern void write_int(char*, int);
