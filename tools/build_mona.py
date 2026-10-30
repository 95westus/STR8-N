"""Build one MON A/B/RAM generation; never rebuild F or access a port.

The script/source filenames retain their historical spelling for existing callers.
New artifacts and runtime banners use STR8-N / MON A/B.
"""
import argparse
import binascii
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from mona_branches import conservative_branches

ROOT = Path(__file__).resolve().parents[1]
sha = lambda body: hashlib.sha256(body).hexdigest()
read_json = lambda path: json.loads(path.read_text(encoding='utf-8'))


def equs(path):
    return {name:int(value,16) for name,value in re.findall(
        r'^(\w+)\s+EQU\s+\$([0-9A-Fa-f]+)', path.read_text(encoding='utf-8'), re.M)}


def cells(path):
    found = {}
    for line in path.read_text(encoding='ascii').splitlines():
        row = bytes.fromhex(line[2:])
        assert len(row) == row[0]+1 and sum(row)&255 == 255
        if line.startswith('S1'):
            address = int.from_bytes(row[1:3],'big')
            for offset,value in enumerate(row[3:-1]):
                assert address+offset not in found
                found[address+offset] = value
    return found


def build(out, generation):
    if not 1 <= generation <= 0xffffffff:
        raise ValueError('Generation must be 1..FFFFFFFF')
    generation_text = f'{generation:08X}'
    out = Path(out).resolve()
    if out.exists():
        raise ValueError('Use a fresh build directory; previous outputs are preserved')
    assembler,linker = shutil.which('wdc02as'),shutil.which('wdcln')
    if not assembler or not linker:
        raise ValueError('WDC assembler/linker not found')
    freeze = read_json(ROOT/'F_FREEZE.json')
    f = (ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin').read_bytes()
    assert len(f) == 4096 and sha(f) == freeze['sha256']
    for name,digest in freeze['sources'].items():
        assert sha((ROOT/name).read_bytes()) == digest, name
    dependency = read_json(ROOT/'monitors/base1-dependency.json')
    assert dependency['foundation']['F_sha256'] == sha(f)
    bs = equs(ROOT/'src/core/boot-symbols.inc')
    ws = equs(ROOT/'src/core/worker-public-symbols.inc')
    private = dict(MON_F_READ=ws['V2W_READ'], MON_F_EXECUTE=ws['V2W_EXECUTE'],
                   MON_F_RECOVERY=bs['BOOT_RECOVERY'], MON_F_NO_SERVICE=bs['BOOT_NO_SERVICE'],
                   MON_F_BOOT_READ=bs['BOOT_READ_RECORD'],MON_F_SELECT=ws['V2W_SELECT'],
                   MON_F_BYTE=ws['V2W_BYTE']+2)
    # Private raw-L entry found in the exact frozen F, never a new public ABI.
    load_pattern = bytes.fromhex('9c697cad2a7c8d2b7c20577b')
    assert f.count(load_pattern) == 1
    private['MON_F_LOAD'] = 0xf000+f.index(load_pattern)
    crc = binascii.crc_hqx(f,0xffff)
    core_sources=('mona.asm','adapter.inc','layout.inc','rtc-read.inc','force.inc',
                  'workbench-interface.inc','service-interface.inc','monitor-ui.inc')
    inputs = {'monitors/src/'+name:sha((ROOT/'monitors/src'/name).read_bytes()) for name in core_sources}
    out.mkdir(parents=True)
    artifacts = {}
    logs = []
    branch_layout = {}
    for variant,page,label in (('A',0xa0,'MON A'),('B',0xb0,'MON B'),('RAM',0,'RAM')):
        stage = out/variant
        stage.mkdir()
        origin = page*256+0x80 if page else 0x0200
        for filename in core_sources:
            body = (ROOT/'monitors/src'/filename).read_text(encoding='utf-8')
            body = body.replace('MON_SLOT_LABEL', '"'+label+'"')
            body = body.replace('MON_GENERATION_TEXT', generation_text)
            if filename != 'layout.inc':
                body,info = conservative_branches(body, prefix='M_LONG_'+variant+'_'+re.sub(r'\W','_',filename)+'_')
                branch_layout[variant+'/'+filename] = info
                if filename=='force.inc':
                    kernel=body.split('MF_FLASH_IMAGE:',1)[1].split('MF_FLASH_END:',1)[0]
                    assert [line.strip() for line in kernel.splitlines() if line.strip().startswith('JMP ')]==['JMP MF_FLASH_DONE']
            (stage/filename).write_text(body,encoding='utf-8',newline='\n')
        shutil.copyfile(ROOT/'src/include/str8n-v2-public.inc', stage/'str8n-v2-public.inc')
        declarations = dict(private, MON_SLOT_PAGE=page,
                            MON_SLOT_CHAR=ord(variant[0]), MON_SERVICE_BASE=0xE000 if page else 0x2000,
                            MON_RAM_FLOOR=2 if page else 0x30, MON_F_CRC_LO=crc&255, MON_F_CRC_HI=crc>>8)
        (stage/'foundation.inc').write_text(''.join(f'{name} EQU ${value:04X}\n' for name,value in declarations.items()),
                                            encoding='ascii',newline='\n')
        entry = '        DB "SN",2,0\n        JMP M_START\n        JMP M_START\n' if page else '        JMP M_START\n'
        (stage/'entry.inc').write_text(entry,encoding='ascii',newline='\n')
        for command in ([assembler,'-G','-L','-S','-W','mona.asm'],
                        [linker,'-g','-s','-t',f'-c{origin:04X}','-hm19','-j','-o','mona.s19','mona.obj']):
            done = subprocess.run(command,cwd=stage,capture_output=True,text=True,encoding='utf-8')
            logs.append(dict(variant=variant,command=command,returncode=done.returncode,
                             stdout=done.stdout,stderr=done.stderr))
            (out/'build-log.json').write_text(json.dumps(logs,indent=2)+'\n',encoding='utf-8',newline='\n')
            if done.returncode:
                raise RuntimeError('MON A/B build failed; inspect '+str(out/'build-log.json'))
        sy = {name:int(value,16) for value,name in re.findall(r'^\s*([0-9A-Fa-f]{8})\s+(\w+)\s*$',
              (stage/'mona.map').read_text(encoding='utf-8'),re.M)}
        memory = cells(stage/'mona.s19')
        assert set(memory) == set(range(origin,sy['M_END']))
        body = bytes(memory[address] for address in range(origin,sy['M_END']))
        assert sy['M_RA']-sy['M_EXPECT_ID'] == 40
        assert sy['MF_FLASH_END']-sy['MF_FLASH_IMAGE']<128
        assert len(body) <= (3968 if page else 25344)
        if page:
            assert body[:4] == b'SN\x02\0' and body[4] == body[7] == 0x4c
            image = bytearray(b'\xff'*4096)
            image[:8] = b'MI\x01'+bytes((page,3,1,0,0))
            image[8:12] = generation.to_bytes(4,'little')
            for offset,value in ((12,len(body)),(14,origin+4),(16,origin+7)):
                image[offset:offset+2] = value.to_bytes(2,'little')
            image[20:24] = b'PR05'
            image[24] = 0xFE  # Monitor install-check byte; outside F's CRC/admission fields.
            image[31] = 0
            for offset in range(32,72,2):
                image[offset:offset+2] = sy['M_UNSUPPORTED'].to_bytes(2,'little')
            # CRC-covered optional MON/tool API. F does not interpret it.
            for index,name in enumerate(('M_STATUS','M_SHARED_TIME','M_WARM_ENTRY','MR_SAMPLE','MR_DISPLAY','M_QUIET_ENTRY')):
                offset=32+2*index
                image[offset:offset+2]=sy[name].to_bytes(2,'little')
            image[72:80]=b'UI\x01\x06PR05'
            image[128:128+len(body)] = body
            image[18:20] = binascii.crc_hqx(image[:18]+image[32:],0xffff).to_bytes(2,'little')
            filename = 'STR8N-MON-0.1.0-dev-g'+generation_text+'-'+variant+'.bin'
            destination = f'B3:{page*256:04X}'
        else:
            image = body
            filename = 'STR8N-MON-0.1.0-dev-g'+generation_text+'-RAM.bin'
            destination = 'RAM:0200; smoke candidate borrows owner RAM'
        (out/filename).write_bytes(image)
        artifacts[filename] = dict(bytes=len(image),sha256=sha(image),variant=variant,
                                   destination=destination,linked_bytes=len(body),
                                   entry=f'{origin+4 if page else origin:04X}',
                                   linked_end=f'{sy["M_END"]:04X}',status='NOT_EXECUTION_QUALIFIED')
        print(filename, len(image),'bytes; linked',len(body),'bytes',flush=True)
    report = dict(schema=1,component='MON A/B',version='0.1.0-dev',generation=generation_text,
                  build_passes=1,assembly_tool_invocations=len(logs),F_rebuilt=False,
                  F_sha256=sha(f),F_CRC16=f'{crc:04X}',private_adapter=private,
                  foundation=dependency['foundation'],source_sha256=inputs,artifacts=artifacts,
                  monitor_RAM='6A00-6AFF',owner_RAM_ROM_startup='0200-66FF unchanged',
                  prompt='B0> through B3> follows selected data bank; active A/B remains in banner',
                  status_rows=['EDU','SSRAM','RTCC','Battery','Wear'],
                  commands=['?','VERSION (V)','TIME','B[0-3]','D addr [end]','M addr byte...','!M addr byte...','G addr','L','Q',
                            'MS services: M1/M2/M3/W/APPS/MAINT/FLASH/CLOCK; WB2: BATCH/S/T/R/AREA/HELP/EDU/SRAM/WORK'],
                  service_dispatcher=dict(interface='MS/01/10/PR05',ROM='B3:E000-EFFF',RAM='2000-2FFF',
                    admission='Header and zero CRC residue over all4096 bytes',owner_RAM_M1_W=False),
                  workbench_bridge=dict(interface='WB2',module_RAM='4800-63FF',state_RAM='6400-66FF',
                    admission='MW/02/1C/PR05 and CRC16 zero residue over all 7168 bytes before every call',
                    ordinary_Modify_respects_module=True,force_Modify_may_evict_module=True,
                    module_required=False,missing_or_corrupt_module='refused; core D/M/G/Q remain available',
                    legacy_WB1_accepted=False,completion_result='655F; 0 OK, 1 syntax/unsupported, 2 refused, 3 canceled, 4 partial'),
                  raw_load=dict(ROM_only=True,tail_entry='Exact frozen F loader',framing='idle-terminated raw bytes',
                    first_byte_Ctrl_C='Frozen F semantics; cancellation goes to REC>',RAM_variant='L refused'),
                  branch_layout=branch_layout,
                  install_check=dict(offset=24,final_byte='FE',staging_byte='FF',
                    purpose='Native !M byte-program check after a fresh monitor-sector erase; no extra erase',
                    excluded_from_F_CRC=True),
                  force_modify=dict(max_bytes=8,protected=['B3:C','B3:D','B3:F'],erase=False,
                    flash_preflight='Whole command must satisfy old AND new == new; identical bytes skipped',
                    raw_IO_readback=False,RAM_kernels=['6B00-6B7F','6D00-6D2A'],may_halt_on_system_edits=True),
                  RAM_modify=dict(max_bytes=8,ranges=['0000-00DF','0200-66FF'],complete_preflight=True,
                    readback=True,RAM_candidate_code_pages_protected=True,flash_writes=False),
                  dump=dict(default_bytes=16,max_bytes='Entire valid non-I/O range',ASCII=True,cancel_between_rows=True),
                  status_limits='-- no reported data; explicit TIME samples EDU Rev D MCP79411; cached sample has no zone; * no physical battery/prior wear certification',
                  personalities='A and B identical commands; only slot identity differs',
                  monitor_UI=dict(format='UI/1',descriptor_offset='48',vector_offset='20',
                    operations=['VERSION','TIME','retain/status return','RTC sample','RTC display','bypass/quiet return'],
                    admission='MI CRC covers descriptor and vectors; tools validate full MI CRC before calls',
                    Foundation_ABI_changed=False,owner_RAM_or_ZP_borrowed=False,
                    warm_return='Preserves MON state and cached RTC sample; selects tool data bank'),
                  RTCC_adapter=dict(trigger='Explicit TIME only; V never probes',profile='WDC EDU Rev D / MCP79411 / VIA1 PA0 SCL, PA7 SDA',
                    automatic_startup=False,RTC_data_writes=False,EEPROM_or_SRAM_access=False,
                    max_snapshot_attempts=3,SCL_wait_polls=255,owner_RAM_borrowed=False),
                  journal_access='Read selected page and verify full record CRC; no writer installed',
                  CPU_simulations=0,hardware_access=False,flashing=False,execution_qualified=False)
    (out/'manifest.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf-8',newline='\n')
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out',type=Path,required=True)
    parser.add_argument('--generation',type=lambda value:int(value,0),required=True)
    args=parser.parse_args()
    build(args.out,args.generation)
