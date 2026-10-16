"""STR8N-006: actual boot paths must separate the retained name from PF text."""
import json
from test_v2_board_name import record, META
from test_v2_status import fresh, boot, layout, snapshot, OUT
from test_v2_journal import event


def main():
    checks=[]
    for foreign in (False,True):
        for named in (False,True):
            cpu,m=fresh(primary=layout())
            if named:m.banks[3][0x1C20:0x1C40]=record(b'LAB-2609')
            m.bus.rtc_regs[3]|=0x10;m.bus.rtc_regs[0x18:0x20]=event(5)
            if foreign:m.bus.ee[:128]=bytes(range(128))
            before=snapshot(m);boot(cpu);output=bytes(m.tx)
            message=b'RTCC: PF logging failed.' if foreign else b'RTCC: PF logged, ACK'
            assert message in output,output
            if named:assert message+b'\r\nBoard: LAB-2609\r\n' in output,output
            else:assert b'Board:' not in output,output
            assert [bytes(b) for b in m.banks]==before[0] and bytes(m.spi.devices[0].data)==before[3]
            assert m.ram[0xF4]==0
            if foreign:assert bytes(m.bus.ee)==before[1] and m.bus.rtc_regs[3]&0x10
            else:assert not m.bus.rtc_regs[3]&0x10
            label=('foreign' if foreign else 'logged')+('-named' if named else '-unnamed')
            (OUT/(label+'-power-fail-boot.txt')).write_bytes(output)
            checks.append(label);print('PASS STR8N-006',label,flush=True)
    (OUT/'board-name-power-fail-test-results.json').write_text(json.dumps(dict(
        passed=True,checks=checks,artifacts=META['artifacts'],local_asset_sha256=META['local_asset_sha256'],
        physical_hardware_tested=False),indent=2)+'\n')


if __name__=='__main__':main()
