"""Prepare a bounded RAM/SPI trial from the accepted preserving RAM harness."""
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]
if (ROOT/'tools/trial_sram_work_positive.py').exists():
    raise SystemExit('One-time scaffold already exists. The trial driver has manual safety fixes; edit it directly, never regenerate over it.')
source=(ROOT/'tools/trial_sram_work_ram.py').read_text()
source=source.replace('Read-only SRAM/WORK RAM trial','Bounded temporary SRAM/WORK positive trial')
source=source.replace('meta_pending=False;edu=None','meta_pending=False;edu=None;spi_dirty=False')
source=source.replace("for a in range(0,0x800,64):","for a in range(0,0x20000,64):")
source=source.replace("def api(kind,request,expected,pointer=0x300):","def api(kind,request,expected,pointer=0x300,write=False):")
source=source.replace("target=0x2003 if kind=='SRAM' else 0x2006", "target=0x2003 if kind=='SRAM' else 0x2006\n        if write:s.modify(sy['SW_UNLOCKED'],b'\\x01')")
source=source.replace("check('fresh-2K-storage-metadata-captured-read-only')", "check('fresh-complete-131072-byte-SRAM-backup')")
start=source.index("            cmd('PREP');cmd('S'")
end=source.index('          except CollectionDue',start)
source=source[:start]+'''            cmd('PREP');cmd('Q',MONS);mon()
            positive_steps()
'''+source[end:]
point=source.index('    save()\n    try:\n')
source=source[:point]+'''    allowed=list(range(0,0xC00,64))+list(range(0x10000,0x10400,64))
    def raw(address,data=None):
        # Test writes are restricted to four backed-up KiB. Restoration only
        # publishes the exact original bytes, never synthesized replacements.
        assert address in allowed and address%64==0
        mon();desc=bytearray(16);desc[0]=2 if data is not None else 1
        desc[2:5]=address.to_bytes(3,'little');desc[5:7]=(0x500).to_bytes(2,'little');desc[7]=64
        if data is not None:
            assert len(data)==64;s.modify(0x500,data)
        s.modify(0x6650,desc);s.modify(sy['SW_UNLOCKED'],b'\\x01' if data is not None else b'\\0')
        target=sy['SW_TRANSFER'];ret=sy['SW_RETURN']
        code=bytes((0x20,target&255,target>>8,0x8D,0x40,3,0x4C,ret&255,ret>>8))
        s.modify(0x380,code);cmd('G 0380',MONS);mon()
        assert s.dump(0x340,0x340)==b'\\0'
        return s.dump(0x500,0x53F)
    def restore_spi():
        nonlocal spi_dirty
        if not spi_dirty:return
        for a in allowed:
            original=before[a:a+64];raw(a,original);assert raw(a)==original
        spi_dirty=False;r['all_test_blocks_restored']=True
        check('all-4096-temporary-SRAM-bytes-restored-and-read-back')
    def positive_steps():
        nonlocal spi_dirty
        # Qualify only the freshly captured existing SS1/64KiB layout.
        from program_format import inspect
        layout=inspect(before);assert layout['format']=='SS1' and layout['boundary']=='10000'
        assert len(layout['free_slots'])>=3
        pages=[int(p,16) for p in layout['free_pages']]
        assert len(pages)>=2 and all(8<=p<12 for p in pages[:2])
        assert b'PVFY' not in before[:0x240]
        spi_dirty=True;mark(SRAM_WORK_SPI_restore_pending=True);save()
        def mut(kind,request,expected=0):return api(kind,request,expected,write=True)
        def store(data):
            s.modify(0x1000,data)
            a=bytearray(req(1,'PVFY',source=(0x1000,0x1007)));mut('SRAM',bytes(a))
        one=bytes.fromhex('A9 31 20 6D 7E 4C 67 7E');two=bytes.fromhex('A9 32 20 6D 7E 4C 67 7E')
        store(one);store(two);s.modify(0x1000,b'\\xA5'*8)
        api('SRAM',req(2,'PVFY'),0);assert s.dump(0x1000,0x1007)==two
        mut('SRAM',req(5));mut('SRAM',req(4,'PVFY'));api('SRAM',req(2,'PVFY'),0x42)
        mut('SRAM',req(5));mut('SRAM',req(6,key='FORMAT!!'))
        check('positive-SRAM-save-latest-restore-reclaim-delete-and-format')
        restore_spi()
        # Restore the original SS1 records before testing its non-destructive
        # upgrade. The WORK payload fixture is confined to10000-103FF.
        spi_dirty=True;mark(SRAM_WORK_SPI_restore_pending=True);save()
        mut('WORK',req(7,key='UPGRADE!'));assert api('WORK',req(0),0)[22]==0
        a=bytearray(32);a[0]=1;a[2:4]=(0xCA01).to_bytes(2,'little');a[18:21]=(256).to_bytes(3,'little')
        handle=bytearray(mut('WORK',bytes(a)))
        cached=s.dump(0x6960+32*handle[4],0x697F+32*handle[4]);assert int.from_bytes(cached[12:15],'little')==0x10000
        pattern=bytes(range(64));s.modify(0x500,pattern)
        def io(op,buffer,offset=0,count=64,expected=0,change_owner=False):
            a=handle.copy();a[0]=op;a[12:15]=offset.to_bytes(3,'little');a[15]=count;a[16:18]=buffer.to_bytes(2,'little')
            if change_owner:a[2]^=1
            return mut('WORK',bytes(a),expected)
        io(4,0x500);s.modify(0x580,b'\\xA5'*64);io(3,0x580);assert s.dump(0x580,0x5BF)==pattern
        io(3,0x580,expected=0x4B,change_owner=True);io(3,0x580,offset=255,count=2,expected=0x44)
        io(3,0x300,expected=0x44)
        a=handle.copy();a[0]=2;mut('WORK',bytes(a));io(3,0x580,expected=0x4B)
        def resize(units,expected=0):
            a=bytearray(req(5,key='RESIZE!!'));a[21]=units;return mut('WORK',bytes(a),expected)
        resize(3);assert api('WORK',req(0),0)[21]==3
        a=bytearray(32);a[0]=1;a[2:4]=(0xCA02).to_bytes(2,'little');a[18:21]=(256).to_bytes(3,'little')
        conflict=bytearray(mut('WORK',bytes(a)));resize(4,0x4A)
        conflict[0]=2;mut('WORK',bytes(conflict));resize(4)
        # Exercise a surviving fallback header without a physical power cut.
        primary=raw(0);bad=bytearray(primary);bad[63]=0;raw(0,bytes(bad))
        assert api('WORK',req(0),0)[23]==1
        mut('WORK',req(8,key='REPAIR!!'));assert api('WORK',req(0),0)[23]==0
        mut('WORK',req(6,key='FORMAT!!'));mut('SRAM',req(6,key='FORMAT!!'),0x4A)
        check('positive-WORK-upgrade-claim-write-read-release-bounds-resize-conflict-repair-and-format')
'''+source[point:]
source=source.replace("                if meta_pending:\n", "                if spi_dirty:restore_spi()\n                if meta_pending:\n")
source=source.replace("check('complete-2K-storage-metadata-unchanged')", "check('entire-131072-byte-SRAM-exactly-restored')\n                        mark(SRAM_WORK_SPI_restore_pending=False)")
source=source.replace("len(r['checks'])==6", "len(r['checks'])==7")
source=source.replace("SRAM/WORK RAM read-only trial; port released", "SRAM/WORK temporary-write trial; port released")
source=source.replace("SRAM_data_writes=0,", "SRAM_data_writes='bounded temporary fixture; see checks',")
source=source.replace("WORKSPACE_writes=0,", "WORKSPACE_writes='10000-103FF temporary fixture',")
source=source.replace("board+'-SRAM-WORK-RAM-readonly'", "board+'-SRAM-WORK-RAM-temporary-writes'")
source=source.replace("last_SRAM_WORK_RAM_trial=", "last_SRAM_WORK_positive_trial=")
source=source.replace("sram_work_RAM_worker_active", "sram_work_positive_worker_active")
target=ROOT/'tools/trial_sram_work_positive.py';target.write_text(source)
print('Prepared bounded 4096-byte positive fixture with complete SRAM preimage and restoration; no port opened')
