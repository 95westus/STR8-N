"""Owner-authorized 2512 copyright candidate installation and live checks.

Fresh backup, exact native wear forecast, qualified OPAQUE writer, positive UI
checks and original owner-RAM/data preservation. Never writes Foundation or
installs host-loaded utilities in flash. No automatic ambiguous-write retry.
"""
import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import sys
import time

import memory_tool as m
from serial_test_coordination import serial_lease, drift_pending

REPO = m.ROOT/'release/str8nf-v0.2.0'
sys.path.insert(0,str(REPO/'tools'))
import nf_opaque as opaque
import nf_recovery as recovery
from journal_rotation_plan import reserve
from native_journal_room import classify_journal

KIT = m.ROOT/'BUILD/str8n-copyright-r2'
REC, MON = b'REC> ', b'B3> '


class Stream:
    def __init__(self,link): self.link=link
    def write(self,data): self.link.send(bytes(data)); return len(data)
    def read(self,count):
        if self.link.pending:
            data=bytes(self.link.pending[:count]); del self.link.pending[:count]; return data
        return self.link.read(count)


class Session:
    def __init__(self,out):
        from installer.engine.legacy_transport import Link
        self.out=out; self.log=(out/'serial.jsonl').open('x'); self.link=Link('COM4',self.log)
        self.context=None; self.counter=0
        self.link.send(b'\r'); self.until((MON,REC))
    def until(self,tokens,seconds=45):
        deadline=time.monotonic()+seconds
        while time.monotonic()<deadline:
            hits=[(self.link.pending.find(t),t) for t in tokens if t in self.link.pending]
            if hits:
                pos,self.context=min(hits,key=lambda x:x[0]); end=pos+len(self.context)
                data=bytes(self.link.pending[:end]); del self.link.pending[:end]; return data
            self.link.pending.extend(self.link.read(max(1,self.link.serial.in_waiting)))
        self.context=None
        raise TimeoutError(repr(bytes(self.link.pending[-300:])))
    def cmd(self,line,tokens=None):
        m.require(self.context is not None,'Unknown context; no blind commands')
        target=tokens or (self.context,)
        self.link.send(line.encode()+b'\r'); data=self.until(target)
        self.counter+=1
        m.durable(self.out/f'{self.counter:03d}-{re.sub("[^A-Za-z0-9]","_",line)[:40]}.txt',data)
        return data
    def rec(self):
        if self.context==opaque.PROMPT:
            self.link.send(b'Q\r'); self.until((REC,))
        elif self.context==recovery.PROMPT:
            self.link.send(b'Q'); self.until((REC,))
        elif self.context==MON: self.cmd('Q',(REC,))
        m.require(self.context==REC,'Known recovery prompt required')
    def load(self,body,prompt):
        m.require(self.context==REC and 0<len(body)<=0x6300,'REC/raw RAM load required')
        self.link.send(b'L\r'); self.until((b'SEND BIN\r\n',))
        for at in range(0,len(body),16):
            self.link.send(body[at:at+16]); time.sleep(.002)
        return self.until((prompt,))
    def reader(self):
        self.rec()
        body=(REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
        self.load(body,recovery.PROMPT)
        client=recovery.RecoveryClient(Stream(self.link),timeout=60)
        client.admitted=True
        return client
    def quit_reset(self):
        self.link.send(b'Q\r')
        self.until((b']:',REC,MON),seconds=20)
        if self.context==b']:': self.link.send(b'S\r'); self.until((REC,))
        if self.context==MON: self.rec()
    def close(self): self.link.serial.close(); self.log.close()


def run(out):
    out=Path(out).resolve(); out.mkdir(parents=True,exist_ok=False)
    m.durable(out/'.gitignore',b'*\n')
    m.durable(out/'driver.py',Path(__file__).read_bytes())
    profile=json.loads((m.ROOT/'firmware/memory-agent/profile.example.json').read_text())
    profile.update(board='2512',cpu='65c02',port='COM4',usb_serial='A10MQFLCA')
    m.save(out/'profile.json',profile)
    marker=m.ROOT/'output/qualification/device-operations/2512.json'
    original_marker=json.loads(marker.read_text()); m.durable(out/'marker-before.json',marker.read_bytes())
    report=dict(board='2512',passed=False,phase='prepared',F_writes=0,checks=[],completed=[],
                authorization='lets flash and test a board',started_utc=datetime.now(timezone.utc).isoformat(),
                RTC_writes=0,SPI_writes=0,EEPROM_writes=0,power_cuts=0,physical_resets=0)
    def save(): m.save(out/'report.json',report)
    def mark(**kw):
        state=json.loads(marker.read_text()); state.update(kw); state['last_copyright_trial']=str(out/'report.json'); m.save(marker,state)
    def check(name):
        report['checks'].append(name); save(); print('PASS '+name,flush=True)
    def artifact(component):
        catalog=json.loads((KIT/'COMPONENTS.json').read_text())['artifacts']
        files=[(f,i) for f,i in catalog.items() if i['component']==component and i.get('load')=='0200']
        m.require(len(files)==1,'RAM component must be unique')
        f,info=files[0]; data=(KIT/f).read_bytes(); m.require(m.sha(data)==info['sha256'],'Changed kit image'); return data
    save()
    with serial_lease('2512-copyright-install-and-test',timeout=30):
        m.require(not drift_pending(),'RTC collection pending; no port opened')
        backup_session=out/'backup-session'; backup_session.mkdir()
        device=None
        try:
            report['phase']='fresh-full-backup'; save()
            device=m.SerialDevice(profile,m.ROOT/'BUILD/memory-agent-v1',backup_session)
            m.backup(device,out/'original',list(m.ORDER))
        finally:
            if device: device.close()
        _,originals=m.archive(out/'original')
        banks=[originals['flash'][i*32768:(i+1)*32768] for i in range(4)]
        frozen=banks[3][-4096:]
        m.require(m.sha(frozen)==profile['foundation_sha256'],'Golden F required')
        catalog=json.loads((KIT/'NATIVE-COMPONENTS.json').read_text())
        expected=list(banks); targets=[]
        for item in catalog['targets']:
            info=item['variants']['65c02'] if 'variants' in item else item
            body=(KIT/info['file']).read_bytes(); m.require(m.sha(body)==info['sha256'],'Changed target')
            bank=item['bank']; address=int(item['address'],16); offset=address-0x8000
            m.require(bank<4 and not(bank==3 and address in (0xc000,0xd000,0xf000)),'Protected target')
            if item.get('preserve_RTC_metadata'): body+=banks[bank][offset+3072:offset+4096]
            m.require(len(body)==4096,'Full sector required')
            before=banks[bank][offset:offset+4096]
            if before!=body: targets.append(dict(bank=bank,address=address,before=before,body=body))
        # Keep MON B as fallback until the other images and MON A are verified.
        targets.sort(key=lambda x:(x['bank']==3 and x['address']==0xb000,
                                   not(x['bank']==3 and x['address']==0xa000),x['bank'],x['address']))
        forecast=[]
        for item in targets:
            bank,address=item['bank'],item['address']; offset=address-0x8000
            expected[3],operation=reserve(expected[3],bank*8+offset//4096)
            image=bytearray(expected[bank]); image[offset:offset+4096]=item['body']; expected[bank]=bytes(image)
            forecast.append(dict(bank=bank,address=f'{address:04X}',before_sha256=m.sha(item['before']),
                                 after_sha256=m.sha(item['body']),journal=operation))
        m.require(expected[3][-4096:]==frozen,'F forecast changed')
        m.save(out/'plan.json',dict(targets=forecast,F_writes=0,
                expected_bank_sha256=[m.sha(x) for x in expected],before_journal=classify_journal(banks[3]),
                after_journal=classify_journal(expected[3])))
        for i,data in enumerate(expected): m.durable(out/f'expected-B{i}.bin',data)
        report.update(phase='installing',image_sectors=len(targets),expected_bank_sha256=[m.sha(x) for x in expected]); save()
        print('PLAN: '+str(len(targets))+' changed sectors; Foundation protected; native wear accounting',flush=True)
        live=out/'live'; live.mkdir(); s=None; verified=False
        mark(copyright_install_worker_active=True,application_RAM_restore_pending=True,application_ram_restored=False,
             block_snapshot=True,firmware_verification_pending=True)
        try:
            s=Session(live); s.rec()
            writer=(REPO/'firmware/payload/STR8N-F-OPAQUE-RAM.bin').read_bytes()
            s.load(writer,opaque.PROMPT)
            wire=opaque.Wire(s.link.serial,timeout=90,trace=s.log,progress=lambda text:print(text,flush=True))
            for item in targets:
                bank,address=item['bank'],item['address']; page=address>>8
                m.require(wire.read_sector(bank,page)==item['before'],'Preimage differs; stop before write')
                report['pending_target']=dict(bank=bank,address=f'{address:04X}'); save()
                s.context=None
                wire.replace_sector(bank,page,item['before'],item['body']); s.context=opaque.PROMPT
                m.require(wire.read_sector(bank,page)==item['body'],'Independent sector readback differs')
                report['completed'].append(report['pending_target']); report['pending_target']=None; save()
            client=s.reader()
            actual=[client.flash(i) for i in range(4)]
            m.require(actual==expected,'Full flash differs from exact journal/image forecast')
            verified=True; check('all-four-banks-match-native-wear-forecast; F-exact')
            s.rec(); face=s.cmd('B',(MON,))
            m.require(b'STR8-N MON B' in face and b'(c)2026 95west.us/wlp1963; MIT' in face,'MON B identity missing')
            face=s.cmd('VERSION'); m.require(b'(c)2026 95west.us/wlp1963; MIT' in face,'MON B notice')
            s.rec(); face=s.cmd('A',(MON,)); face+=s.cmd('VERSION')
            m.require(b'MON A' in face and b'(c)2026 95west.us/wlp1963; MIT' in face,'MON A notice')
            s.rec(); s.cmd('B',(MON,)); check('MON-A/B-entry-and-VERSION-copyright')
            face=s.cmd('R CLOCK',(b'CLOCK> ',)); m.require(b'STR8-N UTIL CLOCK 1.10' in face,'CLOCK title')
            face=s.cmd('VERSION'); m.require(b'(c)2026 95west.us/wlp1963; MIT' in face,'CLOCK notice')
            for command in ('TIME','STATUS'): s.cmd(command)
            s.cmd('Q',(MON,)); check('CLOCK-start-VERSION-time-status; no-setting-writes')
            face=s.cmd('MAINT LOAD',(b'WORKBENCH> ',)); face+=s.cmd('VERSION')
            m.require(b'STR8-N UTIL MAINT WB2 gE' in face,'Workbench identity')
            s.cmd('SRAM'); s.cmd('WORK'); s.cmd('Q',(MON,)); check('MAINT-workbench-and-storage-queries')
            face=s.cmd('R ASM',(b'ASM> ',)); m.require(b'STR8-N DEV ASM' in face and b'Copyright (c)' in face,'ASM identity')
            s.cmd('NEW')
            for command in ('10 ORG $0200','20 LDA #$23','30 JSR $7E6D','40 JMP $7E67','50 END','ASM','LST'):
                face=s.cmd(command)
            m.require(b'A9 23' in face,'Assembler bytes missing')
            s.cmd('QUIT',(MON,b'Discard unsaved edits? Type YES: '))
            if s.context!=MON:s.cmd('YES',(MON,))
            check('installed-ASM-copyright-and-real-assembly')
            face=s.cmd('R DBG',(b'Q MON> ',)); m.require(b'STR8-N DEV DBG' in face and b'Copyright (c)' in face,'DBG identity')
            s.cmd('Q',(MON,)); check('installed-DBG-launch-and-safe-cancel')
            for component,prompt in (('CONFIG',b'RAM CONFIG ? B C I W Q> '),('FLASH',b'FLASH/MAINT> '),('MAINT',b'BM> ')):
                s.rec(); face=s.load(artifact(component),prompt)
                if component=='CONFIG':
                    m.require(b'Copyright (c)' in face,'CONFIG notice'); s.cmd('B'); s.cmd('W')
                else:
                    face=s.cmd('VERSION'); m.require(b'Copyright (c)' in face,component+' VERSION notice')
                    s.cmd('?')
                s.quit_reset(); check('RAM-'+component+'-identity-and-readonly-commands')
            s.rec(); face=s.load(artifact('OPAQUE'),opaque.PROMPT)
            m.require(b'Copyright (c)' in face,'OPAQUE wrapper notice')
            ow=opaque.Wire(s.link.serial,timeout=60,trace=s.log,progress=lambda _:None)
            m.require(ow.read_sector(0,0xe0)==expected[0][0x6000:0x7000],'New OPAQUE read mismatch')
            s.rec(); check('new-OPAQUE-banner-and-readonly-sector-transfer')
            report['phase']='final-flash-verification'; save()
            client=s.reader(); final=[client.flash(i) for i in range(4)]
            m.require(final==expected,'Tests changed flash outside planned installation')
            check('post-test-flash-F-journals-settings-exact')
        except BaseException as error:
            report['error']=repr(error); save(); raise
        finally:
            try:
                if s and s.context is not None:
                    if s.context not in (MON,REC,recovery.PROMPT,opaque.PROMPT):
                        if s.context in (b'CLOCK> ',b'WORKBENCH> '): s.cmd('Q',(MON,))
                        elif s.context==b'ASM> ': s.cmd('QUIT',(MON,))
                        elif s.context==b'Q MON> ': s.cmd('Q',(MON,))
                        elif s.context==b'Discard unsaved edits? Type YES: ': s.cmd('YES',(MON,))
                        elif s.context in (b'BM> ',b'FLASH/MAINT> ',b'RAM CONFIG ? B C I W Q> '): s.quit_reset()
                    client=s.reader(); report['RAM_cleanup']=client.restore_owner(originals['cpu-ram'],originals['zero-page']); s.context=REC
            finally:
                if s:s.close()
                restored=bool(report.get('RAM_cleanup',{}).get('owner_RAM_restored'))
                mark(copyright_install_worker_active=False,application_RAM_restore_pending=not restored,
                     application_ram_restored=restored,block_snapshot=not restored,
                     firmware_verification_pending=not verified,final_prompt='REC>' if restored else 'RESTORATION REQUIRED')
                if verified: mark(current_physical_bank_sha256={f'B{i}':m.sha(x) for i,x in enumerate(expected)})
                save()
        # New MEMORY packet; verify SPI/EEPROM and independently recaptured RAM.
        report['phase']='new-MEMORY-preservation-verification'; save()
        last=out/'new-memory-session'; last.mkdir(); v=None
        try:
            v=m.SerialDevice(profile,KIT/'memory-agent-build',last)
            for name in ('spi-sram','spi-mode','eeprom','zero-page','cpu-ram'):
                data=m.read_region(v,name,initial=True)
                m.require(data==originals[name],'Original memory differs: '+name)
                m.durable(last/(name+'.bin'),data); check('original-'+name+'-preserved')
        finally:
            if v:v.close()
        state=json.loads(marker.read_text()); j=classify_journal(expected[3])
        state.update(copyright_candidate_installed=str(KIT),copyright_candidate_live_passed=True,
                     firmware_verification_pending=False,current_journal_sequence=j.get('sequence'),
                     current_journal_valid_records=j.get('valid_records'),final_prompt='REC>')
        tracked=state.setdefault('current_tracked_erase_counts',{})
        for index,count in enumerate(j['counts']):
            tracked[f'B{index//8}:{index%8+8:X}']=count
        for alias,index in {'A':26,'B':27,'C':28,'D':29,'E':30,'F':31}.items():tracked[alias]=j['counts'][index]
        state['current_full_flash_sha256']=m.sha(b''.join(expected))
        m.save(marker,state)
        report.update(passed=True,phase='complete',port_released=True,finished_utc=datetime.now(timezone.utc).isoformat())
        save()
    print(json.dumps(dict(passed=True,report=str(out/'report.json'),checks=len(report['checks'])),indent=2))


if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__); p.add_argument('--out',type=Path,required=True)
    run(p.parse_args().out)
