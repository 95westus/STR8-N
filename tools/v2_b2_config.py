"""Shared byte format for beta 2 bootstrap locators and sector policy headers.

Pure encoding/validation: does not write a device or claim a flash sector.
"""
LOCATOR_TAG = 0xC1
HEADER_SIZE = 16


def checksum(data):
    first = second = 0
    for value in data:
        first = (first + value) & 255
        second = (second + first) & 255
    return bytes((first, second))


def location(bank, sector):
    if bank not in range(4) or sector not in range(8, 14):
        raise ValueError('Configuration requires bank 0-3 and sector 8-D')
    return bank, sector << 4


def encode_header(bank, sector, masks):
    bank, high = location(bank, sector)
    masks = bytes(masks)
    if len(masks) != 4 or any(mask & 0xC0 for mask in masks):
        raise ValueError('Four masks containing only sector bits 8-D are required')
    data = b'CF\x01\x3f' + masks + bytes((bank, high)) + bytes(4)
    return data + checksum(data)


def decode_header(data, bank, sector):
    bank, high = location(bank, sector)
    data = bytes(data)
    if (len(data) != HEADER_SIZE or data[:4] != b'CF\x01\x3f'
            or data[8:10] != bytes((bank, high))
            or any(mask & 0xC0 for mask in data[4:8])
            or checksum(data[:14]) != data[14:]):
        raise ValueError('Invalid, incompatible or incomplete configuration header')
    effective = bytearray(data[4:8])
    effective[bank] &= ~(1 << (sector - 8))
    return bytes(effective)


def valid_boot_pocket(data):
    data = bytes(data)
    valid = (len(data) == 16 and data[0] == 1 and data[1] < 2 and data[2] < 4
             and data[5] >= 10 and data[6] < 2
             and checksum(data[:14]) == data[14:])
    if valid and data[6] == 0:
        address = int.from_bytes(data[3:5], 'little')
        valid = (address < 0xE0 or 0x200 <= address < 0x5800 or address >= 0x8000)
    return valid


def boot_pocket(existing=None, *, bank=None, sector=None):
    """Preserve a structurally/checksum-valid boot pocket, else monitor defaults."""
    data = bytes(existing or b'')
    valid = valid_boot_pocket(data)
    result = bytearray(data if valid else bytes((1, 0, 3, 0, 0xF0, 10)) + bytes(10))
    result[7:14] = bytes(7)
    if bank is not None:
        selected_bank, high = location(bank, sector)
        result[7:10] = bytes((LOCATOR_TAG, selected_bank, high))
    elif sector is not None:
        raise ValueError('Sector requires a bank')
    result[14:] = checksum(result[:14])
    return bytes(result)


def decode_locator(pocket):
    data = bytes(pocket)
    if not valid_boot_pocket(data):
        raise ValueError('Invalid bootstrap fields/checksum')
    if data[7:10] == bytes(3):
        return None
    if data[7] != LOCATOR_TAG or data[9] & 15:
        raise ValueError('Unsupported or malformed configuration locator')
    return location(data[8], data[9] >> 4)[0], data[9] >> 4
