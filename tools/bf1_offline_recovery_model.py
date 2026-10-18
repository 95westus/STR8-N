"""Offline-only bf1 cut/recovery driver; never imports a live board launcher."""
import json,os,sys
from pathlib import Path
import plan_bf1_2604_route as route
c=route.c;p=route.p;j=route.j
PRIOR=p.ROOT/'output/qualification/bf1-2604-route-2026-10-17-r2'
PHASES={'A':('install-B-complete','install-A-after-B-complete'),
        'restoreA':('install-A-after-B-complete','restore-A40-retain-Bbf1'),
        'restoreB':('restore-A40-retain-Bbf1','restore-original-B35-complete')}
class Cut(Exception):pass
def setup():
    freeze=p.read(p.ROOT/'output/qualification/beta35-release-qualification-2026-10-17-034745Z/freeze.json');ws=Path(freeze['frozen_source_directory'])
    os.environ.update(STR8_RTC_BUILD='BUILD/v2-beta35-candidate',STR8_TEST_DEPS=str(ws/'BUILD/test-deps'));sys.path.insert(0,str(ws/'tools'))
    import serial
    def forbidden(*args,**kwargs):raise RuntimeError('Serial access forbidden in bf1 offline recovery qualification')
    serial.Serial=forbidden
    import beta4_migration as migration
    migration.Link=forbidden
    import test_v2_rtc_upgrade as model
    mf=p.read(ws/'BUILD/v2-beta35-candidate/migrator/manifest.json');model.S=mf['symbols'];model.MANIFEST=mf
    return model,migration,mf,freeze
def context(phase):
    prior=p.read(PRIOR/'report.json');assert prior['passed'] and prior['cases']==28
    for path,digest in prior['sources'].items():assert p.sha(Path(path).read_bytes())==digest
    source_name,name=PHASES[phase];folder=PRIOR/name;info=p.read(folder/'plan.json');tx=info['transaction']
    source=[(PRIOR/source_name/f'b{i}.bin').read_bytes() for i in range(4)];expected=[(folder/f'b{i}.bin').read_bytes() for i in range(4)]
    case=next(v for v in prior['checks'] if v['name']==name);assert case['passed'] and case['outcome']=='complete' and p.bank_hashes(expected)==case['bank_sha256']==info['expected_sha256']
    assert p.bank_hashes(source)==info['source_sha256'] and p.sha((folder/'installer-model-only.s19').read_bytes())==info['installer_sha256']
    cells=c.old.read_s19(folder/'installer-model-only.s19');data=[bytes(cells[i] for i in range(0x3600,0x3680))]
    for n,op in enumerate(tx['operations'][1:]):
        raw=(folder/f'transfer-{n:02d}.bin').read_bytes();assert p.sha(raw)==info['transfer_sha256'][n];body=bytearray(raw)
        if op['kind']=='payload-sector' and op['commit_address'] is not None:
            off=op['commit_address']-op['address'];body[off]=expected[op['bank']][op['commit_address']-0x8000]
        data.append(bytes(body))
    assert [p.sha(v) for v in data]==[op['data_sha256'] for op in tx['operations']]
    events=p.read(folder/'events.json');assert len(events)==case['mutation_events']
    route.attest_recovery(expected,source,events=events,info=info,certificate=p.bank_hashes(expected))
    return dict(phase=phase,name=name,folder=folder,source=source,expected=expected,tx=tx,data=data,info=info,events=events,prior_report_sha256=p.sha((PRIOR/'report.json').read_bytes()))
def schedule(ctx):
    tx=ctx['tx'];commits={(op['bank'],op['commit_address']) for op in tx['operations'] if op['commit_address'] is not None};points={1}
    for n,(kind,bank,address,value) in enumerate(ctx['events'],1):
        if kind=='erase' or kind=='program' and (bank,address) in commits:
            points.add(n)
            if n>1:points.add(n-1)
    return sorted(points)
