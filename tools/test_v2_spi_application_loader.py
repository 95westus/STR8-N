"""Qualify the application S19 loader without opening board ports."""
import tempfile,unittest
from pathlib import Path
from beta4_migration import read_s19,s19,s_record
from qualify_v2_spi_install import read_application_s19,load_image,sha

class ApplicationLoaderTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory()
        self.path=Path(self.temp.name)/'application.s19'
    def tearDown(self):self.temp.cleanup()
    def parse(self,data):
        self.path.write_bytes(data)
        return read_application_s19(self.path)
    def rows(self,*rows):return ('\n'.join(rows)+'\n').encode('ascii')
    def rejected(self,data):
        with self.assertRaises(ValueError):self.parse(data)
    def test_application_addresses_and_installer_limit(self):
        for start,body in ((0x2000,b'\x60'),(0x4000,bytes(range(256))*19),(0x64FF,b'\x60')):
            cells=dict(enumerate(body,start));data=s19(cells,start)
            self.assertEqual(self.parse(data),(cells,start))
            if start>=0x4000:
                with self.assertRaisesRegex(ValueError,'installer outside approved range'):read_s19(self.path)
    def test_dense_whole_allowed_range(self):
        cells=dict(enumerate(bytes([0xEA])*0x4500,0x2000))
        self.assertEqual(self.parse(s19(cells,0x4000)),(cells,0x4000))
    def test_bad_records(self):
        valid=[s_record('0',0,b'app'),s_record('1',0x4000,b'\x60'),s_record('9',0x4000)]
        self.rejected(self.rows(valid[0],valid[1][:-2]+'00',valid[2]))
        self.rejected(self.rows(valid[0],valid[1][:2]+'05'+valid[1][4:],valid[2]))
        self.rejected(self.rows(valid[0],valid[1]+'0',valid[2]))
        self.rejected(self.rows(valid[0],'S2034000605C',valid[2]))
        self.rejected(self.rows(valid[0],'S1044000GG00',valid[2]))
        self.rejected(self.rows(valid[0],valid[1],s_record('9',0x4000,b'\0')))
        self.rejected(self.rows(valid[0],valid[1],valid[2],valid[2]))
        self.rejected(self.rows(valid[0],valid[1],valid[2],s_record('1',0x4001,b'\x60')))
        self.rejected(self.rows(valid[0],'S000FF',valid[2]))
    def test_missing_duplicate_sparse_and_bounds(self):
        self.rejected(self.rows(s_record('0',0,b'app'),s_record('9',0x4000)))
        self.rejected(self.rows(s_record('1',0x4000,b'\x60')))
        self.rejected(self.rows(s_record('1',0x4000,b'\x60'),s_record('1',0x4000,b'\x60'),s_record('9',0x4000)))
        self.rejected(self.rows(s_record('1',0x4000,b'\x60'),s_record('1',0x4002,b'\x60'),s_record('9',0x4000)))
        for start,entry,body in ((0x1FFF,0x1FFF,b'\x60'),(0x64FF,0x64FF,b'\x60\x60'),
                                 (0x4000,0x3FFF,b'\x60'),(0x4000,0x4001,b'\x60'),(0xFFFF,0xFFFF,b'\x60\x60')):
            self.rejected(s19(dict(enumerate(body,start)),entry))
    def test_real_images(self):
        root=Path(__file__).resolve().parents[1]/'BUILD/v2-spi-resident'
        for srec,binary in (('store/sram.s19','store/sram.bin'),('workspace/workspace.s19','workspace/workspace.bin'),
                            ('hardware-client/client.s19','hardware-client/client.bin'),('workspace/example/example.s19','workspace/example/example.bin')):
            cells,entry=read_application_s19(root/srec)
            self.assertEqual(bytes(cells[a] for a in range(min(cells),max(cells)+1)),(root/binary).read_bytes())
            self.assertEqual(entry,min(cells))
    def test_loader_verifies_body_and_returns_hash(self):
        body=b'\xEA\x60';self.path.write_bytes(s19(dict(enumerate(body,0x4000)),0x4000))
        class Link:
            def __init__(self):self.sent=[]
            def command(self,text,until):self.command_args=(text,until)
            def send(self,data):self.sent.append(data)
            def until(self,until):self.until_arg=until
            def dump(self,first,last):self.dump_args=(first,last);return body
        link=Link()
        self.assertEqual(load_image(link,self.path),sha(body))
        self.assertEqual(link.command_args,('L',b'S19'))
        self.assertEqual(link.until_arg,b'\r\nB3> ')
        self.assertEqual(link.dump_args,(0x4000,0x4001))
        self.assertEqual(link.sent,[row+b'\r\n' for row in self.path.read_bytes().splitlines()])

if __name__=='__main__':unittest.main()
