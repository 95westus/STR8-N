"""Bounded adaptation of the archived CONFIG exercise, plus retained-SRAM model.

Keeps the original checker immutable. Only the profile import, sequence/slot
tokens and peripheral observation hooks change. Runs in an offline process.
"""
import json,re,sys,types
from pathlib import Path
import prepare_config_save_restore_seq1021_2609 as p
from edu_sram_model import attach
from test_b14_raw import start,feed

CHECKS=0
ORIGINAL=None


def attach_peripheral(h):
    v=attach(h,mode=0x40);v.chip.data[:]=ORIGINAL;return h


def check_sram(h):
    global CHECKS
    v=h.via;assert bytes(v.chip.data)==ORIGINAL and v.chip.mode==0x40
    assert not v.reads and not v.writes and not v.chip.writes and not v.chip.mode_writes
    CHECKS+=1


def main():
    global ORIGINAL
    plan=Path(sys.argv[sys.argv.index('--plan')+1]).resolve();out=Path(sys.argv[sys.argv.index('--out')+1]).resolve();info=p.verify(plan)
    ORIGINAL=Path(info['baseline']['SRAM_source']).read_bytes();p.admit_SRAM(ORIGINAL,info)
    raw=(p.HERE/'test_config_save_restore_2609.py').read_bytes()
    assert p.cfg.sha(raw)=='2e3b427dec38924b213cac0eb4d57fb5119452bf9383f318942296deadfbdc7a'
    source=raw.decode();old='import prepare_config_save_restore_2609 as p';assert source.count(old)==1
    replacements={'1021':'1022','1022':'1023','0xc600':'0xc700','0xc700':'0xc800','0xc800':'0xc900','0xc6ff':'0xc7ff',
                  'C600':'C700','C6FF':'C7FF','C700':'C800'}
    changes={}
    def swap(match):
        key=match[0];changes[key]=changes.get(key,0)+1;return replacements[key]
    source=re.sub('|'.join(map(re.escape,sorted(replacements,key=len,reverse=True))),swap,source)
    assert all(changes.get(key,0) for key in replacements)
    source=source.replace(old,'import prepare_config_save_restore_seq1021_2609 as p')
    source=source.replace('h=t.current_machine(', 'h=current_machine(')
    anchor='    h=t.legacy.core.Machine(build,cpu,opaque=True)\n'
    assert source.count(anchor)==1;source=source.replace(anchor,anchor+'    attach_peripheral(h)\n')
    assert source.count('    return h\n')==1;source=source.replace('    return h\n','    check_sram(h)\n    return h\n')
    anchor='reply=h.port_command(port,body,prompt);transcript.extend(reply);return reply'
    assert source.count(anchor)==1;source=source.replace(anchor,'reply=h.port_command(port,body,prompt);transcript.extend(reply);check_sram(h);return reply')
    # Use a peripheral-observed boot-record reader for every torn-write prefix.
    source=source.replace('t.legacy.reboot_reader(build,cpu,banks)','observed_reader(build,cpu,banks)')
    module=types.ModuleType('config_seq1021_model');module.__file__=__file__
    module.attach_peripheral=attach_peripheral;module.check_sram=check_sram
    def current_machine(build,cpu,port=1,banks=None):
        t=module.t;h=t.legacy.core.Machine(build,cpu,opaque=True);attach_peripheral(h)
        h.m.banks[:]=list(map(bytearray,banks));h.recovery();h.run(lambda:h.c.pc==h.b['BOOT_B08_READ_LINE'])
        h.original_ram=bytes(h.m.ram);h.initial_banks=tuple(map(bytes,h.m.banks));body=(build/'payload'/p.cfg.BIN).read_bytes();h.loaded_end=0x200+len(body)
        start(h,port);feed(h,port,body);h.run(lambda:bytes(h.m.tx).endswith(module.CFG) and bytes(h.m.acia_tx).endswith(module.CFG))
        assert not h.m.events;check_sram(h);return h
    def observed_reader(build,cpu,banks):
        t=module.t;h=t.legacy.core.Machine(build,cpu,opaque=True);attach_peripheral(h);h.m.banks[:]=list(map(bytearray,banks))
        assert h.call(h.b['BOOT_READ_RECORD']) and bytes(h.m.ram[0x6700:0x6720])==t.legacy.latest(banks)[:32]
        assert not h.m.events;check_sram(h);return h
    module.current_machine=current_machine;module.observed_reader=observed_reader
    exec(compile(source,str(p.HERE/'test_config_save_restore_2609.py'),'exec'),module.__dict__);module.main()
    q=p.cfg.read(out/'qualification.json');assert q['checks']==23
    # Host guards reject a changed ES1 sector/old wear row and altered SRAM.
    original=module.banks_at(plan,'source')
    for bank,offset in ((3,0x20),(3,0x46a0)):
        bad=list(map(bytearray,original));bad[bank][offset]^=1
        try:p.admit_source(bad,info)
        except AssertionError:pass
        else:raise AssertionError('Changed ES1/source journal accepted')
    q['cases'].append(dict(passed=True,cpu='host',port=0,case='changed-ES1-and-seq1021-wear-row-refused',cases=2))
    bad=bytearray(ORIGINAL);bad[65536]^=1
    try:p.admit_SRAM(bad,info)
    except AssertionError:pass
    else:raise AssertionError('Changed retained SRAM accepted')
    q['cases'].append(dict(passed=True,cpu='host',port=0,case='changed-retained-SRAM-refused'))
    q.update(checks=len(q['cases']),retained_SRAM_checks=CHECKS,no_SPI_access=True,SRAM_sha256=p.cfg.sha(ORIGINAL),
        peripheral_model_sha256=p.cfg.digest(p.HERE/'edu_sram_model.py'),source_profile='ES1 seq1021; counts B3:8=27',
        adapted_checker_sha256=p.cfg.sha(source.encode()),archived_checker_sha256=p.cfg.sha(raw))
    p.cfg.save(out/'qualification.json',q);p.cfg.save(out/'adapter.json',dict(archived_checker_sha256=p.cfg.sha(raw),
        adapted_checker_sha256=p.cfg.sha(source.encode()),adapter_sha256=p.cfg.digest(__file__),token_changes=changes,
        hooks=['Peripheral attached before CONFIG startup/cold boot/record reader','Every walkthrough command asserts retained array/mode and no SPI access'],retained_SRAM_checks=CHECKS))
    print('PASS',q['checks'],'groups;',q['mutation_prefixes'],'prefixes;',CHECKS,'retained SRAM/no-SPI checks; no device access',flush=True)


if __name__=='__main__':main()
