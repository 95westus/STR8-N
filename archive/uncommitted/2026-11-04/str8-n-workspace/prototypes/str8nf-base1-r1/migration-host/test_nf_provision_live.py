"""Focused host admission/ordering tests, no CPU/flash model or serial port."""
import contextlib
import io
import json
import sys
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock,patch

import nf_migrate as planning
import nf_migrate_live as live
import nf_provision_live as provision
from test_nf_migrate import blank_banks, with_snapshot, seal, temporary_directory, F_IMAGE

quiet=lambda *args,**kwargs:None


class Link:
    hardware_access=False
    def __init__(self,banks,*,preflight=True,bad_post=False,fail_Y=False,bad_identity=False,change_repeat=False,read_error=False):
        self.banks=list(map(bytes,banks));self.post=list(self.banks)
        self.events=[];self.sent=[];self.pending=bytearray();self.post_phase=False
        self.preflight,self.bad_post,self.fail_Y,self.bad_identity=preflight,bad_post,fail_Y,bad_identity
        self.run_root=None
        self.change_repeat,self.read_error=change_repeat,read_error
        self.read_counts={}
    def until(self,token,**kwargs):
        self.events.append(('until',token))
        if token==provision.CHOICES:
            return (b'wrong F\r\n' if self.bad_identity else provision.IDENTITY)+token
        if token==live.REC:return b'Recovery L A/B 0-3 C1/2/3 ?\r\n'+token
        if token==live.ENGINE_READY:
            return (live.ENGINE_SELF_OK+live.ENGINE_SOURCE_OK if self.preflight else b'')+token
        if token==live.ENGINE_DONE:self.post_phase=True
        return token
    def send(self,body):
        body=bytes(body);self.events.append(('send',body));self.sent.append(body)
        if body==b'Y\r':
            assert list((self.run_root/'phases').glob('*CD-flash-authorized-no-automatic-retry.json'))
            if self.fail_Y:raise IOError('Short Y write')


class Client:
    def __init__(self,stream,**kwargs):
        self.link=stream.link;self.admitted=False
    def load(self,image,digest,**kwargs):
        assert kwargs['REC_observed'] and planning.sha(image)==live.READBACK_SHA256
        assert (self.link.run_root/'owner-ram.bin').exists()
        self.admitted=True;self.link.events.append(('reader-loaded',))
    def flash(self,bank):
        self.link.events.append(('flash-read',bank,self.link.post_phase))
        if self.link.read_error:raise IOError('CRC response failure')
        body=(self.link.post if self.link.post_phase else self.link.banks)[bank]
        self.link.read_counts[bank]=self.link.read_counts.get(bank,0)+1
        if self.link.change_repeat and bank==0 and self.link.read_counts[bank]==2:
            return bytes((body[0]^1,))+body[1:]
        if self.link.post_phase and self.link.bad_post and bank==1:return bytes((body[0]^1,))+body[1:]
        return body
    def verify_flash(self,expected):
        result=[planning.sha(self.flash(bank)) for bank in range(4)]
        planning.require(result==expected,'Final readback mismatch')
        return result
    def restore_owner(self,ram,zp):
        self.link.events.append(('restore',planning.sha(ram),planning.sha(zp)))
        return dict(owner_RAM_restored=True,owner_ZP_restored=True,stopped_at_REC=True)
    def send(self,body):self.link.send(body)
    def until(self,token):return self.link.until(token)
    def paced(self,body):self.link.events.append(('raw-wrapper',bytes(body)))


class FramedLink(Link):
    """Canned CRC frames for the real BASE1 client; no target/flash execution."""
    def __init__(self,banks):
        super().__init__(banks)
        self.buffer=bytearray();self.receiving=None;self.received=bytearray()
        self.ram=bytes(planning.OWNER_RAM_SIZE);self.zp=bytes(planning.OWNER_ZP_SIZE)
    def frame(self,body):
        self.buffer.extend(body+planning.crc(body).to_bytes(2,'little')+b'RAM SERVICE BASE1> ')
    def send(self,body):
        super().send(body)
        if self.receiving:
            self.received.extend(body)
            size={'loader':3078,'W':planning.OWNER_RAM_SIZE+2,'Y':planning.OWNER_ZP_SIZE+2}[self.receiving]
            if len(self.received)==size:
                if self.receiving in ('W','Y'):
                    assert planning.crc(self.received[:-2])==int.from_bytes(self.received[-2:],'little')
                    if self.receiving=='W':self.ram=bytes(self.received[:-2])
                    else:self.zp=bytes(self.received[:-2])
                self.receiving=None;self.buffer.extend(b'RAM SERVICE BASE1> ')
            assert len(self.received)<=size
        elif body==b'L\r':
            self.receiving='loader';self.received=bytearray();self.buffer.extend(b'SEND BIN\r\n')
        elif body[:1]==b'F' and len(body)==2:self.frame(self.banks[body[1]])
        elif body in (b'W',b'Y'):self.receiving=body.decode();self.received=bytearray()
        elif body==b'M':self.frame(self.ram)
        elif body==b'Z':self.frame(self.zp)
        elif body==b'Q':self.buffer.extend(live.REC)
    def read(self,count):
        if not self.buffer:raise EOFError('Unexpected protocol read')
        size=min(count,11);body=bytes(self.buffer[:size]);del self.buffer[:size];return body


