"""Prepare the complete beta4 migration release with an explicit allowlist."""
import hashlib,json,re,shutil,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'BUILD/v2-beta4'
KIT=OUT/'kit'
def main():
    for script in ('build_v2_beta4.py','build_v2_beta4_migrator.py','build_v2_beta4_manuals_pdf.py'):
        subprocess.run([sys.executable,str(ROOT/'tools'/script)],check=True)
    extra={
        'README.md':ROOT/'README.md',
        'str8n-v2-b4-migrator-2000.s19':OUT/'migrator/str8n-v2-b4-migrator-2000.s19',
        'migrator.json':OUT/'migrator/migrator.json',
        'beta4_migration.py':ROOT/'tools/beta4_migration.py',
        'MIGRATE-WDC-TO-STR8N.ps1':ROOT/'MIGRATE-WDC-TO-STR8N.ps1',
        'MIGRATE-WDC-TO-STR8N.sh':ROOT/'MIGRATE-WDC-TO-STR8N.sh',
        'MIGRATE-STR8N-TO-B4.ps1':ROOT/'MIGRATE-STR8N-TO-B4.ps1',
        'MIGRATE-STR8N-TO-B4.sh':ROOT/'MIGRATE-STR8N-TO-B4.sh',
        'STR8N_V2_BETA4_MIGRATION.md':ROOT/'docs/STR8N_V2_BETA4_MIGRATION.md',
        'STR8N_V2_BETA4_QUICK_START.md':ROOT/'docs/STR8N_V2_BETA4_QUICK_START.md',
        'STR8N_V2_BETA4_MANUAL.md':ROOT/'docs/STR8N_V2_BETA4_MANUAL.md',
        'RELEASE_MANUALS.md':ROOT/'docs/RELEASE_MANUALS.md',
        'STR8N_V2_BETA4_HARDWARE_ACCEPTANCE_2026-10-06.md':ROOT/'docs/STR8N_V2_BETA4_HARDWARE_ACCEPTANCE_2026-10-06.md',
    }
    from build_v2_beta4_manuals_pdf import GUIDES
    for label in GUIDES:
        extra['STR8N-2.0b4-'+label+'.pdf']=ROOT/'output/pdf'/('STR8N-2.0b4-'+label+'.pdf')
    manifest=json.loads((KIT/'manifest.json').read_text())
    # Owner-specific cleanup receipts belong in local evidence, not a public kit.
    manifest['artifacts'].pop('STR8N_V2_BETA4_CLEANUP_COM3_2026-10-06.md',None)
    for name,source in extra.items():
        shutil.copyfile(source,KIT/name)
        if name=='README.md':
            # Repository guides live under docs/; the release kit is flat.
            (KIT/name).write_text(source.read_text().replace('](docs/',']('),encoding='utf-8')
        manifest['artifacts'][name]=hashlib.sha256((KIT/name).read_bytes()).hexdigest()
    manifest.update(vendor_firmware_included=False,board_backups_included=False,
        installation='Use the stock-board or STR8-N a24-and-later migration launcher; retain its host backup.',
        migration_validation='COM3 stock-to-beta4 and COM8 a24c1/beta1-to-beta4 passed physical installation, RESET and full-bank checks; see the hardware acceptance report.',
        physical_migration_tested=True,physical_power_cut_tested=False,native_816_program_execution_tested=False)
    for name in manifest['artifacts']:
        data=(KIT/name).read_bytes()
        if name.endswith(('.md','.ps1','.sh','.py')):
            if re.search(rb'\b(FORTH|BASIC|ASM|ZORK|CALC)\b',data,re.I):
                raise ValueError('Excluded program reference in release: '+name)
        if name.endswith('.md'):
            for target in re.findall(r'\[[^\]]+\]\(([^)]+)\)',data.decode('utf-8')):
                if '://' not in target and not target.startswith('#') and target.split('#')[0] not in manifest['artifacts']:
                    raise ValueError('Broken packaged document link: '+name+' -> '+target)
    (KIT/'manifest.json').write_text(json.dumps(manifest,indent=2)+'\n')
    output=ROOT/'output/release/str8n-v2-b4.zip';temporary=output.with_suffix('.zip.tmp')
    with zipfile.ZipFile(temporary,'w',zipfile.ZIP_DEFLATED) as archive:
        for name in sorted([*manifest['artifacts'],'manifest.json']):
            info=zipfile.ZipInfo(name,(2026,10,6,12,0,0));info.create_system=3
            info.external_attr=(0o100755 if name.endswith('.sh') else 0o100644)<<16
            info.compress_type=zipfile.ZIP_DEFLATED;archive.writestr(info,(KIT/name).read_bytes())
    with zipfile.ZipFile(temporary) as archive:
        assert archive.testzip() is None and set(archive.namelist())==set(manifest['artifacts'])|{'manifest.json'}
        for name,digest in manifest['artifacts'].items():assert hashlib.sha256(archive.read(name)).hexdigest()==digest
    temporary.replace(output)
    output.with_suffix('.sha256').write_text(hashlib.sha256(output.read_bytes()).hexdigest()+'  '+output.name+'\n')
    print(f'PASS complete beta4 release: {len(manifest["artifacts"])+1} allowlisted files; hashes, links and ZIP readback')
    print(output)
if __name__=='__main__':main()
