"""Buffered F/OIP1 framing, CRC and owner-scope qualification; no hardware."""
from pathlib import Path
import board_opaque_absent_2512 as h

def main():
    cases=[]
    def done(name):cases.append(dict(case=name,passed=True));print('PASS',name)
    class Peer:
        def __init__(self,body=b'',completion=b'OK: verified sector\r\n'):
            self.pending=bytearray();self.body=bytearray(body);self.sent=[];self.completion=completion;self.bad_ready=False
        def command(self,key,marker):
            assert key=='I' and marker==h.HEADER
            return b'wrong ready' if self.bad_ready else b'I\r\n'+h.HEADER
        def send(self,data):self.sent.append(data)
        def exact(self,n):
            assert n<=len(self.body);data=bytes(self.body[:n]);del self.body[:n];return data
        def until(self,marker,seconds):
            if marker==h.b.OI_PROMPT:
                return (b'\r\nOK: read\r\n' if self.body==bytearray(b'READ') else self.completion)+marker
            return marker
    body=bytes(range(256))*16;crc=h.b.wire.crc(body);old=h.time.sleep;h.time.sleep=lambda _:None
    try:
        p=Peer();h.opaque_write(p,body,0x1234,b'OK: verified sector\r\n')
        header=p.sent[0];assert header==h.protocol.frame_header(0,0x80,body,0x1234)
        assert b''.join(p.sent[1:])==body and all(len(x)<=64 for x in p.sent[1:]);done('fixed-B0-8-whole-binary-payload-CRC-header')
        p=Peer()
        try:h.opaque_write(p,b'bad',0,b'OK: verified sector\r\n')
        except ValueError:assert not p.sent
        else:raise AssertionError('Short sector accepted')
        done('short-write-refuses-before-I')
        p=Peer();p.bad_ready=True
        try:h.opaque_write(p,body,0,b'OK: verified sector\r\n')
        except ValueError:assert not p.sent
        else:raise AssertionError('Unexpected readiness accepted')
        done('ready-mismatch-refuses-before-header')
        p=Peer(completion=b'REFUSED: preimage CRC\r\n')
        result=h.opaque_write(p,body,crc^1,b'REFUSED: preimage CRC\r\n')
        assert result['reply'].startswith('REFUSED: preimage CRC');done('expected-preimage-refusal-framed-without-retry')
        p=Peer(completion=b'FAILED: flash/readback; target may be torn\r\n')
        try:h.opaque_write(p,body,0,b'OK: verified sector\r\n')
        except ValueError:pass
        else:raise AssertionError('Flash failure reported successful')
        done('flash-failure-stops-before-follow-on-command')
    finally:h.time.sleep=old
    p=Peer(body+crc.to_bytes(2,'little')+b'READ');assert h.opaque_read(p,body)==body+crc.to_bytes(2,'little')
    assert p.sent==[h.protocol.frame_header(0,0x80)];done('read-literal-binary-and-CRC-before-menu')
    for bad in (body+b'\0\0'+b'READ',bytes([body[0]^1])+body[1:]+crc.to_bytes(2,'little')+b'READ'):
        p=Peer(bad)
        try:h.opaque_read(p,body)
        except ValueError:pass
        else:raise AssertionError('Bad raw readback accepted')
    done('bad-readback-content-or-CRC-refused')
    marker=h.r.read(h.pf.MARKER);h.source_binding(marker)
    for field,value in [('board','2604'),('MON_A_present',True),('block_snapshot',True),('recovery_worker_active',True),('physical_reset_pending',True),('opaque_sector_restore_pending',True)]:
        bad=dict(marker);bad[field]=value
        try:h.source_binding(bad)
        except ValueError:pass
        else:raise AssertionError('Source scope accepted '+field)
    done('source-other-board-MON-present-and-preservation-guards')
    auth=dict(owner_authorized=True,action='F-only-opaque-install-run-restore',board='2512',usb_serial=h.b.USB,
        target=dict(bank=0,sector=0x80,bytes=4096),other_boards_authorized=False,MON_writes_authorized=False,
        F_writes_authorized=False,RTC_writes_authorized=False,wear_reservation_authorized=True,restore_original_sector=True,
        helper_sha256=h.r.sha(Path(h.__file__).read_bytes()),model_proof_sha256=h.r.sha((h.MODEL/'opaque-live-model-tests.json').read_bytes()))
    h.owner_scope(auth)
    for field,value in [('board','2609'),('target',dict(bank=3,sector=0xf0,bytes=4096)),('F_writes_authorized',True),('MON_writes_authorized',True),('RTC_writes_authorized',True),('other_boards_authorized',True)]:
        bad=dict(auth);bad[field]=value
        try:h.owner_scope(bad)
        except ValueError:pass
        else:raise AssertionError('Owner scope accepted '+field)
    done('owner-permits-only-2512-B0-8-and-wear-journal')
    prior=bytes([0x10])*0x6300;loader=b'CODE';current=bytearray(prior);current[:4]=loader;current[0x4d7f-0x200]=0x20
    preserved,changes=h.preserved_RAM(prior,loader,[bytes(current),bytes(current)])
    assert preserved[:4]==prior[:4] and preserved[4:]==current[4:] and changes==[dict(address_hex='4D7F',prior_hex='10',current_hex='20')]
    for broken in ([bytes(current),prior],[prior,prior]):
        try:h.preserved_RAM(prior,loader,broken)
        except ValueError:pass
        else:raise AssertionError('Inconsistent RAM/load prefix accepted')
    done('preserve-fresh-owner-RAM-tail-and-refuse-inconsistent-reads')
    h.pf.save(Path(__file__).with_name('opaque-absent-host-tests.json'),dict(passed=True,hardware=False,serial_access=False,
        checks=len(cases),cases=cases,helper_sha256=h.r.sha(Path(h.__file__).read_bytes()),checker_sha256=h.r.sha(Path(__file__).read_bytes())))
    print('PASS buffered host groups',len(cases))

if __name__=='__main__':main()
