"""Assertions shared by the offline and explicit-port debugger smoke runners."""
import re


def check(step,text):
    text=text.decode('ascii') if isinstance(text,bytes) else text
    if step.get('error'):
        assert '?\r\n' in text,(step,text)
    else:
        assert '?\r\n' not in text and 'Protected' not in text,(step,text)
    for token in step.get('contains',[]):assert token in text,(step,text)
    if 'registers' in step:
        rows=re.findall(r'PC=([0-9A-F]{4}) A=([0-9A-F]{2}) X=([0-9A-F]{2}) Y=([0-9A-F]{2}) P=([0-9A-F]{2}) S=([0-9A-F]{2})',text)
        assert rows,('Missing saved registers',step,text)
        values=dict(zip(('PC','A','X','Y','P','S'),map(lambda v:int(v,16),rows[-1])))
        for name,value in step['registers'].items():assert values[name]==value,(step,values)
    if 'breakpoints' in step:
        addresses=[int(v,16) for v in re.findall(r'^([0-9A-F]{4})\r?$',text,re.M)]
        assert addresses==step['breakpoints'],(step,addresses)
