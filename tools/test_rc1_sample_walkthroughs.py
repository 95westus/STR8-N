"""Execute the workbook's precise debugger commands on both CPU models."""
import hashlib
import json
import os
from pathlib import Path
import re
import sys

os.environ.setdefault('STR8_SOURCE_BUILD','BUILD/current')
from test_rc1_source_store import Harness, ROOT, OUT
from test_rc1_dev_samples import SampleMemory


def registers(text):
    matches=re.findall(r'PC=([0-9A-F]{4}) A=([0-9A-F]{2}) X=([0-9A-F]{2}) Y=([0-9A-F]{2}) P=([0-9A-F]{2}) S=([0-9A-F]{2})',text)
    return dict(zip(('PC','A','X','Y','P','S'),matches[-1])) if matches else None


def commands(stem):
    edu=stem=='edu-led31'
    return [('G 0200','debug'),*[(s,'debug') for s in
        ('R A=00','R X=00','R Y=00','R P=24','R S=FF','R',
         'U '+('0252' if edu else '021E')+' 04','S',
         'B '+('0272' if edu else '0241'),'C','S' if edu else 'N',
         'N' if edu else 'S','S',*(['S'] if edu else []),
         'D '+('0391 0392' if edu else '02C7 02C8'),
         'BC '+('0272' if edu else '0241'),'C')],('C','monitor')]


def main():
    cases=[]
    for cpu in ('65c02','65c816-e'):
        for slot in ('A','B'):
            for stem in ('sxb-cs-patterns','edu-led31'):
                h=Harness(cpu,slot,memory_factory=SampleMemory);h.command_limit=15000000
                image=(ROOT/'BUILD/rc1-dev-samples/listings'/(stem+'.bin')).read_bytes()
                h.m.ram[0x200:0x200+len(image)]=image
                delay=0x28E if stem=='edu-led31' else 0x254
                original=h.cpu.step
                paced=False
                def step():
                    if paced and h.cpu.pc==delay:
                        h.cpu.x=1;h.cpu.pc+=2;return
                    if paced and stem=='sxb-cs-patterns' and h.cpu.pc==delay+2:
                        h.cpu.y=1;h.cpu.pc+=2;return
                    return original()
                h.cpu.step=step; rows=[]
                for i,(command,context) in enumerate(commands(stem)):
                    # Only the final C animation uses accelerated dwell; N
                    # executes the original first frame's complete loop.
                    paced=command=='C' and rows and rows[-1]['command'].startswith('BC ')
                    text=h.command(command,context)
                    assert '?' not in text and 'INVALID' not in text,(command,text)
                    rows.append(dict(command=command,context=context,registers=registers(text),output=text))
                expected='028B' if stem=='edu-led31' else '0251'
                assert rows[-2]['registers']['PC']==expected
                normalized=next(r for r in rows if r['command']=='R')['registers']
                assert normalized==dict(PC='0252' if stem=='edu-led31' else '021E',A='00',X='00',Y='00',P='24',S='FF'),normalized
                cases.append(dict(cpu=cpu,slot=slot,sample=stem,passed=True,commands=rows))
                print('PASS walkthrough',cpu,slot,stem,flush=True)
    for stem in ('sxb-cs-patterns','edu-led31'):
        selected=[c['commands'] for c in cases if c['sample']==stem]
        # Initial entry registers may differ; all states after explicit
        # normalization and each subsequent step must agree across models.
        for rows in selected[1:]:
            assert [r['registers'] for r in rows[6:]]==[r['registers'] for r in selected[0][6:]]
    report=dict(passed=True,board_access=False,firmware_sha256=hashlib.sha256((OUT/'firmware.bin').read_bytes()).hexdigest(),
                full_original_first_dwell=True,final_animation_dwell_accelerated=True,cases=cases)
    dest=ROOT/'BUILD/rc1-dev-samples/walkthroughs.json';dest.write_text(json.dumps(report,indent=2)+'\n')


if __name__=='__main__':main()
