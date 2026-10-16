"""Generate measured beta28 flash/RAM usage from the linked candidate."""
import json
from pathlib import Path
from build_v2_spi_resident import sha

ROOT=Path(__file__).resolve().parents[1];OUT=ROOT/'BUILD/v2-beta28';BASE=ROOT/'BUILD/v2-beta27'

def main():
    m=json.loads((OUT/'xip/build.json').read_text());s=m['symbols']
    image=(OUT/'xip/utilities.bin').read_bytes();assert sha(image)==m['sha256']
    linked=m['flash_linked_bytes'];assert image[linked:-2]==b'\xff'*(len(image)-linked-2)
    sections=[]
    for name,a,b in [('MAINT','MM_START','MM_BM_END'),('SRAM','SM_INIT','SM_D_DATA_END'),('WORK','WK_ENTRY','WK_APP_END'),('EDU','ED_START','ED_APP_END')]:
        sections.append(dict(name=name,start=s[a],end_exclusive=s[b],bytes=s[b]-s[a]))
    shared=linked-sum(r['bytes'] for r in sections)
    base=json.loads((BASE/'build.json').read_text());bm=json.loads((BASE/'maint/manifest.json').read_text());sm=json.loads((BASE/'store/build.json').read_text())
    wm=json.loads((BASE/'workspace/build.json').read_text());em=json.loads((BASE/'edu/build.json').read_text())
    gate=m['ram_gate_reserved'][1]-m['ram_gate_reserved'][0]+1
    oldram=dict(MAINT=bm['bytes']+0x1400,SRAM=((sm['core_bytes']+255)//256)*256+256+256+96+512+64,WORK=wm['bytes'],EDU=em['bytes'])
    newram=dict(MAINT=0x1400+gate,SRAM=sum(r['bytes'] for r in m['mutable']['SRAM'])+512+64+gate,WORK=64+gate+543+64+64,EDU=sum(r['bytes'] for r in m['mutable']['EDU'])+gate)
    qualification=json.loads((OUT/'beta28-qualification.json').read_text()) if (OUT/'beta28-qualification.json').exists() else {}
    rebuild=json.loads((OUT/'reproducibility-test-results.json').read_text()) if (OUT/'reproducibility-test-results.json').exists() else {}
    qualified=bool(qualification.get('passed') and rebuild.get('passed') and qualification['build_sha256']==rebuild['build_sha256']==sha((OUT/'build.json').read_bytes()))
    ram=[dict(name=n,beta27_bytes=oldram[n],beta28_bytes=newram[n],saved_bytes=oldram[n]-newram[n]) for n in oldram]
    report=dict(version='2.0b28',candidate_only=True,model_qualified=qualified,board_access=False,boards_flashed=False,hardware_tested=False,
        utility_sha256=m['sha256'],flash=dict(bank=2,start=0x8000,end_inclusive=0xD7FF,reserved_bytes=len(image),linked_bytes=linked,seal_bytes=2,used_bytes=linked+2,spare_bytes=len(image)-linked-2,sections=sections,shared_header_gate_bootstrap_and_thunks_bytes=shared),
        ram=dict(active_utility_rows_not_additive=True,baseline_monitor_services_and_stack_excluded=True,shared_gate_reserved_bytes=gate,shared_gate_linked_bytes=m['ram_gate_bytes'],work_compat_reserved_bytes=64,work_compat_linked_bytes=m['work_stub_bytes'],rows=ram,
        regions=dict(MAINT=['5000-63FF editor, line, state, transfer requests','7B90-7BFF shared gateway','6800-77FF additional 4096-byte sector staging during flash writes'],
            SRAM=['67C7-67F6 mutable state (48 bytes)','6900-6AFF directory and transfer workspace (512 bytes)','6400-643F temporary preserved transfer window (64 bytes)','7B90-7BFF shared gateway'],
            WORK=['5000-503F compatibility block, API 5003 (64 bytes)','6800-6A1E cleared transient state/cache allocation (543 bytes; includes a 64-byte vacated slot)','6A40-6A7F transfer-window backup (64 bytes)','6400-643F temporary preserved transfer window (64 bytes)','7B90-7BFF shared gateway'],
            EDU=['7CF0-7CFB mutable state (12 bytes)','7B90-7BFF shared gateway']),
        shared_launch_staging_bytes=2560,maint_extra_sector_staging_bytes=4096))
    (OUT/'usage.json').write_text(json.dumps(report,indent=2)+'\n')
    lines=['# Beta28 candidate — flash-resident utilities','',
        'Offline candidate only. Board 2609 remains on beta27; no serial port was opened and no hardware was flashed. No beta28 installer is provided.','',
        ('Instruction-model qualification and an independent byte-for-byte rebuild passed. Hardware qualification remains pending.' if qualified else 'Instruction-model qualification remains pending; inspect current receipts before use.'),'',
        'MAINT 2.3, SRAM 1.3, WORK 1.3 and EDU 1.3 execute their main code and constant text from B2. The shared RAM gateway performs cross-bank calls/reads and restores B2. Flash mutation uses the existing fixed-ABI RAM worker. WORK retains the callable $5003 ABI and reinstalls its gate when called from any bank.','',
        'B2 NMI and IRQ/BRK vectors route to the initialized RAM dispatchers at $7E20 and $7E31. Its reset vector routes through RAM reset ABI $7E64, which selects B3 before restarting. B2 remains a provider entered after B3 boot, not a standalone cold-boot bank. The VERSION asset code is unchanged; its whole-image CRC seal moves to $FFF6–$FFF7 so the vector pocket remains available. Fixed B3:F stays byte-identical beta27.','',
        '## Measured flash usage','', '| Component | Start | Exclusive end | Linked bytes |','| --- | ---: | ---: | ---: |']
    for r in sections:lines.append(f'| {r["name"]} | ${r["start"]:04X} | ${r["end_exclusive"]:04X} | {r["bytes"]:,} |')
    lines.extend([f'| Shared header, RAM images, gateway thunks and APPS | | | {shared:,} |',f'| CRC seal | | | 2 |','',
        f'B2:$8000–$D7FF reserves **{len(image):,} bytes (22 KiB)**. The candidate uses **{linked+2:,} bytes**, leaving **{len(image)-linked-2:,} bytes** of reserved utility padding. Beta27 used 20,759 bytes in this region and left 1,769 bytes. The other B2 firmware assets stay at D800–FFFF; B1 remains entirely free.','',
        '## Active RAM footprint','',
        'Rows are separate utility lifetimes, not additive. These figures include reserved private buffers and gateway slots; they exclude the unchanged monitor, device-service RAM, zero page and stack.','',
        '| Utility | Beta27 RAM | Beta28 RAM | Reduction |','| --- | ---: | ---: | ---: |'])
    for r in ram:lines.append(f'| {r["name"]} | {r["beta27_bytes"]:,} | {r["beta28_bytes"]:,} | {r["saved_bytes"]:,} |')
    lines.extend(['',
        'MAINT additionally borrows the same 4,096-byte $6800–$77FF sector staging buffer during flash writes in both versions. Launching a utility still temporarily borrows the existing 2,560-byte status/loader staging area. The utility gateway itself links to 68 RAM bytes within its reserved 112-byte slot. WORK adds a 62-byte bootstrap within its 64-byte compatibility block.','',
        'SRAM and EDU preserve all application RAM on query/return. WORK preserves application RAM outside $5000–$503F; its $6400–$643F transfer window is restored on return and cannot be used as a WORK I/O buffer during the call. WORK reloads its transient caches from retained storage on every API call; handles remain in SPI SRAM. MAINT preserves $0200–$4FFF and reserves $5000–$63FF for its editor and state.',''])
    for name,regions in report['ram']['regions'].items():
        lines.append(f'**{name}:** '+ '; '.join(regions)+'.');lines.append('')
    lines.extend(['## Behavior and candidate limits','',
        '`R MAINT`, `R SRAM`, `R WORK` and `R EDU` now validate the sealed flash bundle and enter it directly. APPS lists all four as FLASH utilities. T remains an inventory of saved RAM records; these utilities are no longer SR images. Native utility load-only syntax is refused. The retained SRAM CLK program continues to load into CPU RAM and execute as before.','',
        'MAINT protects B2 against writes/erases while executing its utilities there. Its former S 8 / S 9 self-staging feature is removed because the utility is no longer a RAM image. User saved-program copies between free flash banks and SPI SRAM remain supported. A future flash update requires a separately qualified RAM installer.','',
        'WORK, SRAM and EDU use the existing foreground-only, non-reentrant service contracts. W65C02 instruction-model qualification also covers the common 816 emulation instruction set; physical behavior and native 816 execution have not been qualified.','',
        '## Build and qualification','',
        'Build: `python tools/build_v2_beta28.py`. Test: `python tools/test_v2_beta28_candidate.py` and `python tools/test_v2_beta28_workers.py`. Generate this report: `python tools/report_v2_beta28.py`. The package is BUILD/v2-beta28, with reference bank images in candidate/ and exact linked footprints in usage.json and xip/build.json. Candidate reference images are for offline qualification, not direct installation.','',
        'The complete core/worker suites passed before the final provider-vector addition. Their immutable receipts and reference bank bytes are archived under output/qualification/beta28-core-2026-10-15/. The vector suite compares all four final bank images with that qualified reference: only B2:$FFF6–$FFFF vector/seal padding may differ, and the entire XIP utility bundle must be identical. It then exercises VERSION, XIP EDU, actual NMI/IRQ/BRK vector fetches, the NMI hold gate and reset routing on the final image. This avoids repeating unchanged core tests while binding their evidence by exact bytes.','',
        'Final receipts: BUILD/v2-beta28/beta28-qualification.json and beta28-vector-test-results.json. Confirm their passed fields and build/utility hashes. The independent rebuild receipt is reproducibility-test-results.json. Physical timing, electrical behavior and native 816 mode remain unqualified; no port was opened.',''])
    (ROOT/'docs/STR8N_V2_BETA28_CANDIDATE_2026-10-15.md').write_text('\n'.join(lines),encoding='utf-8')
    print(json.dumps(dict(flash=report['flash'],ram_rows=ram),indent=2))

if __name__=='__main__':main()
