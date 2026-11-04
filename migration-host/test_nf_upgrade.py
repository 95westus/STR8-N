"""Focused upgrade serialization and transport ordering; no CPU/flash model."""
import json
import contextlib
import io
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import patch

import nf_migrate as planning
import nf_migrate_live as live
import nf_upgrade as upgrade
from test_nf_migrate import F_IMAGE,with_snapshot,seal,temporary_directory


class Upgrade(unittest.TestCase):
    def setUp(self):
        self.legacy=bytearray(F_IMAGE);self.legacy[500]^=1;self.legacy=bytes(self.legacy)
        self.pin=patch.object(upgrade,'B15_F_SHA256',planning.sha(self.legacy));self.pin.start();self.addCleanup(self.pin.stop)
    def banks(self):
        banks=with_snapshot(8,[11]*32)
        row=bytearray(banks[3][0x4000:0x4100]);row[7]=ord('2');row[13]=4;row[16]=10
        row[32:48]=bytes(range(16));banks[3][0x4000:0x4100]=seal(row)
        banks[3][-4096:]=self.legacy
        banks[0][:]=bytes(range(256))*128
        return banks
    def plan(self,root):
        capture=root/'capture';capture.mkdir();banks=self.banks()
        for n,body in enumerate(banks):
            for suffix in ('','-repeat'):(capture/f'b{n}{suffix}.bin').write_bytes(body)
        for stem,size in [('owner-ram',planning.OWNER_RAM_SIZE),('owner-zp',planning.OWNER_ZP_SIZE)]:
            for suffix in ('','-repeat'):(capture/(stem+suffix+'.bin')).write_bytes(bytes(size))
        meta=dict(schema=1,cpu='65c02',board_model='W65C02SXB',source_kind='nf-recovery',
            method='independent-double-read',owner_original_before_helpers=True,usb_serial='TEST-2512')
        (capture/'capture.json').write_bytes(planning.encoded(meta))
        target=root/'F.bin';target.write_bytes(F_IMAGE)
        plan_root=root/'plan';plan=upgrade.prepare(capture,plan_root,cpu='65c02',target_file=target)
        return plan_root,plan
    def test_reservation_clones_all_existing_policy_and_retains_every_old_record(self):
        banks=self.banks();tx,expected,frame=upgrade.derive(banks,F_IMAGE)
        self.assertEqual(expected[:3],list(map(bytes,banks[:3])))
        self.assertEqual(tx['reservation']['address'],0xc100)
        before=bytes(banks[3][0x4000:0x4100]);after=expected[3][0x4100:0x4200]
        self.assertEqual(expected[3][0x4000:0x4100],before)
        changed=set(range(8,12))|{30,31,157,158,159,252,253}
        self.assertTrue(all(before[n]==after[n] for n in range(256) if n not in changed))
        self.assertEqual(planning.classify_journal(expected[3])['default'],'2')
        self.assertEqual(planning.classify_journal(expected[3])['counts'],[11]*31+[12])
        self.assertEqual(frame[255],255);self.assertEqual(after[255],0)
        self.assertEqual(expected[3][0x4200:0x7000],banks[3][0x4200:0x7000])
        self.assertEqual(expected[3][-4096:],F_IMAGE)
    def test_full_journal_refuses_without_gc(self):
        banks=self.banks();row=bytes(banks[3][0x4000:0x4100])
        banks[3][0x4000:0x6000]=row*32
        with self.assertRaisesRegex(ValueError,'No erased append page'):upgrade.derive(banks,F_IMAGE)
    def test_exhausted_sequence_and_counter_refuse(self):
        for sequence,count,message in [(0xffffffff,11,'sequence exhausted'),(8,0xffffff,'counter exhausted')]:
            banks=self.banks();row=bytearray(banks[3][0x4000:0x4100])
            row[8:12]=sequence.to_bytes(4,'little');row[157:160]=count.to_bytes(3,'little')
            banks[3][0x4000:0x4100]=seal(row)
            with self.assertRaisesRegex(ValueError,message):upgrade.derive(banks,F_IMAGE)
    def test_torn_or_unknown_history_is_not_converted(self):
        for value in (255,1):
            banks=self.banks();banks[3][0x40ff]=value
            with self.assertRaisesRegex(ValueError,'clean existing SNBT'):upgrade.derive(banks,F_IMAGE)
    def test_already_BASE1_is_noop_without_counter_increment(self):
        banks=self.banks();banks[3][-4096:]=F_IMAGE
        tx,expected,frame=upgrade.derive(banks,F_IMAGE)
        self.assertTrue(tx['completed_noop']);self.assertIsNone(frame)
        self.assertEqual(expected,list(map(bytes,banks)))
    def test_wrong_F_and_unsupported_source_refuse(self):
        banks=self.banks();bad=bytearray(F_IMAGE);bad[0]^=1
        with self.assertRaisesRegex(ValueError,'frozen BASE1'):upgrade.derive(banks,bad)
        banks[3][-4095]^=1
        with self.assertRaisesRegex(ValueError,'Unsupported source'):upgrade.derive(banks,F_IMAGE)
    def test_render_and_inspect_bind_append_page_and_F_only_plan(self):
        with temporary_directory() as tmp:
            root=Path(tmp);plan_root,plan=self.plan(root);self.assertEqual(upgrade.inspect(plan_root),plan)
            image=(plan_root/'upgrade.bin').read_bytes()
            self.assertEqual(image[0x1000:0x1008],b'NFU1\x01\x01\0\0')
            self.assertEqual(image[0x1020:0x1024],b'\xf0\0\0\0')
            self.assertEqual(image[0x1100:0x1200],(plan_root/'reservation-uncommitted.bin').read_bytes())
            self.assertEqual(image[0x1300:0x1305],b'JFR1\xc1')
            self.assertEqual(image[0x1308:0x130c],image[0x1024:0x1028])
            self.assertEqual(image[-4:],planning.fnv(image[:-4]).to_bytes(4,'little'))
            self.assertEqual((plan_root/'upgrade-recovery.bin').read_bytes()[419:],image)
            member=plan_root/'reservation-uncommitted.bin';body=bytearray(member.read_bytes());body[7]^=1;member.write_bytes(body)
            with self.assertRaisesRegex(ValueError,'Changed plan member'):upgrade.inspect(plan_root)
    def test_built_variant_calls_append_before_F_guard_and_uses_commit_last(self):
        builder=upgrade.recovery_transport.module_at('test_upgrade_builder',upgrade.ROOT/'migrator/upgrade/build.py')
        text=builder.source()
        self.assertIn('MIG_NEXT:\n        JSR U_APPEND\n        BCC FAIL_FLASH\n        JSR SET_ROW',text)
        self.assertIn('CHECK_PLAN:\n        JSR U_CHECK\n        BCC CHECK_BAD',text)
        appendix=(upgrade.ROOT/'migrator/upgrade/reserve.inc').read_text()
        self.assertNotIn('ERASE_RAW',appendix)
        self.assertLess(appendix.index('U_COMPARE:'),appendix.index('STZ FLASH_DATA'))
        manifest=planning.read_json(upgrade.ROOT/'migrator/upgrade/payload/engine-manifest.json')
        self.assertEqual(planning.sha(text.encode('ascii')),manifest['source_sha256'])
        self.assertLess(manifest['code_bytes'],4096)
        self.assertEqual(manifest['template_sha256'],upgrade.UPGRADE_SHA256)
        for name,digest in manifest['inputs_sha256'].items():
            self.assertEqual(planning.sha((upgrade.ROOT/'migrator'/name).read_bytes()),digest)
    def test_live_requires_reservation_marker_before_F_payload_and_restores_after_readback(self):
        with temporary_directory() as tmp:
            root=Path(tmp);plan_root,plan=self.plan(root);run=live.private_root(root/'run')
            link=Link(run,plan_root)
            real=upgrade.recovery_transport.module_at
            def module(name,path):
                return SimpleNamespace(RecoveryClient=Client) if Path(path).name=='nf_recovery.py' else real(name,path)
            with patch.object(upgrade.recovery_transport,'module_at',side_effect=module):
                result=upgrade.execute(link,plan_root,run,allow_unqualified=True,message=lambda *a,**k:None,pace=lambda _:None)
            self.assertTrue(result['passed'] and result['owner_RAM_restored'])
            self.assertLess(link.events.index(('until',upgrade.RESERVED)),link.events.index(('F-payload',)))
            self.assertEqual(link.payload,(plan_root/'target-F.bin').read_bytes())
            self.assertEqual(link.events[-1],('restore',))
    def test_missing_reservation_proof_sends_no_F_bytes_and_never_retries(self):
        with temporary_directory() as tmp:
            root=Path(tmp);plan_root,_=self.plan(root);run=live.private_root(root/'run')
            link=Link(run,plan_root,missing_reservation=True)
            real=upgrade.recovery_transport.module_at
            with patch.object(upgrade.recovery_transport,'module_at',side_effect=lambda name,path:
                SimpleNamespace(RecoveryClient=Client) if Path(path).name=='nf_recovery.py' else real(name,path)):
                with self.assertRaisesRegex(IOError,'reservation proof'):
                    upgrade.execute(link,plan_root,run,allow_unqualified=True,message=lambda *a,**k:None,pace=lambda _:None)
            self.assertFalse(link.payload)
            state=planning.read_json(run/'result.json')
            self.assertTrue(state['journal_may_have_changed'] and state['owner_RAM_restore_required'])
            self.assertFalse(state['F_may_have_changed'] or state['passed'])
    def test_archived_reference_plan_is_refused_before_any_device_or_output(self):
        with temporary_directory() as tmp:
            root=Path(tmp);self.plan(root)
            path=root/'capture/capture.json';meta=planning.read_json(path);meta['reference_only']=True
            path.write_bytes(planning.encoded(meta))
            plan_root=root/'reference-plan'
            upgrade.prepare(root/'capture',plan_root,cpu='65c02',target_file=root/'F.bin')
            with self.assertRaisesRegex(ValueError,'reference-only plan cannot execute'):
                upgrade.execute(SimpleNamespace(),plan_root,root/'run',allow_unqualified=True)
            self.assertFalse((root/'run').exists())
            argv=['nf_upgrade.py','execute','--plan',str(plan_root),'--out',str(root/'run'),
                  '--port','COM4','--execute','--allow-unqualified']
            with patch('sys.argv',argv),patch.object(upgrade.recovery_transport,'RecoveryLink') as factory,contextlib.redirect_stderr(io.StringIO()):
                with self.assertRaises(SystemExit):upgrade.main()
            factory.assert_not_called()


