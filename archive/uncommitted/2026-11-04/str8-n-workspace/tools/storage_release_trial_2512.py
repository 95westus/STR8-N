"""Shared preservation for the exact approved14-erase2512 storage scope."""
import binascii,json,re,sys
from contextlib import ExitStack
from pathlib import Path
import install_named_edu_2512 as ins
import nf_opaque as opaque
from serial_test_coordination import drift_pending
t=ins.t;d=ins.d;Q=ins.Q;ROOT=t.ROOT
sys.path.insert(0,str(t.REPO/'tools'))
from journal_rotation_plan import reserve
SCOPE=Q/'2512-storage-BATCH-AUTO-scope-20261101-r1'
INST=Q/'2512-storage-BATCH-AUTO-installed-20261101-r1'
POS=Q/'2512-storage-BATCH-AUTO-positive-20261101-r1'
MONS=tuple(f'B{n}> '.encode() for n in range(4))
SRAM=b'SRAM> ';WORK=b'WORK> ';BM=b'BM> ';FT=d.FT;PB=t.PB
FLASH_YES=b'Flash STORE; no erase; type YES: '
PROGRAM_YES=b'STORE PROGRAM from original RAM; type YES: '
DENSE_YES=b'; type YES> '


def approved():
    a=json.loads((SCOPE/'approval.json').read_text());p=json.loads((SCOPE/'plan.json').read_text())
    assert a['approved'] and a['owner_answer']=='Approve reviewed 14-erase trial/install'
    assert a['total_erases']==p['total_erases']==14 and p['SPI_temporary']['bytes']==8256
    for name,key in (('plan.json','plan_sha256'),('review-document.md','review_document_sha256')):assert t.sha((SCOPE/name).read_bytes())==a[key]
    f=json.loads((t.REPO/'F_FREEZE.json').read_text())
    assert t.sha((t.REPO/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes())==f['sha256']==p['F_sha256']
    assert all(t.sha((t.REPO/n).read_bytes())==h for n,h in f['sources'].items())
    for x in p['targets']:assert t.sha((SCOPE/x['file']).read_bytes())==x['sha256']
    return p


def forecast_install(p):
    banks={n:bytearray((SCOPE/f'B{n}-original.bin').read_bytes()) for n in range(4)}
    state=bytes(banks[3]);ops=[]
    for x in p['targets']:
        bank,page=x['bank'],x['page'];off=(page-0x80)*256;body=(SCOPE/x['file']).read_bytes()
        state,op=reserve(state,bank*8+(page-0x80)//16);ops.append(op)
        banks[bank][off:off+4096]=body
        if bank==3:b=bytearray(state);b[off:off+4096]=body;state=bytes(b)
    banks[3]=bytearray(state)
    assert t.classify_journal(state)['sequence']==1161
    return {n:bytes(b) for n,b in banks.items()},ops


class Trial:
    def __init__(self,folder,kind,expected_banks,seconds=300):
        self.folder=folder;self.kind=kind;self.expected=expected_banks.copy();self.seconds=seconds
        self.s=None;self.ram=self.zp=self.prefix=None;self.borrowed=False;self.marker=None;self.created=False
        self.r=dict(board='2512',passed=False,checks=[],flash_erase_requests=0,F_writes=0,MON_A_B_writes=0,metadata_appends=0,
            RTC_SET=0,trim_writes=0,PF_ACK=0,resets=0,power_cuts=0,WORKSPACE_writes=0,
            owner_RAM_restored=False,owner_ZP_restored=False,CPU_simulations=0,automatic_write_retries=0)
        self.reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
        self.writer=(t.REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
        self.mp=Q/'device-operations/2512.json';self.stack=ExitStack()
    def save(self):t.save(self.folder/'report.json',self.r)
    def mark(self,**kw):m=json.loads(self.mp.read_text());m.update(kw);t.save(self.mp,m)
    def cmd(self,line,tokens=None):
        if tokens is None and self.s.context in MONS:tokens=MONS
        b=self.s.command(line,tokens);(self.folder/f'{self.s.counter:04d}-{re.sub("[^A-Za-z0-9]","_",line)[:40]}.txt').write_bytes(b);return b
    def mon(self):
        s=self.s
        if s.context is None:
            s.link.send(b'\x03\r');s.until(MONS+(t.REC,t.WB,SRAM,WORK,BM,FT,PB,opaque.PROMPT,FLASH_YES,PROGRAM_YES,DENSE_YES),seconds=12)
        if s.context in (FLASH_YES,PROGRAM_YES,DENSE_YES):self.cmd('NO',MONS+(FT,))
        if s.context==PB:s.link.send(b'Q');s.until(MONS)
        if s.context in (t.WB,SRAM,WORK,BM,FT,t.CLOCK):self.cmd('Q',MONS)
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        if s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        if s.context==t.REC:self.cmd('B',MONS)
        if s.context in MONS and s.context!=t.MON:self.cmd('B3',MONS)
        assert s.context==t.MON
    def rec(self):
        s=self.s
        if s.context==d.SERVICE:s.client.send(b'Q');s.client.until(t.REC);s.context=t.REC
        elif s.context==opaque.PROMPT:s.link.send(b'Q\r');s.link.until(t.REC);s.context=t.REC
        elif s.context!=t.REC:self.mon();self.cmd('Q',(t.REC,))
    def readback(self):
        if self.s.context!=d.SERVICE:self.rec();self.s.service(self.reader)
    def wire(self):
        if self.s.context!=opaque.PROMPT:self.rec();self.s.load(self.writer,t.sha(self.writer),opaque.PROMPT)
        return opaque.Wire(self.s.link.serial,timeout=90,trace=self.log,progress=lambda x:print(x,flush=True))
    def check(self,name):self.r['checks'].append(name);self.save();print('PASS2512 '+name,flush=True)
    def replace(self,bank,page,before,body):
        assert not self.r.get('uncertain_flash_mutation')
        assert (bank,page) in {(x['bank'],x['page']) for x in approved()['targets']} or (bank,page) in ((0,0x90),(0,0xA0))
        assert not (bank==3 and page in (0xA0,0xB0,0xC0,0xD0,0xF0))
        wire=self.wire();assert wire.read_sector(bank,page)==before and body!=before
        future,op=reserve(self.expected[3],bank*8+(page-0x80)//16)
        self.r['flash_erase_requests']+=1;self.r['pending_target']=f'B{bank}:{page:02X}00';self.save()
        self.s.context=None
        try:
            assert not wire.replace_sector(bank,page,before,body)
            self.s.context=opaque.PROMPT;assert wire.read_sector(bank,page)==body
        except BaseException:
            self.r['uncertain_flash_mutation']=self.r['pending_target'];self.save();raise
        b=bytearray(self.expected[bank]);off=(page-0x80)*256;b[off:off+4096]=body;self.expected[bank]=bytes(b)
        if bank==3:a=bytearray(future);a[off:off+4096]=body;future=bytes(a)
        self.expected[3]=future;self.r.pop('pending_target',None)
        self.r.setdefault('operations',[]).append(op)
        (self.folder/'B3-current-predicted.bin').write_bytes(future);self.save()
    def verify_banks(self,banks):
        self.readback()
        for bank in banks:
            b=self.s.client.flash(bank);assert b==self.expected[bank],f'Unexpected B{bank} image/history'
            (self.folder/f'B{bank}-after.bin').write_bytes(b)
        self.r['NVM_verified']=True;self.save()
    def __enter__(self):
        try:return self._enter()
        except BaseException as e:
            if self.created:self.__exit__(type(e),e,e.__traceback__)
            else:self.stack.close()
            raise
    def _enter(self):
        ins.window(self.seconds);self.folder.mkdir(exist_ok=False);self.created=True;(self.folder/'.gitignore').write_text('*\n')
        (self.folder/'common-driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
        for n in ('approval.json','plan.json','review.json','review-document.md'):(self.folder/n).write_bytes((SCOPE/n).read_bytes())
        self.save();self.stack.enter_context(t.serial_lease(self.kind,timeout=30));ins.window(self.seconds)
        self.marker=json.loads(self.mp.read_text())
        assert not self.marker['block_snapshot'] and self.marker['application_ram_restored'] and not self.marker['application_RAM_restore_pending']
        assert not any(v for k,v in self.marker.items() if k.endswith('_worker_active'))
        assert all(self.marker['current_physical_bank_sha256'][f'B{n}']==t.sha(b) for n,b in self.expected.items())
        self.log=self.stack.enter_context((self.folder/'serial.jsonl').open('x'))
        self.s=d.Session(self.folder,self.log,'2512');self.s.link.send(b'\r');self.s.until(MONS+(t.REC,),seconds=12);self.mon()
        assert b'g0000000F / MON B' in self.cmd('VERSION')
        self.prefix=self.s.dump(0x200,0x1FF+len(self.reader));self.zp=self.s.dump(0,0xDF)
        opaque.durable_file(self.folder/'owner-prefix.bin',self.prefix);opaque.durable_file(self.folder/'owner-zp.bin',self.zp)
        self.mark(storage_release_worker_active=True,application_RAM_restore_pending=True,block_snapshot=True);self.borrowed=True
        self.readback();memory=self.s.client.read(b'M',0x6500);assert memory[:len(self.reader)]==self.reader
        self.ram=self.prefix+memory[len(self.reader):];opaque.durable_file(self.folder/'owner-ram.bin',self.ram)
        return self
    def __exit__(self,typ,error,tb):
        if error:self.r['error']=repr(error)
        try:
            if self.borrowed:
                self.rec();self.s.service(self.reader)
                if self.ram is None:
                    memory=self.s.client.read(b'M',0x6500);assert memory[:len(self.reader)]==self.reader;self.ram=self.prefix+memory[len(self.reader):]
                self.r.update(self.s.client.restore_owner(self.ram,self.zp));self.s.context=t.REC
        finally:
            if self.s:self.s.link.close();self.r['port_released']=True
            if self.borrowed:
                restored=self.r['owner_RAM_restored'] and self.r['owner_ZP_restored']
                dirty=bool(self.r.get('B0_restore_pending') or self.r.get('SPI_restore_pending') or self.r.get('uncertain_flash_mutation'))
                safe=restored and not dirty and (not self.r['flash_erase_requests'] or self.r.get('NVM_verified'))
                kw=dict(storage_release_worker_active=False,application_RAM_restore_pending=not restored,application_ram_restored=restored,
                    block_snapshot=self.marker['block_snapshot'] if safe else True,final_prompt='REC>' if safe else 'PRESERVATION CHECK REQUIRED',
                    storage_batch_auto_qualification_pending=not (self.r.get('scope_checks_complete',False) and safe),last_storage_release_trial=str(self.folder/'report.json'))
                if self.r.get('NVM_verified'):
                    j=t.classify_journal(self.expected[3]);hs={f'B{n}':t.sha(b) for n,b in self.expected.items()}
                    counts=self.marker['current_tracked_erase_counts'].copy()
                    for i,v in enumerate(j['counts']):counts[f'B{i//8}:{i%8+8:X}']=v
                    for name,index in zip('ABCDEF',range(26,32)):counts[name]=j['counts'][index]
                    kw.update(current_physical_bank_sha256=hs,current_wear_counts=j['counts'],current_tracked_erase_counts=counts,
                        current_journal_sequence=j['sequence'],current_journal_valid_records=j['valid_records'],current_valid_journal_records=j['valid_records'],
                        workbench_generation='0000000E',storage_generation='00000004',native_storage_batch_capability='BQ/1.1',
                        current_owner_RAM_sha256=t.sha(self.ram),current_owner_ZP_sha256=t.sha(self.zp))
                self.mark(**kw)
            self.save();self.stack.close()
        return False
