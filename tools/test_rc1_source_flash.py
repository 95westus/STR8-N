"""Execute flash source storage with linked RAM flash worker and AMD command model.

No board/network/serial access. All actual byte programming, polling and verify
instructions execute; only the flash chip and optional SRAM transfers are modeled.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import struct
from test_rc1_source_store import Harness, Memory, OUT, ROOT, packed, capsule


class Cut(BaseException):
    pass


class FlashMemory(Memory):
    def __init__(self,image,data=None):
        super().__init__(image,data)
        self.unlock=0;self.busy=None;self.events=[];self.programmed=set()
        self.flash_cut=None;self.flash_fault=None;self.id_mode=False

    def __getitem__(self,a):
        if isinstance(a,int) and a>=0x8000:
            if self.id_mode and a in (0x8000,0x8001):return 0xBF if a==0x8000 else 0xB5
            if self.busy:
                assert self.cpu.pc<0x8000, ('ROM fetch while flash busy',self.cpu.pc)
                bank,address,value,ticks=self.busy
                assert self.bank==bank
                if ticks:
                    self.busy=(bank,address,value,ticks-1)
                    return value^0x80
                self.busy=None
        return super().__getitem__(a)

    def __setitem__(self,a,v):
        if a<0x8000:return super().__setitem__(a,v)
        v&=255
        if self.unlock==3:
            assert self.cpu.pc<0x8000, 'Programming must execute in RAM'
            assert self.bank==0 and 0x8000<=a<0xE000, ('Protected flash mutation',self.bank,a)
            assert self.banks[0][a-0x8000]==255 and a not in self.programmed, ('Reprogrammed byte',a)
            self.programmed.add(a)
            actual=v^(1 if self.flash_fault=='verify' else 0)
            self.banks[0][a-0x8000]=actual
            self.busy=(self.bank,a,v,2);self.unlock=0
            self.events.append((self.bank,a,v))
            if self.flash_cut:self.flash_cut(len(self.events),a,v)
        elif a in (0xD555,0x8000) and v==0xF0:
            self.unlock=0;self.busy=None;self.id_mode=False
        elif self.unlock==0 and a==0xD555 and v==0xAA:self.unlock=1
        elif self.unlock==1 and a==0xAAAA and v==0x55:self.unlock=2
        elif self.unlock==2 and a==0xD555 and v==0xA0:self.unlock=3
        elif self.unlock==2 and a==0xD555 and v==0x90:self.unlock=0;self.id_mode=True
        else:raise AssertionError(('Unexpected/erase flash command',self.unlock,a,v))


def source_record(name,source,marker=0x3F):
    body=capsule(source);header=bytearray(32)
    header[:4]=b'SF\1\xff';header[4:6]=len(body).to_bytes(2,'little')
    header[6]=1 if len(body)<=4064 else 2
    header[8:24]=name.encode().ljust(16,b'\0')
    header[24:26]=binascii.crc_hqx(header[:24],0xFFFF).to_bytes(2,'little')
    header[3]=marker
    return header+body


def fixture(cpu='65c02',slot='A',edu=False,bank=None):
    h=Harness(cpu,slot,edu=edu,memory_factory=FlashMemory)
    h.command_limit=10000000
    if bank is not None:h.m.banks[0][:]=bank
    h.open()
    return h


def main():
    ap=argparse.ArgumentParser();ap.add_argument('--cpu',choices=('65c02','65c816-e'),default='65c02')
    ap.add_argument('--smoke',action='store_true');a=ap.parse_args()
    digest=hashlib.sha256(Path(__file__).read_bytes()).hexdigest()
    checks=[];transcripts=[]
    def passed(text):
        checks.append(text);print('PASS',text,flush=True)
        (OUT/f'flash-progress-{a.cpu}.json').write_text(json.dumps(dict(
            complete=False,cpu=a.cpu,checks=checks,harness_sha256=digest,
            firmware_sha256=hashlib.sha256((OUT/'firmware.bin').read_bytes()).hexdigest()),indent=2)+'\n')
    if a.smoke:
        h=fixture(a.cpu);h.set_source(packed([(10,'SEI'),(20,'END')]))
        print(h.command('SAVE FLASH DEMO'),flush=True)
        print(h.m.events,flush=True)
        print(h.command('LOAD FLASH DEMO'),flush=True)
        return
    program=[(10,'ORG $0200'),(20,'SEI'),(30,'CLD'),(35,'JSR wipe'),(40,'LDX #$01'),
             (50,'BRK $01'),(60,'INX'),(70,'BRK $02'),(80,'JMP $7E67'),
             (90,'wipe: LDA #$00'),(100,'STA $10'),(110,'LDA #$33'),(120,'STA $11'),
             (130,'LDY #$00'),(140,'LDA #$A7'),(150,'page: STA ($10),Y'),(160,'INY'),
             (170,'BNE page'),(180,'INC $11'),(190,'LDX $11'),(200,'CPX #$4F'),
             (210,'BNE page'),(220,'RTS'),(230,'END')]
    for edu in (False,True):
        for slot in ('A','B'):
            h=fixture(a.cpu,slot,edu);m=h.m
            system=[bytes(b) for b in m.banks[1:]];external=bytes(m.data)
            optional=bytes(m.ram[0x6500:0x6700]);upper=bytes(m.banks[0][0x6000:])
            for n,line in program:h.command(f'{n} {line}')
            source=h.source();h.command('SAVE FLASH DEMO',contains='Source saved')
            assert m.banks[0][:32+len(capsule(source))]==source_record('DEMO',source)
            image=bytes(m.banks[0]);events=len(m.events)
            h.command('SAVE FLASH DEMO',contains='Source storage: 50')
            assert len(m.events)==events and bytes(m.banks[0])==image
            h.command('ASM',contains='OK ')
            n=int.from_bytes(m.ram[0x6302:0x6304],'little');code=bytes(m.ram[0x200:0x200+n])
            h.command('QUIT','monitor');h.command('G 0200','debug',contains='PC=0209')
            assert m.ram[0x3300:0x4F00]==b'\xA7'*7168
            h.command('S','debug',contains='X=02');h.command('X','monitor');h.open()
            h.command('LOAD FLASH DEMO',contains='Source loaded');assert h.source()==source
            h.command('ASM',contains='OK ');assert bytes(m.ram[0x200:0x200+n])==code
            h.command('40 LDX #$05');h.command('SAVE FLASH DEMO2',contains='Source saved')
            h.command('ASM',contains='OK ');h.command('QUIT','monitor')
            h.command('G 0200','debug',contains='X=05');h.command('N','debug',contains='X=06')
            h.command('C','debug');h.command('C','monitor');h.open()
            h.command('LOAD FLASH DEMO2',contains='Source loaded');assert b'LDX #$05' in h.source()
            # Flash sources are not SR executable records. The normal R command
            # cannot load/execute their payload, including addressed lookup.
            h.command('QUIT','monitor')
            for command in ('R 0 DEMO','R 0 8000'):
                result=h.command(command,'monitor')
                assert result.rstrip().endswith('B3>') and m.bank==3,(command,result,m.bank)
            assert system==[bytes(b) for b in m.banks[1:]]
            assert bytes(m.data)==external and bytes(m.banks[0][0x6000:])==upper
            assert bytes(m.ram[0x6500:0x6700])==optional
            if not edu:assert not m.transfers
            transcripts.append(dict(cpu=a.cpu,slot=slot,edu=edu,commands=h.transcripts))
            cold=fixture(a.cpu,slot,edu,bytes(m.banks[0]))
            cold.command('LOAD FLASH DEMO2',contains='Source loaded')
            assert b'LDX #$05' in cold.source()
            print('PASS flash cycle',a.cpu,slot,'EDU' if edu else 'bare SXB',flush=True)
    passed('MON A/B, bare SXB and EDU: flash edit-save-assemble-debug-overwrite-source-load-edit-new-name-rebuild-debug; retained flash after fresh CPU initialization; normal R refuses source data')
    (OUT/f'flash-transcripts-{a.cpu}.json').write_text(json.dumps(transcripts,indent=2)+'\n')
    # Other saved programs/opaque vendor bytes remain intact. Only entire
    # erased sectors qualify, even if a sector has an apparently empty header.
    base=packed([(10,'SEI'),(20,'END')])
    for edu in (False,True):
        h=fixture(a.cpu,edu=edu);h.set_source(base)
        h.m.banks[0][0x800:0x810]=bytes(range(16));h.m.banks[0][0x4000:]=b'\x81'*0x4000
        before=bytes(h.m.banks[0]);h.command('SAVE FLASH SAFE',contains='Source saved')
        assert h.m.banks[0][:0x1000]==before[:0x1000]
        assert h.m.banks[0][0x2000:]==before[0x2000:]
        assert h.m.banks[0][0x1000:0x1002]==b'SF'
        snapshot=bytes(h.m.banks[0]);h.command('LOAD FLASH ABSENT',contains='Source storage: 42')
        assert bytes(h.m.banks[0])==snapshot and h.source()==base
        # No implicit fallback between storage providers.
        if edu:
            h.command('LOAD SRAM SAFE',contains='Source storage: 42')
            h.command('SAVE SRAM SAME',contains='Source saved')
            h.command('SAVE FLASH SAME',contains='Source saved')
        else:h.command('LOAD SRAM SAFE',contains='Source storage: 80')
    passed('whole-erased-sector allocation preserves opaque/previous data; explicit providers with no fallback; absent EDU refuses SRAM while flash works')
    full=packed([(i,';'+'X'*119) for i in range(1,58)]+[(58,';'+'Y'*95)])
    assert len(full)==7168
    for edu in (False,True):
        h=fixture(a.cpu,edu=edu);h.command('SAVE FLASH EMPTY',contains='Source saved')
        h.command('LOAD FLASH EMPTY',contains='Source loaded');assert h.source()==b''
        h.set_source(full);h.command('SAVE FLASH MAX',contains='Source saved')
        h.set_source(b'',dirty=0);h.command('LOAD FLASH MAX',contains='Source loaded');assert h.source()==full
        assert h.m.banks[0][0x1006]==2
        h.set_source(base);before=h.source()
        h.command('LOAD FLASH EMPTY\rNO',contains='Load cancelled');assert h.source()==before
        h.command('LOAD FLASH EMPTY\rYES',contains='Source loaded');assert h.source()==b''
    passed('empty and maximum 7168-byte sources; two-sector payload; confirmation/cancellation in both configurations')
    for edu in (False,True):
        h=fixture(a.cpu,edu=edu);h.set_source(base)
        h.m.banks[0][:0x6000]=b'\xA5'*0x6000;snapshot=bytes(h.m.banks[0])
        h.command('SAVE FLASH FULL',contains='Source storage: 51')
        assert bytes(h.m.banks[0])==snapshot and h.source()==base
        for kind in ('metadata','payload','length','ambiguous','pending','marker'):
            h=fixture(a.cpu,edu=edu);h.set_source(base,dirty=0)
            r=source_record('BAD',base);h.m.banks[0][:len(r)]=r
            if kind=='metadata':h.m.banks[0][8]^=1
            elif kind=='payload':h.m.banks[0][40]^=1
            elif kind=='length':
                h.m.banks[0][4:6]=b'\xff\xff';header=bytearray(h.m.banks[0][:32]);header[3]=255
                h.m.banks[0][24:26]=binascii.crc_hqx(header[:24],0xFFFF).to_bytes(2,'little')
            elif kind=='ambiguous':h.m.banks[0][0x1000:0x1000+len(r)]=r
            elif kind=='pending':h.m.banks[0][3]=255
            else:h.m.banks[0][3]=0x7F
            before=h.source();snapshot=bytes(h.m.banks[0])
            result=h.command('LOAD FLASH BAD')
            assert ('Invalid source image' in result or 'Source storage:' in result),(kind,result)
            assert h.source()==before and bytes(h.m.banks[0])==snapshot
            if kind=='pending':
                h.command('SAVE FLASH BAD',contains='Source storage: 50')
                assert bytes(h.m.banks[0])==snapshot
    passed('full/corrupt/torn/ambiguous/oversized flash metadata and corrupt payload refuse without source replacement or flash writes')
    # Verify failure is reported by the linked worker's actual comparison.
    h=fixture(a.cpu);h.set_source(base);h.m.flash_fault='verify'
    h.command('SAVE FLASH BAD',contains='Source storage: 53');assert h.source()==base
    h.m.flash_fault=None
    h.command('LOAD FLASH BAD\rYES',contains='Source storage: 42')
    passed('program/readback failure prevents publication; source remains editable')
    # Header/first-payload/last-payload/commit cuts, including every header byte.
    reference=fixture(a.cpu);reference.set_source(base);reference.command('SAVE FLASH CUT',contains='Source saved')
    count=len(reference.m.events)
    first_payload=next(i for i,(_,address,_) in enumerate(reference.m.events,1) if address>=0x8020)
    cuts=sorted({*range(1,first_payload+1),count-1,count})
    for edu in (False,True):
        for cut in cuts:
            h=fixture(a.cpu,edu=edu);h.set_source(base)
            def interrupt(n,address,value):
                if n==cut:raise Cut()
            h.m.flash_cut=interrupt
            try:h.command('SAVE FLASH CUT')
            except Cut:pass
            else:raise AssertionError(('cut not reached',cut,count))
            cold=fixture(a.cpu,edu=edu,bank=bytes(h.m.banks[0]));cold.set_source(b'',dirty=0)
            result=cold.command('LOAD FLASH CUT')
            if cut==count:assert 'Source loaded' in result and cold.source()==base
            else:assert 'Source loaded' not in result and cold.source()==b'',(cut,result)
            assert [bytes(b) for b in cold.m.banks[1:]]==[bytes(b) for b in h.m.banks[1:]]
    passed(f'{len(cuts)*2} flash program-cut/restart cases: no source published before final commit; committed source reloads')
    for edu in (False,True):
        h=fixture(a.cpu,edu=edu);h.set_source(full)
        def cut_second_sector(n,address,value):
            if address>=0x9000:raise Cut()
        h.m.flash_cut=cut_second_sector
        try:h.command('SAVE FLASH TWOSECT')
        except Cut:pass
        else:raise AssertionError('second-sector cut not reached')
        cold=fixture(a.cpu,edu=edu,bank=bytes(h.m.banks[0]))
        cold.command('LOAD FLASH TWOSECT',contains='Source storage: 42')
        cold.set_source(base);cold.command('SAVE FLASH NEXT',contains='Source saved')
        assert cold.m.banks[0][0x2000:0x2002]==b'SF'
    passed('two-sector interruption remains unpublished and reserves both sectors; next new-name save preserves the partial source extent')
    report=dict(passed=True,cpu=a.cpu,configurations=['bare-sxb','sxb-edu'],monitor_slots=['A','B'],
                checks=checks,check_groups=len(checks),write_cut_cases=len(cuts)*2+2,board_access=False,
                serial_ports_opened=False,sector_erases=0,peripheral_model='AMD byte-program/poll/verify flash chip; optional SRAM transfer ABI',
                firmware_sha256=hashlib.sha256((OUT/'firmware.bin').read_bytes()).hexdigest(),harness_sha256=digest)
    (OUT/f'flash-test-{a.cpu}.json').write_text(json.dumps(report,indent=2)+'\n')
    print('PASS all flash source checks',a.cpu,flush=True)


if __name__=='__main__':main()
