"""Offline compression sizing experiment; no firmware or board changes."""
from collections import Counter
import json
import re
import zlib

from measure_v2_messages import ROOT, BUILD


def pair_encode(strings, limit, max_depth):
    encoded = list(strings)
    dictionary = []
    depth = {i: 0 for i in range(128)}
    for token in range(128, 128+limit):
        counts = Counter()
        for text in encoded:
            pairs = set(zip(text, text[1:]))
            for pair in pairs:
                if max(depth[pair[0]], depth[pair[1]]) < max_depth:
                    counts[pair] += text.count(bytes(pair))
        if not counts:
            break
        pair = min(counts, key=lambda p: (-counts[p], p))
        if counts[pair] <= 2:  # New dictionary entry itself costs two bytes.
            break
        dictionary.append(pair)
        depth[token] = 1+max(depth[pair[0]], depth[pair[1]])
        encoded = [text.replace(bytes(pair), bytes([token])) for text in encoded]

    def decode(token):
        if token < 128:
            return bytes([token])
        a, b = dictionary[token-128]
        return decode(a)+decode(b)

    assert all(b''.join(decode(t) for t in compressed) == original
               for original, compressed in zip(strings, encoded))
    size = sum(map(len, encoded))+2*len(dictionary)
    return dict(payload_bytes=sum(map(len, encoded)), dictionary_bytes=2*len(dictionary),
                total_text_bytes=size, tokens=len(dictionary), max_expansion_depth=max(depth.values()),
                roundtrip_verified=True)


def main():
    audit = json.loads((ROOT/'BUILD/message-catalog-audit.json').read_text())
    grouped = {}
    for row in audit['declarations']:
        if row['category'] == 'display':
            key = row['component'], row['label']
            grouped[key] = grouped.get(key, b'')+row['text'].encode('latin1')
    strings = list(grouped.values())
    pool = bytes(int(x, 16) for x in re.findall(r'\$([0-9A-F]{2})', (BUILD/'asm/text-image.inc').read_text()))
    message = bytearray()
    for byte in pool:
        message.append(byte & 127)
        if byte & 128:
            strings.append(bytes(message))
            message.clear()
    assert not message
    strings.append(audit['extension_help_text'].encode('ascii'))
    assert len(strings) == audit['display_inventory_entries']
    assert sum(map(len, strings)) == audit['display_inventory_bytes_single_copy']
    assert all(all(b < 128 for b in text) for text in strings)
    unique = list(dict.fromkeys(strings))
    overhead = 128+8*len(strings)
    methods = {}
    for count in (64, 128):
        for depth in (4, 8):
            result = pair_encode(unique, count, depth)
            result['catalog_bytes_including_index_and_headers'] = result['total_text_bytes']+overhead
            methods[f'pair_dictionary_{count}_depth_{depth}'] = result
    stream = b''.join(unique)
    compressor = zlib.compressobj(level=9, wbits=-15)
    compressed = compressor.compress(stream)+compressor.flush()
    assert zlib.decompress(compressed, wbits=-15) == stream
    report = dict(raw_text_bytes=sum(map(len, strings)), message_count=len(strings),
                  deduplicated_text_bytes=len(stream), unique_messages=len(unique),
                  index_and_headers_bytes=overhead,
                  raw_catalog_bytes=sum(map(len, strings))+overhead,
                  deduplicated_catalog_bytes=len(stream)+overhead,
                  methods=methods,
                  whole_stream_deflate_comparison_bytes=len(compressed),
                  deflate_limitation='Whole-stream comparison only: no random-access index, decoder or chunk overhead included.',
                  limitations=['Pair dictionary is global; changes rebuild and commit an entire catalog copy.',
                               'Pair dictionary results retain all original terminators and control bytes.',
                               'Decoder, lookup/call changes and retained fallback text have not been assembled.'])
    (ROOT/'BUILD/message-compression-audit.json').write_text(json.dumps(report, indent=2)+'\n')
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()
