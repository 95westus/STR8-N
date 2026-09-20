"""Extract, disassemble, annotate, and validate current embedded worker bytes.

Documentation only: never assembles project firmware or contacts hardware.
Instruction round trips use the py65 W65C02 assembler at the actual RAM PC.
"""
import hashlib
import re
import sys

SOURCE = 'tools/bank-maint/str8n-v1.23-bank-maint-2000.asm'
ROUTINES = {
    0x0200: ('MW_ENTRY', 'Entry jump skips the four header bytes. The stored image is at $3400; all absolute code operands refer to its runtime address $0200.'),
    0x0207: ('MW_DISPATCH', 'Save processor status, mask IRQ, and read mode from $7DF0. Modes 05/06/07 dispatch; other values restore status and return C=0 before selecting any bank. There is no mode 08 guest jump in this image.'),
    0x021B: ('MW_MODE_PROGRAM', 'Call staged-sector program, then join the common return path. Caller supplies destination bank, aligned sector, and staging-buffer page.'),
    0x0220: ('MW_MODE_STAGE', 'Call sector staging. This reads selected flash into RAM and does not issue flash mutation commands.'),
    0x0225: ('MW_MODE_RECORD', 'Call the private record writer. Its caller must already have bounded the request to the intended directory bytes.'),
    0x022A: ('MW_RETURN', 'Carry selects the success/failure tail. Both recognized-operation tails select Bank 3, restore entry processor status, and override only the returned carry. A/X/Y are not preserved.'),
    0x0238: ('MW_PROGRAM_SECTOR', 'Erase only if necessary, program non-FF bytes, then compare the complete sector against the staging tray. Each failed substep stops the sequence. No rollback is attempted.'),
    0x024B: ('MW_STAGE_SECTOR', 'Select source bank from $7DEE, form flash pointer from $7DE9 and RAM pointer from $7DF6, then tail-call the page-copy loop. The maintenance wrapper uses $0A00-$19FF.'),
    0x0262: ('MW_PROGRAM_RECORD', 'Select Bank 3, initialize destination and $7B00 source pointers, and preflight the entire request for one-to-zero legality. Only after that complete pass are bytes programmed. Equal bytes are skipped. Zero length succeeds without writing.'),
    0x02A0: ('MW_RECORD_FAILURE', 'Record destination address, observed byte, and expected byte at $7EA5-$7EA8, then return carry clear. The caller additionally verifies each requested directory byte on success.'),
    0x02B8: ('MW_RECORD_INIT', 'Load destination from the record card and reset the source pointer to $7B00. Reinitialization separates preflight and write passes.'),
    0x02C9: ('MW_RECORD_ADVANCE', 'Increment the 16-bit destination and only the low byte of the source pointer. The bounded one-byte count fits within the source page; this is not an arbitrary-length copier.'),
    0x02D2: ('MW_COPY_PAGES', 'Copy 256 bytes using Y, advance both pointer pages, and repeat until sixteen pages have been copied. The final equal comparison supplies Z=1 and C=1 to the return.'),
    0x02E5: ('MW_ERASE_DESTINATION', 'Select destination bank and scan the sector. If already erased, return success without erase. Otherwise use the first non-FF address as an address inside the target sector, issue erase, and rescan the full sector.'),
    0x0308: ('MW_CHECK_ERASED', 'Scan the aligned flash sector for FF. The high-nibble boundary terminates the scan. On the first non-FF byte, publish its address and return C=0. Alignment is a caller precondition.'),
    0x0324: ('MW_ERASE_SCAN_FAILURE', 'Store the scan index and flash-pointer high byte as the first non-erased address at $7DEA-$7DEB.'),
    0x032F: ('MW_PROGRAM_BYTES', 'Select destination bank, traverse the staged sector, and skip FF bytes. Program other bytes through the transition-checking primitive. Record the failing destination address and stop on failure.'),
    0x036E: ('MW_VERIFY_SECTOR', 'Compare every flash byte with staged RAM, including FF bytes skipped by programming. A mismatch is a failure even if all byte-program polls previously succeeded.'),
    0x0397: ('MW_VERIFY_FAILURE', 'Publish the first comparison mismatch address at $7DEA-$7DEB and return C=0.'),
    0x03A2: ('MW_BUFFER_END', 'Compute staging start page plus $10 and compare with the current buffer page. With the supported tray this means exactly 4096 bytes. Final equality deliberately supplies carry set to callers that immediately RTS.'),
    0x03AB: ('MW_FLASH_ERASE', 'Send AA/55 unlock, 80 erase setup, AA/55 unlock, and 30 sector erase at the destination pointer. Poll for FF using a high timeout count of 08.'),
    0x03C5: ('MW_FLASH_WRITE', 'Read the destination. Equal data succeeds without a command. Otherwise require (old AND desired) == desired before AA/55/A0 and the data write. Poll for the desired byte using timeout high count 02.'),
    0x03E5: ('MW_FLASH_WAIT', 'Use three countdown bytes at $D4-$D6. Poll for exact byte equality. Equality leaves carry set through CMP; timeout sends F0 reset and returns failure. This is bounded polling, not a calibrated wall-clock guarantee.'),
    0x0402: ('MW_FLASH_UNLOCK', 'Write AA to $D555 and 55 to $AAAA. This private image does not write the EDU LED port; the resident worker has a different unlock routine.'),
    0x040D: ('MW_FLASH_RESET_FAIL', 'Write F0 to $D555 to request flash read/reset mode, then return C=0. Reached on write-transition failure or poll exhaustion; no sector restoration occurs.'),
    0x0414: ('MW_SELECT_BANK3', 'Load bank number 3 and fall through to the common selector. Recognized operations finish here even when their operation failed.'),
    0x0416: ('MW_SELECT_BANK', 'Mask A to two bank bits, look up the PCR pattern, clear selection bits under EE, then set the requested pattern. Invalid caller bank values alias modulo four rather than being rejected here.'),
}

