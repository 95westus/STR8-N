"""Preservation and workload checks for the powered-on beta35 soak."""
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import run_v2_beta35_soak as soak
from soak_led_patterns import playlist

class ClockLink:
    def __init__(self, trim='0C'):
        self.commands=[]
        self.trim=trim

    def command(self, text, prompt=None):
        self.commands.append(text)
        if text=='R CLOCK':return b'CLOCK 1.10\r\nCLOCK> '
        if text=='STATUS':return ('Running: yes\r\nBackup enabled: yes\r\nRTC registers (raw): C2 51 07 2C 16 10 26 80 '+self.trim+'\r\nCLOCK> ').encode()
        return b'CLOCK> '

class Tests(unittest.TestCase):
    def test_led_patterns_are_replayable_and_bounded(self):
        patterns=set()
        for seed in range(64):
            shows=playlist(seed)
            self.assertEqual(shows,playlist(seed))
            self.assertEqual(len(shows),3)
            self.assertEqual(sum(s['name']=='random-sparkle' for s in shows),1)
            for show in shows:
                patterns.add(show['name'])
                self.assertEqual(len(bytes.fromhex(show['frames_hex'])),8)
                self.assertLessEqual(120,show['hold_ms'])
                self.assertLessEqual(show['hold_ms'],240)
        self.assertEqual(len(patterns),10)
        self.assertEqual(soak.GROUPS.count('led'),7)
        self.assertEqual([g for g in soak.GROUPS if g!='led'],soak.READ_GROUPS)

    def test_actual_led_probe_restores_and_only_writes_led_and_ram(self):
        from test_v2_rtc import MPU
        body=(soak.probes.PROBES/'led/led.bin').read_bytes()
        class Memory(list):
            def __init__(self):super().__init__([0]*65536);self.writes=[]
            def __setitem__(self,address,value):
                if isinstance(address,int):self.writes.append(address)
                super().__setitem__(address,value)
        for seed in range(16):
            for show in playlist(seed):
                m=Memory();m[0x4000:0x4000+len(body)]=body
                m[0x3200:0x3208]=bytes.fromhex(show['frames_hex'])
                m[0x7FA0]=0x35;m[0x7FA1]=4;m.writes.clear()
                cpu=MPU(memory=m,pc=0x4000);frames=0
                for _ in range(1000):
                    if cpu.pc==0x7E67:break
                    if cpu.pc in (0x7E6D,0x7E70):
                        if cpu.pc==0x7E6D:self.assertEqual(cpu.a,ord('~'))
                        else:frames+=1
                        cpu.pc=cpu.stPopWord()+1
                    else:cpu.step()
                else:self.fail('LED probe did not return')
                self.assertEqual(frames,8)
                self.assertEqual(m[0x7FA0],0x35)
                self.assertTrue(all(a==0x7FA0 or 0x100<=a<0x200 or 0x4036<=a<=0x4037 for a in m.writes))

    def test_led_show_yields_after_restoration(self):
        class Link:
            def __init__(self):self.sent=[];self.writes=[];self.reads=0
            def dump(self,a,b):
                if (a,b)!=(0x500F,0x5010):raise ValueError('Monitor I/O read would be protected')
                self.reads+=1
                return b'\x01\x04' if self.reads==1 else b'\x01\x84'
            def command(self,text):
                if text!='G 5000':raise ValueError('Unexpected command')
            def write_ram(self,a,b):self.writes.append((a,b))
            def send(self,data):self.sent.append(data)
            def until(self,prompt,seconds):return prompt
        link=Link();proof=soak.base.read_json(soak.probes.PROBES/'build.json')['led']
        # First sequence runs; then a drift request arrives between sequences.
        with tempfile.TemporaryDirectory(dir=soak.ROOT/'tmp') as d:
            with patch.object(soak.base,'load_image',return_value=proof['sha256']),\
                 patch.object(soak,'drift_pending',side_effect=[False,True]),\
                 patch.object(soak.time,'sleep'):
                result=soak.led_show(link,Path(d),seed=17)
            self.assertFalse(soak.base.read_json(Path(d)/'led-state.json')['needs_restore'])
        self.assertTrue(result['original_led_restored'])
        self.assertTrue(result['yielded_early'])
        self.assertEqual(len(result['sequences']),1)
        self.assertEqual([a for a,b in link.writes],[0x5000,0x3200])
        self.assertEqual(link.sent,[b'G 4000\r']+[b'\r']*8)

    def test_led_readback_helper_only_writes_ram(self):
        from test_v2_rtc import MPU
        class Memory(list):
            def __init__(self):super().__init__([0]*65536);self.writes=[]
            def __setitem__(self,address,value):
                if isinstance(address,int):self.writes.append(address)
                super().__setitem__(address,value)
        m=Memory();m[0x5000:0x5000+len(soak.LED_READBACK)]=soak.LED_READBACK
        m[0x7FA0]=0xA5;m[0x7FA1]=0x34;m.writes.clear()
        cpu=MPU(memory=m,pc=0x5000)
        for _ in range(10):
            if cpu.pc==0x7E67:break
            cpu.step()
        else:self.fail('Readback helper failed to return')
        self.assertEqual(m[0x500F:0x5011],[0xA5,0x34])
        self.assertEqual(m.writes,[0x500F,0x5010])

    def test_clock_queries_are_read_only(self):
        link=ClockLink()
        with tempfile.TemporaryDirectory(dir=soak.ROOT/'tmp') as d:
            r=soak.clock(link,Path(d),dict(trim_steps=-12,control_register=128))
        self.assertEqual(r['trim'],-12)
        self.assertEqual(link.commands,['R CLOCK','STATUS','TIME','EUI','TRIM','OFFSET','BATTERY','HELP','Q'])

    def test_wrong_trim_stops_and_exits_clock(self):
        link=ClockLink('0B')
        with tempfile.TemporaryDirectory(dir=soak.ROOT/'tmp') as d:
            with self.assertRaisesRegex(AssertionError,'RTC settings changed'):
                soak.clock(link,Path(d),dict(trim_steps=-12,control_register=128))
        self.assertEqual(link.commands,['R CLOCK','STATUS','Q'])

    def test_restore_never_executes_original_ram(self):
        class Link:
            def __init__(self):self.commands=[];self.rows=[]
            def command(self,text,prompt):self.commands.append(text)
            def send(self,row):self.rows.append(row)
            def until(self,prompt):return b'\r\nB3> '
        link=Link()
        original=b'original RAM bytes'
        with tempfile.TemporaryDirectory(dir=soak.ROOT/'tmp') as d:
            path=Path(d)/'restore.s19'
            path.write_bytes(b'S113020000\nS9030200FA\n')
            with patch.object(soak,'ram',return_value=original),patch.object(soak.time,'sleep'):
                soak.restore(link,path,original)
        self.assertEqual(link.commands,['L'])
        self.assertEqual(len(link.rows),2)

if __name__=='__main__':unittest.main()
