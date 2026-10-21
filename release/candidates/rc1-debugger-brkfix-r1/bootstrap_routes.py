"""Direct WDCMONV2/beta4 -> v1g route adapters. No intermediate gen49 image.

The target kit is separately generated/sealed from preserved migration inputs.
Vendor images are recognized by digest; no vendor or board backup bytes ship.
"""
from pathlib import Path
import sys


def modules(root):
    kit=Path(root).resolve()/'migration'
    sys.path.insert(0,str(kit))
    import migrate
    import factory_wdc
    if Path(migrate.__file__).resolve()!=kit/'migrate.py' or Path(factory_wdc.__file__).resolve()!=kit/'factory_wdc.py':
        raise ValueError('Different migration module already loaded; run in a fresh process')
    migrate.verify_kit(kit)
    return kit,migrate,factory_wdc


def identify(root,banks):
    kit,m,f=modules(root)
    try:
        profile=f.profile_for(banks,kit)
        return 'wdcmonv2-'+profile['cpu']
    except ValueError:
        m.admit_beta4(banks,kit)
        return 'beta4'


def prepare(root,capture,out,*,accept_unknown_wear_history=False,history=None,metadata_escrow=None):
    kit,m,f=modules(root)
    identity,banks=m.capture(capture);source=identify(root,banks)
    if source=='beta4':
        info=m.prepare_beta4(capture,kit,out,metadata_escrow)
    else:
        info=f.prepare(capture,kit,out,history=history,metadata=metadata_escrow,accept_unknown_history=accept_unknown_wear_history)
    _,_,row,_=m.r.clean_journal([(out/f'expected-b{n}.bin').read_bytes() for n in range(4)])
    m.r.require(int.from_bytes(row[17:21],'little')==50,'Migration target journal is not generation50')
    for page in (0xa0,0xb0):
        body=(out/'expected-b3.bin').read_bytes()[(page-0x80)*256:(page-0x80)*256+4096]
        m.r.require(body[8:12]==(50).to_bytes(4,'little') and m.bridge.slot_valid(body,page),'Migration target monitor is not valid generation50')
    info.update(source_profile=source,target_profile='v1g',action='direct-migration',usb_serial=identity.get('usb_serial'),
                native_debugging=False,RTC_drift_in_release_qualification=False,intermediate_generation49=False,
                uniform_manifest_sha256=m.r.sha((Path(root)/'uniform-manifest.json').read_bytes()))
    (out/'plan.json').write_text(__import__('json').dumps(info,indent=2)+'\n')
    return info


def verify(root,plan):
    kit,m,f=modules(root);info=m.r.read(plan/'plan.json')
    m.r.require(info['uniform_manifest_sha256']==m.r.sha((Path(root)/'uniform-manifest.json').read_bytes()),'Wrong uniform kit binding')
    m.r.require(info['target_profile']=='v1g' and info['intermediate_generation49'] is False and info['action']=='direct-migration','Wrong migration route')
    if info['source_profile']=='beta4':
        _,source,expected=m.validate_beta4_plan(plan,kit)
        metadata=None
        if info['metadata_escrow'] is not None:metadata=(plan/info['metadata_escrow']['file']).read_bytes()
        cfg,desired=m.beta4_target(source,kit,metadata)
        tx,data,replayed=m.r.transaction(source,desired,m.r.preference(cfg,cfg[8] if cfg[7]==ord('P') else 0xb0,50),'Portable published beta4 to rc1')
        import tempfile
        with tempfile.TemporaryDirectory(prefix='uniform-beta4-verify-',dir=plan.parent) as temp:
            check=Path(temp)/'plan';m.r.compose(kit/'template',check,source,tx,data,replayed)
            m.r.require((check/'installer-model-only.s19').read_bytes()==(plan/'installer-model-only.s19').read_bytes(),'Re-derived beta4 installer differs')
    else:
        _,source,expected=f.validate_plan(plan,kit)
    m.r.require(identify(root,source)==info['source_profile'],'Changed source profile')
    identity=m.r.read(plan/'source-capture.json')
    m.r.require(info['usb_serial']==identity.get('usb_serial') and bool(info['usb_serial']),'Wrong/missing USB binding')
    return info


def capture_stock(link,path,board,usb,save):
    """Truthful guarded empty-bank source: B3/RAM repeated, B0-2 checked by
    the RAM installer's full-bank preflight before its very first mutation.
    No unsupported claim that WDC's host debugger independently read all banks.
    """
    _,m,_=modules(Path(__file__).resolve().parent)
    path.mkdir();(path/'.gitignore').write_text('*\n');files={}
    b3=link.stock_read(0x8000,32768)
    m.r.require(b3==link.stock_read(0x8000,32768),'Repeated WDC source reads differ')
    for bank,body in enumerate([b'\xff'*32768]*3+[b3]):
        for suffix in ('','-repeat'):
            name=f'b{bank}{suffix}.bin';(path/name).write_bytes(body)
            files[name]=dict(bytes=len(body),sha256=m.r.sha(body))
    ram=link.stock_read(0x200,0x6300);repeat=link.stock_read(0x200,0x6300)
    profile=m.r.read(Path(__file__).resolve().parent/'migration/profiles.json')
    cpu=next(p['cpu'] for name,p in profile.items() if name.startswith('wdcmonv2') and p['source_sha256']==m.r.sha(b3))
    protected=(0x700-0x200,0x800-0x200) if cpu=='65C816' else (0,0)
    m.r.require(ram[:protected[0]]==repeat[:protected[0]] and ram[protected[1]:]==repeat[protected[1]:], 'Repeated stable WDC RAM ranges differ')
    for name,body in [('application-ram.bin',ram),('application-ram-repeat.bin',repeat),('restore-application-ram.s19',m.bridge.s19(dict(enumerate(ram,0x200)),0x200))]:
        (path/name).write_bytes(body);files[name]=dict(bytes=len(body),sha256=m.r.sha(body))
    save(path/'capture.json',dict(schema=2,board=board,usb_serial=usb,repeat_verified=False,assumed_erased_banks=[0,1,2],
        independently_repeated_banks=[3],device_full_bank_preflight_required=True,files=files,
        RAM_repeat_excludes_live_debugger_page='0700-07FF' if cpu=='65C816' else None,
        full_application_RAM_restoration_deferred_until_target_monitor=cpu=='65C816'))
    return [b'\xff'*32768]*3+[b3],ram
