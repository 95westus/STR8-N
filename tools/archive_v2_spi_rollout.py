"""Fresh repeated flash/EEPROM/SRAM archive before resident SPI installation."""
import argparse,concurrent.futures,json,os,subprocess,sys
from pathlib import Path
from serial.tools.list_ports import comports
from install_v2_rtc_upgrade import SERIALS
ROOT=Path(__file__).resolve().parents[1]

def main():
    p=argparse.ArgumentParser();p.add_argument('--root',required=True,type=Path);p.add_argument('--board',action='append',choices=tuple(SERIALS));a=p.parse_args()
    a.root.mkdir(parents=True,exist_ok=True);boards=a.board or list(SERIALS)
    ports={p.serial_number:p.device for p in comports()}
    print('PORTS',json.dumps(ports),flush=True)
    (a.root/'ports.json').write_text(json.dumps(ports,indent=2)+'\n')
    for b in boards:assert SERIALS[b] in ports,f'Board {b} not enumerated'
    def run_board(board):
        root=a.root/board;root.mkdir(exist_ok=True);port=ports[SERIALS[board]]
        def run(script,*args):
            result=subprocess.run([sys.executable,str(ROOT/'tools'/script),*map(str,args)],cwd=ROOT,capture_output=True,text=True)
            (root/(script+'.log')).write_text(result.stdout+result.stderr)
            print(('PASS ' if result.returncode==0 else 'FAIL ')+board+' '+script,flush=True)
            if result.returncode:print((result.stdout+result.stderr)[-2200:],flush=True);raise RuntimeError(script)
        run('backup_str8n_board.py','--port',port,'--board',board,'--out',root/'prior')
        run('archive_v2_binding_state.py','--root',root,'--board',board,'--port',port)
        run('inspect_v2_spi_via.py','--port',port,'--out',root/'via-prior')
        via=json.loads((root/'via-prior/report.json').read_text())
        if via['IFR']&0x18:
            # Explicit test setup only, after archived read-only state; helper
            # refuses enabled CB interrupts, active port mode or driven selects.
            run('inspect_v2_spi_via.py','--port',port,'--out',root/'via-setup','--ack-disabled')
        run('qualify_v2_spi_board.py','--root',root,'--board',board,'--port',port,'--stage','archive')
        return dict(board=board,port=port,passed=True,flash_written=False)
    with concurrent.futures.ThreadPoolExecutor(max_workers=len(boards)) as pool:
        results=list(pool.map(run_board,boards))
    (a.root/'archive-report.json').write_text(json.dumps(dict(passed=True,boards=results),indent=2)+'\n')
    print('PASS fresh source archives; no flash writes',flush=True)

if __name__=='__main__':main()
