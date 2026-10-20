"""RAM-only registration cases shared by the offline rehearsal and board checks."""
PREFIX=bytes.fromhex('78 D8 A2 FF 9A')
HOLD=bytes.fromhex('4C 67 7E')

def cases():
    result=[]
    def make(name,code,requests=(),handler=b'\x60',stops=(),bank=3):
        code=PREFIX+(bytes.fromhex('AD 08 A0 85 00 AD 09 A0 85 01') if bank==1 else b'')+code+HOLD
        cells=dict(enumerate(code,0x200));cells.update(dict(enumerate(bytes.fromhex('6C 00 00'),0x340)))
        for address,request in requests:cells.update(dict(enumerate(bytes(request),address)))
        cells.update(dict(enumerate(handler,0x500)))
        image=bytes(cells.get(a,0) for a in range(0x200,max(cells)+1))
        result.append(dict(name=name,image_hex=image.hex(),entry=0x200,bank=bank,stops=list(stops),code_bytes=len(code),handler_hex=handler.hex()))
    def user(pointer=0x400):return bytes([0xA9,pointer&255,0xA2,pointer>>8,0,0x81])
    def system(pointer=0x400):return bytes([0xA9,pointer&255,0xA2,pointer>>8,0x20,0x40,3])
    def stop(a,ids=(),carry=None,callback=None):return dict(A=a,ids=list(ids),carry=carry,callback=callback)
    handler=bytes.fromhex('8D 80 04 8E 81 04 8C 82 04 A9 42 8D 02 70 60')
    make('user callback arguments, saved A result, unregister, missing-ID refusal',user()+bytes.fromhex('00 C1 00 01 A9 C1 00 82 00 02 A9 C1 00 82 00 03'),[(0x400,[0xC1,0,5,0])],handler,[stop(0x42,[0xC1],callback=[0,0x70,0xC1]),stop(0,carry=True),stop(1,carry=False)])
    handler=bytes.fromhex('8D 80 04 8E 81 04 8C 82 04 A9 66 8D 02 70 60')
    make('system callback arguments, saved A result and HOLD cleanup',system()+bytes.fromhex('00 A1 00 01'),[(0x400,[0xA1,0,5,0])],handler,[stop(0x66,[0xA1],callback=[0,0x70,0xA1])],1)
    requests=[(0x400+4*i,[0xC0+i,0,5,0]) for i in range(17)]
    make('16 user slots, seventeenth refusal, unregister frees capacity',b''.join(user(a) for a,_ in requests)+bytes.fromhex('00 01 A9 C3 00 82 00 02')+user(0x440)+bytes.fromhex('00 03'),requests,stops=[stop(1,range(0xC0,0xD0),False),stop(0,[x for x in range(0xC0,0xD0) if x!=0xC3],True),stop(0,[x for x in range(0xC0,0xD0) if x!=0xC3]+[0xD0],True)])
    requests=[(0x400+4*i,[0xA0+i,0,5,0]) for i in range(5)]+[(0x420,[0xC1,0,5,0])]
    make('four system slots, fifth refusal and independent user capacity',b''.join(system(a) for a,_ in requests[:5])+bytes.fromhex('00 01')+user(0x420)+bytes.fromhex('00 02'),requests,stops=[stop(1,range(0xA0,0xA4),False),stop(0,list(range(0xA0,0xA4))+[0xC1],True)],bank=1)
    for name,pointer,request in [('fixed ID',0x400,[0x80,0,5,0]),('system ID',0x400,[0xA1,0,5,0]),('FF ID',0x400,[0xFF,0,5,0]),('flags',0x400,[0xC1,0,5,1]),('ROM handler',0x400,[0xC1,0,0x90,0]),('low handler',0x400,[0xC1,0,1,0]),('low request',0x1FF,[0xC1,0,5,0]),('request crosses RAM end',0x64FE,[0xC1,0,5,0])]:
        make('user rejects '+name,user(pointer)+bytes.fromhex('00 01'),[(0x400,request)],stops=[stop(1,carry=False)])
    make('user duplicate refusal',user()+user()+bytes.fromhex('00 01'),[(0x400,[0xC1,0,5,0])],stops=[stop(1,[0xC1],False)])
    for name,request in [('user ID',[0xC1,0,5,0]),('flags',[0xA1,0,5,1]),('ROM handler',[0xA1,0,0x90,0])]:
        make('system rejects '+name,system()+bytes.fromhex('00 01'),[(0x400,request)],stops=[stop(1,carry=False)],bank=1)
    make('system duplicate refusal',system()+system()+bytes.fromhex('00 01'),[(0x400,[0xA1,0,5,0])],stops=[stop(1,[0xA1],False)],bank=1)
    make('nested BRK refuses with A=9 while preserving outer context',user()+bytes.fromhex('00 C1 00 01'),[(0x400,[0xC1,0,5,0])],bytes.fromhex('00 83 8D 02 70 60'),[stop(9,[0xC1])])
    return result

def exercise(link,case):
    """Link exposes command/dump; caller loads the exact verified image first."""
    outputs=[]
    for index,expected in enumerate(case['stops']):
        text=link.command('G 0200' if index==0 else 'C',b'DBG> ');outputs.append(text.decode('ascii'))
        raw=link.dump(0x7000,0x7006)
        assert raw[2]==expected['A'],(case['name'],index,raw.hex())
        if expected['carry'] is not None:assert bool(raw[5]&1)==expected['carry'],(case['name'],raw.hex())
        table=link.dump(0x7C30,0x7C7F);ids=[table[i] for i in range(0,80,4) if table[i]]
        assert sorted(ids)==sorted(expected['ids']),(case['name'],ids,expected['ids'])
        listing=link.command('F',b'DBG> ');outputs.append(listing.decode('ascii'))
        for ident in ids:assert f'{ident:02X} 0500'.encode() in listing,(case['name'],listing)
        if expected['callback'] is not None:assert link.dump(0x480,0x482)==bytes(expected['callback'])
    outputs.append(link.command('C').decode('ascii'))
    assert link.dump(0x7BFC,0x7BFF)==bytes(4),'HOLD registry/lifecycle cleanup failed'
    image=bytes.fromhex(case['image_hex'])
    assert link.dump(0x200,0x200+case['code_bytes']-1)==image[:case['code_bytes']],'Application code changed'
    assert link.dump(0x500,0x500+len(bytes.fromhex(case['handler_hex']))-1)==bytes.fromhex(case['handler_hex']),'Handler code changed'
    return dict(passed=True,name=case['name'],stops=len(case['stops']),outputs=outputs,HOLD_clears_all_registrations=True,program_and_handler_unchanged=True)
