"""Regression checks for RTC estimation and the guarded CLOCK write protocol."""
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import rtc
from rtc_timing import calculate, decode_rtc, samples

FIXTURE = Path(__file__).resolve().parents[1]/'firmware/rtc-sample/sample.csv'


class TimingTests(unittest.TestCase):
    def test_sample_recommendation(self):
        fit=calculate(samples(FIXTURE))
        self.assertAlmostEqual(fit['drift_ppm'],12.2,places=3)
        self.assertEqual(fit['proposed_trim'],-12)

    def test_slow_clock_recommends_positive_trim(self):
        rows=samples(FIXTURE)
        for row in rows:
            lo,hi=float(row['offset_low_s']),float(row['offset_high_s'])
            row.update(offset_low_s=str(-hi),offset_high_s=str(-lo))
        fit=calculate(rows)
        self.assertAlmostEqual(fit['drift_ppm'],-12.2,places=3)
        self.assertEqual(fit['proposed_trim'],12)

    def test_offset_jump_refuses_trim(self):
        rows=samples(FIXTURE)
        rows[1]['offset_low_s']='4.1'
        rows[1]['offset_high_s']='4.11'
        with self.assertRaisesRegex(ValueError,'No constant drift'):
            calculate(rows)

    def test_uncertainty_prevents_rounding(self):
        rows=samples(FIXTURE)
        for row in rows:
            row['offset_low_s']=str(float(row['offset_low_s'])-.1)
            row['offset_high_s']=str(float(row['offset_high_s'])+.1)
        self.assertIsNone(calculate(rows)['proposed_trim'])

    def test_pf_and_bad_bcd_refused(self):
        raw=bytearray(bytes.fromhex('80 00 00 29 01 11 26 80 00')+bytes(8))
        decode_rtc(raw)
        raw[3]|=0x10
        with self.assertRaises(ValueError):
            decode_rtc(raw)
        raw[3]&=~0x10
        raw[0]=0xFA
        with self.assertRaises(ValueError):
            decode_rtc(raw)


class WriteProtocolTests(unittest.TestCase):
    before=dict(device='example',server='test',control_hex='80',trim_hex='00')
    fit=dict(device='example',reference='test',current_trim=0,proposed_trim=-12)

    def make_board(self):
        board=Mock()
        board.context=rtc.CLOCK
        def command(line,*args):
            if line.startswith('TRIM '):
                board.context=rtc.CONFIRM
                return b'Requested trim: -12 steps; coarse OFF.\r\n'+rtc.CONFIRM
            if line.startswith('SET '):
                board.context=rtc.CONFIRM
                return b'Requested UTC: '+line[4:].encode()+b'\r\nSET changes UTC\r\n'+rtc.CONFIRM
            if line=='YES':
                board.context=rtc.CLOCK
                return b'RTCC: Trim -12 steps; coarse OFF; OSCTRIM $0C'
            if line=='Q':
                board.context=rtc.MON
                return rtc.MON
            raise AssertionError(line)
        def send(data,*args,**kwargs):
            if data==b'YES':
                board.context=b'YES'
                return b'YES'
            if data==b'\r':
                board.context=rtc.CLOCK
                return b'SET completed. Checking time:'
            raise AssertionError(data)
        board.cmd.side_effect=command
        board.send.side_effect=send
        return board

    @patch('builtins.input',return_value='NO')
    def test_decline_changes_no_state(self,_):
        board=self.make_board()
        with self.assertRaisesRegex(ValueError,'cancelled'):
            rtc.apply(board,SimpleNamespace(mode='trim'),Mock(),self.before,self.fit)
        self.assertEqual(board.mock_calls,[])

    @patch('builtins.input',return_value='YES')
    @patch('rtc.status')
    @patch('rtc.start_segment',return_value='next')
    def test_confirmed_trim_uses_clock_and_reads_back(self,_segment,status,_):
        board=self.make_board()
        result=rtc.apply(board,SimpleNamespace(mode='trim'),Mock(),self.before,self.fit)
        self.assertEqual(result['trim_hex'],'0c')
        self.assertEqual(status.call_args_list[-1].args,(board,result))
        board.cmd.assert_any_call('YES',(rtc.CLOCK,rtc.OFFSET))
        board.send.assert_not_called()

    @patch('builtins.input',return_value='YES')
    @patch('rtc.status')
    @patch('rtc.time.sleep')
    @patch('rtc.start_segment',return_value='next')
    def test_sync_stages_yes_before_trigger(self,_segment,_,status,_input):
        board=self.make_board()
        ref=Mock()
        ref.now.side_effect=iter(range(1_700_000_000,1_700_000_030))
        result=rtc.apply(board,SimpleNamespace(mode='sync'),ref,self.before,None)
        self.assertEqual([call.args[0] for call in board.send.call_args_list],[b'YES',b'\r'])
        self.assertEqual(status.call_args_list[-1].args,(board,result))

    @patch('builtins.input',return_value='YES')
    @patch('rtc.status')
    def test_late_sync_leaves_confirmation_for_cancellation(self,_status,_input):
        board=self.make_board()
        ref=Mock()
        ref.now.side_effect=[1_700_000_000,1_700_000_010]
        with self.assertRaisesRegex(ValueError,'Missed UTC boundary'):
            rtc.apply(board,SimpleNamespace(mode='sync'),ref,self.before,None)
        self.assertEqual(board.context,rtc.CONFIRM)
        self.assertEqual([call.args[0] for call in board.send.call_args_list],[b'YES'])


if __name__=='__main__':
    unittest.main()

