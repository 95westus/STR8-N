"""Measure SPI Phase 1 headroom and isolated branch-size experiments.

No serial access, SPI implementation, matched firmware build or deployment.
Original beta12/beta13 artifacts are read-only. Experiments are not installers.
"""
import hashlib,json,re,shutil
from pathlib import Path
import build_v2_config as compiler
from build_v2_recovery import relax_branches
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-spi-phase1'
sha=lambda b:hashlib.sha256(b).hexdigest()
read=lambda p:json.loads(p.read_text())

def inventory(folder):
    meta=read(folder/'build.json');split=read(folder/'split/build.json');banner=read(folder/'banner/build.json')
    p=split['provider_bytes'];b=banner['bytes'];j=meta['journal_bytes']
    return dict(version=meta['version'],clock_version=meta['clock_version'],
        monitor_bytes=meta['monitor_bytes'],monitor_capacity=3968,monitor_slack=3968-meta['monitor_bytes']['a0'],
        launcher_bytes=meta['launcher_bytes'],launcher_capacity=1760,launcher_slack=1760-meta['launcher_bytes'],
        provider_bytes_with_seal=p,banner_bytes=b,gateway_template_bytes=512,
        sector8_gaps=[dict(start=0x8000+p,end=0x8900,bytes=0x900-p),
                      dict(start=0x8900+b,end=0x8DF0,bytes=0x8DF0-0x8900-b),
                      dict(start=0x8FF0,end=0x8FFE,bytes=14)],
        journal_bytes=j,journal_code_slack=3070-j,identity_tail_bytes=1024,
        gateway_code_bytes=split['gateway_code_bytes'],gateway_code_slack=0x150-split['gateway_code_bytes'],
        private_state_bytes=split['private_ram_bytes'],service_ram='6500-66FF',user_ram_top='64FF',
        artifacts=meta['artifacts'])

def experiment(label,source,name,start,end_symbol,expected,original):
    folder=OUT/label;stage=folder/'source';stage.mkdir(parents=True,exist_ok=True);(folder/'asm').mkdir(exist_ok=True)
    for p in source.iterdir():
        if p.is_file():shutil.copyfile(p,stage/p.name)
    compiler.OUT=folder;compiler.SOURCE=stage
    def assemble():return compiler.assemble(name,start,shutil.which('wdc02as'),shutil.which('wdcln'),source=stage)
    cells,symbols=assemble();before=compiler.dense_image(cells,start,symbols[end_symbol])
    assert len(before)==expected and before==original, label
    files=sorted(p for p in stage.iterdir() if p.suffix in ('.asm','.inc'))
    original_text={p.name:p.read_text() for p in files}
    pattern=r'\s+(B[A-Z]{2}) (\w*LONG_\d+)\n\s+JMP (\w+)\n\2:'
    expanded_before=sum(len(re.findall(pattern,t)) for t in original_text.values())
    for _ in range(3):
        old_size=symbols[end_symbol]-start
        for p in files:
            if re.search(pattern,p.read_text()):cells,symbols=relax_branches(p,cells,symbols,assemble)
        if symbols[end_symbol]-start==old_size:break
    after=compiler.dense_image(cells,start,symbols[end_symbol]);assert len(after)<=len(before)
    (folder/'size-probe.bin').write_bytes(after)
    return dict(original_bytes=len(before),compacted_bytes=len(after),bytes_saved=len(before)-len(after),
        original_sha256=sha(before),compacted_sha256=sha(after),conditional_expansions_before=expanded_before,
        conditional_expansions_after=sum(len(re.findall(pattern,p.read_text())) for p in files),
        executable_qualification=False,deployable=False,public_entry=start,
        changed_source_files=[p.name for p in files if p.read_text()!=original_text[p.name]])

def main():
    OUT.mkdir(parents=True,exist_ok=True);new=ROOT/'BUILD/v2-rtc-trim';old=ROOT/'BUILD/v2-rtc-binding'
    acceptance=read(ROOT/'output/qualification/rtc-trim-2026-10-07/acceptance.json');assert acceptance['passed']
    meta=read(new/'build.json');assert all(sha((new/n).read_bytes())==h for n,h in meta['artifacts'].items())
    profiles={p.name:inventory(p) for p in (old,new)}
    experiments={}
    specs=[('provider',new/'split/source','rtc-provider',0x8000,'SERVICE_END',2265,(new/'split/provider.bin').read_bytes()[:-2]),
           ('banner',new/'banner-source','rtc-banner',0x8900,'BANNER_END',1156,(new/'str8n-rtc-component-8000-8fff.bin').read_bytes()[0x900:0xD84]),
           ('journal',new/'journal-source','journal',0x9000,'JOURNAL_END',2810,(new/'str8n-journal-9000-9fff.bin').read_bytes()[:2810]),
           ('clock',ROOT/'BUILD/v2-clock-1.5/source','clock',0x2000,'APP_END',6443,(ROOT/'BUILD/v2-clock-1.5/clock.bin').read_bytes())]
    for label,source,name,start,end,expected,original in specs:
        experiments[label]=experiment(label,source,name,start,end,expected,original)
        print('SIZE',label,experiments[label]['original_bytes'],'->',experiments[label]['compacted_bytes'],flush=True)
    compact_slack=3070-experiments['journal']['compacted_bytes']
    result=dict(passed=True,phase=1,profiles=profiles,experiments=experiments,
        spi_implemented=False,board_access=False,board_writes=False,installed_firmware_changed=False,
        preferred_rom='compact existing B3:9 immutable prefix; preserve 9C00-9FFF identity tail',
        measured_compacted_journal_slack=compact_slack,spi_driver_budget=min(640,compact_slack),
        full_spi_fit_proven=False,additional_sector_allocated=False,
        proposed_ram=dict(spi_descriptor='6646-664C',sram_descriptor_and_stub='66A2-66AD',spi_stub='66B8-66BC',
                          shared_request='6650-665F',shared_private_state='666A-66A1',reservation='6500-66FF',user_ram_top='64FF'),
        gateway_growth_budget=10,hardware_acceptance_sha256=sha((ROOT/'output/qualification/rtc-trim-2026-10-07/acceptance.json').read_bytes()))
    (OUT/'report.json').write_text(json.dumps(result,indent=2)+'\n')
    print('PASS SPI Phase 1 inventory; isolated assembly sizes; current firmware hashes unchanged; full SPI fit remains for Phase 2')

if __name__=='__main__':main()