def recovery(current,ctx,events):
    """Resume to this phase's intended payload, preserving all newer counts.

    The original baseline and global release flags are never touched. A fully
    restored, clean state is a write-free no-op instead of two journal erases.
    """
    route.attest_recovery(current,ctx['source'],events=events,info=ctx['info'],certificate=p.bank_hashes(current))
    cfg=c.latest(ctx['expected'])[2][8:24];latest=c.latest(current)[2]
    same=all(bytes(current[b])==ctx['expected'][b] for b in (0,1,2)) and bytes(current[3][:0x4000])==ctx['expected'][3][:0x4000] and bytes(current[3][0x6000:])==ctx['expected'][3][0x6000:]
    clean=all(bytes(current[3][off:off+128])==b'\xff'*128 or any(o==off for _,o,_ in c.latest(current)[3]) for off in range(0x4000,0x6000,128))
    if same and clean and latest[8:24]==cfg:
        return dict(no_change=True,source_configuration_hex=latest[8:24].hex(),target_configuration_hex=cfg.hex(),operations=[],planned_erase_order=[],counts_before=[int.from_bytes(latest[24+i*3:27+i*3],'little') for i in range(32)],model_only=True,installation_permitted=False,release_qualified=False),[],list(map(bytes,current))
    return route.transaction(current,ctx['expected'],fallback_page=ctx['tx']['fallback_page'],target_config=cfg,label='Replay-attested '+ctx['phase']+' recovery',attestation=p.bank_hashes(current))