class Link:
    hardware_access=False
    def __init__(self,run,plan_root,missing_reservation=False):
        self.run,self.plan_root=run,plan_root
        self.events=[];self.pending=bytearray();self.payload=bytearray();self.ready=False
        self.missing_reservation=missing_reservation
    def send(self,body):
        if body==b'Y\r':assert list((self.run/'phases').glob('*journal-append-authorized-before-Y-no-retry.json'))
        elif self.ready:
            if not self.payload:self.events.append(('F-payload',))
            self.payload.extend(body)
    def until(self,token,**kwargs):
        self.events.append(('until',token))
        if token==upgrade.RESERVED and self.missing_reservation:raise IOError('Missing reservation proof')
        if token==b'SEND 4096 BYTES FOR B3:F\r\n':self.ready=True
        if token==live.ENGINE_READY:return live.ENGINE_SELF_OK+live.ENGINE_SOURCE_OK+token
        if token==live.ENGINE_DONE:self.ready=False
        if token==upgrade.recovery_transport.CHOICES:return upgrade.recovery_transport.IDENTITY+token
        if token==live.REC:return b'Recovery L A/B 0-3 C1/2/3 ?\r\n'+token
        return token


class Client:
    def __init__(self,stream,**kwargs):self.link=stream.link
    def send(self,body):self.link.send(body)
    def until(self,token):return self.link.until(token)
    def paced(self,body):self.link.events.append(('wrapper',))
    def load(self,*args,**kwargs):self.link.events.append(('post-reader',))
    def flash(self,bank):return (self.link.plan_root/f'expected-b{bank}.bin').read_bytes()
    def restore_owner(self,ram,zp):
        self.link.events.append(('restore',))
        return dict(owner_RAM_restored=True,owner_ZP_restored=True,stopped_at_REC=True)


if __name__=='__main__':unittest.main()
