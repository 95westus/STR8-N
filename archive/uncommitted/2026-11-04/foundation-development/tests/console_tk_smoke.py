"""Hidden Tk smoke with a fake worker. No serial port or CPU model is used."""
import queue
import sys
import tkinter as tk
import tempfile
from pathlib import Path
from types import SimpleNamespace

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/'tools'))
from nf_console import make_app


class FakeWorker:
    def __init__(self,events):self.commands=queue.Queue()
    def start(self):pass
    def is_alive(self):return False


def main():
    root=tk.Tk();root.withdraw()
    try:
        ports=[SimpleNamespace(device='COM4',serial_number='A10MQFLCA'),
               SimpleNamespace(device='COM8',serial_number='A10MPQXCA')]
        app=make_app(root,port='COM4',worker_factory=FakeWorker,port_lister=lambda:ports)
        root.update_idletasks()
        assert 'Board 2512 / 65C02' in app.identity.get() and 'COM4' in root.title()
        # Identity follows the adapter inventory, never a guessed COM mapping.
        ports[0].device='COM14';app.scan_ports()
        assert 'Board unknown' in app.identity.get() and 'device unavailable' in app.identity.get()
        app.port.set('com14');assert 'Board 2512 / 65C02' in app.identity.get()
        ports[0].serial_number='UNRECOGNIZED';app.scan_ports()
        assert 'Board unknown' in app.identity.get() and 'unrecognized USB' in app.identity.get()
        app.board.set('2609');ports.clear();app.scan_ports()
        assert 'Board 2609 / 65C816 emulation' in app.identity.get() and 'Manual' in app.identity.get()
        app.board.set('Bench spare');assert 'Board Bench spare' in root.title()
        app.board.set('');assert 'Board unknown' in root.title()
        ports.extend([SimpleNamespace(device='COM4',serial_number='A10MQFLCA'),
                      SimpleNamespace(device='COM8',serial_number='A10MPQXCA')])
        app.scan_ports();app.port.set('COM4')
        # Changing a selector must not relabel a different, still-open connection.
        app.connecting_port='COM4';app.events.put(('connected',True));app.pump()
        app.port.set('COM8');assert 'COM4' in root.title() and 'Board 2512' in root.title()
        app.events.put(('connected',False));app.pump()
        assert 'COM8' in root.title() and 'Board 2609' in root.title()
        assert app.worker.commands.empty(), 'Identity changes must never connect or probe'
        assert root.bind('<F5>') and root.bind('<F12>')
        assert root.bind('<Shift-F2>') and root.bind('<Shift-F3>')
        app.action('F5');assert app.worker.commands.empty()
        app.connected=True
        app.action('F5');name,args=app.worker.commands.get_nowait()
        assert name=='start' and Path(args[0]).name=='STR8N-F-MAP-RAM.bin' and args[3] is True
        app.selected.set(str(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin'));app.action('F3')
        assert app.worker.commands.empty() and 'flash component' in app.status.get()
        # The modified function keys have their own route and cannot send BINs.
        app.selected_s19.set(str(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin'))
        app.s19_action('send');assert app.worker.commands.empty() and '.s19' in app.status.get()
        with tempfile.TemporaryDirectory() as tmp:
            path=Path(tmp)/'example.s19';path.write_text('S10435004284\nS9033500C7\n')
            app.selected_s19.set(str(path))
            assert app.key(SimpleNamespace(keysym='F3',state=1,char=''))=='break'
            name,args=app.worker.commands.get_nowait()
            assert name=='s19' and args[1]==b'S10435004284\r\nS9033500C7\r\n'
            assert app.worker.commands.empty(), 'Shift+F3 must not also invoke BIN F3'
        print('PASS hidden Tk: auto/manual board identity, port changes, key routing, MAP preset and ROM refusal; no ports opened')
    finally:root.destroy()


if __name__=='__main__':main()
