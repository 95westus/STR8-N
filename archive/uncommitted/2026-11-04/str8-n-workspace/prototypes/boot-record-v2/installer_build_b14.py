"""Rebase the unchanged OIP1 installer logic for b14's raw $0200 entry."""
import installer_build as frozen
LOAD_ADDRESS=0x0200
STAGE_ADDRESS=frozen.STAGE_ADDRESS
SECTOR_BYTES=frozen.SECTOR_BYTES
HEADER_BYTES=frozen.HEADER_BYTES
HERE=frozen.HERE
source=frozen.Path(frozen.__file__).read_text()
source=source[source.index('def build_installer('):source.index('\ndef main():')]
source=source.replace("    a.emit('ram-installer-offline.rlp1', rlp1_header(body) + body)\n",'')
source=source.replace('<= 0x6000','<= 0x6500').replace('Installer exceeds RLP1 RAM window','Installer exceeds raw RAM window')
source=source.replace('Only escrowed tool span','Disposable loaded tool span')
exec(compile(source,str(frozen.Path(__file__)),'exec'),globals())
