"""Build isolated beta22 startup guard candidate; never accesses boards."""
import build_v2_status as status
from build_v2_local_time import main as local_time

def main():
    status.SPI_STARTUP_ACK=True
    local_time(build='BUILD/v2-spi-startup',version='2.0b22',generation=31)

if __name__=='__main__':main()