class Driver:
    def __init__(self,out,backup,helper):
        self.out=out;self.backup=backup;self.helper=helper;self.model,self.migration,self.mf,self.freeze=setup();self.checks=[];self.boot_cache={};self.exec_cache={};self.fresh_boots=0;self.fresh_transactions=0;self.reused=0
    def record(self,name,**kw):
        self.checks.append(dict(name=name,passed=True,**kw));(self.out/'progress.json').write_text(json.dumps(self.checks,indent=2)+'\n');print('PASS',name,flush=True)
    def execute(self,name,banks,tx,data,expected,*,cut=None,stale=None,corrupt=None,partial=None):
        folder=self.out/name;model=self.model;S=self.mf['symbols'];driver=self
        if tx['no_change']:
            folder.mkdir();assert list(map(bytes,banks))==expected and not data;self.record(name,outcome='write-free no-op',mutation_events=0);return None,None
        info=route.compose(tx,data,banks,expected,folder,self.helper);initial=list(map(bytearray,banks))
        if stale is not None:initial[stale][123]^=1
        def invariant(m):
            row=c.latest(m.banks)[2];cfg=row[8:24];original=bytes.fromhex(tx['source_configuration_hex']);assert cfg[:7]==original[:7] and cfg[13]==original[13] and cfg[14:]==p.config_checksum(cfg)
            assert all(int.from_bytes(row[24+i*3:27+i*3],'little')>=tx['counts_before'][i]+m.attempts[i] for i in range(32))
            assert cfg[7:8]==b'P' and cfg[8] in (0xa0,0xb0);off=(cfg[8]-0x80)*256;slot=m.banks[3][off:off+4096]
            assert slot[:4]==b'MI\1'+cfg[8:9] and slot[31]==0 and slot[8:12]==cfg[9:13] and p.crc(slot[:18]+slot[32:])==int.from_bytes(slot[18:20],'little')
            fo=(tx['fallback_page']-0x80)*256;assert bytes(m.banks[3][fo:fo+4096])==bytes(banks[3][fo:fo+4096])
            assert bytes(m.banks[0])==bytes(banks[0]) and bytes(m.banks[3][0x6000:])==bytes(banks[3][0x6000:])
        class Memory(model.Memory):
            def __init__(self):
                super().__init__(initial,set(map(tuple,info['steps'])),{},commit_records={});self.require_maintenance_commit=False;self.attempts=[0]*32
            def mutated(self,kind,address,value):
                super().mutated(kind,address,value)
                if kind=='erase':self.attempts[self.bank*8+(address>>12)-8]+=1
                invariant(self)
                if len(self.events)==cut:raise Cut()
        m=Memory();cells,entry=self.migration.read_s19(folder/'installer-model-only.s19')
        for address,value in cells.items():m.ram[address]=value
        cpu=model.CPU(memory=m,pc=entry);m.cpu=cpu;m.rx.extend(b'Y\r');outcome='complete';self.fresh_transactions+=1
        try:
            for n,(bank,sector) in enumerate(info['steps']):
                token=f'SEND 4096 BYTES FOR B{bank}:{sector:X}\r\n'.encode();model.run(cpu,lambda:token in bytes(m.tx) or cpu.pc==S['MIG_HALT'])
                if cpu.pc==S['MIG_HALT']:
                    assert stale is not None and not m.events and b'REFUSED/FAILED' in m.tx;outcome='stale preimage refused before mutation';break
                m.tx.clear();before=len(m.events);body=bytearray((folder/f'transfer-{n:02d}.bin').read_bytes())
                if corrupt==n:body[127]^=1
                if partial==n:body=body[:2048]
                m.rx.extend(body)
                if corrupt==n:
                    model.run(cpu,lambda:cpu.pc==S['MIG_HALT']);assert len(m.events)==before and b'REFUSED/FAILED' in m.tx;outcome='corrupt row refused before row mutation';break
                if partial==n:
                    model.run(cpu,lambda:not m.rx and cpu.pc==S['V2W_RAW_POLL']);assert len(m.events)==before;outcome='partial row waiting without row mutation';break
            else:
                model.run(cpu,lambda:cpu.pc==S['MIG_HALT']);assert b'MIGRATION VERIFIED' in m.tx and list(map(bytes,m.banks))==expected
                assert [[e[1],e[2]>>12] for e in m.events if e[0]=='erase']==tx['planned_erase_order']
        except Cut:assert len(m.events)==cut;outcome='fresh CPU mutation-boundary cut'
        except BaseException:
            for i,b in enumerate(m.banks):(folder/f'failed-b{i}.bin').write_bytes(b)
            (folder/'failure-transcript.txt').write_bytes(m.tx);raise
        if stale is None:invariant(m)
        for i,b in enumerate(m.banks):(folder/f'b{i}.bin').write_bytes(b)
        (folder/'events.json').write_text(json.dumps(m.events)+'\n');(folder/'transcript.txt').write_bytes(m.tx)
        self.record(name,outcome=outcome,mutation_events=len(m.events),erase_attempts=sum(m.attempts),bank_sha256=p.bank_hashes(m.banks),fresh_cpu_execution=True);return m,info
    def boot(self,name,banks):
        hashes=p.bank_hashes(banks);key=tuple(hashes);cfg=c.latest(banks)[2][8:24];page=cfg[8]
        if key in self.boot_cache:
            self.reused+=1;self.record(name,selected_page=page,reused_from=self.boot_cache[key],equivalence='All four banks and global EEPROM/SRAM/virtual RTC inputs identical');return
        from test_v2_status import fresh,boot
        cpu,m=fresh();m.fast=True
        for i,b in enumerate(banks):m.banks[i][:]=b
        ee=(self.backup/'eeprom.bin').read_bytes();m.bus.ee[:128]=ee[:128];m.bus.ee[0xff]=ee[128];m.bus.ee[0xf0:0xf8]=ee[129:137];m.spi.devices[0].data[:]=(self.backup/'sram.bin').read_bytes();m.bus.rtc_regs[:9]=bytes.fromhex('95 53 19 2F 18 10 26 00 0C')
        before=(bytes(m.bus.ee),bytes(m.spi.devices[0].data),bytes(m.bus.rtc_regs));boot(cpu);assert m.ram[0x7d30]==page,(name,bytes(m.tx)[-1000:]);assert before==(bytes(m.bus.ee),bytes(m.spi.devices[0].data),bytes(m.bus.rtc_regs))
        differences=[(bank,i) for bank in range(4) for i,(x,y) in enumerate(zip(banks[bank],m.banks[bank])) if x!=y];assert all(b==3 and 0x1d00<=i<0x2000 for b,i in differences)
        (self.out/(name+'.txt')).write_bytes(m.tx);self.fresh_boots+=1;self.boot_cache[key]=name;self.record(name,selected_page=page,boot_BA_changed_bytes=len(differences),retained_devices_unchanged=True,fresh_cpu_execution=True)
