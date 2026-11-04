"""Host-only console state/protocol tests. No Tk, CPU model or physical port."""
import hashlib
import json
from pathlib import Path
import sys
import unittest

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from console_core import Session,ConsoleError,REC,SEND_BIN,RAM_LIMIT,ram_image
from nf_console import Worker,KEYS


class Clock:
    def __init__(self):self.now=0
    def __call__(self):return self.now
    def advance(self,n=.004):self.now+=n


class Port:
    def __init__(self):self.rx=bytearray();self.tx=bytearray();self.closed=False;self.short=False
    @property
    def in_waiting(self):return len(self.rx)
    def read(self,n):result=bytes(self.rx[:n]);del self.rx[:n];return result
    def write(self,body):
        if self.short:return 0
        self.tx.extend(body);return len(body)
    def close(self):self.closed=True


class ConsoleState(unittest.TestCase):
    def setUp(self):
        self.clock=Clock();self.events=[];self.port=Port()
        self.session=Session(lambda *e:self.events.append(e),clock=self.clock)
        self.session.attach(self.port)
        self.body=b'\x78\xd8'+bytes(range(256))*2
        self.digest=hashlib.sha256(self.body).hexdigest()
    def prompt(self,body):self.port.rx.extend(body);self.session.tick()
    def start(self,recovery=True):self.session.start('sample.bin',self.body,self.digest,from_recovery=recovery)
    def finish(self):
        while self.session.mode=='sending':self.clock.advance();self.session.tick()
        self.clock.advance(3.6);self.session.tick()
    def test_attach_never_sends_a_board_command(self):self.assertEqual(self.port.tx,b'')
    def test_wrong_or_absent_prompt_prevents_L_and_payload(self):
        for prompt in (b'B3> ',b'OPAQUE BASE1 / PR05 I Q> ',b'REC> old output\r\n'):
            self.prompt(prompt)
            with self.assertRaises(ConsoleError):self.start()
        self.assertEqual(self.port.tx,b'')
    def test_split_ready_marker_and_byte_exact_paced_transfer(self):
        self.prompt(REC);self.start();self.assertEqual(self.port.tx,b'L\r')
        self.prompt(b'SEND B');self.assertEqual(self.port.tx,b'L\r')
        self.prompt(b'IN\r\n');self.assertLessEqual(len(self.port.tx)-2,16)
        self.finish();self.assertEqual(self.port.tx,b'L\r'+self.body)
        result=[e[1] for e in self.events if e[0]=='transfer'][-1]
        self.assertTrue(result['host_complete']);self.assertFalse(result['board_readback_verified'])
    def test_manual_send_requires_SEND_BIN(self):
        self.prompt(REC)
        with self.assertRaises(ConsoleError):self.start(False)
        self.prompt(SEND_BIN);self.start(False);self.finish()
        self.assertEqual(self.port.tx,self.body)
    def test_cancel_before_ready_sends_only_initial_ctrl_c(self):
        self.prompt(REC);self.start();self.assertTrue(self.session.cancel())
        self.assertEqual(self.port.tx,b'L\r\x03');self.assertEqual(self.session.mode,'idle')
    def test_cancel_before_first_manual_payload_byte(self):
        self.prompt(SEND_BIN);self.start(False);self.session.cancel();self.session.tick()
        self.assertEqual(self.port.tx,b'\x03')
    def test_ctrl_c_after_first_byte_is_not_injected(self):
        self.prompt(SEND_BIN);self.start(False);self.session.tick()
        written=bytes(self.port.tx);self.assertTrue(written)
        self.assertFalse(self.session.cancel());self.finish()
        self.assertEqual(self.port.tx,self.body)
    def test_keyboard_and_second_transfer_cannot_interleave(self):
        self.prompt(SEND_BIN);self.start(False)
        with self.assertRaises(ConsoleError):self.session.terminal(b'C 0\r')
        with self.assertRaises(ConsoleError):self.start(False)
        self.finish();self.assertEqual(self.port.tx,self.body)
    def test_disconnect_waits_through_payload_and_idle_interval(self):
        self.prompt(SEND_BIN);self.start(False);self.session.tick()
        self.assertFalse(self.session.disconnect());self.assertFalse(self.port.closed)
        while self.session.mode=='sending':self.clock.advance();self.session.tick()
        self.assertFalse(self.port.closed)
        self.clock.advance(3.6);self.session.tick()
        self.assertTrue(self.port.closed);self.assertEqual(self.port.tx,self.body)
    def test_timeout_sends_no_payload_and_does_not_retry(self):
        self.prompt(REC);self.start();self.clock.advance(16);self.session.tick()
        self.assertEqual(self.port.tx,b'L\r');self.assertEqual(self.session.mode,'idle')
        self.assertTrue(any(e[0]=='error' and 'No SEND BIN' in e[1] for e in self.events))
    def test_slow_serial_output_drains_before_disconnect_interval(self):
        self.prompt(SEND_BIN);self.start(False);self.session.tick()
        self.session.disconnect();self.port.out_waiting=100
        while self.session.mode=='sending':self.clock.advance();self.session.tick()
        self.clock.advance(20);self.session.tick();self.assertFalse(self.port.closed)
        self.port.out_waiting=0
        self.clock.advance(3.6);self.session.tick();self.assertTrue(self.port.closed)
    def test_partial_write_failure_is_not_reported_as_verified(self):
        self.prompt(SEND_BIN);self.start(False);self.session.tick();self.port.short=True
        self.clock.advance()
        with self.assertRaises(IOError):self.session.tick()
        self.session.fail(IOError('USB disappeared'))
        self.assertTrue(self.port.closed)
        self.assertTrue(any(e[0]=='error' and 'incomplete raw BIN' in e[1] for e in self.events))
        self.assertFalse(any(e[0]=='transfer' for e in self.events))
    def test_terminal_paste_is_paced_and_invalidates_old_prompt(self):
        self.prompt(REC);self.session.terminal(b'A'*40)
        with self.assertRaises(ConsoleError):self.start()
        self.session.tick();self.assertEqual(len(self.port.tx),16)
        self.session.tick();self.assertEqual(len(self.port.tx),16)
        self.clock.advance();self.session.tick();self.assertEqual(len(self.port.tx),32)
        self.clock.advance();self.session.tick();self.assertEqual(len(self.port.tx),40)
    def test_bad_digest_or_initial_ctrl_c_never_sends_L(self):
        self.prompt(REC)
        for body,digest in ((self.body,'bad'),(b'\x03',hashlib.sha256(b'\x03').hexdigest())):
            with self.assertRaises(ConsoleError):self.session.start('bad.bin',body,digest,from_recovery=True)
        self.assertEqual(self.port.tx,b'')
    def test_worker_does_not_construct_serial_port_until_commanded(self):
        import queue
        calls=[];worker=Worker(queue.Queue(),factory=lambda *args:calls.append(args))
        self.assertFalse(calls);worker.commands.put(('stop',()));worker.start();worker.join(1)
        self.assertFalse(worker.is_alive());self.assertFalse(calls)
    def test_all_twelve_keys_have_local_actions(self):
        self.assertEqual([key for key,_ in KEYS],[f'F{n}' for n in range(1,13)])


class FileAdmission(unittest.TestCase):
    def test_bundled_RAM_tools_match_the_release_manifest(self):
        for name in ('MAP','CONFIG','OPAQUE','DEMO','READBACK'):
            path,body,digest=ram_image(ROOT/'firmware/payload'/f'STR8N-F-{name}-RAM.bin',ROOT)
            self.assertEqual(digest,hashlib.sha256(body).hexdigest())
    def test_programmer_F_BIN_is_not_sent_as_a_RAM_program(self):
        with self.assertRaisesRegex(ConsoleError,'flash component'):
            ram_image(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin',ROOT)
    def test_manifest_validation_precedes_any_serial_operation(self):
        from unittest.mock import patch
        with patch.object(Path,'read_bytes',return_value=b'\x78\xd8'):
            with self.assertRaisesRegex(ConsoleError,'does not match'):
                ram_image(ROOT/'firmware/payload/STR8N-F-MAP-RAM.bin',ROOT)


if __name__=='__main__':unittest.main()
