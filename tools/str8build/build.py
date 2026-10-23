"""The single build recipe for all current STR8-N components."""
from pathlib import Path

from .assemble import Assembly
from .baselines import Baselines, read
from .formats import db, s19, save, sealed, sha
from .images import (assembler_image, boot_sector, compose, dispatcher_sector,
                     monitor_slot, rtc_sector, version_asset, wear_record)


def build(root, out, assembler, linker):
    source = root/'src/current'
    layout = read(source/'layout.json')
    baseline = Baselines(root, source, layout)
    assembly = Assembly(source, out, assembler, linker)
    link, emit = assembly.link, assembly.emit
    stage, payload = out/'s', out/'payload'

    worker, _ = link('core','str8n-v2-worker',0x7800,'V2W_END')
    vectors, vs = link('core','str8n-v2-vectors',0x7E20,'V2V_END')
    db(stage/'core/worker-image.inc',worker); db(stage/'core/vectors-image.inc',vectors)
    messages = read(stage/'core/text.json')
    first = next(i for i,m in enumerate(messages) if m['name']=='V2_BAD_PREFIX')
    pool = bytearray()
    for i, message in enumerate(messages):
        raw = bytearray(message['text'].replace('{version}',layout['version']).encode('ascii'))
        if i < first:raw = raw[4:]
        raw[-1] |= 128; pool.extend(raw)
    db(stage/'core/text-image.inc',pool,'V2_TEXT:\n')
    boot, bs = link('core','str8n-v2-boot',0xF000,'BOOT_END')
    fixed = boot_sector(boot,bs,vs,layout['boot_compatibility'])
    emit('str8n-v2-recovery-f000-ffff.bin',fixed)

    app, _ = link('assembler','asm-app',0xE000,'APP_END')
    app, app_vectors = assembler_image(app,fixed)
    emit('assembler/asm-e000.bin',app); emit('assembler/vectors-f000.bin',app_vectors)
    sr, _ = link('core','str8n-v2-sr',0xE800,'SR_END')
    launcher, ls = link('core','launcher',0xE000,'AP_END')
    mode, _ = link('mode','status-mode-init',0xEE92,'AUX_END')
    loader, _ = link('loader','version-loader',0xEF00,'AUX_END')
    emit('str8n-v2-recovery-e000-efff.bin',dispatcher_sector(launcher,sr,mode,loader,ls,app))
    batch, _ = link('batch','batch-gate',0x7C90,'B29_GATE_END')
    db(stage/'core/batch-gate.inc',batch+b'\xEA'*(96-len(batch)))
    b_source = (stage/'core/monitor-b0.asm').read_text()
    anchor = 'V2_IMAGE_PAGE EQU $B0'
    if b_source.count(anchor) != 1:
        raise ValueError('Monitor slot-page declaration changed')
    for page in (0xB0,0xA0):
        name = f'monitor-{page:02x}'
        if page == 0xA0:
            (stage/'core'/f'{name}.asm').write_text(b_source.replace(anchor,'V2_IMAGE_PAGE EQU $A0',1))
        body, symbols = link('core',name,(page<<8)+128,'V2_END')
        emit(f'str8n-v2-recovery-slot-{page:02x}.bin',
             monitor_slot(body,symbols,page,layout['generation'],layout['boot_compatibility']))

    provider, _ = link('provider','rtc-provider',0x8000,'SERVICE_END')
    gate, gs = link('gateway','rtc-gateway',0x6500,'GATE_END')
    banner, _ = link('banner','rtc-banner',0x8900,'BANNER_END')
    emit('str8n-rtc-component-8000-8fff.bin',rtc_sector(provider,gate,banner,gs))
    journal, _ = link('journal','journal',0x9000,'JOURNAL_END')
    emit('str8n-journal-9000-9fff.bin',sealed(journal,3072)+b'\xff'*1024)
    for module,name,address,size,target in [
        ('status','storage-status',0x6E00,2560,'boot-status/asset.bin'),
        ('battery','battery',0x6E00,2560,'battery/asset.bin'),
        ('local','local-display',0x6700,1792,'local-display/asset.bin'),
        ('pf','pf',0x6700,768,'pf-worker/asset.bin')]:
        body, _ = link(module,name,address,'APP_END'); emit(target,sealed(body,size))
    version, _ = link('version','version',0x6E00,'APP_END')
    emit('version/asset.bin',version_asset(version,(payload/'pf-worker/asset.bin').read_bytes(),vs))
    gate, _ = link('xip','gate',0x7B90,'G_END')
    stub, _ = link('xip','work-stub',0x5000,'STUB_END')
    db(stage/'xip/gate-image.inc',gate); db(stage/'xip/work-stub.inc',stub+b'\xff'*(64-len(stub)))
    utilities, _ = link('xip','utilities',0x8000,'X28_END')
    emit('xip/utilities.bin',sealed(utilities,0x5800))
    clock, _ = link('clock','clock',0x2000,'APP_END')
    emit('clock/clock.bin',clock); emit('clock/clock.s19',s19(clock,0x2000,0x2000))
    record = b'SR\x01\x3F\x00\x20'+len(clock).to_bytes(2,'little')+b'CLOCK'.ljust(16,b'\0')+clock
    emit('clock/storage.bin',record+b'\xff'*(12288-len(record)))

    db(stage/'bootstrap/initial-record.inc',wear_record(),'INITIAL_RECORD:\n')
    bootstrap, _ = link('bootstrap','bootstrap-journal',0x2000,'APP_END')
    emit('bootstrap/bootstrap-journal.bin',bootstrap)
    worker, _ = link('migration','migration-worker',0x7800,'V2W_END')
    db(stage/'migration/migration-worker-image.inc',worker)
    db(stage/'migration/migration-table.inc',b'\xff'*(16*9))
    migration, _ = link('migration','rtc-migrator',0x2000,'MIG_END')
    emit('migrator/rtc-migrator-2000.s19',s19(migration,0x2000,0x2000))
    extension, source_symbols = link('source-store','source',0x9000,'NS_END')
    source_component = sealed(extension,4096); (out/'source-9000.bin').write_bytes(source_component)
    debug, debugger_symbols = link('debugger','debugger',0xA000,'DEBUG_END')
    debugger = sealed(debug,4096); (out/'debugger/debugger-a000.bin').write_bytes(debugger)
    emit('debugger-a000.bin',baseline.legacy)  # Recorded compatibility export, never installed in the image.
    image = compose(layout,payload,baseline.uchess,source_component,debugger)
    (out/'firmware.bin').write_bytes(image)
    report = baseline.verify(assembly,source_symbols,debugger_symbols,image,debugger)
    report['toolchain'] = {str(Path(t).resolve()):sha(Path(t).read_bytes()) for t in (assembler,linker)}
    report['build_sources'] = {p.name:sha(p.read_bytes()) for p in sorted(Path(__file__).parent.glob('*.py'))}
    report['layout_sha256'] = sha((source/'layout.json').read_bytes())
    save(out/'build-report.json',report)
    if not report['passed']:
        raise ValueError('Selected firmware baseline equivalence failed; inspect build-report.json')
    print(f'PASS: {len(assembly.compiled)} fresh links, {len(report["artifacts"])} payloads, '
          f'all symbols and firmware match {report["candidate_id"]}. No board access.',flush=True)
    return report