MEMORY = {
    0xCD:'flash pointer low',0xCE:'flash pointer high',0xCF:'buffer pointer low',0xD0:'buffer pointer high',
    0xD1:'destination pointer low',0xD2:'destination pointer high',0xD3:'desired byte',
    0xD4:'timeout low',0xD5:'timeout middle',0xD6:'timeout high',
    0x7DE9:'sector base high',0x7DEA:'failure address low',0x7DEB:'failure address high',
    0x7DEE:'source bank',0x7DEF:'destination bank',0x7DF0:'private operation mode',0x7DF6:'staging start page',
    0x7E9E:'record destination low',0x7E9F:'record destination high',0x7EA0:'record byte count',
    0x7EA5:'record failure address low',0x7EA6:'record failure address high',
    0x7EA7:'record observed byte',0x7EA8:'record expected byte',0x7FEC:'bank PCR',
    0xD555:'flash unlock/command address 1',0xAAAA:'flash unlock address 2',0x0427:'bank-pattern table',
}
SPECIAL = {
    0x020E:'mode 05 -> staged-sector program',0x0212:'mode 06 -> read sector to RAM',0x0216:'mode 07 -> record writer',
    0x0218:'unknown mode: restore entry status',0x0219:'unknown mode: publish failure',
    0x0228:'zero-displacement BRA; retained exact instruction',0x022A:'operation C=0 selects failure-return tail',
    0x026B:'zero-length private record is a no-write success',0x0275:'old AND desired; test one-way flash legality',
    0x0279:'illegal transition -> record failure before writes',0x027F:'preflight next byte until X reaches zero',
    0x0281:'restart pointers after successful whole-record preflight',0x0291:'equal byte: skip physical programming',
    0x02CB:'increment destination high byte only on low-byte wrap',0x02CF:'source page cannot wrap for valid bounded count',
    0x02D9:'continue copying within this 256-byte page',0x02E2:'copy next page until 4 KiB endpoint',
    0x02EE:'entire sector already FF: skip physical erase',0x0302:'full post-erase scan must pass',
    0x031E:'aligned sector ends when page low nibble becomes zero',0x0315:'first non-FF byte ends erased scan',
    0x0349:'staged FF needs no program pulse after erase',0x036D:'return C=1 inherited from equal end comparison',
    0x0388:'first flash/RAM mismatch -> report failing address',0x0396:'return C=1 inherited from equal end comparison',
    0x03A6:'16 pages = one 4 KiB staging extent; requires binary arithmetic',
    0x03CB:'already equal: CMP supplies C=1; no flash write',0x03CD:'old AND desired checks one-to-zero transition',
    0x03D1:'reject a zero-to-one request; reset flash and fail',0x03E4:'equal-byte success retains carry from CMP',
    0x03F1:'exact readback equality ends polling with carry set',0x03FF:'all timeout counters exhausted',
    0x0401:'return equality result; carry is already set',0x0416:'mask bank to 0-3; no explicit range rejection',
    0x041C:'preserve table value while loading bank mask',0x041F:'clear only the selection bits under EE',
    0x0423:'set bits for chosen bank; carry remains unchanged',
}


