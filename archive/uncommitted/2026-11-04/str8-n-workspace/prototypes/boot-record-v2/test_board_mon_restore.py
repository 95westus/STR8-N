"""Buffered restore-command, boot evidence and preservation/scope tests."""
from pathlib import Path
import board_mon_restore_2512 as h

def main():
    cases=[]
    def done(name):cases.append(dict(case=name,passed=True));print('PASS',name)
    boot=b'\r\nMON KIT DONE\r\n\r\nWAIT...\r\n'+h.b.CHOICES+b'Boot : 6 5 4 3 2 1 0\r\n\r\n'+h.BANNER+b'\r\nABI 65C02 | 816E | 816N-VEC\r\nB3> '
    class Peer:
        def __init__(self,raw=boot):self.raw=raw;self.sent=[]
        def send(self,data):self.sent.append(data)
        def until(self,token,seconds):assert token==h.b.MON_PROMPT;return self.raw
        def dump(self,a,b):return {(0x7d01,0x7d02):b'\x02\x03',(0x7d30,0x7d30):b'\xb0'}[(a,b)]
    p=Peer();assert h.restore_and_boot(p)==boot and p.sent==[b'T'];done('T-only-no-X-or-transfer-headers-and-ordered-boot')
    for broken in (boot.replace(h.BANNER,b'wrong version'),boot.replace(b'Boot : 6 5 4 3 2 1 0',b'Boot : 6'),b'MON KIT REFUSED/FAILED\r\nREC> '):
        p=Peer(broken)
        try:h.restore_and_boot(p)
        except ValueError:pass
        else:raise AssertionError('Bad boot accepted')
    done('missing-incomplete-or-refused-boot-not-reported-successful')
    p=Peer();h.identity(p,0xb0)
    try:h.identity(p,0xa0)
    except ValueError:pass
    else:raise AssertionError('Wrong active slot accepted')
    done('runtime-CPU-console-and-slot-identity')
    p=Peer()
    try:h.select_MON(p,'0')
    except ValueError:assert not p.sent
    else:raise AssertionError('Opaque bank accepted as MON selection')
    done('only-A-B-selection-before-any-I-O')
    marker=h.r.read(h.pf.MARKER);h.source_binding(marker)
    for field,value in [('board','2609'),('MON_A_present',True),('MON_B_present',True),('mon_restore_pending',True),('application_RAM_restore_pending',True),('recovery_worker_active',True)]:
        bad=dict(marker);bad[field]=value
        try:h.source_binding(bad)
        except ValueError:pass
        else:raise AssertionError('Unsafe source accepted '+field)
    done('exact-absent-MON-source-and-device-preservation-guards')
    auth=dict(owner_authorized=True,action='restore-saved-b14-MON-AB-through-F',board='2512',usb_serial=h.b.USB,
        targets=['B3:A','B3:B'],generation_hex='8000000E',other_boards_authorized=False,F_writes_authorized=False,
        RTC_writes_authorized=False,wear_reservation_authorized=True,helper_sha256=h.r.sha(Path(h.__file__).read_bytes()),
        model_proof_sha256=h.r.sha((h.MODEL/'mon-restore-model-tests.json').read_bytes()))
    h.owner_scope(auth)
    for field,value in [('board','2604'),('targets',['B3:F']),('F_writes_authorized',True),('RTC_writes_authorized',True),('generation_hex','00000034'),('other_boards_authorized',True)]:
        bad=dict(auth);bad[field]=value
        try:h.owner_scope(bad)
        except ValueError:pass
        else:raise AssertionError('Unsafe owner scope accepted '+field)
    done('owner-scope-excludes-other-boards-F-RTC-and-other-builds')
    h.pf.save(Path(__file__).with_name('mon-restore-host-tests.json'),dict(passed=True,hardware=False,serial_access=False,
        checks=len(cases),cases=cases,helper_sha256=h.r.sha(Path(h.__file__).read_bytes()),checker_sha256=h.r.sha(Path(__file__).read_bytes())))
    print('PASS buffered MON restoration groups',len(cases))

if __name__=='__main__':main()
