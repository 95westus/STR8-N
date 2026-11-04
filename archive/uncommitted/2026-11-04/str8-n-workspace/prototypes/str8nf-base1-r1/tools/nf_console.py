"""STR8N-F serial console: function-key RAM transfers; no connection on startup."""
import argparse
from datetime import datetime,timezone
import json
from pathlib import Path
import queue
import threading
import time
from console_core import Session,ConsoleError,ram_image

ROOT=Path(__file__).resolve().parents[1]
VERSION='0.1.0'
KEYS=(('F1','Help'),('F2','Choose BIN'),('F3','Send at SEND BIN'),('F4','REC L + BIN'),
      ('F5','MAP'),('F6','CONFIG'),('F7','OPAQUE'),('F8','DEMO'),('F9','Log'),
      ('F10','Connect/disconnect'),('F11','Clear'),('F12','Ctrl-C'))
PRESETS={'F5':'MAP','F6':'CONFIG','F7':'OPAQUE','F8':'DEMO'}


def serial_port(name,baud):
    try:import serial
    except ImportError as error:raise ConsoleError('Install pyserial: python -m pip install -r requirements-console.txt') from error
    port=serial.Serial(port=None,baudrate=baud,timeout=0,write_timeout=1,
                       xonxoff=False,rtscts=False,dsrdtr=False)
    port.dtr=False;port.rts=False;port.port=name;port.open()
    return port


class Worker(threading.Thread):
    def __init__(self,events,*,factory=serial_port):
        super().__init__(daemon=True)
        self.events,self.factory=events,factory
        self.commands=queue.Queue();self.session=Session(lambda *e:events.put(e))
        self.stopping=False
    def run(self):
        try:
            while True:
                try:
                    for _ in range(32):
                        try:command,args=self.commands.get_nowait()
                        except queue.Empty:break
                        if self.stopping and command!='stop':continue
                        if command=='connect':
                            if self.session.port is not None:raise ConsoleError('Already connected')
                            self.session.attach(self.factory(*args))
                        elif command=='disconnect':self.session.disconnect()
                        elif command=='terminal':self.session.terminal(*args)
                        elif command=='start':self.session.start(*args[:3],from_recovery=args[3])
                        elif command=='cancel':self.session.cancel()
                        elif command=='stop':self.stopping=True;self.session.disconnect()
                    self.session.tick()
                except ConsoleError as error:self.events.put(('error',str(error)))
                except Exception as error:self.session.fail(error)
                if self.stopping and self.session.port is None:break
                time.sleep(.002)
        finally:
            if self.session.port is not None:self.session.port.close()