def load_decoder(root):
    for path in [root/'output/book-deps', *sorted((root/'BUILD').glob('v*/local/test-deps'), reverse=True)]:
        if (path/'py65').is_dir():
            sys.path.insert(0,str(path))
    from py65.devices.mpu65c02 import MPU
    from py65.disassembler import Disassembler
    from py65.assembler import Assembler
    return MPU, Disassembler, Assembler


def extract(root):
    text = (root/SOURCE).read_text(encoding='utf-8-sig')
    active = False
    raw = bytearray()
    origin = []
    for n,line in enumerate(text.splitlines(),1):
        if line.strip() == '; BEGIN GENERATED STR8 MUTATION WORKER':
            assert not active and not raw
            active = True
        elif line.strip() == '; END GENERATED STR8 MUTATION WORKER':
            active = False
            break
        elif active and re.match(r'\s*DB\s',line):
            data = re.findall(r'\$([0-9A-Fa-f]{2})\b',line.split(';')[0])
            raw.extend(int(x,16) for x in data)
            origin.extend([n]*len(data))
    assert len(raw)==555 and raw[3:7]==bytes.fromhex('49 57 01 FE')
    assert raw[-4:]==bytes.fromhex('CC CE EC EE')
    return bytes(raw), origin


def s19_bytes(path):
    data = {}
    for line in path.read_text().splitlines():
        if not line.startswith('S'):
            continue
        raw = bytes.fromhex(line[2:])
        assert raw[0]==len(raw)-1 and sum(raw)&255==255, path
        if line[1]=='1':
            address = int.from_bytes(raw[1:3],'big')
            for i,b in enumerate(raw[3:-1]):
                assert address+i not in data
                data[address+i]=b
    return data


