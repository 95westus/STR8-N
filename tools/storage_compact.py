"""Optimal token selection for the existing, unchanged compact-decode format."""
from build_bank_features import expand


def compact(data):
    # Cost includes each flag byte. The eight states count tokens in its group.
    # Retain the closest match of each achievable length in the4K window.
    n=len(data); matches=[None]*n; seen={}
    for p in range(n):
        key=data[p:p+3]; best=2; options=[]
        for old in reversed(seen.get(key,())):
            if p-old>4096: break
            length=0
            while length<18 and p+length<n and data[old+length]==data[p+length]:
                length+=1
            if length>best:
                options.extend((k,p-old) for k in range(best+1,length+1))
                best=length
            if best==18: break
        matches[p]=options
        seen.setdefault(key,[]).append(p)
    costs=[[0]*8 for _ in range(n+1)]; choices=[None]*n
    for p in range(n-1,-1,-1):
        choices[p]=[]
        for phase in range(8):
            nxt=(phase+1)%8; overhead=int(phase==0)
            best=(1+costs[p+1][nxt],-1,0)
            for length,distance in matches[p]:
                option=(2+costs[p+length][nxt],-length,distance)
                if option<best: best=option
            costs[p][phase]=best[0]+overhead
            choices[p].append((-best[1],best[2]))
    out=bytearray();p=0
    while p<n:
        flags_at=len(out);out.append(0)
        for phase in range(8):
            if p==n: break
            length,distance=choices[p][phase]
            if length==1:
                out[flags_at]|=1<<phase;out.append(data[p])
            else:
                out.extend(((distance-1)&255,((distance-1)>>8)<<4|(length-3)))
            p+=length
    assert len(out)==costs[0][0]
    assert expand(out,n)==data
    return bytes(out)
