"""Narrow fake-stream checks of BASE1 restoration framing; no CPU/device."""
import sys
import unittest
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from nf_recovery import RecoveryClient,PROMPT,RAM_BYTES,ZP_BYTES,crc,sha


class Stream:
    def __init__(self,ram,zp):
        self.ram,self.zp=ram,zp
        self.buffer=bytearray()
        self.writes=[]
        self.receiving=None
        self.received=bytearray()
    def write(self,body):
        self.writes.append(bytes(body))
        if self.receiving:
            self.received.extend(body)
            size=RAM_BYTES if self.receiving==b'W' else ZP_BYTES
            if len(self.received)==size+2:
                assert crc(self.received[:size])==int.from_bytes(self.received[size:],'little')
                if self.receiving==b'W':self.ram=bytes(self.received[:size])
                else:self.zp=bytes(self.received[:size])
                self.receiving=None
                self.buffer.extend(PROMPT)
            return len(body)
        if body in (b'W',b'Y'):
            self.receiving=body;self.received=bytearray()
        elif body in (b'M',b'Z'):
            data=self.ram if body==b'M' else self.zp
            self.buffer.extend(data+crc(data).to_bytes(2,'little')+PROMPT)
        elif body==b'Q':self.buffer.extend(b'REC> ')
        return len(body)
    def read(self,count):
        if not self.buffer:raise EOFError('Unexpected protocol read')
        body=bytes(self.buffer[:count]);del self.buffer[:count];return body


class RestoreProtocol(unittest.TestCase):
    def client(self,stream):
        c=RecoveryClient(stream,sleep=lambda _:None,progress=lambda _:None)
        c.admitted=True
        return c
    def test_full_owner_ranges_and_verified_return(self):
        ram=bytes(range(256))*(RAM_BYTES//256)
        zp=bytes(range(ZP_BYTES))
        io=Stream(bytes(RAM_BYTES),bytes(ZP_BYTES))
        result=self.client(io).restore_owner(ram,zp)
        self.assertTrue(result['owner_RAM_restored'] and result['owner_ZP_restored'])
        self.assertEqual((io.ram,io.zp),(ram,zp))
        self.assertEqual(io.writes[-3:],[b'M',b'Z',b'Q'])
    def test_bad_lengths_and_unadmitted_service_issue_no_writes(self):
        io=Stream(bytes(RAM_BYTES),bytes(ZP_BYTES));c=self.client(io)
        with self.assertRaises(ValueError):c.restore_owner(bytes(RAM_BYTES-1),bytes(ZP_BYTES))
        c.admitted=False
        with self.assertRaises(ValueError):c.restore_owner(bytes(RAM_BYTES),bytes(ZP_BYTES))
        self.assertFalse(io.writes)
    def test_bad_read_CRC_never_claims_success(self):
        io=Stream(bytes(RAM_BYTES),bytes(ZP_BYTES))
        io.buffer.extend(b'abc\x00\x00'+PROMPT)
        with self.assertRaises(ValueError):self.client(io).read(b'?',3)
    def test_wrong_loader_identity_does_not_send_L(self):
        io=Stream(bytes(RAM_BYTES),bytes(ZP_BYTES));c=self.client(io)
        with self.assertRaises(ValueError):c.load(b'\x78',sha(b'bad'),REC_observed=True)
        self.assertFalse(io.writes)


if __name__=='__main__':unittest.main()