def instruction_comment(pc, text):
    if pc in SPECIAL:
        return SPECIAL[pc]
    op, _, operand = text.partition(' ')
    address = re.search(r'\$([0-9a-fA-F]+)',operand)
    value = int(address.group(1),16) if address else None
    if op in ('JMP','JSR','BCC','BCS','BEQ','BNE','BRA'):
        target = ROUTINES.get(value,(f'MW_L{value:04X}',))[0]
        action = {'JMP':'jump to','JSR':'call','BCC':'if C=0, branch to','BCS':'if C=1, branch to',
                  'BEQ':'if Z=1, branch to','BNE':'if Z=0, branch to','BRA':'branch to'}[op]
        return f'{action} {target}'
    if op=='RTS': return 'return to caller; preserve current flags'
    if op=='PHP': return 'save entry processor status on stack'
    if op=='PLP': return 'restore saved processor status'
    if op=='SEI': return 'mask IRQ; does not mask NMI'
    if op=='SEC': return 'publish carry set / success'
    if op=='CLC': return 'clear carry before buffer-end addition' if pc==0x03A5 else 'publish carry clear / failure'
    if op=='PHA': return 'push accumulator on stack'
    if op=='PLA': return 'restore accumulator from stack; update N/Z'
    if op=='TAX': return 'use masked bank number as table index'
    if op=='TYA': return 'use byte index as failure-address low byte'
    if op=='INY': return 'advance byte index within page'
    if op=='DEX': return 'decrement remaining record byte count'
    target = MEMORY.get(value,operand)
    if operand.startswith('#'): target=operand+' immediate'
    elif operand.startswith('('):
        target={0xCD:'flash byte at scan pointer + Y',0xCF:'staging/data byte at buffer pointer + Y',
                0xD1:'flash byte at destination pointer + Y'}.get(value,operand)
    actions={'LDA':'load A from','LDX':'load X from','LDY':'load Y from','STA':'store A to',
             'STZ':'zero','INC':'increment','DEC':'decrement','CMP':'compare A with','AND':'AND A with',
             'ADC':'add with carry','TRB':'clear A-mask bits in','TSB':'set A-mask bits in'}
    return actions.get(op,op)+' '+target


def disassemble(root):
    raw, origin=extract(root)
    MPU, Disassembler, Assembler=load_decoder(root)
    cpu=MPU()
    cpu.memory[0x200:0x42B]=raw
    decoder, assembler=Disassembler(cpu),Assembler(cpu)
    decoded=[]
    pc=0x200
    while pc<0x427:
        if pc==0x203:
            pc=0x207
            continue
        size, text=decoder.instruction_at(pc)
        assert '???' not in text
        actual=raw[pc-0x200:pc-0x200+size]
        assert bytes(assembler.assemble(text,pc))==actual, (pc,text)
        decoded.append((pc,actual,text))
        pc+=size
    assert pc==0x427
    starts={a for a,_,_ in decoded}
    targets=set()
    for address,_,text in decoded:
        if text.split()[0] in ('JSR','JMP','BEQ','BNE','BCS','BCC','BRA'):
            target=int(text.split('$')[1],16)
            assert target in starts,(address,target)
            targets.add(target)
    # Recursive reachability distinguishes executable instructions from metadata.
    instructions={a:(b,t) for a,b,t in decoded}
    reached=set()
    pending=[0x200]
    while pending:
        address=pending.pop()
        if address in reached: continue
        assert address in instructions,address
        reached.add(address)
        data,text=instructions[address]
        op=text.split()[0]
        if op=='RTS': continue
        if op in ('JSR','JMP','BEQ','BNE','BCS','BCC','BRA'):
            pending.append(int(text.split('$')[1],16))
        if op not in ('JMP','BRA'):
            pending.append(address+len(data))
    assert reached==starts, sorted(starts-reached)
    rebuilt=bytearray()
    for address,data,text in decoded:
        if address==0x207: rebuilt.extend(raw[3:7])
        rebuilt.extend(assembler.assemble(text,address))
    rebuilt.extend(raw[-4:])
    assert bytes(rebuilt)==raw
    artifacts=[]
    for variant in ('bank-maint','bank-maint-menu','str8-in65-bank-maint'):
        path=root/f'BUILD/v1.35/s19/str8n-v1.35-{variant}-2000.s19'
        assert path.exists(),f'Missing current worker cross-check {path}'
        image=s19_bytes(path)
        assert bytes(image[i] for i in range(0x3400,0x362B))==raw, variant
        artifacts.append({'path':path.relative_to(root).as_posix(),'sha256':hashlib.sha256(path.read_bytes()).hexdigest(),'worker_matches':True})
    lines=['; ANNOTATED DERIVATION - labels and comments are editorial, not original symbols.',
           '; W65C02 instructions; code is addressed at runtime $0200, stored at $3400.',
           '; Each line: RAM PC | stored address | exact bytes | instruction | explanation.',
           '; Original DB source span: '+str(origin[0])+'-'+str(origin[-1])+'.',
           '; Source SHA-256: '+hashlib.sha256((root/SOURCE).read_bytes()).hexdigest(),
           '; Worker SHA-256: '+hashlib.sha256(raw).hexdigest(), '']
    for pc,data,text in decoded:
        if pc==0x207:
            lines+=['0203 | 3403 | 49 57 01 FE | DB $49,$57,$01,$FE ; IW header, not executable instructions','']
        if pc in ROUTINES:
            name,comment=ROUTINES[pc]
            lines+=['',name+':','; '+comment]
        elif pc in targets:
            lines.append(f'MW_L{pc:04X}:')
        hexbytes=' '.join(f'{b:02X}' for b in data)
        lines.append(f'{pc:04X} | {pc+0x3200:04X} | {hexbytes:<8} | {text.upper():<15} ; {instruction_comment(pc,text)}')
    lines+=['','MW_BANK_PATTERNS:', '0427 | 3627 | CC CE EC EE | DB $CC,$CE,$EC,$EE ; bank 0/1/2/3 PCR values']
    report={'source':SOURCE,'source_first_db_line':origin[0],'source_last_db_line':origin[-1],
            'bytes':len(raw),'runtime':'0200-042A','storage':'3400-362A',
            'sha256':hashlib.sha256(raw).hexdigest(),'decoded_instructions':len(decoded),
            'data_bytes':8,'instruction_round_trip':'pass','whole_blob_round_trip':'pass',
            'branch_targets':'all target instruction boundaries','reachable_code':'all decoded instructions reached from entry',
            'existing_artifact_cross_checks':artifacts,'hardware_executed':False}
    return '\n'.join(lines),report


