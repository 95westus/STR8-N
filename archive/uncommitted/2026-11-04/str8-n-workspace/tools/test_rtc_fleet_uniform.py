"""Offline tests for fleet launch timing, gaps, bounds and restoration delegation."""
import contextlib, importlib, json, math, sys, tempfile, unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parent))
import rtc_fleet_uniform as u

class UniformTests(unittest.TestCase):
    def test_no_burst_and_anchor(self):
        g={'next_epoch_unix':10000,'slots':{}}
        self.assertEqual(u.advance(g,9700),10000)
        self.assertEqual(u.advance(g,9980),13600)
        self.assertEqual(g['slots']['10000']['status'],'missed; no interpolation')
        g['slots']['13600']={'status':'accepted'}
        self.assertEqual(u.advance(g,10000),17200)
    def test_linear_phase_zero_adev_and_counts(self):
        ps=[dict(time=3600*i,mid=i*.01,low=i*.01-.001,high=i*.01+.001) for i in range(7)]
        aa=u.adev(ps)
        self.assertEqual([a['terms'] for a in aa],[5,3,1])
        self.assertLess(max(a['adev'] for a in aa),1e-15)
        self.assertTrue(all(a['compatibility_bounds'][0]==0 for a in aa))
    def test_known_second_difference(self):
        ps=[dict(time=3600*i,mid=x,low=x,high=x) for i,x in enumerate([0,.01,0])]
        a=u.adev(ps)[0]
        self.assertAlmostEqual(a['adev'],.02/(math.sqrt(2)*3600))
        self.assertEqual(a['compatibility_bounds'],[a['adev'],a['adev']])
    def test_gap_never_interpolated(self):
        ps=[dict(time=3600*i,mid=0,low=-1,high=1) for i in [0,1,3]]
        self.assertEqual(u.adev(ps),[])
    def test_midpoint_bounds_projection(self):
        rows=[dict(reference_start_unix=1000+i*.1,reference_end_unix=1000+i*.1+.01,rtc_minus_reference_interval_s=[.1,.2]) for i in range(621)]
        p=u.phase_point(rows,1031)
        self.assertAlmostEqual(p['midpoint_error_s'],.005)
        self.assertLessEqual(p['low'],.1)
        self.assertGreaterEqual(p['high'],.2)
        self.assertAlmostEqual(p['epoch_projection_allowance_s'],.005*u.RATE)
    def test_all_raw_phase_intervals_recomputed(self):
        rows=[dict(rtc_unix=1000,reference_start_unix=999.9,reference_end_unix=1000.1,rtc_minus_reference_interval_s=[0,0]) for i in range(9)]
        with self.assertRaises(AssertionError):u.phase_point(rows,1000,.01)
    def test_empty_compatibility_not_relaxed(self):
        rows=[dict(reference_start_unix=i,reference_end_unix=i,rtc_minus_reference_interval_s=[i,i+.01]) for i in range(9)]
        with self.assertRaises(AssertionError):u.phase_point(rows,4)
    def test_hooks_delay_and_restore_on_exception(self):
        import installer.engine.legacy_transport as tr
        module=importlib.import_module(u.MODULES['2205'])
        clock=[0.];sent=[]
        class Ref:
            def __init__(self,s):self.uncertainty=.01
            def now(self):return 900+clock[0]
        class Link:
            def send(self,data):sent.append((data,clock[0]))
        def sleep(t):clock[0]+=t
        original_lease=module.serial_lease
        with patch.object(tr,'Link',Link),patch.object(module.b,'Reference',Ref):
            try:
                with u.timing_hooks(module,1000,{},clock=lambda:clock[0],sleep=sleep):
                    module.b.Reference([])
                    link=tr.Link();link.send(b'V\r');link.send(b'G 2000\r')
                    self.assertEqual(sent[0],(b'V\r',0))
                    self.assertAlmostEqual(sent[1][1],69)
                    raise ValueError('simulated acquisition error')
            except ValueError:pass
            self.assertIs(tr.Link,Link);self.assertIs(module.b.Reference,Ref)
            self.assertIs(module.serial_lease,original_lease)
    def test_late_setup_restores_actual_collectors_before_agent_start(self):
        # Execute each unchanged collector's real try/finally with simulated
        # hardware. Setup misses its start after borrowing RAM: no G/q commands
        # are sent and original restoration/prompt/close paths must complete.
        for board,name in u.MODULES.items():
            module=importlib.import_module(name)
            import installer.engine.legacy_transport as tr
            sent=[];stages=[];image,_=module.load();backup=bytes([0x5a])*len(image)
            marker={};real_read=module.c.read;real_save=module.c.save
            marker_path=u.Q/f'device-operations/{board}.json'
            class Link:
                def __init__(self,*args):self.serial=SimpleNamespace(close=lambda:None)
                def send(self,data):sent.append(data)
                def command(self,cmd,*args):
                    if cmd=='V':return b'65C02 65C816 EDU ON  gen 00000010'
                    return b''
            class Ref:
                def __init__(self,s):self.uncertainty=.01
                def now(self):return 980.
            def dump(link,start,end):
                if start==0x7d00:return bytes([0,2])+bytes(62)
                if start==0x7e60:return b'RA\x01\x0d'
                return backup
            def save(path,value):
                if Path(path)==marker_path:marker.clear();marker.update(value)
                else:real_save(path,value)
            @contextlib.contextmanager
            def lease(*a,**kw):yield
            with tempfile.TemporaryDirectory() as tmp,patch.object(tr,'Link',Link),patch.object(module.b,'Reference',Ref),patch.object(module.f,'admission',lambda b:{}),patch.object(module.f,'dump_ram',dump),patch.object(module.f,'until_any',lambda *a:(b'',module.f.REC)),patch.object(module,'stage',lambda link,data:stages.append(data)),patch.object(module.c,'read',lambda path:dict(marker) if Path(path)==marker_path else real_read(path)),patch.object(module.c,'save',save),patch.object(module.b,'ntp_sample',lambda s:{}),patch('serial.tools.list_ports.comports',lambda:[SimpleNamespace(device='FAKE',serial_number=module.f.IDS[board])]),patch.object(module.time,'sleep',lambda s:None),patch('serial_test_coordination.serial_lease',lease):
                with u.timing_hooks(module,1000,{}):r=module.collect(board,Path(tmp)/'capture')
            self.assertFalse(r['passed'],board)
            self.assertTrue(r['error'].startswith('TimingDefer('),r)
            self.assertTrue(all(r.get(k) for k in ['application_ram_restored','LED_restored','returned_to_original_prompt','port_released']),r)
            self.assertEqual(stages,[image,backup])
            self.assertNotIn(b'G 2000\r',sent);self.assertNotIn(b'q',sent)
            self.assertFalse(marker.get('application_RAM_restore_pending'))
    def test_restart_reaudits_saved_capture_without_hardware(self):
        module=importlib.import_module(u.MODULES['2205'])
        with tempfile.TemporaryDirectory() as tmp:
            folder=Path(tmp);(folder/'report.json').write_text(json.dumps({'passed':True}))
            rows=[dict(reference_start_unix=969+i*.1,reference_end_unix=969+i*.1,rtc_minus_reference_interval_s=[.1,.2]) for i in range(621)]
            (folder/'observations.jsonl').write_text('\n'.join(json.dumps(r) for r in rows))
            grid={'points':[],'slots':{'1000':{'status':'in flight; audit before retry','folder':str(folder)}}}
            cfg={'boards':{'2205':grid}}
            with patch.object(module,'audit_board',lambda item,state:{'trim':-17,'control':128,'PF_latched':False}),patch.object(module,'collect',side_effect=AssertionError('Must not touch hardware')):
                u.reconcile(cfg,{})
                u.reconcile(cfg,{})
            self.assertEqual(grid['slots']['1000']['status'],'accepted')
            self.assertEqual(len(grid['points']),1)
    def test_early_wait_and_stop_never_open_ports(self):
        import rtc_drift_campaign as c,rtc_hourly_schedule as hourly
        grids={b:{'next_epoch_unix':10000,'slots':{},'points':[]} for b in ['2205','2512','2609']}
        cfg={'active':True,'boards':grids}
        state={'active':True};plan={'active':True}
        def read(path):return cfg if Path(path)==u.CONFIG else state if Path(path)==c.STATE else plan
        with patch.object(u,'verify'),patch.object(u,'read',read),patch.object(u,'render'),patch.object(u,'save'),patch.object(u,'reconcile'),patch.object(u.time,'time',lambda:9000),patch.object(u,'components',side_effect=AssertionError('No hardware components on WAIT')):
            self.assertEqual(u.run_once()['action'],'wait')
            plan['active']=False
            self.assertEqual(u.run_once()['action'],'pause_automation')
    def test_controller_mutex_never_reaudits_active_unit(self):
        import msvcrt
        with tempfile.TemporaryDirectory() as tmp,patch.object(u,'LOCK',Path(tmp)/'host.lock'),patch.object(u,'run_once',side_effect=lambda:{'nested':u.run()}):
            r=u.run()
            self.assertEqual(r['nested']['reason'],'Uniform controller already running')
    def test_qualified_binary_and_current_admissions(self):
        import rtc_drift_campaign as c
        state=u.read(c.STATE);mode,modules,ready=u.components()
        self.assertTrue(mode.enabled(state))
        for b in modules:
            image,proof=modules[b].load()
            self.assertEqual(len(image),794)
            self.assertEqual(proof['RTC_data_writes'],0)
            self.assertTrue(ready[b](state),b)

if __name__=='__main__':unittest.main(verbosity=2)

