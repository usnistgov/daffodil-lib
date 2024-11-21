import ctypes
import ctypes.util

pgpio = ctypes.CDLL(ctypes.util.find_library("pgpio"))
assert pgpio.open_mem() == 0

ABI_magic_number = 0x12340001
ABI_magic_number_addr = 0x40

assert pgpio.read_addr(ABI_magic_number_addr) == ABI_magic_number

gpio_data_offset = 4096
assert ctypes.c_int.in_dll(pgpio, "gpio_data_offset").value == gpio_data_offset

# Basic read/writes to a pin (not pulsed)
pow_en_pin_1 = ctypes.c_int.in_dll(pgpio, "power_en_pin_1").value
to_write = 0

pgpio.write_bit(gpio_data_offset, pow_en_pin_1, to_write)
assert pgpio.read_bit(gpio_data_offset, pow_en_pin_1) == to_write

to_write = 1
pgpio.write_bit(gpio_data_offset, pow_en_pin_1, to_write)
assert pgpio.read_bit(gpio_data_offset, pow_en_pin_1) == to_write
pgpio.close_mem()