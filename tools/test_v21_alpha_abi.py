"""Execute the alpha directory on a banked 65C02 model; never opens hardware."""
import copy,json,sys,unittest
from pathlib import Path
import build_v21_alpha_abi as build

ROOT=build.ROOT;OUT=build.OUT
for folder in [ROOT/'tmp/migration-python',*sorted((ROOT/'BUILD').glob('v*/local/test-deps'),reverse=True)]:
    if (folder/'py65').is_dir():sys.path.insert(0,str(folder))
from py65.devices.mpu65c02 import MPU

REGISTRY=build.registry();META=json.loads((OUT/'build.json').read_text());SY=META['symbols']

class Memory:
    def __init__(self,meta=META,out=OUT,bank=3,cpu=2,flags=15):
        self.data=bytearray(b'\x5a'*65536);self.bank=bank;self.reads=[];self.writes=[];self.deny_optional=False
        self.data[meta['base']:meta['end']]=(out/'abi-directory.bin').read_bytes()
        self.data[0x7E60:0x7E64]=b'RA\x01\x0d';self.data[0x7D01]=cpu;self.data[0x7D02]=0
        self.data[0x7D04:0x7D0C]=b'SV\x01'+bytes([flags])+ (b'\0\x65\xff\x64' if flags else b'\0\0\xff\x66')
        self.data[0x6664]=3
        for s in REGISTRY['services']:
            if sig:=s.get('signature'):
                a=int(sig['address'],0);self.data[a:a+4]=bytes.fromhex(sig['hex'])
    def __getitem__(self,a):
        if isinstance(a,slice):return self.data[a]
        assert not 0x7F00<=a<0x8000,'Unexpected hardware I/O read'
        if self.deny_optional:assert not 0x6500<=a<0x6700,'Gateway read before discovery validation'
        self.reads.append(a)
        return self.data[a] if a<0x8000 else (a+self.bank*31)&255
    def __setitem__(self,a,v):
        assert a<0x7F00,'Unexpected I/O or flash write'
        self.data[a]=v;self.writes.append(a)

def call(mem,address,a=0,x=0,y=0):
    cpu=MPU(memory=mem,pc=address);cpu.a=a;cpu.x=x;cpu.y=y;cpu.p=cpu.UNUSED|cpu.INTERRUPT
    cpu.stPushWord(0x01FF);sp=cpu.sp;mem.writes.clear();mem.reads.clear();minimum_sp=sp
    for _ in range(10000):
        if cpu.pc==0x0200:break
        minimum_sp=min(minimum_sp,cpu.sp);cpu.step()
    else:raise AssertionError(f'Timeout at {cpu.pc:04X}')
    assert cpu.sp==(sp+2)&255,'Unbalanced stack'
    assert cpu.p&cpu.INTERRUPT and not cpu.p&cpu.DECIMAL
    return cpu,sp-minimum_sp

def lookup(mem,service,operation=1,version=1,symbols=SY):
    cpu,_=call(mem,symbols['ABI_LOOKUP'],service,operation,version)
    return cpu.a,bool(cpu.p&cpu.CARRY),cpu.x|(cpu.y<<8)

