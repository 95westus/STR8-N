"""BASE1 recovery readback and owner-RAM restoration protocol.

No serial port is opened here. A caller supplies an already owned byte stream
after observing REC>. This is not hardware qualification.
"""
import binascii
import hashlib
import time

PROMPT = b'RAM SERVICE BASE1> '
RAM_BYTES = 0x6500                 # 0200-66FF
ZP_BYTES = 0xe0                    # 00-DF; never system E0-FF
crc = lambda body: binascii.crc_hqx(bytes(body), 0xffff)
sha = lambda body: hashlib.sha256(bytes(body)).hexdigest()


class RecoveryClient:
    def __init__(self, stream, *, sleep=time.sleep, timeout=30, progress=print):
        self.stream, self.sleep, self.timeout, self.progress = stream, sleep, timeout, progress
        self.pending = bytearray()
        self.admitted = False

    def send(self, body):
        result = self.stream.write(bytes(body))
        if result is not None and result != len(body):
            raise IOError('Short recovery write; stopped without retry')

    def paced(self, body):
        for offset in range(0, len(body), 16):
            self.send(body[offset:offset+16])
            self.sleep(0.002)

    def exact(self, count):
        result = bytearray()
        deadline = time.monotonic()+self.timeout
        while len(result) < count:
            if self.pending:
                take = min(count-len(result), len(self.pending))
                result.extend(self.pending[:take])
                del self.pending[:take]
            else:
                result.extend(self.stream.read(count-len(result)))
            if time.monotonic() > deadline:
                raise TimeoutError('Recovery data incomplete; no automatic retry')
        return bytes(result)

    def until(self, token):
        deadline = time.monotonic()+self.timeout
        while True:
            end = self.pending.find(token)
            if end >= 0:
                result = bytes(self.pending[:end+len(token)])
                del self.pending[:end+len(token)]
                return result
            self.pending.extend(self.stream.read(1))
            if time.monotonic() > deadline:
                raise TimeoutError('Recovery marker absent: '+repr(token))

    def load(self, image, expected_sha256, *, REC_observed=False):
        if not REC_observed or sha(image) != expected_sha256 or not 0 < len(image) <= 0x6300:
            raise ValueError('Observed REC> and matching BASE1 READBACK image required')
        self.progress('RECOVERY: loading matching RAM readback/restore tool at 0200')
        self.send(b'L\r')
        self.until(b'SEND BIN\r\n')
        self.paced(image)
        self.until(PROMPT)         # raw L itself supplies the idle-to-run delay
        self.admitted = True

    def read(self, command, count):
        if not self.admitted:
            raise ValueError('BASE1 RAM service has not been admitted')
        self.send(command)
        body, trailer = self.exact(count), self.exact(2)
        if crc(body) != int.from_bytes(trailer, 'little'):
            raise ValueError('Recovery read CRC mismatch; preservation is not verified')
        self.until(PROMPT)
        return body

    def flash(self, bank):
        if type(bank) is not int or not 0 <= bank <= 3:
            raise ValueError('Flash bank must be 0-3')
        return self.read(b'F'+bytes((bank,)), 32768)

    def verify_flash(self, expected_hashes):
        if len(expected_hashes) != 4:
            raise ValueError('Four expected bank SHA-256 values required')
        actual = []
        for bank in range(4):
            self.progress(f'READBACK: independently reading B{bank}, 32768 bytes')
            actual.append(sha(self.flash(bank)))
            if actual[-1] != expected_hashes[bank]:
                raise ValueError(f'B{bank} postimage mismatch; stopped before RAM restoration')
        return actual

    def restore_owner(self, ram, zp):
        if not self.admitted or len(ram) != RAM_BYTES or len(zp) != ZP_BYTES:
            raise ValueError('Exact 0200-66FF and 00-DF escrow required')
        self.progress('RESTORE: owner RAM 0200-66FF, 25856 bytes')
        self.send(b'W')
        self.paced(ram+crc(ram).to_bytes(2,'little'))
        self.until(PROMPT)
        self.progress('RESTORE: owner ZP 00-DF; stage and CRC before copying')
        self.send(b'Y')
        self.paced(zp+crc(zp).to_bytes(2,'little'))
        self.until(PROMPT)
        self.progress('VERIFY: read back restored RAM and ZP')
        if self.read(b'M', RAM_BYTES) != ram or self.read(b'Z', ZP_BYTES) != zp:
            raise ValueError('Owner RAM/ZP restoration mismatch; not complete')
        self.send(b'Q')
        self.until(b'REC> ')
        self.admitted = False
        return dict(owner_RAM_restored=True, owner_ZP_restored=True,
                    RAM_sha256=sha(ram), ZP_sha256=sha(zp), stopped_at_REC=True)
