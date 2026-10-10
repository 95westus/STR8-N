"""Focused program-preservation and optional-device guards for Phase 5."""
import json
from test_v2_workspace import boot,install,call,req,OUT,META,k
from test_v2_sram_store import formatted,run_api as store_api,request as store_request

def main():
    checks=[]
    def passed(t):checks.append(t);print('PASS',t,flush=True)
    cpu,m=formatted(fast=True);m.ram[0x2000:0x6100]=bytes([0x36])*0x4100
    assert store_api(cpu,m,store_request(1,'BIG',0x2000,0x60FF,0))==0
    install(cpu,m);assert call(cpu,m,req(7,key=b'UPGRADE!'))[0]==0
    a=m.spi.devices[0].data;before=bytes(a)
    assert call(cpu,m,req(5,units=1,key=b'RESIZE!!'))[0]==0x41
    assert bytes(a)==before
    passed('shrinking refuses a committed program extent beyond the new boundary and preserves every SRAM byte')
    cpu,m=boot(present=False);install(cpu,m)
    assert call(cpu,m,req(0))[0]==7 and m.ram[0x66AE]==1
    cpu,m=boot();install(cpu,m);m.ram[0x7D07]&=~8;n=len(m.spi.frames)
    assert call(cpu,m,req(0))[0]==0x80 and len(m.spi.frames)==n
    passed('missing hardware and unavailable SPI software refuse without changing the public write policy')
    report=dict(passed=True,workspace_sha256=META['sha256'],resident_artifacts=k.REPORT['artifacts'],checks=checks,board_access=False)
    (OUT/'guard-test-results.json').write_text(json.dumps(report,indent=2)+'\n')

if __name__=='__main__':main()