class AbiTests(unittest.TestCase):
    def test_all_operations_in_each_flash_bank(self):
        for bank in range(4):
            mem=Memory(bank=bank,cpu=0x16)
            for s in REGISTRY['services']:
                for op in s['operations']:
                    expected=SY['ABI_SYSTEM_QUERY'] if op['target']=='ABI_SYSTEM_QUERY' else int(op['target'],0)
                    self.assertEqual(lookup(mem,s['id'],op['id']),(0,True,expected))
                    self.assertEqual(mem.bank,bank)
                    self.assertTrue(all(0xD0<=a<=0xD7 or 0x100<=a<=0x1FF for a in mem.writes))

    def test_records_are_discoverable_even_if_optional_service_disabled(self):
        mem=Memory(flags=0);mem.deny_optional=True
        for s in REGISTRY['services']:
            status,ok,pointer=lookup(mem,s['id'],0)
            self.assertEqual((status,ok),(0,True))
            self.assertEqual(mem.data[pointer],s['version'])
            self.assertEqual(mem.data[pointer+4],len(s['operations']))

    def test_absent_optional_service_never_reads_gateway(self):
        mem=Memory(flags=0);mem.deny_optional=True
        for service in range(5,10):self.assertEqual(lookup(mem,service)[:2],(0x80,False))

    def test_bad_sv_refuses_before_gateway_access(self):
        for offset,value in [(0,0),(2,2),(3,0x80),(4,1),(5,0x64),(6,0),(7,0x66)]:
            mem=Memory();mem.data[0x7D04+offset]=value;mem.deny_optional=True
            self.assertEqual(lookup(mem,5)[:2],(0x81,False))

    def test_service_signatures_and_work_load_state(self):
        for service in range(5,10):
            s=REGISTRY['services'][service-1];a=int(s['signature']['address'],0)
            for i in range(4):
                mem=Memory();mem.data[a+i]^=1
                self.assertEqual(lookup(mem,service)[:2],(0x84,False))

    def test_invalid_ids_versions_and_legacy_descriptor(self):
        mem=Memory()
        for service,op in [(0,1),(10,1),(255,1),(1,4),(1,255)]:self.assertEqual(lookup(mem,service,op)[:2],(0x82,False))
        self.assertEqual(lookup(mem,1,1,2)[:2],(0x83,False))
        self.assertEqual(lookup(mem,1,1,0)[:2],(0,True))
        for i in range(4):
            bad=Memory();bad.data[0x7E60+i]^=1
            self.assertEqual(lookup(bad,1)[:2],(0x81,False))

    def test_native_vectors_only_on_detected_816(self):
        self.assertEqual(lookup(Memory(cpu=2),4,2)[:2],(0x80,False))
        self.assertEqual(lookup(Memory(cpu=0x16),4,2),(0,True,0x7E10))
        self.assertEqual(lookup(Memory(cpu=0),1)[:2],(0x81,False))

    def test_system_query_distinguishes_cpu_profiles_and_cached_console(self):
        for cpu_code,effective in [(2,0x11),(0x16,0x17)]:
            for console in (0,1):
                mem=Memory(cpu=cpu_code);mem.data[0x7D02]=console
                cpu,stack=call(mem,SY['ABI_SYSTEM_QUERY'],0,0x30,24)
                self.assertEqual((cpu.a,bool(cpu.p&cpu.CARRY)),(0,True))
                r=mem.data[0x3000:0x3018]
                self.assertEqual(r[:7],bytes([1,24,cpu_code,1,0x17,effective,1]))
                self.assertEqual(r[7:10],bytes([0,255,1] if console else [1,0,1]))
                self.assertEqual(r[10:16],bytes([15,3,9,1,8,0]))
                self.assertEqual(int.from_bytes(r[16:18],'little'),SY['ABI_LOOKUP'])
                self.assertEqual(int.from_bytes(r[18:20],'little'),META['base'])
                self.assertEqual(r[20:],b'\xff\x64\x0d\0')
                self.assertLessEqual(stack,8)
                self.assertTrue(all(0xD0<=a<=0xD7 or 0x100<=a<=0x1FF or 0x3000<=a<0x3018 for a in mem.writes))

    def test_system_query_off_and_invalid_discovery(self):
        for invalid in (False,True):
            mem=Memory(flags=0);mem.deny_optional=True
            if invalid:mem.data[0x7D04]=0
            cpu,_=call(mem,SY['ABI_SYSTEM_QUERY'],0,0x30,24)
            self.assertEqual((cpu.a,bool(cpu.p&cpu.CARRY)),(0,True))
            self.assertEqual(mem.data[0x300A:0x300C],b'\0\0')
            self.assertEqual(mem.data[0x3014:0x3016],b'\0\0' if invalid else b'\xff\x66')

    def test_result_bounds_and_self_overlap_refuse_before_output(self):
        for address,capacity in [(0x1FF,24),(0x64E9,24),(0x6500,24),(0xFFFF,24),(0x3000,23),
                                 (META['base'],24),(META['base']-22,24),(META['end']-1,24)]:
            mem=Memory();before=bytes(mem.data)
            cpu,_=call(mem,SY['ABI_SYSTEM_QUERY'],address&255,address>>8,capacity)
            self.assertEqual((cpu.a,bool(cpu.p&cpu.CARRY)),(0x82,False))
            self.assertTrue(all(0xD0<=a<=0xD7 or 0x100<=a<=0x1FF for a in mem.writes))
            self.assertEqual(mem.data[0x200:0x6500],before[0x200:0x6500])
        for address in [0x200,0x64E8,META['base']-24,META['end']]:
            mem=Memory();cpu,_=call(mem,SY['ABI_SYSTEM_QUERY'],address&255,address>>8,255)
            self.assertEqual((cpu.a,bool(cpu.p&cpu.CARRY)),(0,True))

    def test_relocated_build_uses_discovered_entry(self):
        out=ROOT/'BUILD/v2.1-alpha/abi-relocated';meta=build.build(0x2800,out);mem=Memory(meta,out,cpu=0x16)
        header=mem.data[meta['base']:meta['base']+16]
        entry=int.from_bytes(header[6:8],'little')
        cpu,_=call(mem,entry,1,1,1)
        self.assertEqual((cpu.a,bool(cpu.p&cpu.CARRY)),(0,True))
        query=cpu.x|(cpu.y<<8);self.assertEqual(query,meta['symbols']['ABI_SYSTEM_QUERY'])
        cpu,_=call(mem,query,0,0x30,24)
        self.assertEqual((cpu.a,bool(cpu.p&cpu.CARRY)),(0,True))
        self.assertEqual(int.from_bytes(mem.data[0x3010:0x3012],'little'),entry)

    def test_registry_rejects_collisions_and_private_targets(self):
        for change in [lambda d:d['services'][1].update(id=1),lambda d:d['services'][1].update(name='SYSTEM'),
                       lambda d:d['services'][0]['operations'][1].update(id=1),
                       lambda d:d['services'][0]['operations'][0].update(target='0xF30D'),
                       lambda d:d['services'][0]['operations'][0].update(target='0x6C03')]:
            data=copy.deepcopy(REGISTRY);change(data)
            path=OUT/'invalid-registry.json';path.write_text(json.dumps(data))
            with self.assertRaises(ValueError):build.registry(path)

if __name__=='__main__':
    result=unittest.TextTestRunner(verbosity=2).run(unittest.defaultTestLoader.loadTestsFromTestCase(AbiTests))
    report=dict(passed=result.wasSuccessful(),tests=result.testsRun,build_sha256=build.sha((OUT/'build.json').read_bytes()),
        code_sha256=META['sha256'],cpu_model='py65 65C02/common emulation instruction set; not native 816 hardware',
        flash_banks_tested=4,hardware_accessed=False,firmware_image_built=False)
    (OUT/'test-results.json').write_text(json.dumps(report,indent=2)+'\n');raise SystemExit(0 if result.wasSuccessful() else 1)
