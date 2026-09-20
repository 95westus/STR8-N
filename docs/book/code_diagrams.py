"""Vector atlas for the current-code book; documentation only.

Each diagram is drawn once and reused as PDF vectors and inline SVG. All
coordinates use a top-left origin. Edges express the relationship named in
the caption, not an exhaustive instruction-level call graph.
"""
from dataclasses import dataclass
import math
import textwrap
from reportlab.graphics.shapes import Drawing, Rect, String, PolyLine, Polygon
from reportlab.lib.colors import HexColor, white
from reportlab.pdfbase.pdfmetrics import stringWidth


@dataclass
class Node:
    key: str
    x: float
    y: float
    w: float
    h: float
    text: str
    kind: str = 'normal'


class Chart:
    def __init__(self, height=450):
        self.height = height
        self.nodes = {}
        self.edges = []

    def node(self, key, x, y, text, w=146, h=48, kind='normal'):
        self.nodes[key] = Node(key, x, y, w, h, text, kind)
        return self

    def edge(self, a, b, label='', sides='bt', via=(), label_at=None, dashed=False):
        self.edges.append((a, b, label, sides, via, label_at, dashed))
        return self

    def draw(self):
        d = Drawing(528, self.height)
        ink = HexColor('#173044')
        def port(n, side):
            return {'t': (n.x+n.w/2, n.y), 'b': (n.x+n.w/2, n.y+n.h),
                    'l': (n.x, n.y+n.h/2), 'r': (n.x+n.w, n.y+n.h/2)}[side]
        def xy(p):
            return p[0], self.height-p[1]
        for a, b, label, sides, via, label_at, dashed in self.edges:
            start, end = port(self.nodes[a], sides[0]), port(self.nodes[b], sides[1])
            pts = [start, *via, end]
            if not via and start[0] != end[0] and start[1] != end[1]:
                mid = (start[1]+end[1])/2
                pts = [start, (start[0], mid), (end[0], mid), end]
            flat = [v for p in pts for v in xy(p)]
            d.add(PolyLine(flat, strokeColor=HexColor('#64828e'), strokeWidth=1,
                           strokeDashArray=[4, 3] if dashed else None))
            x2, y2 = xy(pts[-1])
            x1, y1 = xy(pts[-2])
            angle = math.atan2(y2-y1, x2-x1)
            backx, backy = x2-6*math.cos(angle), y2-6*math.sin(angle)
            d.add(Polygon([x2,y2,backx+2.8*math.sin(angle),backy-2.8*math.cos(angle),
                           backx-2.8*math.sin(angle),backy+2.8*math.cos(angle)],
                          fillColor=HexColor('#64828e'), strokeColor=None))
            if label:
                px, py = label_at or ((start[0]+end[0])/2, (start[1]+end[1])/2)
                width = stringWidth(label, 'Helvetica', 7.5)+8
                d.add(Rect(px-width/2, self.height-py-5, width, 12, fillColor=white, strokeColor=None))
                d.add(String(px, self.height-py-2, label, textAnchor='middle', fontName='Helvetica', fontSize=7.5, fillColor=ink))
        for n in self.nodes.values():
            palette = {'normal': ('#eef5f7','#91adb9'), 'decision': ('#fff4d9','#b4934e'),
                       'mutate': ('#fff0e9','#bd7d5c'), 'exit': ('#e6f4ec','#6c9e82'),
                       'failure': ('#fbecef','#bd7e8b')}
            fill, stroke = palette[n.kind]
            d.add(Rect(n.x, self.height-n.y-n.h, n.w, n.h, rx=6, ry=6,
                       fillColor=HexColor(fill), strokeColor=HexColor(stroke), strokeWidth=.8))
            lines = []
            for line in n.text.split('\n'):
                chars = max(12, int((n.w-16)/4.2))
                lines.extend(textwrap.wrap(line, width=chars, break_long_words=True, break_on_hyphens=False) or [''])
            assert len(lines)*10 <= n.h-8, (n.key, n.text, len(lines), n.h)
            yy = self.height-n.y-(n.h-len(lines)*10)/2-8
            for line in lines:
                assert stringWidth(line, 'Helvetica', 8.3) <= n.w-8, (n.key, line)
                d.add(String(n.x+n.w/2, yy, line, textAnchor='middle', fontName='Helvetica', fontSize=8.3, fillColor=ink))
                yy -= 10
        return d


