"""Hidden Tk smoke with a fake worker. No serial port or CPU model is used."""
import queue
import sys
import tkinter as tk
from pathlib import Path

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
        app=make_app(root,worker_factory=FakeWorker)
        root.update_idletasks()
        assert root.bind('<F5>') and root.bind('<F12>')
        app.action('F5');assert app.worker.commands.empty()
        app.connected=True
        app.action('F5');name,args=app.worker.commands.get_nowait()
        assert name=='start' and Path(args[0]).name=='STR8N-F-MAP-RAM.bin' and args[3] is True
        app.selected.set(str(ROOT/'firmware/payload/STR8N-F-BOOT-4096.bin'));app.action('F3')
        assert app.worker.commands.empty() and 'flash component' in app.status.get()
        print('PASS hidden Tk: widgets, key routing, MAP preset and ROM refusal; no ports opened')
    finally:root.destroy()


if __name__=='__main__':main()
