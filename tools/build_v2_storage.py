"""Build isolated beta17 storage executive; no ports or hardware writes."""
import json,subprocess,sys
import build_v2_status as status
def main():
    root=status.ROOT;status.OUT=root/'BUILD/v2-storage'
    def build(script,*args):subprocess.run([sys.executable,str(root/'tools'/script),*args],cwd=root,check=True)
    build('build_v2_sram_store.py','--build','BUILD/v2-storage','--streams')
    status.VERSION='2.0b17';status.GENERATION=26;status.STORAGE=True;status.main()
    build('build_v2_workspace.py','--build','BUILD/v2-storage','--base','0x5000')
    build('build_v2_workspace_example.py','--build','BUILD/v2-storage')
    build('build_v2_spi_hardware_client.py','--build','BUILD/v2-storage')
    build('build_v2_storage_maint.py')
    build('build_v2_edu_utility.py','--build','BUILD/v2-storage')
if __name__=='__main__':main()