def worker_charts(Chart):
    result={}
    c=Chart(430)
    c.node('entry',179,0,'Resident worker at 0200\nRead private mode',170,58,kind='decision')
    c.node('sector',8,112,'05: staged sector\nErase if needed\nProgram and verify',154,76,kind='mutate')
    c.node('record',187,112,'07: directory bytes\nPreflight, then program',154,76,kind='mutate')
    c.node('jump',366,112,'08: bank jump\nSelect bank\nValidate RESET',154,76)
    c.node('ret',75,278,'Returning operation\nRestore Bank 3 and running LEDs\nRestore status; publish carry',262,82,kind='exit')
    c.node('go',366,278,'Valid jump\nCommit BJ\nRelease LEDs\nNo return',154,82,kind='exit')
    c.edge('entry','sector').edge('entry','record').edge('entry','jump')
    c.edge('sector','ret').edge('record','ret').edge('jump','go','valid')
    c.edge('jump','ret','failure',sides='bl',via=((443,225),(65,225),(65,319)),label_at=(355,225))
    result['worker-resident']=c

    c=Chart(440)
    c.node('copy',174,0,'BM_MAIN copies 555 bytes\n3400-362A -> 0200-042A',180,66)
    c.node('mode',174,104,'MW_DISPATCH at 0207\nPHP, SEI, read 7DF0',180,58,kind='decision')
    c.node('write',8,208,'05: program sector\nMW_PROGRAM_SECTOR',154,58,kind='mutate')
    c.node('stage',187,208,'06: stage sector\nMW_STAGE_SECTOR',154,58)
    c.node('rec',366,208,'07: write record\nMW_PROGRAM_RECORD',154,58,kind='mutate')
    c.node('return',144,330,'Recognized operation return\nSelect Bank 3\nPLP; set carry result; RTS',240,78,kind='exit')
    c.edge('copy','mode').edge('mode','write').edge('mode','stage').edge('mode','rec')
    c.edge('write','return').edge('stage','return').edge('rec','return')
    result['worker-maint-dispatch']=c

    c=Chart(450)
    c.node('read',8,0,'Mode 06: read source sector\nSelect bank from 7DEE',236,58)
    c.node('copy',8,105,'Flash pointer: sector base\nRAM pointer: staging page\nCopy 16 pages of 256 bytes',236,78)
    c.node('done',8,247,'No flash command writes\nReturn through Bank-3 tail',236,66,kind='exit')
    c.node('erase',284,0,'Mode 05: select destination\nCheck entire sector for FF',236,58,kind='decision')
    c.node('blank',284,105,'If needed: erase and rescan\nStop on failure',236,78,kind='mutate')
    c.node('program',284,247,'Program staged non-FF bytes\nSkip FF; stop on failure',236,66,kind='mutate')
    c.node('verify',284,355,'Compare all 4096 bytes\nReturn result; no rollback',236,66,kind='decision')
    c.edge('read','copy').edge('copy','done')
    c.edge('erase','blank').edge('blank','program','erased').edge('program','verify')
    result['worker-sector']=c

    c=Chart(450)
    c.node('caller',8,0,'Caller bounds directory request\nMode 07; data at 7B00',230,60)
    c.node('pre',8,100,'Select Bank 3\nPreflight every requested byte\n(old AND desired) = desired?',230,78,kind='decision')
    c.node('write',8,226,'Reset pointers\nSkip equal bytes; program others\nStop on first failure',230,78,kind='mutate')
    c.node('verify',8,364,'Return C=1\nCaller independently verifies bytes',230,62,kind='exit')
    c.node('fail',296,212,'Record first failure at 7EA5-7EA8\nAddress / observed / expected\nReturn C=0 through common tail',224,90,kind='failure')
    c.edge('caller','pre').edge('pre','write','all legal').edge('write','verify','success')
    c.edge('pre','fail','illegal',sides='rt',via=((408,139),),label_at=(315,139))
    c.edge('write','fail','failed',sides='rl',label_at=(266,265))
    result['worker-record']=c

    c=Chart(442)
    c.node('request',8,0,'Byte program request\nDestination and desired byte',228,58)
    c.node('check',8,103,'Already equal? Return success\nOtherwise check one-to-zero',228,66,kind='decision')
    c.node('command',8,221,'AA / 55 unlock, A0 command\nWrite desired byte\nSet timeout high count 02',228,78,kind='mutate')
    c.node('poll',294,221,'Poll for exact equality\nDecrement D4-D6 on mismatch',224,78,kind='decision')
    c.node('ok',294,360,'Equality: C=1\nReturn success',224,58,kind='exit')
    c.node('fail',8,360,'Illegal transition or timeout\nF0 reset command; C=0',228,58,kind='failure')
    c.edge('request','check').edge('check','command','legal')
    c.edge('command','poll',sides='rl').edge('poll','ok','equal')
    c.edge('poll','fail','timeout',sides='bl',via=((406,330),(4,330),(4,389)),label_at=(228,330))
    result['worker-flash']=c

    c=Chart(460)
    c.node('tu',8,0,'TU_PROGRAM_STAGE\nTop updater / directory refresh',238,58)
    c.node('tuerase',8,100,'Erase selected sector F\nPoll target for FF',238,58,kind='mutate')
    c.node('tuprog',8,202,'Program staged data\nSkip RESET bytes FFFC/FFFD\nWrite those two bytes last',238,80,kind='mutate')
    c.node('tuverify',8,346,'Verify complete staged sector\nPublish AC or E1/E2/E3\nReturn to updater/recovery',238,78,kind='exit')
    c.node('w2',282,0,'W2I_PROGRAM_STAGE\nMigration / stock-restore engine',238,58)
    c.node('w2erase',282,100,'Erase requested sector\nVerify entire sector is FF',238,58,kind='mutate')
    c.node('w2prog',282,202,'Program staged non-FF bytes\nCheck transition and poll\nStop at first failure',238,80,kind='mutate')
    c.node('w2verify',282,346,'Verify entire sector\nReset flash command state\nReturn carry result to caller',238,78,kind='exit')
    for a,b in [('tu','tuerase'),('tuerase','tuprog'),('tuprog','tuverify'),('w2','w2erase'),('w2erase','w2prog'),('w2prog','w2verify')]:c.edge(a,b)
    result['worker-other-engines']=c
    return result


