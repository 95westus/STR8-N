"""Current STR8-N component layout and image metadata."""
from .formats import crc, sealed

SR_CALLS = ('V2_HEX_WORD', 'V2_HEX_BYTE', 'V2_SKIP_SPACES', 'V2_PRINT_ADDR',
            'V2_PUTC', 'V2_HEX_OUT', 'V2_NEWLINE', 'V2_BAD_HEX', 'V2_BAD_RANGE',
            'V2_PROTECTED', 'V2_PROMPT', 'V2_MESSAGE', 'V2_FLASH_FAILED',
            'V2_FLASH_DONE', 'V2_CONFIRM', 'V2_PRINT', 'V2_READ_LINE',
            'V2_CHECK_CANCEL', 'V2_CANCELLED')


def boot_sector(body, boot, vectors, compatibility):
    image = bytearray(b'\xff'*4096)
    image[:len(body)] = body
    for address, name in {0xFFE4:'V2V_NATIVE_COP', 0xFFE6:'V2V_NATIVE_BRK',
                          0xFFE8:'V2V_NATIVE_ABORT', 0xFFEA:'V2V_NATIVE_NMI',
                          0xFFEE:'V2V_NATIVE_IRQ', 0xFFF4:'V2V_COP', 0xFFF8:'V2V_ABORT',
                          0xFFFA:'V2V_NMI', 0xFFFE:'V2V_IRQ_BRK'}.items():
        image[address-0xF000:address-0xF000+2] = vectors[name].to_bytes(2, 'little')
    image[0xFFC:0xFFE] = (0xF004).to_bytes(2, 'little')
    offset = boot['BOOT_COMPAT_DATA']-0xF000
    image[offset:offset+4] = compatibility.to_bytes(4, 'little')
    return image


def assembler_image(body, boot):
    app = bytearray(body)
    app[4:6] = len(app).to_bytes(2, 'little')
    app[14:16] = crc(app[:14]).to_bytes(2, 'little')
    vectors = bytearray(b'\xff'*4096)
    vectors[:len(app)-4096] = app[4096:]
    vectors[-32:] = boot[-32:]
    vectors[-4:-2] = (0x7E67).to_bytes(2, 'little')
    return app, vectors


def dispatcher_sector(launcher, sr, mode, loader, symbols, app):
    image = bytearray(b'\xff'*4096)
    image[:len(launcher)] = launcher
    image[0x800:0x800+len(sr)] = sr
    image[0xE92:0xE92+len(mode)] = mode
    image[0xF00:0xF00+len(loader)] = loader
    image[0x6E0:0x6E8] = b'MP\x01\x08'+(0xE011).to_bytes(2,'little')+(0x7D90).to_bytes(2,'little')
    offset = symbols['AP_LIST']-0xE000
    image[offset:offset+5] = bytes.fromhex('A9084C09EF')
    row = bytearray(32)
    row[:3] = b'ASM'; row[12:14] = bytes([1,1])
    for offset, value in [(14,0xE000),(16,len(app)),(18,0xE010),(20,0x0200),(22,0x64FF)]:
        row[offset:offset+2] = value.to_bytes(2, 'little')
    row[24:26] = bytes([0,0x3F]); row[26:28] = crc(app).to_bytes(2,'little'); row[30] = 0x3F
    row[28:30] = crc(row[:28]+row[30:]).to_bytes(2,'little')
    image[0x6F0:0x6F4] = b'AT\x01\x08'; image[0x6F4:0x7F4] = row+bytes(224)
    image[0x7F4:0x7FD] = b'\r\nAPPS\r\n\0'
    image[0x7FE:0x800] = crc(image[:0x7FE]).to_bytes(2,'big')
    image[-2:] = crc(image[:-2]).to_bytes(2,'big')
    return image


