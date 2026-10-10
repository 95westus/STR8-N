"""Model the exact temporary SRAM corruption/refusal and layout repair checks."""
import argparse,hashlib,json
from test_v2_workspace import fresh,call,req,install as install_work
from test_v2_sram_store import install,run_api,request,records,k,OUT


def main():
    p=argparse.ArgumentParser();p.add_argument('--cold-restarts',action='store_true');args=p.parse_args()
    def restart(cpu,m):
        before=bytes(m.spi.devices[0].data);cpu.pc=0xF004
        k.model.run(cpu,lambda:k.model.waiting(cpu),30000000)
        assert bytes(m.spi.devices[0].data)==before,'Cold boot modified retained cut state'
    cpu,m=fresh();install(cpu,m)
    payload=bytes.fromhex('EE 00 27 4C 67 7E');m.ram[0x2600:0x2606]=payload
    assert run_api(cpu,m,request(1,'B23FAULT',0x2600,0x2605,0x2600))==0
    slot,header=records(m)[0];base=64+64*slot;page=header[14]*256
    a=m.spi.devices[0].data;valid=bytes(a);checks=[]
    for label,position,value,expected in [('payload-crc',page,a[page]^1,0x45),
                                          ('header-crc',base+4,a[base+4]^1,0x41),
                                          ('unpublished',base+63,0,0x42)]:
        a[:]=valid;a[position]=value
        if args.cold_restarts:restart(cpu,m)
        install(cpu,m)
        m.ram[0x2600:0x2606]=bytes([0x7C])*6;m.ram[0x2700]=0
        assert run_api(cpu,m,request(2,'B23FAULT'))==expected
        assert m.ram[0x2600:0x2606]==bytes([0x7C])*6
        if label=='payload-crc':assert run_api(cpu,m,request(3,'B23FAULT'))==expected and m.ram[0x2700]==0
        checks.append(dict(label=label,address=position,status=expected))
    a[:]=valid;a[63]=0
    if args.cold_restarts:restart(cpu,m)
    install_work(cpu,m);status,result=call(cpu,m,req(0))
    assert status==0 and result[23]==1
    install(cpu,m);assert run_api(cpu,m,request(2,'B23FAULT'))==0x40
    install_work(cpu,m);assert call(cpu,m,req(8,key=b'REPAIR!!'))[0]==0
    install(cpu,m);assert run_api(cpu,m,request(2,'B23FAULT'))==0 and m.ram[0x2600:0x2606]==payload
    checks.append(dict(label='missing-primary-explicit-secondary-repair',status=0))
    report=dict(passed=True,artifacts=k.REPORT['artifacts'],payload_hex=payload.hex(),checks=checks,
                original_header_hex=header.hex(),slot=slot,model_only=True,cold_restarts=args.cold_restarts)
    name='storage-fault-cold-model.json' if args.cold_restarts else 'storage-fault-hardware-model.json'
    (OUT/name).write_text(json.dumps(report,indent=2)+'\n')
    print('PASS modeled payload/header CRC and uncommitted refusal, no destination overwrite/jump, and explicit secondary repair')


if __name__=='__main__':main()
