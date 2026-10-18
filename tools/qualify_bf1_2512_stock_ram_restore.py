"""Test stock RAM restoration using the saved archive and simulated endpoint."""
import argparse,json
from pathlib import Path
import beta4_migration as migration
import bf1_2512_stock_ram_restore as worker
from plan_bf1_2512_legacy import BACKUP,sha

def main():
    ap=argparse.ArgumentParser(description=__doc__);ap.add_argument('--out',type=Path,required=True);a=ap.parse_args();assert not a.out.exists()
    original=(BACKUP/'application-ram-original.bin').read_bytes();assert original==(BACKUP/'application-ram-restored.bin').read_bytes();checks=[]
    class Endpoint:
        stock_read=migration.Link.stock_read
        def __init__(self,bad=None,ack=b'\0'):self.ram=bytearray(b'\xa5'*32768);self.commands=[];self.command=None;self.reply=None;self.bad=bad;self.ack=ack
        def protocol(self,command):assert command in (2,3),'Only RAM write/read permitted';self.command=command;self.commands.append(command)
        def send(self,data):
            address=int.from_bytes(data[:3],'little');n=int.from_bytes(data[3:6],'little');assert 0x200<=address and address+n<=0x6500
            if self.command==2:assert len(data)==n+6 and n<=256;self.ram[address:address+n]=data[6:]
            else:
                assert len(data)==6;self.reply=bytearray(self.ram[address:address+n])
                if self.bad is not None and address<=self.bad<address+n:self.reply[self.bad-address]^=1
        def exact(self,count):
            if self.command==2:assert count==1;return self.ack
            assert self.reply is not None and len(self.reply)==count;return bytes(self.reply)
    good=Endpoint();receipt=worker.restore(good,original);assert receipt['passed'] and not receipt['execution_requested'] and good.ram[0x200:0x6500]==original
    assert good.ram[:0x200]==b'\xa5'*0x200 and good.ram[0x6500:]==b'\xa5'*(0x8000-0x6500)
    checks.append(dict(name='exact saved RAM restored and fully verified; no execute, I/O or flash address',passed=True))
    for address in (0x200,0x3200,0x64ff):
        try:worker.restore(Endpoint(bad=address),original)
        except IOError:checks.append(dict(name='RAM mismatch refused '+hex(address),passed=True))
        else:raise AssertionError('RAM mismatch hidden')
    try:worker.restore(Endpoint(ack=b'\x01'),original)
    except IOError:checks.append(dict(name='failed write acknowledgement refused',passed=True))
    else:raise AssertionError('Bad write acknowledgement ignored')
    try:worker.restore(Endpoint(),original[:-1])
    except ValueError:checks.append(dict(name='incomplete application archive refused before transfer',passed=True))
    else:raise AssertionError('Short RAM archive accepted')
    a.out.write_text(json.dumps(dict(passed=True,cases=len(checks),checks=checks,archive_sha256=sha(original),restorer_source_sha256=sha(Path(worker.__file__).read_bytes()),test_source_sha256=sha(Path(__file__).read_bytes()),board_access=False,hardware_qualified=False),indent=2)+'\n');print('PASS',len(checks),'stock application RAM restoration checks')
if __name__=='__main__':main()