def charts():
    result = {}
    c = Chart(410)
    c.node('root',174,0,'src/\nResident firmware',180)
    c.node('resident',12,84,'str8.asm\nSupervisor, commands, parser, directory and console',242,66)
    c.node('worker',274,84,'str8-worker.asm\nRAM flash operations and bank handoff',242,66)
    c.node('interfaces',12,182,'Interfaces and identity\nstr8-console-eq.inc\nstr8-directory-eq.inc\nhimon-image-eq.inc\nstr8-version.inc',242,94)
    c.node('shared',274,182,'Shared contracts\nstr8-ram-abi.inc\nstr8-record-eq.inc\nstr8-jump-eq.inc\nstr8-led-eq.inc\nstr8-worker-eq.inc',242,94)
    c.node('config',12,316,'str8-config-eq.inc\nConfiguration pocket definitions\nIndependent of direct ASM includes',504,64)
    c.edge('root','resident').edge('root','worker')
    result['source-core'] = c

    c = Chart(470)
    c.node('root',174,0,'tools/\nBoard-executed source',180)
    c.node('maint',12,78,'bank-maint/\nstr8n-v1.23-bank-maint-2000.asm\nstr8n-v1.23-bank-maint-menu-2000.asm\nstr8n-v1.23-bank-maint-rename.inc\nstr8n-v1.28-str8-in65-bank-maint-flags.inc',246,128)
    c.node('update',276,78,'top-update/\nstr8n-v1.23-top-update-2000.asm\n\nstr8-in65/\nstr8n-v1.35-str8-in65-bank-maint-2000.asm',240,128)
    c.node('migration',12,240,'wdcmonv2/\nwdcmonv2str8n-archive-2000.asm\nwdcmonv2str8n-install-2000.asm',246,76)
    c.node('probes',276,240,'RAM hardware probes\nconsole-abi-test/\nstr8n-v1.23-console-abi-test-2000.asm\ninterrupt-test/\nstr8n-v1.35-irq-test-2000.asm\nled-status-test/\nstr8n-v1.35-led-worker-test-2000.asm',240,140)
    c.edge('root','maint').edge('root','update')
    result['source-tools'] = c

    c = Chart(390)
    c.node('resident',12,0,'str8.asm',220)
    c.node('worker',296,0,'str8-worker.asm',220)
    c.node('shared',145,114,'Shared includes\nstr8-ram-abi.inc\nstr8-record-eq.inc\nstr8-jump-eq.inc\nstr8-led-eq.inc\nstr8-worker-eq.inc',238,96)
    c.node('private',12,268,'Resident-only includes\nstr8-console-eq.inc\nstr8-directory-eq.inc\nhimon-image-eq.inc\nstr8-version.inc',242,96)
    c.node('ram',294,276,'Worker image in RAM\nPrefix: 0200-0226\nFull worker: 0200-0437',222,70)
    c.edge('resident','shared','includes',label_at=(170,78))
    c.edge('worker','shared','includes',label_at=(357,78))
    c.edge('resident','private',sides='lb',via=((4,24),(4,376),(133,376)))
    c.edge('worker','ram','linked to execute here',sides='rb',via=((524,24),(524,370),(405,370)),label_at=(433,365),dashed=True)
    result['dependencies'] = c

    c = Chart(456)
    c.node('reset',184,0,'RESET / START',160)
    c.node('init',184,76,'CPU, EDU, IVI and console initialization',160,58)
    c.node('selector',184,164,'Reset marker, banner and startup selector',160,58,kind='decision')
    c.node('bank',8,266,'0-2: guarded bank launch',146,58)
    c.node('menu',191,266,'S: command loop\nI / L / C / W / J',146,58)
    c.node('himon',374,266,'C / W / timeout\nValidate local HIMON',146,58,kind='decision')
    c.node('guest',8,388,'Guest RESET vector',146,48,kind='exit')
    c.node('entry',374,388,'HIMON C000\nCold or warm entry',146,48,kind='exit')
    c.edge('reset','init').edge('init','selector')
    c.edge('selector','bank').edge('selector','menu').edge('selector','himon')
    c.edge('bank','guest','valid').edge('himon','entry','compatible')
    c.edge('bank','menu','failure',sides='rl',label_at=(173,295))
    c.edge('himon','menu','missing',sides='lr',label_at=(356,295))
    result['startup'] = c

    c = Chart(462)
    c.node('input',12,0,'I: bank, range, identity\nValidate directory',224,56)
    c.node('confirm',12,85,'WRITE confirmed?',224,46,kind='decision')
    c.node('copy',12,160,'Copy and verify full worker',224,48)
    c.node('start',12,241,'Write START; write first metadata and seal if needed',224,66,kind='mutate')
    c.node('recv',12,343,'Print S19\nEnter dense receiver',224,60,kind='exit')
    c.node('fail',304,159,'Rejected / cancelled / failed\nReturn to command loop',212,68,kind='failure')
    c.node('boundary',304,290,'Persistent boundary\nChanges made after START are not rolled back',212,86,kind='mutate')
    c.edge('input','confirm','accepted').edge('confirm','copy','yes').edge('copy','start','verified').edge('start','recv','prepared')
    c.edge('confirm','fail','no',sides='rt',via=((410,108),),label_at=(315,108))
    c.edge('copy','fail','failed',sides='rl',label_at=(270,193))
    c.edge('start','fail','failed',sides='rb',via=((410,274),),label_at=(311,274))
    result['install-prepare'] = c

    c = Chart(482)
    c.node('record',12,0,'Parse next record\nValidate dense ordering',224,54,kind='decision')
    c.node('stage',12,89,'S1: fill sector tray\n0A00-19FF',224,54)
    c.node('sector',12,184,'Complete sector?',224,48,kind='decision')
    c.node('program',304,184,'Non-final: program and verify\nContinue receiving',212,64,kind='mutate')
    c.node('hold',12,272,'Final: hold sector in RAM\nWait for valid S9',224,54)
    c.node('commit',12,361,'Check coverage and S9 policy\nRequire COMMIT confirmation',224,60,kind='decision')
    c.node('finish',304,350,'Program and verify final sector\nPublish B3 entry if needed\nWrite COMPLETE last\nReport OK',212,96,kind='mutate')
    c.edge('record','stage','S1').edge('stage','sector')
    c.edge('sector','program','non-final',sides='rl',label_at=(270,208))
    c.edge('sector','hold','final').edge('hold','commit','S9')
    c.edge('sector','record','incomplete',sides='ll',via=((4,208),(4,27)),label_at=(35,165))
    c.edge('commit','finish','accepted',sides='rl',label_at=(270,391))
    c.edge('program','record','next record',sides='tr',via=((410,27),),label_at=(410,90))
    result['install-stream'] = c

    c = Chart(432)
    c.node('parse',12,0,'L: parse next record',222,48,kind='decision')
    c.node('span',12,96,'S1: entire nonempty span inside 2000-7AFF?',222,60,kind='decision')
    c.node('copy',12,211,'Copy directly to RAM\nMark data received',222,54)
    c.node('s9',294,0,'S9: data received and entry inside 2000-7AFF?',222,62,kind='decision')
    c.node('run',294,113,'SEI, CLD, reset stack\nRelease LEDs\nJump to S9',222,74,kind='exit')
    c.node('fail',294,265,'Any parse / policy failure\nQuench if needed\nReport BAD; no jump',222,74,kind='failure')
    c.node('limit',12,350,'No rollback of RAM writes\nNo flash worker\nNo prepared RTS return address',222,66)
    c.edge('parse','span','S1').edge('span','copy','valid')
    c.edge('parse','s9','S9',sides='rl',label_at=(264,24))
    c.edge('s9','run','valid')
    c.edge('copy','parse','next',sides='ll',via=((4,238),(4,24)),label_at=(24,183))
    c.edge('span','fail','invalid',sides='rb',via=((264,126),(264,353),(405,353)),label_at=(264,225))
    result['ram-load'] = c

    c = Chart(444)
    c.node('sel',12,0,'F010 public selector',232,48)
    c.node('guard',12,89,'Check bank and RAM return\nCopy / verify 39-byte prefix',232,60,kind='decision')
    c.node('ret',12,194,'Run 0203 selector\nReturn to RAM caller with selected bank visible',232,74,kind='exit')
    c.node('j',284,0,'J0-J3 launch',232,48)
    c.node('gate',284,89,'J0-J2 need COMPLETE row\nJ3 bypasses row gate',232,60,kind='decision')
    c.node('full',284,194,'Copy / verify full worker\nSelect requested bank\nValidate RESET vector',232,74)
    c.node('go',284,320,'Commit BJ record\nSEI, CLD, reset stack, release LEDs\nJump through RESET; no return',232,82,kind='exit')
    c.node('fail',12,320,'Failure paths\nSelector rejects without changing bank\nWorker launch failure restores B3',232,82,kind='failure')
    c.edge('sel','guard').edge('guard','ret','valid')
    c.edge('j','gate').edge('gate','full','allowed').edge('full','go','valid vector')
    result['handoff'] = c

    c = Chart(384)
    c.node('menu',12,0,'bank-maint-menu wrapper',242,48)
    c.node('in65',274,0,'v1.35 iN65 wrapper',242,48)
    c.node('body',145,105,'Shared bank-maint body\nCommands and private worker',238,62)
    c.node('top',12,233,'top-update source',154,54)
    c.node('rename',188,233,'rename include',154,54)
    c.node('flags',364,233,'iN65 flags include',154,54)
    c.node('image',12,327,'Candidate image data',154,42)
    c.edge('menu','body').edge('in65','body')
    c.edge('body','top','menu form',label_at=(102,205))
    c.edge('body','rename','standalone / iN65',label_at=(264,205))
    c.edge('body','flags','iN65 form',label_at=(428,205))
    c.edge('top','image')
    c.edge('top','rename','embedded menu',sides='rb',via=((177,260),(177,310),(265,310)),label_at=(225,310))
    result['maintenance'] = c

    c = Chart(474)
    c.node('check',12,0,'RAM updater preflight\nSave directory for ordinary update',228,62)
    c.node('backup',12,101,'Backup confirmation\nCopy live B3:F to B2:F and verify',228,64,kind='mutate')
    c.node('confirm',12,205,'Active rewrite confirmed?',228,50,kind='decision')
    c.node('write',12,301,'Prepare candidate\nErase / program / verify B3:F',228,64,kind='mutate')
    c.node('reset',12,409,'Success: arm RS marker\nJump through RESET vector',228,54,kind='exit')
    c.node('safe',294,96,'Pre-active failure / cancellation\nReturn to resident or embedding menu',222,76,kind='exit')
    c.node('recovery',294,280,'Active-write failure\nRemain in RAM recovery prompt',222,64,kind='failure')
    c.node('restore',294,390,'O: check backup, restore old B3:F and verify\nSuccess resets; failure stays in recovery',222,78)
    c.edge('check','backup','accepted').edge('backup','confirm','verified')
    c.edge('confirm','write','yes').edge('write','reset','verified')
    c.edge('confirm','safe','no',sides='rt',via=((264,230),(264,80),(405,80)),label_at=(275,214))
    c.edge('write','recovery','failure',sides='rl',label_at=(268,324))
    c.edge('recovery','write','R: retry',sides='bl',via=((405,378),(4,378),(4,333)),label_at=(229,378))
    c.edge('recovery','restore','O')
    result['top-update'] = c
    return result