def make_app(root,*,kit=ROOT,port='',baud=115200,worker_factory=Worker):
    import tkinter as tk
    from tkinter import ttk,filedialog,messagebox
    class App:
        def __init__(self):
            self.root=root;self.kit=Path(kit);self.events=queue.Queue()
            self.worker=worker_factory(self.events);self.connected=False;self.busy=False
            self.log=None;self.closing=False;self.last_was_cr=False
            self.port=tk.StringVar(value=port);self.baud=tk.StringVar(value=str(baud))
            self.selected=tk.StringVar();self.status=tk.StringVar(value='Disconnected — choose a port, then F10')
            root.title(f'STR8N-F Serial Console {VERSION} — BASE1 / PR05')
            root.geometry('1060x720')
            row=ttk.Frame(root,padding=6);row.pack(fill='x')
            ttk.Label(row,text='Port').pack(side='left')
            self.port_box=ttk.Combobox(row,textvariable=self.port,width=15);self.port_box.pack(side='left',padx=4)
            ttk.Button(row,text='Refresh ports',command=self.refresh).pack(side='left')
            ttk.Label(row,text='Baud').pack(side='left',padx=(12,4))
            ttk.Combobox(row,textvariable=self.baud,values=(115200,19200,9600),width=10).pack(side='left')
            ttk.Button(row,text='F10 Connect / disconnect',command=self.toggle).pack(side='left',padx=8)
            ttk.Label(row,text='8N1 • DTR/RTS off • no auto-connect/reset').pack(side='left',padx=8)
            row=ttk.Frame(root,padding=6);row.pack(fill='x')
            ttk.Label(row,text='RAM BIN @0200').pack(side='left')
            ttk.Entry(row,textvariable=self.selected).pack(side='left',fill='x',expand=True,padx=6)
            ttk.Button(row,text='F2 Choose…',command=self.choose).pack(side='left')
            keys=ttk.Frame(root,padding=4);keys.pack(fill='x')
            for number,(key,label) in enumerate(KEYS):
                ttk.Button(keys,text=f'{key} {label}',command=lambda k=key:self.action(k)).grid(
                    row=number//6,column=number%6,sticky='ew',padx=2,pady=2)
                keys.columnconfigure(number%6,weight=1)
                root.bind('<'+key+'>',lambda event,k=key:self.action(k))
            frame=ttk.Frame(root);frame.pack(fill='both',expand=True,padx=6,pady=4)
            self.text=tk.Text(frame,wrap='none',font=('Consolas',11),state='disabled',undo=False)
            scroll=ttk.Scrollbar(frame,orient='vertical',command=self.text.yview)
            self.text.configure(yscrollcommand=scroll.set);scroll.pack(side='right',fill='y');self.text.pack(fill='both',expand=True)
            self.text.bind('<KeyPress>',self.key)
            self.text.bind('<<Paste>>',self.paste)
            self.progress=ttk.Progressbar(root,maximum=1);self.progress.pack(fill='x',padx=6)
            ttk.Label(root,textvariable=self.status,padding=6).pack(fill='x')
            self.worker.start();root.protocol('WM_DELETE_WINDOW',self.close)
            root.after(20,self.pump)
        def command(self,name,*args):
            if not self.closing or name=='stop':self.worker.commands.put((name,args))
        def refresh(self):
            try:
                from serial.tools.list_ports import comports
                self.port_box['values']=[p.device for p in comports()]
                self.status.set('Port list refreshed; no device opened')
            except ImportError:self.status.set('Install pyserial: python -m pip install -r requirements-console.txt')
        def choose(self):
            if self.busy:return
            chosen=filedialog.askopenfilename(parent=root,title='Choose a RAM BIN for entry 0200',
                    initialdir=str(self.kit/'firmware/payload'),filetypes=(('RAM binary','*.bin'),('All files','*')))
            if chosen:self.selected.set(chosen)
        def toggle(self):
            if self.connected:self.command('disconnect');return
            try:
                if not self.port.get().strip():raise ConsoleError('Choose a port first')
                baud_value=int(self.baud.get())
                if not 1<=baud_value<=4000000:raise ConsoleError('Invalid baud rate')
                self.command('connect',self.port.get().strip(),baud_value)
            except (ValueError,ConsoleError) as error:self.status.set(str(error))
        def send_file(self,*,recovery):
            try:
                if not self.connected:raise ConsoleError('Connect first (F10); no file was sent')
                if not self.selected.get():self.choose()
                if not self.selected.get():return
                path,body,digest=ram_image(self.selected.get(),self.kit)
                self.status.set(f'{path.name}: {len(body)} bytes; SHA-256 {digest}')
                self.command('start',path,body,digest,recovery)
                self.text.focus_set()
            except (OSError,ValueError) as error:self.status.set(str(error))
        def action(self,key):
            if key=='F1':messagebox.showinfo('STR8N-F console keys',
                '\n'.join(k+'  '+label for k,label in KEYS)+
                '\n\nF4/F5-F8 require an observed REC> and wait for SEND BIN.\n'
                'Raw L runs the RAM image after idle; it does not program a flash image.\n'
                'Ctrl-C cancels only before payload. Payload input is locked.\n'
                'Every key also has a button; laptops may need Fn.',parent=root)
            elif key=='F2':self.choose()
            elif key in ('F3','F4'):self.send_file(recovery=key=='F4')
            elif key in PRESETS:
                self.selected.set(str(self.kit/'firmware/payload'/f'STR8N-F-{PRESETS[key]}-RAM.bin'))
                self.send_file(recovery=True)
            elif key=='F9':self.toggle_log()
            elif key=='F10':self.toggle()
            elif key=='F11':self.text.configure(state='normal');self.text.delete('1.0','end');self.text.configure(state='disabled')
            elif key=='F12':self.command('cancel')
            return 'break'
        def key(self,event):
            if event.keysym in dict(KEYS):return self.action(event.keysym)
            if event.state&4 and event.state&1 and event.keysym.lower()=='c':
                try:
                    selected=self.text.get('sel.first','sel.last')
                    root.clipboard_clear();root.clipboard_append(selected)
                except tk.TclError:pass
                return 'break'
            if event.state&4 and event.keysym.lower()=='v':return self.paste()
            if event.state&4 and event.keysym.lower()=='c':self.command('cancel');return 'break'
            controls={'Return':b'\r','KP_Enter':b'\r','BackSpace':b'\x08','Delete':b'\x7f','Tab':b'\t','Escape':b'\x1b'}
            body=controls.get(event.keysym)
            if body is None and event.char:
                try:body=event.char.encode('ascii')
                except UnicodeEncodeError:self.status.set('Board console accepts ASCII input')
            if body:self.command('terminal',body)
            return 'break'
        def paste(self,event=None):
            try:
                value=root.clipboard_get().replace('\r\n','\n').replace('\r','\n').replace('\n','\r').encode('ascii')
                for n in range(0,len(value),16):self.command('terminal',value[n:n+16])
            except (tk.TclError,UnicodeEncodeError):self.status.set('Clipboard needs ASCII text')
            return 'break'
        def toggle_log(self):
            if self.log:self.log.close();self.log=None;self.status.set('Host logging stopped');return
            path=filedialog.asksaveasfilename(parent=root,title='Save private serial transcript',defaultextension='.jsonl',filetypes=(('Serial log','*.jsonl'),))
            if path:
                try:self.log=Path(path).open('x',encoding='utf-8',newline='\n');self.status.set('Host RX/TX logging enabled')
                except OSError as error:self.status.set('Log not opened: '+str(error))
        def display(self,body):
            self.text.configure(state='normal')
            for byte in body:
                if byte==13:self.text.insert('end','\n');self.last_was_cr=True
                elif byte==10:
                    if not self.last_was_cr:self.text.insert('end','\n')
                    self.last_was_cr=False
                elif byte in (8,127):
                    if self.text.compare('end-1c','>','1.0') and self.text.get('end-2c','end-1c')!='\n':self.text.delete('end-2c','end-1c')
                    self.last_was_cr=False
                elif byte==9 or 32<=byte<127:self.text.insert('end',chr(byte));self.last_was_cr=False
                elif byte!=0:self.text.insert('end',f'\\x{byte:02X}');self.last_was_cr=False
            if int(self.text.index('end-1c').split('.')[0])>12000:self.text.delete('1.0','2001.0')
            self.text.see('end');self.text.configure(state='disabled')
        def pump(self):
            for _ in range(200):
                try:event=self.events.get_nowait()
                except queue.Empty:break
                kind,*data=event
                if self.log and kind in ('rx','tx','transfer','status','error','connected'):
                    record=dict(time=datetime.now(timezone.utc).isoformat(),event=kind)
                    record.update(hex=data[0].hex() if kind in ('rx','tx') else None,result=data[0] if kind not in ('rx','tx') else None)
                    try:self.log.write(json.dumps(record)+'\n');self.log.flush()
                    except OSError as error:
                        try:self.log.close()
                        except OSError:pass
                        self.log=None;self.status.set('Host log stopped: '+str(error))
                if kind=='rx':self.display(data[0])
                elif kind=='connected':self.connected=data[0];self.status.set('Connected; press Enter if REC> was already waiting' if data[0] else 'Disconnected')
                elif kind in ('status','error'):self.status.set(data[0])
                elif kind=='progress':self.progress.configure(maximum=data[1],value=data[0]);self.busy=True
                elif kind=='busy':self.busy=data[0]
                elif kind=='transfer':self.busy=False
            if self.closing and not self.worker.is_alive():
                if self.log:
                    try:self.log.close()
                    except OSError:pass
                root.destroy();return
            root.after(20,self.pump)
        def close(self):
            if self.closing:return
            self.closing=True;self.status.set('Closing; an active BIN will finish before disconnect')
            self.command('stop')
    return App()


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--version',action='version',version='STR8N-F Serial Console '+VERSION)
    parser.add_argument('--port',default='',help='Preselect only; F10 opens the port')
    parser.add_argument('--baud',type=int,default=115200)
    parser.add_argument('--kit',type=Path,default=ROOT)
    args=parser.parse_args()
    try:
        import tkinter as tk
        root=tk.Tk();make_app(root,kit=args.kit,port=args.port,baud=args.baud);root.mainloop()
    except ImportError as error:parser.exit(2,'Console needs Python with Tk: '+str(error)+'\n')


if __name__=='__main__':main()
