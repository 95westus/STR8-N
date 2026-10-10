"""Build isolated beta23 compact local boot candidate; no board access."""
import build_v2_status as status
from build_v2_local_time import main as local_time

def main():
    status.SPI_STARTUP_ACK=True
    status.COMPACT_BOOT_LOCAL=True
    local_time(build='BUILD/v2-compact-boot',version='2.0b23',generation=32)

if __name__=='__main__':main()