CHARTS = charts()


def atlas_text():
    sections = [
        ('Source structure: resident firmware', 'source-core',
         'The complete src directory is grouped by responsibility. These are source files, not a proposed refactor. The configuration include is shown separately because neither resident ASM file directly includes it.',
         'Most includes contain constants and contracts. str8-version.inc contributes identity data. str8.asm contains many logical subsystems within one assembly module; a box in a flow map does not imply a separate file.'),
        ('Source structure: board RAM programs', 'source-tools',
         'Current board-executed maintenance, migration, and probe sources under tools/. Host scripts, Makefiles, packaging, and generated carriers are deliberately absent from this map.',
         'Older version numbers remain in maintained filenames. These RAM programs are separate from the always-resident supervisor. Migration archive/install programs run under the external stock-monitor environment; probes require their intended hardware setup.'),
        ('Resident include dependencies', 'dependencies',
         'Solid arrows mean source inclusion. The dashed arrow describes execution placement, not an INCLUDE or JSR. The resident copies the stored worker into RAM before invoking the relevant entry.',
         'Source anchors: str8.asm:66; str8-worker.asm:19; str8-worker-eq.inc:3. F010 copies only the selector prefix. I and J use the full worker. Sharing a constants include is not a runtime call relationship.'),
        ('Reset and command dispatch', 'startup',
         'Logical flow through the active resident startup path. Physical RESET selects Bank 3. The command loop dispatches I, L, C, W, and J; successful handoffs leave that loop.',
         'Source anchors: str8.asm:268, :530, :663, :804. Timeout requests warm HIMON entry. C requests cold entry. A missing compatible target or failed guest launch returns to STR8-N. Invalid commands are discarded. This is a subsystem map, not every assembly branch.'),
        ('Flash installation: preparation', 'install-prepare',
         'I validates the requested bank/range and directory, then obtains WRITE confirmation. The receiver is not invited to send until worker relocation and transaction preparation succeed.',
         'Source anchors: str8.asm:909, :1143, :1225. Preflight rejection also returns without starting payload reception. Once START or identity writes occur, failure does not roll them back. A preparation failure reports FAIL directly rather than entering the receive loop.'),
        ('Flash installation: receive and commit', 'install-stream',
         'Continuation of I after preparation. This chart shows the main payload path and final commit; the failure policy below applies to receive, validation, and worker errors.',
         'Source anchors: str8.asm:1365, :1552, :1566, :1595, :1250. S0 metadata and incomplete sectors continue reception; malformed records or ordering failures quench through valid S9 or Ctrl-C. Non-final sectors may already be changed. A rejected COMMIT does not roll them back. Finalization failure reports FAIL; COMPLETE is never intentionally published before verified payload completion.'),
        ('RAM loading and execution', 'ram-load',
         'L shares the record parser but applies each valid S1 directly to RAM. S0 metadata simply continues parsing; valid S9 triggers the final entry checks.',
         'Source anchor: str8.asm:849. S1 ordering need not be dense or ascending. The complete data span must be in range. An in-range S9 does not prove its target was loaded. After failure, accepted RAM bytes remain; later records cannot rescue the poisoned load. Success transfers control without preparing an RTS return.'),
        ('Public selector and guarded bank launch', 'handoff',
         'Two different ways to change banks. The public selector returns to a RAM caller. J performs directory gating and transfers control through the selected bank RESET vector.',
         'Source anchors: str8.asm:1812, :1843; str8-worker.asm:62, :132. J rejects RESET below $8000 or equal to $FFFF. Gate/copy failure reports failure without a guest jump. Worker modes $05/$07 return through a Bank-3 restoration path; $08 is the nonreturning successful handoff. Unknown modes fail before changing banks or flash.'),
        ('Maintenance source relationships', 'maintenance',
         'Arrows are conditional INCLUDE relationships. Labels shorten the full filenames shown in Atlas 2. The shared maintenance body carries its own private worker.',
         'Source anchors: bank-maint/str8n-v1.23-bank-maint-2000.asm:2600; top-update/str8n-v1.23-top-update-2000.asm:645. The combined menu includes the updater, which includes the rename extension. Standalone and iN65 forms include rename directly; only iN65 adds the flags editor. These are distinct selected forms, not all commands in every image.'),
        ('Protected-top update and recovery', 'top-update',
         'The driver remains executable in RAM while B3:F is unavailable. The first confirmation authorizes backup mutation; the second authorizes active top replacement.',
         'Source anchor: top-update/str8n-v1.23-top-update-2000.asm:60. Ordinary update overlays the saved directory; refresh leaves the candidate directory cleared. Both install candidate configuration. Cancelling the second confirmation can leave a newly written backup. After active erase, failure stays in RAM recovery. Power loss can remove that recovery path.'),
    ]
    intro = '\n## Code atlas: scope and legend\n\n'
    intro += 'These diagrams extend the reference with current source structure and runtime flow. They contain no development history. Source maps omit build/host tooling. Flow diagrams aggregate related instructions; arrows are not a complete instruction-level call graph.\n\n'
    intro += 'Blue boxes describe code or data; amber boxes mark decisions; orange marks persistent mutation; green marks an exit or handoff; rose marks failure handling. Read the edge labels and the exceptions beneath each figure. The same vector diagrams appear in PDF and searchable HTML.\n\n'
    for number, (title, key, before, after) in enumerate(sections, 1):
        intro += f'## Atlas {number}. {title}\n\n{before}\n\n:::diagram {key}:::\n\n{after}\n\n'
    return intro
