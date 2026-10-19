"""Offline orchestration checks using the exact CPU-model smoke transcripts."""
from pathlib import Path
import json,sys,tempfile,unittest
from unittest.mock import patch
ROOT=Path(__file__).resolve().parents[1];KIT=ROOT/'BUILD/rc1-debugger-boardtest-r1'
sys.path.insert(0,str(KIT))
import board_link as transport
import run_rc1_dbg_soak as soak

class Replay:
    def __init__(self,events,asm=False,bad_assembly=False,corrupt_cleanup=False):
        self.events=list(events);self.ram=bytearray(32768);self.entry=0x200;self.in_asm=False;self.asm=asm;self.bad_assembly=bad_assembly;self.corrupt_cleanup=corrupt_cleanup;self.finished=False;self.executions=0
    def command(self,text,prompt=b'\r\nB3> '):
        if text=='L':return b'S19'
        if self.asm:
            if text=='ASM' and not self.in_asm:self.in_asm=True;return b'STR8-N ASM 0.5\r\nASM> '
            if self.in_asm:
                if text=='ASM':self.ram[0x200:0x20C]=bytes.fromhex('78D8A2FF9A008000034C677E');return b'OK 12 bytes, origin $0200, buffer $0200\r\nASM> '
                if text=='QUIT':
                    self.in_asm=False
                    if self.bad_assembly:self.ram[0x200]^=1
                    return b'\r\nB3> '
                assert text in ('NEW','DUMP','S19') or text in soak.ASM_LINES,text
                return b'ASM> '
        assert self.events,'Extra command: '+text
        event=self.events.pop(0);assert event['command']==text,(event['command'],text)
        if text.startswith('G '):self.executions+=1
        if prompt==b'\r\nB3> ':self.finished=True
        return event['output'].encode()
    def send(self,data):
        row=data.decode().strip()
        if not row.startswith('S'):return
        raw=bytes.fromhex(row[2:]);address=int.from_bytes(raw[1:3],'big')
        if row.startswith('S1'):self.ram[address:address+len(raw[3:-1])]=raw[3:-1]
        elif row.startswith('S9'):self.entry=address
    def until(self,prompt):return f'Entry {self.entry:04X}\r\nB3> '.encode()
    def dump(self,first,last,prompt=b'\r\nB3> '):
        if first==0x7D0A and last==0x7D0B:return b'\xff\x64'
        data=bytes(self.ram[first:last+1])
        if self.corrupt_cleanup and self.finished and first==0x200 and len(data)>2:return bytes([data[0]^1])+data[1:]
        return data

def events(cpu,slot):
    suffix='-65c816-e' if cpu=='816' else ''
    rows=json.loads((ROOT/f'BUILD/rc1-debugger-v1e/debugger-transcripts{suffix}.json').read_text())
    return [x for x in rows if x.get('smoke') and x.get('slot')==slot]

class Checks(unittest.TestCase):
    def test_exact_smoke_replay_both_CPUs_slots(self):
        for cpu in ('02','816'):
            for slot in ('A','B'):
                with self.subTest(cpu=cpu,slot=slot),patch.object(transport.time,'sleep'):
                    link=Replay(events(cpu,slot));proof=soak.debugger_unit(link,transport,KIT)
                    self.assertTrue(proof['passed']);self.assertEqual(proof['breakpoint_hits'],16);self.assertFalse(link.events)
    def test_ASM_query_matches_tested_image_and_transcript(self):
        for cpu in ('02','816'):
            for slot in ('A','B'):
                query=[x for x in events(cpu,slot) if x['smoke'].startswith('BRK 80')]
                link=Replay(query,asm=True);proof,_=soak.asm_unit(link,transport,KIT)
                self.assertTrue(proof['passed']);self.assertEqual(proof['bytes'],12);self.assertFalse(link.events)
    def test_bad_ASM_output_refuses_before_execution(self):
        link=Replay([],asm=True,bad_assembly=True)
        with self.assertRaisesRegex(AssertionError,'execution refused'):soak.asm_unit(link,transport,KIT)
        self.assertEqual(link.executions,0)
    def test_leftover_patch_refuses(self):
        link=Replay(events('02','A'),corrupt_cleanup=True)
        with patch.object(transport.time,'sleep'),self.assertRaisesRegex(AssertionError,'Breakpoint patch remains'):soak.debugger_unit(link,transport,KIT)
    def test_deadline_and_STOP(self):
        with tempfile.TemporaryDirectory(dir=ROOT/'tmp') as folder:
            stop=Path(folder)/'STOP';self.assertFalse(soak.due(100,stop,99));self.assertTrue(soak.due(100,stop,100));stop.touch();self.assertTrue(soak.due(100,stop,99))
    def test_one_restoration_failure_still_attempts_other_board(self):
        called=[]
        def restore(board):
            called.append(board)
            if board=='2604':raise RuntimeError('simulated restoration failure')
            return dict(passed=True,RAM_restored_host_verified=True)
        proof=soak.restore_all(['2604','2609'],restore)
        self.assertEqual(called,['2604','2609']);self.assertFalse(proof['2604']['passed']);self.assertTrue(proof['2609']['passed'])

if __name__=='__main__':unittest.main(verbosity=2)
