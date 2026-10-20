"""Offline known-context recovery checks; no board or serial connection."""
import argparse,sys,unittest
from pathlib import Path

ap=argparse.ArgumentParser();ap.add_argument('--run',type=Path,required=True);args,rest=ap.parse_known_args()
sys.path.insert(0,str(args.run.resolve()));import runner

class Link:
    def __init__(self,context):self.context=context;self.commands=[]
    def command(self,text,prompt=b'\r\nB3> '):
        self.commands.append((text,prompt))
        if text=='':return b'\r\n'+self.context
        assert text in ('Q','X','QUIT')
        self.context=b'B3> ';return b'\r\nB3> '

class Recovery(unittest.TestCase):
    def exercise(self,context):
        obj=runner.Runner.__new__(runner.Runner);link=Link(context);events=[]
        obj.drain=lambda l:events.append('drain')
        def establish(l):
            self.assertTrue(l.context in (b'B0> ',b'B1> ',b'B2> ',b'B3> '));events.append('B3');l.context=b'B3> '
        obj.establish=establish
        obj.recover_idle(link)
        self.assertEqual(events,['drain','B3']);self.assertEqual(link.context,b'B3> ')
        return link
    def test_known_utilities(self):
        for context in ('BM','SRAM','WORK','EDU','CLOCK'):
            with self.subTest(context=context):self.assertEqual(self.exercise((context+'> ').encode()).commands[-1][0],'Q')
    def test_debugger_abort(self):self.assertEqual(self.exercise(b'DBG> ').commands[-1][0],'X')
    def test_assembler_exit(self):self.assertEqual(self.exercise(b'ASM> ').commands[-1][0],'QUIT')
    def test_idle_bank_requires_no_exit_or_reset(self):
        for bank in range(4):
            with self.subTest(bank=bank):self.assertEqual(len(self.exercise(f'B{bank}> '.encode()).commands),1)
    def test_unknown_native_or_spoofed_prompts_refuse(self):
        for prompt in (b'UNKNOWN> ',b'NATIVE> ',b'notBM> ',b'notDBG> ',b'B4> ',b'BM> extra> '):
            with self.subTest(prompt=prompt):
                obj=runner.Runner.__new__(runner.Runner);link=Link(prompt)
                obj.drain=lambda l:None;obj.establish=lambda l:self.fail('Must not establish an unknown context')
                with self.assertRaisesRegex(RuntimeError,'Unknown context'):obj.recover_idle(link)
                self.assertEqual(len(link.commands),1)
    def test_transport_failure_does_not_issue_blind_exit(self):
        obj=runner.Runner.__new__(runner.Runner);link=Link(b'BM> ');obj.drain=lambda l:None
        obj.establish=lambda l:self.fail('Must not establish after failed prompt read')
        def fail(*a):raise TimeoutError('simulated missing prompt')
        link.command=fail
        with self.assertRaises(TimeoutError):obj.recover_idle(link)

if __name__=='__main__':unittest.main(argv=[sys.argv[0]]+rest,verbosity=2)
