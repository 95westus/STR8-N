"""Fresh candidate3 extraction/preparation acceptance; no device access/build."""
import argparse,hashlib,json,subprocess,sys,zipfile
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def run(base):
    base=Path(base).resolve();archive=base/'STR8N-MON-g00000010-candidate3.zip'
    extract=base/'fresh-extraction';extract.mkdir(exist_ok=False)
    with zipfile.ZipFile(archive) as z:
      for item in z.namelist():
        p=(extract/item).resolve();assert p.is_relative_to(extract.resolve())
        p.parent.mkdir(parents=True,exist_ok=True);p.write_bytes(z.read(item))
    kit=extract/'STR8N-MON-g00000010-candidate3';results=[]
    b1=ROOT/'BUILD/storage-installed-auto-r2/B1-candidate.bin'
    b2=ROOT/'output/qualification/2512-startup-traditional-scope-20261101-r1/B2-target.bin'
    b3=ROOT/'output/qualification/2512-BOOT-CLOCK-positive-20261101-r1/B3-after.bin'
    preparer=[sys.executable,str(kit/'tools/nf_native_images.py'),'--current-b2',str(b2),'--current-b3',str(b3)]
    for command in ([sys.executable,str(kit/'verify_candidate.py')],
      preparer+['--current-b1',str(b1),'--out',str(base/'prepared-2512')],
      [sys.executable,str(kit/'foundation/tools/nf_console.py'),'--version']):
      p=subprocess.run(command,cwd=kit,capture_output=True,text=True);assert p.returncode==0,p.stdout+p.stderr
      results.append(dict(command=command,stdout=p.stdout));print(p.stdout.strip()[:350])
    negative=base/'missing-B1-refused'
    p=subprocess.run(preparer+['--out',str(negative)],cwd=kit,capture_output=True,text=True)
    assert p.returncode!=0 and 'B1 utility targets require --current-b1' in p.stderr and not negative.exists()
    plan=json.loads((base/'prepared-2512/install-plan.json').read_text())
    assert len(plan['targets'])==19 and all(t['identical_to_capture'] for t in plan['targets'])
    before=b3.read_bytes()
    assert (base/'prepared-2512/B3-9000.bin').read_bytes()[3072:]==before[0x1C00:0x2000]
    assert (base/'prepared-2512/retained-CD-history.bin').read_bytes()==before[0x4000:0x6000]
    r=dict(status='EXTRACTED_HOST_PREPARATION_ACCEPTED_LIVE_PENDING',passed=True,archive=str(archive),
      sha256=hashlib.sha256(archive.read_bytes()).hexdigest(),bytes=archive.stat().st_size,extracted_kit=str(kit),
      targets=19,all_identical_to_archived_2512=True,RTC_metadata_retained=True,CD_history_retained=True,
      missing_B1_refused_before_output=True,serial_access=False,firmware_builds=0,CPU_simulations=0,F_writes=0,
      published_changes=False,physical_keys_accepted=False,live_extracted_kit_accepted=False,commands=results)
    (base/'EXTRACTION-PREPARATION-RECEIPT.json').write_text(json.dumps(r,indent=2)+'\n')
    print('PASS19 identical targets; exact RTC/CD retention; missing B1 refused; live/physical keys pending')

if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--package-dir',type=Path,default=ROOT/'BUILD/unified-g10-candidate3-20261101-r3')
    run(p.parse_args().package_dir)
