"""Install only the ten signed utility sectors from the approved2512 scope."""
from pathlib import Path
from storage_release_trial_2512 import *


def run():
    p=approved();expected,ops=forecast_install(p)
    before={n:(SCOPE/f'B{n}-original.bin').read_bytes() for n in range(4)}
    with Trial(INST,'2512-approved-storage-image-install',before,300) as x:
        (INST/'driver-as-executed.py').write_bytes(Path(__file__).read_bytes())
        for bank in range(4):
            b=x.s.client.flash(bank);assert b==before[bank];opaque.durable_file(INST/f'B{bank}-before.bin',b)
        x.check('fresh-images-journal-golden-F-and-owner-admitted')
        for target in p['targets']:
            if drift_pending():raise InterruptedError('RTC priority; no next erase started')
            bank,page=target['bank'],target['page'];off=(page-0x80)*256
            assert x.r['flash_erase_requests']<10
            x.replace(bank,page,before[bank][off:off+4096],(SCOPE/target['file']).read_bytes())
            x.r.setdefault('completed',[]).append(target['address']);x.check('installed-'+target['address'])
        assert x.expected==expected and x.r['operations']==ops
        x.verify_banks((1,2,3));x.r['native_journal_erases']=['B3:C']
        x.check('exact-ten-targets-native-C-rotation-and-EDU-status-preservation')
        x.mon()
        for manager,query,content in (('SRAM','T',b'CLK'),('WORK','?',b'workspace:')):
            face=x.cmd(f'BATCH R {manager};{query};Q;D 1000',MONS)
            assert b'BATCH done' in face and b'1000:' in face and content in face and b'BATCH stopped' not in face,face[-1000:]
        x.check('installed-SRAM-and-WORK-BATCH-Q-continue-on-MON')
        x.cmd('R MAINT',(BM,));face=x.cmd('M 3');assert b'WEAR' in face.upper() or b'COUNT' in face.upper() or b'B0' in face,face[-1000:]
        x.cmd('Q',MONS);x.cmd('R FLASH',(FT,));x.cmd('BANK 0');x.cmd('I 9000 AFFF',(DENSE_YES,))
        face=x.cmd('NO',(FT,));assert b'Send dense' not in face;x.cmd('Q',MONS)
        x.check('packed-MAINT-and-relocated-dense-library-real-command-NO')
        x.cmd('AREA 0 9000 9FFF');assert x.s.dump(0x6A29,0x6A2E)==bytes.fromhex('01 00 00 90 00 A0')
        face=x.cmd('TIME');assert b' trim $0C ctrl $80' in face,face
        x.check('installed-AREA-snapshot-and-native-TIME-trim-unchanged')
        x.r['passed']=True
    r=json.loads((INST/'report.json').read_text())
    assert r['passed'] and r['owner_RAM_restored'] and r['owner_ZP_restored'] and r['port_released']
    print('PASS2512 ten images installed; F/MON/settings retained; owner RAM restored; COM4 free',flush=True)


if __name__=='__main__':run()
