"""Build isolated beta18 read-only boot/TIME trim display; no board access."""
import shutil
import build_v2_status as status
import build_v2_storage_migrator as migrator

def main(out='BUILD/v2-trim-display',version='2.0b18',generation=27):
    root=status.ROOT;status.OUT=root/out
    status.VERSION=version;status.GENERATION=generation
    status.STORAGE=True;status.TRIM_DISPLAY=True
    # Unchanged SRAM/workspace/utilities; keep their qualified bytes intact.
    for name in ('store','workspace','example','hardware-client','maint','edu','clock'):
        shutil.copytree(root/'BUILD/v2-storage'/name,status.OUT/name,dirs_exist_ok=True)
    status.main()
    # The resident builder emits an intermediate MAINT 1.7. Restore the exact
    # already-qualified saved MAINT 1.8; this display update never replaces it.
    shutil.copytree(root/'BUILD/v2-storage/maint',status.OUT/'maint',dirs_exist_ok=True)
    import json
    original=json.loads((root/'BUILD/v2-storage/build.json').read_text())
    meta=json.loads((status.OUT/'build.json').read_text())
    name=original['maintenance_storage_file']
    shutil.copyfile(root/'BUILD/v2-storage'/name,status.OUT/name)
    meta.update(maintenance_version=original['maintenance_version'],maintenance_storage_file=name)
    meta['artifacts'][name]=original['artifacts'][name]
    (status.OUT/'build.json').write_text(json.dumps(meta,indent=2)+'\n')
    migrator.OUT=status.OUT/'migrator';migrator.VERSION=status.VERSION;migrator.main()

if __name__=='__main__':main()
