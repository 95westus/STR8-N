"""Execute the hexadecimal generation banner on both CPU/slots."""
import argparse,json,os
from pathlib import Path

def main():
    p=argparse.ArgumentParser();p.add_argument('--build',type=Path,required=True);a=p.parse_args()
    os.environ['STR8_SOURCE_BUILD']=str(a.build.resolve())
    from test_rc1_source_store import Harness
    from str8build.formats import sha,save
    rows=[]
    for cpu in ('65c02','65c816-e'):
        for slot in ('A','B'):
            h=Harness(cpu,slot,edu=slot=='B')
            expected=b'STR8-N 2.0rc1 g0034 B3 '+(b'65C02' if cpu=='65c02' else b'65C816')
            assert expected in h.m.tx,bytes(h.m.tx)
            # This editor fixture intentionally mocks provider discovery, so
            # VERSION routing is verified on hardware rather than forced here.
            assert b'Build: rc1-r10p2-current' in (a.build/'payload/version/asset.bin').read_bytes()
            rows.append(dict(cpu=cpu,slot=slot,passed=True,boot=bytes(h.m.tx).decode('ascii')))
    save(a.build/'generation-header-tests.json',dict(passed=True,checks=4,firmware_sha256=sha((a.build/'firmware.bin').read_bytes()),cases=rows,hardware=False,VERSION_routing='live board check'))
    print('PASS four CPU/slot hexadecimal g0034 boot header checks',flush=True)

if __name__=='__main__':main()
