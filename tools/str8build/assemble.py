"""WDC invocation and fresh, isolated compiler outputs."""
import re
import shutil
import subprocess

from .formats import read_s19, save, sha


class Assembly:
    def __init__(self, source, out, assembler, linker):
        self.out, self.assembler, self.linker = out, assembler, linker
        self.symbols, self.compiled = {}, []
        self.sources = {p.relative_to(source).as_posix(): sha(p.read_bytes())
                        for p in sorted(source.rglob('*')) if p.is_file()}
        out.mkdir(parents=True)
        shutil.copytree(source, out/'s')
        shutil.copytree(source/'source-store', out/'source')
        shutil.copytree(source/'debugger', out/'debugger')
        (out/'payload').mkdir()

    def link(self, module, name, address, end):
        if module == 'source-store':
            stage = self.out/'source'
        elif module == 'debugger':
            stage = self.out/'debugger'
        else:
            stage = self.out/'s'/module
        commands = [
            [self.assembler, '-G', '-L', '-S', '-W', '-I', str(stage), name+'.asm'],
            [self.linker, '-g', '-s', '-t', f'-c{address:04X}', '-hm19', '-j',
             '-o', name+'.s19', name+'.obj'],
        ]
        log = []
        for command in commands:
            result = subprocess.run(command, cwd=stage, capture_output=True, text=True)
            log.append(dict(command=command, returncode=result.returncode,
                            stdout=result.stdout, stderr=result.stderr))
            save(stage/(name+'.log.json'), log)
            if result.returncode:
                raise RuntimeError(f'WDC failed: {module}/{name}; see {stage/(name+".log.json")}')
        symbols = {n: int(v, 16) for v, n in re.findall(r'^\s*([0-9a-fA-F]{8}) (\w+)\s*$',
                                                       (stage/(name+'.map')).read_text(), re.M)}
        cells = read_s19(stage/(name+'.s19'))
        stop = symbols[end]
        if set(cells) != set(range(address, stop)):
            raise ValueError(f'Non-contiguous or out-of-range link: {module}/{name}')
        body = bytes(cells[a] for a in range(address, stop))
        if module not in ('source-store', 'debugger'):
            self.symbols[module+'/'+name] = symbols
        self.compiled.append(dict(module=module, name=name, start=address, end=stop,
                                  bytes=len(body), sha256=sha(body)))
        print(f'{module}/{name}: {len(body)} bytes', flush=True)
        return body, symbols

    def emit(self, name, data):
        path = self.out/'payload'/name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
