"""Replayable, bounded eight-frame LED sequences; no board or storage access."""
import random


def playlist(seed):
    rng = random.Random(seed)
    rotate = lambda value,n: ((value << n)|(value >> (8-n)))&255
    start = rng.randrange(256)
    named = {
        'wig-wag': [0xAA,0x55]*4,
        'scanner': [1<<i for i in range(8)],
        'reverse-scanner': [1<<i for i in reversed(range(8))],
        'bounce': [1,2,4,8,16,8,4,2],
        'mirrored-pairs': [0x81,0x42,0x24,0x18]*2,
        'zipper': [0x11,0x22,0x44,0x88]*2,
        'ripple': [0x18,0x24,0x42,0x81,0x42,0x24,0x18,0],
        'double-chase': [rotate(3,i) for i in range(8)],
        'gray-code': [((start+i)&255)^(((start+i)&255)>>1) for i in range(8)],
    }
    chosen = rng.sample(list(named),2)
    shows = [(name,named[name]) for name in chosen]
    sparkle = [sum(1<<bit for bit in rng.sample(range(8),rng.randint(1,3))) for _ in range(8)]
    shows.insert(rng.randrange(3),('random-sparkle',sparkle))
    return [{'name':name,'frames_hex':bytes(frames).hex(),'hold_ms':rng.choice([120,160,200,240])}
            for name,frames in shows]
