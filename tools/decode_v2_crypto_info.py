"""Decode CRC-checked ATECC informational replies without accessing hardware."""
import json

def summarize(rows):
    byname={r['name']:r for r in rows}
    def data(name):
        row=byname[name]
        return bytes.fromhex(row['data']) if row['crc_valid'] and len(bytes.fromhex(row['response']))==7 else None
    cfgparts=[data(f'config_{i*4:03d}') for i in range(32)]
    summary={'revision':data('revision').hex() if data('revision') else None,
             'unavailable':{r['name']:r['data'] for r in rows if len(bytes.fromhex(r['response']))==4},
             'all_response_crcs_valid':all(r['crc_valid'] for r in rows)}
    if all(v is not None for v in cfgparts):
        cfg=b''.join(cfgparts)
        def lock(value): return {0x55:'unlocked',0:'locked'}.get(value,f'unknown 0x{value:02X}')
        summary.update(serial_number=(cfg[:4]+cfg[8:13]).hex().upper(),configuration_revision=cfg[4:8].hex(),
                       i2c_address_7bit=f'0x{cfg[16]>>1:02X}',configuration_lock=lock(cfg[87]),
                       data_otp_lock=lock(cfg[86]),slot_locked_bitmap=f'0x{int.from_bytes(cfg[88:90],"little"):04X}',
                       slot_config_raw=[cfg[20+2*i:22+2*i].hex() for i in range(16)],
                       key_config_raw=[cfg[96+2*i:98+2*i].hex() for i in range(16)])
    summary['counters']={str(i):int.from_bytes(data(f'counter_{i}'),'little') if data(f'counter_{i}') else None for i in range(2)}
    summary['state_raw']=data('state').hex() if data('state') else None
    summary['persistent_latch_raw']=data('persistent_latch').hex() if data('persistent_latch') else None
    return summary
if __name__=='__main__':
    import sys
    from pathlib import Path
    rows=json.loads(Path(sys.argv[1]).read_text())
    print(json.dumps(summarize(rows),indent=2))
