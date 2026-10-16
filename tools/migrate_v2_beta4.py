"""Published b4 layout conversion for the unified, backup-bound launcher."""
import json
from pathlib import Path
import beta4_migration as m

def record(body, name, entry):
    return b'SR\1\x3f'+entry.to_bytes(2,'little')+len(body).to_bytes(2,'little')+name.encode().ljust(16,b'\0')+body

def convert(banks, build, root):
    kit=root/'BUILD/v2-beta4/kit'; manifest=m.validate_kit(kit)
    assert banks[3][:8192]==m.maintenance_storage(kit), 'Unregistered b4 MAINT; preserve source'
    assert banks[3][0x6000:0x7000]==(kit/'str8n-v2-b4-e000-efff.bin').read_bytes(), 'Unregistered b4 E'
    old=json.loads((root/'BUILD/v2-beta4/build.json').read_text())
    new=json.loads((build/'build.json').read_text())
    assert m.sha((build/'clock/clock.bin').read_bytes())==new['clock_sha256']
    for folder,filename in (('store','sram.bin'),('workspace','workspace.bin'),('edu','edu.bin')):
        meta=json.loads((build/folder/'build.json').read_text())
        assert m.sha((build/folder/filename).read_bytes())==meta['sha256']
    for suffix,name in (('f000-ffff','f000-ffff'),('e000-efff','e000-efff'),('slot-a0','slot-a'),('slot-b0','slot-b')):
        assert (root/f'BUILD/v2-beta4/str8n-v2-recovery-{suffix}.bin').read_bytes()==(kit/f'str8n-v2-b4-{name}.bin').read_bytes()
    from build_v2_beta25 import references
    refs=references(root/'BUILD/v2-beta4/asm','monitor-a0.asm')
    for name in refs:
        if name in old['boot']:assert new['boot'][name]==old['boot'][name],('b4 reference moved',name)
    # Published b4 and beta23 have identical F; prove the retained private ABI too.
    for group in ('worker','vectors'):
        for name,value in old[group].items():
            assert new[group].get(name)==value, ('b4 ABI moved',group,name)
    for name in ('BOOT_SLOT_CHECK','BOOT_SR_ROUTE','J_ENTER','J_READ_CONFIG'):
        assert old['boot'][name]==new['boot'][name], ('b4 ABI moved',name)
    final=[bytearray(b) for b in banks]; regions=[]
    def add(bank,offset,data,name):
        regions.append((bank,offset,data,name))
    add(1,0,(build/new['maintenance_storage_file']).read_bytes(),'MAINT')
    add(1,0x3000,record((build/'clock/clock.bin').read_bytes(),'CLOCK',0x2000),'CLOCK')
    for offset,path,name,entry in ((0x2000,'store/sram.bin','SRAM',0x4000),(0x3000,'workspace/workspace.bin','WORK',0x5000),(0x4580,'edu/edu.bin','EDU',0x2000)):
        add(2,offset,record((build/path).read_bytes(),name,entry),name)
    add(2,0x4800,(build/'boot-status/asset.bin').read_bytes(),'status asset')
    add(2,0x6000,(build/'local-display/asset.bin').read_bytes(),'local asset')
    # Refuse records which cross into a reserved region even when the overlapping
    # payload happens to be FF. Never overwrite a user program based on its name.
    for bank in (0,1,2):
        image=banks[bank]; i=0
        while i+24<=len(image):
            h=image[i:i+24];n=int.from_bytes(h[6:8],'little');entry=int.from_bytes(h[4:6],'little')
            if h[:3]==b'SR\1' and h[3] in (63,255) and n and 0x200<=entry and entry+n<=0x6700 and i+24+n<=len(image):
                name=h[8:24].rstrip(b'\0').decode('ascii',errors='replace')
                overlaps=[r for r in regions if r[0]==bank and i<r[1]+len(r[2]) and r[1]<i+24+n]
                reserved=name in ('MAINT','CLOCK','SRAM','WORK','EDU')
                if overlaps or reserved:
                    assert any(r[0]==bank and r[1]==i and r[3]==name for r in regions), 'User SR record conflicts with b25 layout: '+name
                i+=24+n
            else:i+=1
    for bank,offset,data,name in regions:
        before=banks[bank][offset:offset+len(data)]
        allowed=[b'\xff'*len(data),data]
        if name=='MAINT':
            # Previously installed exact system copies are safe to replace;
            # modified or merely same-named programs still refuse.
            for directory in ('v2-beta25','v2-beta25-b23','v2-beta25-b24g34'):
                p=root/'BUILD'/directory
                meta=json.loads((p/'build.json').read_text())
                allowed.append((p/meta['maintenance_storage_file']).read_bytes())
        assert before in allowed, f'Occupied b25 destination B{bank}:{offset+0x8000:04X} ({name}); no writes permitted'
        final[bank][offset:offset+len(data)]=data
    for offset,name in ((0,'str8n-rtc-component-8000-8fff.bin'),(4096,'str8n-journal-9000-9fff.bin')):
        final[3][offset:offset+4096]=(build/name).read_bytes()
    # Descending sectors finish each complete multi-sector SR body before its
    # header sector, allowing the installer to publish its SR3F byte last.
    order=[(bank,sector) for bank in (1,2) for sector in range(15,7,-1)
           if final[bank][(sector-8)*4096:(sector-7)*4096]!=banks[bank][(sector-8)*4096:(sector-7)*4096]]
    commits={}
    for bank,offset,data,name in regions:
        if data[:4]==b'SR\1\x3f' and any(b==bank and offset<(s-7)*4096 and (s-8)*4096<offset+len(data) for b,s in order):
            commits.setdefault((bank,8+offset//4096),[]).append(0x8000+offset+3)
    return final,order,commits,dict(published_kit_sha256=m.sha((kit/'manifest.json').read_bytes()),
        published_version=manifest['version'],layout_conversion=True,user_records_preserved=True,
        identity_offset_defaults='unbound / UTC+00:00; b4 has no identity or offset journal')
