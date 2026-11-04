"""Execute b12's no-V verification path on both CPUs, with MON initially absent."""
import argparse,tempfile
from pathlib import Path
import board_b12_2512 as board
import test_opaque_installer as model

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);build=p.parse_args().build.resolve()
    model.base.GENERATION=0x8000000c;rows=[];body=(build/'payload/ram-installer-offline.bin').read_bytes()
    for cpu in ('65c02','65c816-e'):
        h=model.patterned_machine(build,cpu,via_f=True)
        assert not h.m.events and bytes(h.m.ram[0x2000:0x2000+len(body)])==body
        expected=h.sector(0,0x80);out=h.request(model.frame(op=0,bank=0,sector=0x80))
        assert out==model.READ_READY+expected+model.crc(expected).to_bytes(2,'little')+model.READ_DONE+model.PROMPT
        h.command(b'Q\r',b'REC> ')
        model.install_protected_monitor_fixtures(h)
        h.command(b'B\r',board.MON_PROMPT)
        class Link:
            def command(self,text,prompt=board.MON_PROMPT):return h.command(text.encode()+b'\r',prompt)
            dump=board.wire.Link.dump
        with tempfile.TemporaryDirectory(dir=board.ROOT/'tmp') as folder:
            board.b12_mon_readback(Link(),Path(folder),body,expected,h.i)
        assert not h.m.events
        rows.append(dict(cpu=cpu,passed=True,F_load_run_with_MON_absent=True,OIP_sector_read_CRC_verified=True,
            MON_independent_RAM_readback_verified=True,recovery_V_not_used=True,flash_mutations=0))
    board.save(build/'b12-deployment-cpu-tests.json',dict(passed=True,checks=len(rows),hardware=False,serial_access=False,cases=rows,
        adapter_sha256=board.r.sha(Path(board.__file__).read_bytes()),checker_sha256=board.r.sha(Path(__file__).read_bytes()),
        F_sha256=board.r.sha((build/'payload/f-offline-component.bin').read_bytes()),
        RAM_tool_sha256=board.r.sha(body)))
    print('PASS b12 F load/run, read-only OIP and independent MON RAM readback:2 CPUs',flush=True)

if __name__=='__main__':main()