def worker_text(root):
    listing,report=disassemble(root)
    text='''
## Worker inventory and coverage

The resident worker already has a mnemonic source listing in this book. The separate Bank Maintenance mutation worker was previously visible only as DB bytes inside its parent source. This section adds a complete annotated W65C02 disassembly of that current embedded image, along with workflows and its caller obligations. No older worker implementation is substituted for the bytes in this checkout.

| Implementation | Current representation | Execution and coverage |
|---|---|---|
| Resident unified worker | src/str8-worker.asm | 568 bytes; stored FD78-FFAF, runs 0200-0437; full original source already listed |
| Bank Maintenance private worker | DB block in bank-maint source | 555 bytes; stored 3400-362A, runs 0200-042A; annotated disassembly added below |
| Standalone, menu and iN65 maintenance | Shared private DB block | Same 555 bytes in all three existing current S19 images; independently compared |
| Protected-top updater / refresh | TU_PROGRAM_STAGE and helpers | Inline RAM-resident assembly, already listed; additional primitive workflow below |
| Migration / stock restore | W2I_PROGRAM_STAGE and helpers | Inline RAM-resident assembly, already listed; additional primitive workflow below |
| LED/worker probe | Relocates resident production worker | Reuses that worker; not another embedded mutation implementation |
| Archive and interrupt/console probes | Source-listed RAM programs | Archive is read-only; these are not additional mutation-worker blobs |

Scope: current resident and selected board-tool sources were checked for worker references and embedded code. Generated candidate top images are data carried by RAM tools and contain the resident image already covered. Test-fixture payloads are regression inputs, not additional current deployed workers.

## Private worker contract and differences

The private entry is $0200. Bytes $0203-$0206 are an IW header ($49,$57,$01,$FE), not a callable selector. The jump at $0200 skips them and enters $0207. The trailing bank-pattern table at $0427-$042A is also data. Both regions must be excluded from instruction decoding.

BM_MAIN copies the private image from $3400 to $0200 each time it enters its initialization path. That copy loop does not perform the resident relocation routine's immediate per-byte comparison. Calling the resident F010 service while this private image occupies the tray would overwrite its prefix. Conversely, calling $0203 as though the private worker were the resident selector would execute header bytes. Ownership of the shared tray is therefore a phase contract.

| Mode | Private worker inputs | Result and caller |
|---|---|---|
| 05 program sector | 7DEF destination bank; 7DE9 sector high; 7DF6 staging page | Erase if necessary, program, full verify; BM_PROGRAM supplies the fields |
| 06 stage sector | 7DEE source bank; 7DE9 sector high; 7DF6 staging page | Copy 4 KiB flash to RAM; BM_STAGE supplies the fields |
| 07 program record | 7E9E-7E9F destination; 7EA0 length; desired bytes at 7B00 | Select B3; whole-request transition preflight; write; BM_COPY_DIR_WRITE verifies again |
| Other values | Mode at 7DF0 | C=0, no bank change or flash write |

All recognized-operation returns select Bank 3, restore entry processor status, and publish carry. Registers A/X/Y and scratch $CD-$D6 are volatile. The source-stage wrapper's caller restores its original bank where needed; staging does not return with its selected source bank visible.

The dispatcher masks IRQ but does not clear decimal mode. The buffer-end ADC therefore requires the normal caller's binary-arithmetic state. SEI does not protect against NMI. Bank arguments are masked with AND #03, not range-checked. Sector alignment, a valid 4 KiB staging tray, request destination limits, and confirmation/role policies are caller responsibilities. In particular, mode 07 does not itself enforce a directory-only address range. A raw call can bypass the maintenance command's protections. These modes are private, not a supported public destructive API.

Unlike the resident worker, the private image has mode 06 and no mode 08 guest handoff. It also has no PIA LED writes. The code does not refresh every failure field on every successful return; inspect carry before treating retained diagnostic bytes as a new failure report. None of the workers provides rollback, wear tracking, or interrupt-safe flash mutation.

## Disassembly evidence and annotation conventions

The disassembler uses the W65C02 instruction table, runtime base $0200, and explicit header/table data boundaries. Every decoded instruction is reassembled at its original PC and compared with its exact bytes. Recombining instructions and the eight data bytes must reproduce the complete 555-byte blob. Every direct branch/call target must land on a decoded instruction boundary, and recursive traversal from $0200 must reach every decoded instruction.

The extracted bytes are also compared against $3400-$362A in each existing current standalone, menu, and iN65 maintenance S19 image. Those checks validate this derived listing and artifact consistency; they do not constitute fresh electrical or board qualification. The firmware and original DB block remain unchanged.

Names beginning MW_ are editorial names inferred from decoded behavior. They are not recovered original assembler symbols or stable public ABI names. RAM PCs and stored addresses are both printed to prevent confusion about absolute jumps. Comments explain observed mechanics and preconditions; no claim is made about undocumented author intent.

'''
    text+=f'Worker SHA-256: `{report["sha256"]}`. Decoded instructions: {report["decoded_instructions"]}; explicit data: {report["data_bytes"]} bytes. Byte round trips, instruction-target checks, reachability, and all three current image comparisons passed.\n\n'
    flows=[
        ('Resident worker dispatch','worker-resident','Source: src/str8-worker.asm:94. Unknown modes restore status and fail before bank selection. Directory byte programming is mode 07; guest jump is mode 08. Recognized failures use the return path. A successful guest jump does not return.'),
        ('Private mutation-worker dispatch','worker-maint-dispatch','Source: maintenance DB block, runtime 0200-0237. Unknown modes fail before bank selection and do not pass through the Bank-3 return tail. Recognized operations share status restoration and carry-result publication. The four-byte IW header at 0203 is data.'),
        ('Private sector staging and programming','worker-sector','Source: decoded routines 0238, 024B, 02D2, 02E5, 0308, 032F and 036E. Erased-sector scan skips unnecessary erase; programming skips FF bytes; full comparison still checks all 4096 bytes. Failure addresses are recorded at 7DEA-7DEB where those paths specify them. Mode 06 reads flash without flash-command writes.'),
        ('Private record preflight and write','worker-record','Source: decoded 0262-02D1; caller BM_COPY_DIR_WRITE at source line 1377. A zero-length private request returns success without writes, while the real directory wrapper uses positive bounded requests. Complete preflight occurs before the first write, but a hardware failure during the write pass can leave partial changes. The worker is not the policy boundary.'),
        ('Private flash commands and polling','worker-flash','Source: decoded 03AB-0413. Erase uses AA/55, 80, AA/55, then 30 and polls for FF with timeout high count 08. Program uses timeout high count 02. Equality returns carry set from CMP; timeout and illegal transitions send F0 and return carry clear. No elapsed-time guarantee or automatic retry is implied.'),
        ('Other source-listed mutation engines','worker-other-engines','Source: top updater TU_PROGRAM_STAGE and migration W2I_PROGRAM_STAGE. These run inline in their RAM programs, not through the maintenance DB blob. TU writes the RESET vector bytes last, then verifies the full sector. W2I verifies full erasure before programming. Failures stop and return to the owning tool, whose recovery policy is described in the surrounding chapters.'),
    ]
    for number,(title,key,note) in enumerate(flows,11):
        text+=f'## Atlas {number}. {title}\n\nCurrent execution workflow. Addresses below are hexadecimal.\n\n:::diagram {key}:::\n\n{note}\n\n'
    text+='<a id="worker-annotated"></a>\n\n## Annotated listing: private mutation worker\n\n'
    text+='The original DB source remains in the Bank Maintenance listing. This derived listing covers every byte once: executable instructions plus the IW header and bank table. Address comments explain private behavior, not permission to call it without the owning tool.\n\n```text\n'+listing+'\n```\n\n'
    return text,report
