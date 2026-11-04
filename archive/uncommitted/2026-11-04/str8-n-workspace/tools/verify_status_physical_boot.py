"""Armed physical RESET receiver for an already installed STATUS profile.

No flash writes. Default2512 B/default2609 S must finish without chooser input.
"""
import argparse,json
from pathlib import Path
import install_status_reviewed as i
t=i.t;d=i.d
def run(board,reported_reset=False):
    install=i.BASE/board;record=json.loads((install/'report.json').read_text())
    assert record['passed'] and record['NVM_verified']
    root=install/'physical-boot'
    folder=root/'reported-reset' if reported_reset else root
    folder.mkdir(exist_ok=False)
    ram=(install/'owner-ram.bin').read_bytes();zp=(install/'owner-zp.bin').read_bytes()
    reader=(t.REPO/'firmware/payload/STR8N-F-READBACK-RAM.bin').read_bytes()
    path=t.ROOT/f'output/qualification/device-operations/{board}.json'
    report=dict(board=board,passed=False,phase='armed',flash_writes=0,RTC_SET=0,PF_ACK=0,SRAM_writes=0,owner_RAM_restored=False)
    def save():t.save(folder/'report.json',report)
    def mark(**kw):
        m=json.loads(path.read_text());m.update(kw);t.save(path,m)
    s=None;borrowed=False;save()
    with t.serial_lease(board+'-STATUS-physical-reset',timeout=30):
      marker=json.loads(path.read_text());assert not marker['application_RAM_restore_pending']
      with (folder/'serial.jsonl').open('x') as log:
       try:
        s=d.Session(folder,log,board)
        mark(status_boot_worker_active=True,physical_reset_pending=True)
        if reported_reset:
            # Trusted human RESET report after the receiver expired. Observe
            # the default result BEFORE any A/B selector command. Never claim
            # that the missing startup/countdown stream was captured.
            s.link.send(b'\r')
            out=s.until((t.MON,t.REC),seconds=15)
            assert s.context==(t.MON if board=='2512' else t.REC)
            if board=='2512':out+=s.command('VERSION')
            report.update(reset_trigger='Owner explicitly reported physical RESET',
                startup_stream_captured=False,post_reset_default_observed_without_selector=True)
        else:
            s.link.serial.reset_input_buffer();s.link.pending.clear()
            print('ARMED '+board+' physical RESET; no chooser key; keep USB power.',flush=True)
            # Require fresh startup identity, not an old prompt queued at port open.
            prefix=s.link.until(b'BASE1',seconds=180)
            out=prefix+s.until((t.MON if board=='2512' else t.REC,),seconds=45)
            report['startup_stream_captured']=True
        (folder/'physical-default-startup.txt').write_bytes(out)
        if board=='2512':assert b'g0000000C / MON B' in out
        else:
            assert s.context==t.REC
            out=s.command('A',(t.MON,));assert b'g0000000C / MON A' in out
        version=s.command('VERSION');assert b'STATUS tools unavailable' not in version
        assert b'MONITOR A gen 0000000C VALID' in version and b'MONITOR B gen 0000000C VALID' in version
        report['default_physical_startup_passed']=True
        # Capture exactly what the readback tool will overwrite, then check
        # its remainder. This verifies all pre-helper RAM without another full
        # text dump of the board or the 25K owner image.
        assert s.dump(0x200,0x1FF+len(reader))==ram[:len(reader)] and s.dump(0,0xDF)==zp
        s.command('Q',(t.REC,));mark(application_RAM_restore_pending=True,block_snapshot=True);borrowed=True
        s.service(reader)
        assert s.client.read(b'M',0x6500)==reader+ram[len(reader):] and s.client.read(b'Z',0xE0)==zp
        b3=s.client.flash(3);assert t.sha(b3)==record['final_B3_sha256']
        report['boot_preserved_RAM_ZP_and_B3']=True
       finally:
        try:
         if borrowed and s.context==i.SERVICE:
            report.update(s.client.restore_owner(ram,zp));s.context=t.REC
            if board=='2512':s.command('B',(t.MON,))
            report['owner_RAM_restored']=True
        finally:
         if s is not None:s.link.close();report['port_released']=True
         restored=report['owner_RAM_restored'] if borrowed else not marker['application_RAM_restore_pending']
         okay=report.get('boot_preserved_RAM_ZP_and_B3',False) and report['owner_RAM_restored']
         mark(status_boot_worker_active=False,physical_reset_pending=not okay,
            application_RAM_restore_pending=not restored,application_ram_restored=restored,
            block_snapshot=marker['block_snapshot'] if restored else True,
            status_installation_complete=okay,status_physical_boot_pending=not okay,
            state='MON-gC-STATUS-physical-accepted' if okay else marker['state'],
            last_STATUS_physical_boot=str(folder/'report.json'),final_prompt='B3>' if board=='2512' else 'REC>')
         save()
    report.update(passed=okay,phase='physical-boot-verified-owner-restored',finished_utc=t.utc());save()
    if reported_reset and okay:
        (root/'expired-receiver-report.json').write_bytes((root/'report.json').read_bytes())
        combined=dict(report,completion_detail=str(folder/'report.json'))
        t.save(root/'report.json',combined)
    print(json.dumps(report,indent=2),flush=True)
if __name__=='__main__':
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('--board',choices=['2512','2609'],required=True);p.add_argument('--reported-reset',action='store_true');a=p.parse_args();run(a.board,a.reported_reset)