def monitor_slot(body, symbols, page, generation, compatibility):
    if len(body) > 3968:
        raise ValueError('Monitor exceeds slot')
    slot = bytearray(b'\xff'*4096)
    slot[:8] = b'MI\x01'+bytes([page])+b'\x03\x01\0\0'
    slot[8:12] = generation.to_bytes(4,'little')
    for offset, value in [(12,len(body)),(14,symbols['START']),(16,symbols['V2_PROMPT_ENTRY'])]:
        slot[offset:offset+2] = value.to_bytes(2,'little')
    slot[20:24] = compatibility.to_bytes(4,'little')
    for i, name in enumerate(SR_CALLS):
        slot[32+2*i:34+2*i] = symbols[name].to_bytes(2,'little')
    slot[70:72] = symbols['V2_M_EDIT'].to_bytes(2,'little')
    slot[128:128+len(body)] = body
    # Fixed executable DBG1 slot ABI, identical in MON A and MON B.
    stub = bytes.fromhex('48 DA 5A AD EC 7F 48 A9 01 20 48 78 4C 10 A0')
    init = bytes([0xA2,14,0xBD,0x6C,page,0x9D,0x81,0x7B,0xCA,0x10,0xF7])
    init += bytes.fromhex('A9 81 8D 02 7E A9 7B 8D 03 7E')
    init += b''.join(bytes([0x9C,a,0x7B]) for a in range(0xFC,0x100))
    init += b'\x4C'+symbols['V2_RESET'].to_bytes(2,'little')
    hook = bytes.fromhex('00 FF 4C')+symbols['V2_REENTER'].to_bytes(2,'little')
    slot[72:128] = init+stub+hook
    slot[18:20] = crc(slot[:18]+slot[32:]).to_bytes(2,'little'); slot[31] = 0
    return slot


def rtc_sector(provider, gate, banner, symbols):
    gateway = bytearray(512); gateway[:len(gate)] = gate
    gateway[0x146:0x14D] = bytes.fromhex('535001014CB866')
    gateway[0x1A2:0x1AE] = bytes.fromhex('534D01014CA966A2064C')+symbols['ENTER'].to_bytes(2,'little')
    gateway[0x1AE:0x1B0] = b'\x01\0'; gateway[0x1B0:0x1B8] = bytes.fromhex('AD0000608D000060')
    gateway[0x1B8:0x1BD] = b'\xA2\x05\x4C'+symbols['ENTER'].to_bytes(2,'little')
    image = bytearray(b'\xff'*4096)
    image[:len(provider)+2] = provider+crc(provider).to_bytes(2,'big')
    image[0x900:0x900+len(banner)] = banner; image[0xDF0:0xFF0] = gateway
    image[-2:] = crc(image[:-2]).to_bytes(2,'big')
    return image


def version_asset(body, powerfail, vectors):
    image = bytearray(sealed(body,2048)); image[0x300:0x600] = powerfail
    image[-8:] = b'\xff\xff'+b''.join(vectors[n].to_bytes(2,'little') for n in
                                      ('V2V_NMI','V2V_RAM_RESET_ENTRY','V2V_IRQ_BRK'))
    seed = crc(image[:-10])
    for word in range(65536):
        patch = word.to_bytes(2,'big')
        if crc(patch+image[-8:],seed) == 0:
            image[-10:-8] = patch
            return image
    raise ValueError('VERSION seal patch unavailable')


def wear_record(generation=None):
    config = bytearray([1,0,3,7,0xF0,10,0]+[0]*9)
    if generation is not None:
        config[7:13] = b'P\xA0'+generation.to_bytes(4,'little'); config[13] = 0xA5
    a = b = 0
    for value in config[:14]:a=(a+value)&255; b=(b+a)&255
    config[14:] = bytes([a,b])
    row = bytearray(b'\xff'*128); row[:8] = b'WC\x01\0\x01\0\0\0'
    row[8:24] = config; row[24:120] = bytes(96)
    row[120:122] = crc(row[:120]).to_bytes(2,'little'); row[127] = 0
    return row


def compose(layout, payload, uchess, source, debugger):
    image = bytearray(b'\xff'*layout['image_bytes']); coverage = bytearray(len(image))
    def put(bank, address, data):
        first = (bank-1)*32768+address-0x8000
        if first < 0 or first+len(data) > len(image) or any(coverage[first:first+len(data)]):
            raise ValueError(f'Invalid/overlapping segment B{bank}:{address:04X}')
        image[first:first+len(data)] = data; coverage[first:first+len(data)] = b'\x01'*len(data)
    for bank, address, name, offset, size in layout['segments']:
        data = (payload/name).read_bytes()[offset:offset+size]
        if len(data) != size:
            raise ValueError('Invalid segment size: '+name)
        put(bank,address,data)
    put(1,0x8000,uchess); put(1,0x9000,source); put(1,0xA000,debugger)
    put(3,0xC000,wear_record(layout['generation']))
    return image
