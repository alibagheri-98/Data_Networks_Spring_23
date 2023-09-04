class CRC:
    """Compute CRC of given `data` due to `divisor` polynomial."""
    def __init__(self, divisor:int) -> None:
        """get divisor polynomial.
            `divisor`: [int] irreducable divisor polynomial"""
        self.divisor = divisor
        self.divisor_len = divisor.bit_length()-1

    def encode(self, data, data_len):
        """get `data` and compute CRC encoded data.
            `data_len`: packet size"""
        num = data<<(self.divisor_len)  # add 0s
        rem = self.div_remainder(num, data_len+self.divisor_len)
        return num | rem, data_len+self.divisor_len

    def decode(self, data, data_len):
        """CRC checker. if packet is valid return `original data, True` and if not return `0, False`"""
        rem = self.div_remainder(data, data_len)
        if rem == 0:
            return (data>>self.divisor_len), data_len-self.divisor_len, True
        return 0, 0, False

    def div_remainder(self, num, num_len):
        """divide `num` by `divisor` in modulo 2"""
        shift_ind = num_len-self.divisor_len
        denum = self.divisor<<(shift_ind-1)  # align divisor to data MSB 1
        indicator = 1<<(num_len-1)
        # Shift
        for i in range(shift_ind):
            # print(i)
            if (indicator & num) == 0:
                num <<= 1
                continue
            num = num ^ denum
            num <<= 1

        remainder = num >>(shift_ind)
        return remainder


if __name__ == '__main__':
    divisor = 0xB
    crc = CRC(divisor)

    data = 0xAB23FF23412524527465262
    data_len = data.bit_length()

    print(f'Raw     data: {bin(data)}')
    enc_data, enc_data_size = crc.encode(data, data_len)
    print(f'encoded data: {bin(enc_data)}')
    dec_data, dec_data_size, status = crc.decode(enc_data, enc_data_size)
    print(f'packet validation: {status}')
    print(f'decoded data: {bin(dec_data)}')
    print(dec_data == data)

    # import time
    # t_start = time.time()
    # for i in range(10**5):
        # enc_data, enc_data_size = crc.encode(data, data_len)
    # t_end = time.time()
    # print(f'time is :{t_end - t_start} s.')