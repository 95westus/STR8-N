"""Buffered serial framing and scope tests; no serial/device imports."""
from pathlib import Path
import board_mon_absent_2512 as h

def main():
    cases=[]
    def done(name):cases.append(dict(case=name,passed=True))
    class Peer:
        def __init__(self,body=b'',pending=b''):
            self.pending=bytearray(pending);self.body=bytearray(body);self.sent=[];self.prompts=[]
        def exact(self,n):assert len(self.body)>=n;out=bytes(self.body[:n]);del self.body[:n];return out
        def send(self,data):self.sent.append(data)
        def until(self,token,seconds):self.prompts.append(token);return token
        def command(self,key,token):assert key=='L';return b'L\r\nSEND BIN\r\n'
    p=Peer(b'cdef',b'ab');assert h.exact(p,4)==b'abcd' and not p.pending and p.body==b'ef';done('binary-reply-consumes-pending-first')
    body=bytes(range(256))*128;p=Peer(body+h.b.wire.crc(body).to_bytes(2,'little'))
    assert h.read_service(p,b'F\x03',32768)==body and p.sent==[b'F\x03'];done('whole-bank-read-with-trailer-CRC')
    p=Peer(body+b'\0\0')
    try:h.read_service(p,b'F\x03',32768)
    except ValueError:assert not p.prompts
    else:raise AssertionError('Corrupt binary accepted')
    done('bad-binary-CRC-fails-before-next-command')
    old=h.time.sleep;h.time.sleep=lambda _:None
    try:
        p=Peer();data=bytes(range(256))*10;h.raw_load(p,data,h.KIT)
        assert b''.join(p.sent)==data and all(len(s)<=64 for s in p.sent);done('raw-BIN-exact-chunks-no-header-or-T')
        p=Peer();ram=bytes(range(256))*99;h.write_owner_ram(p,ram)
        assert p.sent[0]==b'W' and b''.join(p.sent[1:])==ram+h.b.wire.crc(ram).to_bytes(2,'little');done('fixed-owner-RAM-length-and-CRC')
        p=Peer()
        try:h.write_owner_ram(p,b'bad')
        except ValueError:assert not p.sent
        else:raise AssertionError('Short RAM restore accepted')
        done('short-RAM-restoration-refused')
    finally:h.time.sleep=old
    for field,value in [('board','2604'),('other_boards_authorized',True),('targets',['B3:F']),('F_writes_authorized',True)]:
        bad=dict(owner_authorized=True,action='erase-only-2512-MON-A-B',board='2512',usb_serial=h.b.USB,targets=['B3:A','B3:B'],other_boards_authorized=False,F_writes_authorized=False,RTC_writes_authorized=False,wear_reservation_authorized=True)
        bad[field]=value
        try:h.auth_check(bad,{})
        except ValueError:pass
        else:raise AssertionError('Unsafe scope accepted '+field)
    done('other-board-and-F-target-scope-refused')
    h.pf.save(Path(__file__).with_name('mon-absent-host-tests.json'),dict(passed=True,hardware=False,serial_access=False,
        checks=len(cases),cases=cases,helper_sha256=h.r.sha(Path(h.__file__).read_bytes()),checker_sha256=h.r.sha(Path(__file__).read_bytes())))
    print('PASS buffered MON-removal host checks',len(cases),flush=True)

if __name__=='__main__':main()