class Provisioning(unittest.TestCase):
    def escrow(self,root):
        directory=root/'escrow';directory.mkdir()
        meta=dict(schema=1,cpu='65c02',board_model='W65C02SXB',usb_serial='TEST-2512',
            original_before_helpers=True,method='independent-double-read',
            owner_RAM_range='0200-66FF',owner_ZP_range='0000-00DF',files={})
        for name,size in provision.ESCROW_FILES.items():
            body=bytes(range(256))*(size//256)+bytes(range(size%256))
            (directory/name).write_bytes(body)
            meta['files'][name]=dict(bytes=size,sha256=planning.sha(body))
        (directory/'escrow.json').write_bytes(planning.encoded(meta))
        return directory
    def setup_run(self,root,banks=None,**kwargs):
        banks=banks if banks is not None else blank_banks(True)
        link=Link(banks,**kwargs);link.run_root=live.private_root(root/'run')
        return link,self.escrow(root)
    def run_trial(self,link,escrow,real_client=False,**kwargs):
        real=provision.module_at
        def module(name,path):
            return SimpleNamespace(RecoveryClient=Client) if Path(path).name=='nf_recovery.py' and not real_client else real(name,path)
        with patch.object(provision,'module_at',side_effect=module):
            return provision.run(link,link.run_root,escrow=escrow,cpu='65c02',usb_serial='TEST-2512',
                readback_file=provision.ROOT/'firmware/payload/STR8N-F-READBACK-RAM.bin',
                f_file=provision.ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin',
                engine_file=provision.ROOT/'migrator/payload/template.bin',
                manifest_file=provision.ROOT/'firmware/minimal-manifest.json',
                allow_unqualified=True,message=quiet,pace=lambda _:None,**kwargs)
    def test_preview_double_captures_and_restores_without_engine_or_Y(self):
        with temporary_directory() as tmp:
            link,escrow=self.setup_run(Path(tmp))
            result=self.run_trial(link,escrow,provision_cd=True)
            self.assertTrue(result['passed'] and result['owner_RAM_restored'])
            self.assertFalse(result['flash_may_have_changed'] or result['flash_written'])
            self.assertNotIn(b'Y\r',link.sent)
            self.assertFalse(any(e[0]=='raw-wrapper' for e in link.events))
            self.assertEqual([e[1] for e in link.events if e[0]=='flash-read'][:8],[3,0,1,2]*2)
            capture=link.run_root/'capture';planning.read_capture(capture,'65c02','nf-recovery')
    def test_real_recovery_client_handles_split_frames_and_exact_escrow_restoration(self):
        with temporary_directory() as tmp:
            root=Path(tmp);link=FramedLink(blank_banks(True));link.run_root=live.private_root(root/'run')
            escrow=self.escrow(root)
            result=self.run_trial(link,escrow,provision_cd=True,real_client=True)
            self.assertTrue(result['passed'] and result['stopped_at_REC'])
            self.assertEqual(link.ram,(escrow/'owner-ram.bin').read_bytes())
            self.assertEqual(link.zp,(escrow/'owner-zp.bin').read_bytes())
            self.assertFalse(link.buffer or link.pending)
            self.assertNotIn(b'Y\r',link.sent)
    def test_existing_nondefault_history_is_noop_even_with_execute(self):
        with temporary_directory() as tmp:
            banks=with_snapshot(17,[9]*32)
            row=bytearray(banks[3][0x4000:0x4100]);row[7]=ord('2');row[13]=4
            banks[3][0x4000:0x4100]=seal(row)
            link,escrow=self.setup_run(Path(tmp),banks)
            result=self.run_trial(link,escrow,execute=True)
            plan=planning.inspect(link.run_root/'plan')
            self.assertTrue(result['completed_noop'] and result['passed'])
            self.assertEqual(plan['transaction']['reserved_counts'],[9]*32)
            self.assertEqual(plan['transaction']['journal_before']['default'],'2')
            self.assertNotIn(b'Y\r',link.sent)
    def test_explicit_reinitialize_of_existing_history_refused_and_RAM_restored(self):
        with temporary_directory() as tmp:
            link,escrow=self.setup_run(Path(tmp),with_snapshot())
            with self.assertRaisesRegex(ValueError,'preserved'):self.run_trial(link,escrow,provision_cd=True,execute=True)
            self.assertNotIn(b'Y\r',link.sent)
            result=planning.read_json(link.run_root/'result.json')
            self.assertTrue(result['owner_RAM_restored']);self.assertFalse(result['passed'])
    def test_damaged_history_refused_without_write_and_with_restoration(self):
        with temporary_directory() as tmp:
            banks=with_snapshot();banks[3][0x4046]^=1
            link,escrow=self.setup_run(Path(tmp),banks)
            with self.assertRaisesRegex(ValueError,'Damaged'):self.run_trial(link,escrow,provision_cd=True,execute=True)
            self.assertNotIn(b'Y\r',link.sent)
            self.assertTrue(planning.read_json(link.run_root/'result.json')['owner_RAM_restored'])
    def test_missing_conversion_flag_refused_before_engine(self):
        with temporary_directory() as tmp:
            link,escrow=self.setup_run(Path(tmp))
            with self.assertRaisesRegex(ValueError,'provision-cd'):self.run_trial(link,escrow,execute=True)
            self.assertNotIn(b'Y\r',link.sent)
    def test_actual_F_mismatch_refused_before_engine(self):
        with temporary_directory() as tmp:
            banks=blank_banks(True);banks[3][-100]^=1
            link,escrow=self.setup_run(Path(tmp),banks)
            with self.assertRaisesRegex(ValueError,'Actual F differs'):self.run_trial(link,escrow,provision_cd=True,execute=True)
            self.assertNotIn(b'Y\r',link.sent)
    def test_wrong_startup_face_prevents_first_helper(self):
        with temporary_directory() as tmp:
            link,escrow=self.setup_run(Path(tmp),bad_identity=True)
            with self.assertRaisesRegex(ValueError,'startup identity'):self.run_trial(link,escrow,provision_cd=True)
            self.assertFalse(any(e[0]=='reader-loaded' for e in link.events))
    def test_changed_repeat_prevents_confirmation_and_restores_escrow(self):
        with temporary_directory() as tmp:
            link,escrow=self.setup_run(Path(tmp),change_repeat=True)
            with self.assertRaisesRegex(ValueError,'Repeated source bank differs'):
                self.run_trial(link,escrow,provision_cd=True,execute=True)
            self.assertNotIn(b'Y\r',link.sent)
            self.assertTrue(planning.read_json(link.run_root/'result.json')['owner_RAM_restored'])
    def test_protocol_failure_stops_without_blind_restore_or_retry(self):
        with temporary_directory() as tmp:
            link,escrow=self.setup_run(Path(tmp),read_error=True)
            with self.assertRaisesRegex(IOError,'CRC response failure'):
                self.run_trial(link,escrow,provision_cd=True,execute=True)
            result=planning.read_json(link.run_root/'result.json')
            self.assertTrue(result['owner_RAM_restore_required'])
            self.assertFalse(result['owner_RAM_restored'] or result['flash_may_have_changed'])
            self.assertEqual(len([e for e in link.events if e[0]=='flash-read']),1)
    def test_imported_lower_bounds_retained_without_recording_an_F_erase(self):
        with temporary_directory() as tmp:
            root=Path(tmp);link,escrow=self.setup_run(root)
            history=dict(schema=1,semantics='tracked-lower-bounds',source_sha256=planning.bank_hashes(link.banks),
                counts=[7]*32,sequence=42,unknown_mask='ffffffff',provenance='Operator private wear escrow')
            path=root/'history.json';path.write_bytes(planning.encoded(history))
            self.run_trial(link,escrow,provision_cd=True,history_file=path)
            tx=planning.inspect(link.run_root/'plan')['transaction']
            self.assertEqual(tx['reserved_counts'][31],7)
            self.assertEqual(tx['reserved_counts'][28:30],[8,8])
            self.assertEqual(tx['prior_history_unknown_mask'],'ffffffff')
    def test_missing_preflight_never_sends_confirmation(self):
        with temporary_directory() as tmp:
            link,escrow=self.setup_run(Path(tmp),preflight=False)
            with self.assertRaisesRegex(ValueError,'preflight missing'):self.run_trial(link,escrow,provision_cd=True,execute=True)
            self.assertNotIn(b'Y\r',link.sent)
            result=planning.read_json(link.run_root/'result.json')
            self.assertFalse(result['flash_may_have_changed']);self.assertTrue(result['owner_RAM_restore_required'])
    def test_execute_only_D_C_and_restore_after_independent_readback(self):
        with temporary_directory() as tmp:
            link,escrow=self.setup_run(Path(tmp))
            _,transfers,expected=planning.derive(link.banks,F_IMAGE,source_kind='nf-recovery',provision_cd=True)
            link.post=expected
            result=self.run_trial(link,escrow,provision_cd=True,execute=True)
            self.assertTrue(result['passed'] and result['flash_written'] and result['owner_RAM_restored'])
            self.assertFalse(result['F_written'] or result['execution_qualified'])
            self.assertEqual(link.sent.count(b'Y\r'),1)
            start=link.sent.index(b'Y\r')+1
            payload=b''.join(link.sent[start:start+128])
            self.assertEqual(payload,transfers[0][0]+transfers[1][0])
            self.assertEqual(len(payload),8192)
            wrapper=next(e[1] for e in link.events if e[0]=='raw-wrapper')
            self.assertEqual(len(wrapper),8611)
            self.assertEqual(wrapper[419:],(link.run_root/'plan/migrator.bin').read_bytes())
            restore_index=next(i for i,e in enumerate(link.events) if e[0]=='restore')
            self.assertEqual([e[1] for e in link.events[:restore_index] if e[0]=='flash-read' and e[2]],[0,1,2,3])
            plan=planning.inspect(link.run_root/'plan')
            self.assertEqual(plan['transaction']['reserved_counts'][31],0)
            self.assertEqual(plan['transaction']['reserved_counts'][28:30],[1,1])
    def test_final_mismatch_never_claims_or_attempts_restoration(self):
        with temporary_directory() as tmp:
            link,escrow=self.setup_run(Path(tmp),bad_post=True)
            link.post=planning.derive(link.banks,F_IMAGE,source_kind='nf-recovery',provision_cd=True)[2]
            with self.assertRaisesRegex(ValueError,'final bank mismatch'):self.run_trial(link,escrow,provision_cd=True,execute=True)
            result=planning.read_json(link.run_root/'result.json')
            self.assertTrue(result['flash_may_have_changed'] and result['owner_RAM_restore_required'])
            self.assertFalse(result['passed'] or result['independent_flash_readback_verified'])
            self.assertFalse(any(e[0]=='restore' for e in link.events))
    def test_short_confirmation_is_logged_as_possible_mutation_without_retry(self):
        with temporary_directory() as tmp:
            link,escrow=self.setup_run(Path(tmp),fail_Y=True)
            with self.assertRaisesRegex(IOError,'Short Y'):self.run_trial(link,escrow,provision_cd=True,execute=True)
            result=planning.read_json(link.run_root/'result.json')
            self.assertTrue(result['flash_may_have_changed']);self.assertEqual(link.sent.count(b'Y\r'),1)
    def test_bad_escrow_rejected_before_any_transport_action(self):
        with temporary_directory() as tmp:
            link,escrow=self.setup_run(Path(tmp))
            (escrow/'owner-ram.bin').write_bytes(b'wrong')
            with self.assertRaisesRegex(ValueError,'escrow'):self.run_trial(link,escrow,provision_cd=True)
            self.assertFalse(link.events)
    def test_unqualified_cli_does_not_open_port(self):
        args=['--port','COM4','--usb-serial','TEST-2512','--cpu','65c02','--owner-escrow','missing','--out','missing']
        with patch.object(provision,'RecoveryLink') as factory,contextlib.redirect_stderr(io.StringIO()):
            with self.assertRaises(SystemExit):provision.main(args)
        factory.assert_not_called()
    def test_USB_mismatch_is_rejected_before_constructing_serial_port(self):
        factory=Mock()
        ports=SimpleNamespace(comports=lambda:[SimpleNamespace(device='COM3',serial_number='OTHER')])
        with patch.dict(sys.modules,{'serial':SimpleNamespace(Serial=factory),
            'serial.tools':SimpleNamespace(list_ports=ports),'serial.tools.list_ports':ports}):
            with self.assertRaisesRegex(ValueError,'does not match escrow USB'):
                provision.RecoveryLink('COM4',None,usb_serial='TEST-2512')
        factory.assert_not_called()
    def test_cli_missing_original_escrow_never_opens_port_even_with_flags(self):
        with temporary_directory() as tmp:
            args=['--port','COM4','--usb-serial','TEST-2512','--cpu','65c02','--owner-escrow',str(Path(tmp)/'missing'),
                  '--out',str(Path(tmp)/'run'),'--execute','--provision-cd','--allow-unqualified']
            with patch.object(provision,'RecoveryLink') as factory,contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):provision.main(args)
            factory.assert_not_called()


if __name__=='__main__':unittest.main()
