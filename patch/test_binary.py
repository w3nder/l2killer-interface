#!/usr/bin/env python3
"""PE invariants and actual x86 execution against simulated Windows/native APIs.

This verifies ABI/indices, not the game's renderer or the real Windows loader.
Run with research/venv/bin/python patch/test_binary.py after build_patch.py.
"""
import hashlib
import json
import struct
from unicorn import Uc, UC_ARCH_X86, UC_MODE_32, UC_HOOK_CODE
from unicorn.x86_const import (UC_X86_REG_EAX, UC_X86_REG_EBX, UC_X86_REG_ECX,
    UC_X86_REG_EDX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP, UC_X86_REG_ESP,
    UC_X86_REG_EIP)
from build_patch import PE, ROOT, SOURCE_SHA256, SOURCE_PATH, PACKAGE_NAME, L2KILLER, align, checksum

PACKAGE = ROOT / 'dist' / PACKAGE_NAME
HIT_RVA = 0x1063a0 if L2KILLER else 0x1060f0
TABLE_RVA = 0x1ccdc0 if L2KILLER else 0x1cbd68
STOP = 0x7000f000
STACK = 0x60008000
SELF = 0x50000000
CANVAS = 0x50001000
GAME = 0x50002000
CONSOLE = 0x50003000
CALLEE = [UC_X86_REG_EBX, UC_X86_REG_ESI, UC_X86_REG_EDI, UC_X86_REG_EBP]


def r32(uc, address):
    return struct.unpack('<I', uc.mem_read(address, 4))[0]


def w32(uc, address, value):
    uc.mem_write(address, struct.pack('<I', value & 0xffffffff))


def map_pe(uc, pe, base):
    uc.mem_map(base, align(pe.u32(pe.opt + 56), 4096))
    uc.mem_write(base, bytes(pe.data[:pe.u32(pe.opt + 60)]))
    for _, _, rva, rawsize, raw in pe.sections:
        if rawsize:
            uc.mem_write(base + rva, bytes(pe.data[raw:raw + rawsize]))
    delta = base - pe.u32(pe.opt + 28)
    if delta:
        rva, size = pe.directory(5)
        assert rva and size
        pos = pe.offset(rva)
        end = pos + size
        while pos < end:
            page, blocksize = struct.unpack_from('<II', pe.data, pos)
            assert blocksize >= 8 and pos + blocksize <= end
            for offset in range(pos + 8, pos + blocksize, 2):
                relocation = pe.u16(offset)
                kind, rel = relocation >> 12, relocation & 0xfff
                assert kind in (0, 3), kind
                if kind == 3:
                    at = base + page + rel
                    w32(uc, at, r32(uc, at) + delta)
            pos += blocksize


def emulator():
    uc = Uc(UC_ARCH_X86, UC_MODE_32)
    uc.mem_map(0x60000000, 0x10000)
    uc.mem_map(0x70000000, 0x10000)
    uc.mem_map(SELF, 0x10000)
    return uc


def invoke(uc, entry, args, ecx=SELF, edx=0x13579bdf, cdecl=False):
    uc.reg_write(UC_X86_REG_ESP, STACK)
    uc.reg_write(UC_X86_REG_ECX, ecx)
    uc.reg_write(UC_X86_REG_EDX, edx)
    for reg in CALLEE:
        uc.reg_write(reg, 0x12340000 + reg)
    uc.mem_write(STACK, struct.pack('<' + 'I' * (len(args) + 1), STOP, *args))
    uc.emu_start(entry, STOP, count=200000)
    assert uc.reg_read(UC_X86_REG_EIP) == STOP, 'instruction limit or bad return'
    assert uc.reg_read(UC_X86_REG_ESP) == STACK + 4 + (0 if cdecl else len(args) * 4), 'wrong stack cleanup'
    for reg in CALLEE:
        assert uc.reg_read(reg) == 0x12340000 + reg, 'callee-saved register corrupted'
    return uc.reg_read(UC_X86_REG_EAX)


def return_from_stub(uc, count, value=1):
    sp = uc.reg_read(UC_X86_REG_ESP)
    result = r32(uc, sp)
    uc.reg_write(UC_X86_REG_EAX, value & 0xffffffff)
    uc.reg_write(UC_X86_REG_ESP, sp + 4 + count * 4)
    uc.reg_write(UC_X86_REG_EIP, result)


def symbols(pe, base):
    start, count = pe.u32(pe.pe + 12), pe.u32(pe.pe + 16)
    strings = start + count * 18
    result = {}
    i = 0
    while i < count:
        o = start + i * 18
        if pe.u32(o) == 0:
            first = strings + pe.u32(o + 4)
            last = pe.data.index(0, first)
            name = bytes(pe.data[first:last]).decode('ascii')
        else:
            name = bytes(pe.data[o:o + 8]).split(b'\0')[0].decode('ascii')
        value, section = struct.unpack_from('<Ih', pe.data, o + 8)
        if section > 0:
            result[name] = base + pe.sections[section - 1][2] + value
        i += 1 + pe.data[o + 17]
    return result


def verify_pe():
    original = PE(SOURCE_PATH.read_bytes())
    patched = PE((PACKAGE / 'bin/NWindow.dll').read_bytes())
    helper = PE((PACKAGE / 'bin/C4Bars.dll').read_bytes())
    assert hashlib.sha256(original.data).hexdigest() == SOURCE_SHA256
    assert checksum(patched.data, patched.opt + 64) == patched.u32(patched.opt + 64)
    for section in original.sections:
        assert section in patched.sections
        _, _, _, size, raw = section
        assert original.data[raw:raw + size] == patched.data[raw:raw + size]
    old_imports, new_imports = original.imports(), patched.imports()
    assert len(new_imports) == len(old_imports) + 1
    for a, b in zip(old_imports, new_imports):
        assert [a[0], *a[2:]] == [b[0], *b[2:]]
    added = new_imports[-1]
    assert patched.directory(12) == original.directory(12), 'Preserve original Windows IAT protection range'
    def section_flags(rva):
        for i, (_, size, start, rawsize, _) in enumerate(patched.sections):
            if start <= rva < start + max(size, rawsize):
                return patched.u32(patched.table + i * 40 + 36)
        raise AssertionError('RVA outside sections')
    assert section_flags(added[4]) & 0xe0000000 == 0xc0000000, 'New IAT must be read/write, not executable'
    assert section_flags(patched.u32(patched.opt + 16)) & 0xe0000000 == 0x60000000, 'Entry must be read/execute, not writable'
    assert patched.cstring(added[3]) == 'C4Bars.dll'
    thunk = patched.u32(patched.offset(added[0]))
    assert patched.cstring(thunk + 2) == 'C4BarsInitialize'
    assert {helper.cstring(d[3]).lower() for d in helper.imports()} == {'kernel32.dll', 'user32.dll'}
    manifest = json.loads((PACKAGE / 'manifest.json').read_text())
    assert manifest['patched_sha256'] == hashlib.sha256(patched.data).hexdigest()
    assert manifest['dll_sha256'] == hashlib.sha256(helper.data).hexdigest()
    manager = (PACKAGE / 'Gerenciar.ps1').read_text()
    assert manifest['patched_sha256'] in manager and manifest['dll_sha256'] in manager
    assert '__PATCH_SHA256__' not in manager and '__DLL_SHA256__' not in manager
    print('PE: source sections/imports preserved; hashes, checksum and new import validated')
    return original, patched, helper


def verify_entry(original, patched):
    count = 0
    for base in (0x10000000, 0x35000000):
        for reason in range(4):
            for original_result in (0, 1):
                uc = emulator()
                map_pe(uc, patched, base)
                old_entry = base + original.u32(original.opt + 16)
                init = 0x70000100
                w32(uc, base + patched.imports()[-1][4], init)
                seen = []

                def hook(uc, address, size, user):
                    sp = uc.reg_read(UC_X86_REG_ESP)
                    if address == old_entry:
                        assert [r32(uc, sp + n * 4) for n in (1, 2, 3)] == [base, reason, 0x11223344]
                        seen.append('original')
                        return_from_stub(uc, 3, original_result)
                    elif address == init:
                        assert r32(uc, sp + 4) == base
                        seen.append('init')
                        return_from_stub(uc, 0, 123)  # cdecl; wrapper pops hInstance

                uc.hook_add(UC_HOOK_CODE, hook)
                actual = invoke(uc, base + patched.u32(patched.opt + 16), [base, reason, 0x11223344])
                assert actual == original_result
                assert seen == (['original', 'init'] if reason == 1 and original_result else ['original'])
                count += 1
    print(f'x86 entry wrapper: {count} attach/detach/failure/rebase cases passed')


def verify_hooks(helper):
    count = 0
    for base in (helper.u32(helper.opt + 28), 0x25000000):
        uc = emulator()
        map_pe(uc, helper, base)
        syms = symbols(helper, base)

        def symbol(part):
            matches = [address for name, address in syms.items() if part in name
                       and (not part.endswith('Hook') or (name.startswith('@') and '.part.' not in name))]
            assert len(matches) == 1, (part, matches)
            return matches[0]

        def put_global(part, value):
            w32(uc, symbol(part), value)

        uc.mem_map(0x10000000, 0x400000)
        put_global('potionL10moduleBaseE', 0x10000000)
        put_global('potionL6panelXE', 2000)
        uc.mem_write(symbol('potionL9collapsedE'),b'\x00')
        for offset, value in {0x1f8: 0, 0x268: 12, 0x26c: 10, 0x274: 32,
                              0x200: 0x50100000, 0x1fc: 0x50200000}.items():
            w32(uc, SELF + offset, value)
        w32(uc, CONSOLE + 0x3bf4, GAME)
        w32(uc, GAME + 0x15c, SELF)
        seen = []
        modifiers = set()
        put_global('secondPage', 4)
        put_global('thirdPage', 7)
        stub_targets = {}
        for index, (name, argc) in enumerate((('originalPaint', 1), ('originalBounds', 2),
                ('originalConsole', 3), ('pushClip', 4), ('popClip', 0), ('originalChat', 4),
                ('originalTooltip', 1), ('originalMouseMove', 2), ('potionL4tileE', 11), ('potionL10normalTextE', 15))):
            address = 0x70000200 + index * 16
            put_global(name, address)
            stub_targets[address] = (name, argc)
        get_key_state = 0x70000400
        w32(uc, symbol('__imp__GetKeyState@4'), get_key_state)
        save_ini = 0x70000410
        w32(uc, symbol('__imp__WritePrivateProfileStringA@16'), save_ini)
        w32(uc, symbol('__imp__CallWindowProcW@20'), 0x70000910)
        forwarded_mouse = []
        saved = []
        button_calls = []
        cursor_position = None
        titles = []
        cursor_apis = {}
        for i, (name, argc) in enumerate((('GetForegroundWindow', 0), ('GetWindowThreadProcessId', 2),
                ('GetCurrentProcessId', 0), ('GetCursorPos', 1), ('ScreenToClient', 2), ('GetModuleHandleA', 1))):
            at = 0x70000600 + i * 16
            w32(uc, symbol('__imp__' + name + '@' + str(argc * 4)), at)
            cursor_apis[at] = (name, argc)
        uc.mem_map(0x50100000, 0x100000)
        credits = []
        button_paint = 0x70000420
        for offset, button in ((0x24c, SELF + 0x8000), (0x250, SELF + 0x8400)):
            w32(uc, SELF + offset, button)
            w32(uc, button, SELF + 0x8800)
            w32(uc, button + 0x44, 11)
            w32(uc, button + 0x48, 12)
        w32(uc, SELF + 0x8800 + 0xf8, button_paint)

        tick_now = 10000
        potion_requests = []
        potion_user = SELF + 0x9500
        def hook(uc, address, size, user):
            sp = uc.reg_read(UC_X86_REG_ESP)
            if address in (0x70000920,0x70000930):
                assert uc.reg_read(UC_X86_REG_ECX)==CONSOLE
                return_from_stub(uc,1 if address==0x70000930 else 0)
            elif address == 0x70000910:
                forwarded_mouse.append(r32(uc,sp+12))
                return_from_stub(uc,5,37)
            elif address == 0x70000800:
                return_from_stub(uc, 0, tick_now)
            elif address == 0x70000810:
                return_from_stub(uc, 0, potion_user)
            elif address == 0x70000820:
                assert uc.reg_read(UC_X86_REG_ECX) == CONSOLE
                potion_requests.append(r32(uc, sp + 4))
                return_from_stub(uc, 1)
            elif address in cursor_apis:
                name, argc = cursor_apis[address]
                result = 1
                if name == 'GetModuleHandleA': result = 0
                elif name == 'GetForegroundWindow': result = 123 if cursor_position else 0
                elif name == 'GetWindowThreadProcessId': w32(uc, r32(uc, sp + 8), 1)
                elif name == 'GetCursorPos':
                    uc.mem_write(r32(uc, sp + 4), struct.pack('<ii', *cursor_position))
                return_from_stub(uc, argc, result)
            elif address == button_paint:
                button = uc.reg_read(UC_X86_REG_ECX)
                button_calls.append((button, r32(uc, button + 0x44), r32(uc, button + 0x48)))
                return_from_stub(uc, 1)
            elif address == save_ini:
                def string_at(at):
                    data = bytearray()
                    while uc.mem_read(at, 1) != b'\0':
                        data.extend(uc.mem_read(at, 1)); at += 1
                    return bytes(data)
                saved.append((string_at(r32(uc, sp + 8)), string_at(r32(uc, sp + 12))))
                return_from_stub(uc, 4)
            elif address == get_key_state:
                key = r32(uc, sp + 4)
                return_from_stub(uc, 1, 0x8000 if key in modifiers else 0)
            elif address in stub_targets:
                name, argc = stub_targets[address]
                if name in ('originalPaint', 'originalTooltip'):
                    assert uc.reg_read(UC_X86_REG_ECX) == SELF
                    assert r32(uc, sp + 4) == CANVAS
                    seen.append((name, r32(uc, SELF + 0x44), r32(uc, SELF + 0x48), r32(uc, SELF + 0x270)))
                elif name == 'originalConsole':
                    assert uc.reg_read(UC_X86_REG_ECX) == CONSOLE
                    seen.append((name, r32(uc, sp + 4), r32(uc, sp + 8), r32(uc, SELF + 0x270)))
                elif name == 'originalChat':
                    assert uc.reg_read(UC_X86_REG_ECX) == GAME
                    at = r32(uc, sp + 4)
                    data = bytearray()
                    while uc.mem_read(at, 2) != b'\0\0':
                        data.extend(uc.mem_read(at, 2)); at += 2
                    credits.append(data.decode('utf-16le'))
                elif name == 'drawText':
                    at = r32(uc, sp + 20)
                    data = bytearray()
                    while uc.mem_read(at, 2) != b'\0\0':
                        data.extend(uc.mem_read(at, 2)); at += 2
                    titles.append(data.decode('utf-16le'))
                elif name == 'originalBounds':
                    x, y = r32(uc, sp + 4), r32(uc, sp + 8)
                    ox, oy = r32(uc, SELF + 0x44), r32(uc, SELF + 0x48)
                    horizontal = r32(uc, SELF + 0x264)
                    result = ox <= x < ox + (504 if horizontal else 46) and oy <= y < oy + (46 if horizontal else 504)
                    return_from_stub(uc, argc, int(result)); return
                return_from_stub(uc, argc)

        uc.hook_add(UC_HOOK_CODE, hook)
        for horizontal in (0, 1):
            w32(uc, SELF + 0x264, horizontal)
            for origin in (0, 200):
                w32(uc, SELF + 0x44, origin)
                w32(uc, SELF + 0x48, origin)
                direction = -1 if origin >= 92 else 1
                for page in range(10):
                    w32(uc, SELF + 0x270, page)
                    for row in range(3):
                        for slot in (0, 3, 4, 7, 8, 11):
                            along = 33 + slot * 37 + (slot // 4) * 5 + 16
                            cross = 22 + row * 46 * direction
                            x, y = (origin + along, origin + cross) if horizontal else (origin + cross, origin + along)
                            actual = invoke(uc, syms['_C4BarsHitBridge'], [x, y])
                            assert actual == (page if row == 0 else 4 if row == 1 else 7) * 12 + slot
                            assert uc.reg_read(UC_X86_REG_ECX) == SELF
                            assert uc.reg_read(UC_X86_REG_EDX) == 0x13579bdf
                            count += 1
                # Execute the real compiled paint hook with stand-ins for the native renderer.
                w32(uc, SELF + 0x27c, 0xffffffff)
                w32(uc, SELF + 0x270, 9)
                uc.mem_write(SELF + 0x4c, struct.pack('<ff', 504 if horizontal else 46,
                                                    46 if horizontal else 504))
                seen.clear()
                button_calls.clear()
                assert invoke(uc, symbol('paintHook'), [CANVAS]) == 1
                assert len(button_calls) == 5
                for button in (SELF + 0x8000, SELF + 0x8400):
                    assert r32(uc, button + 0x44) == 11 and r32(uc, button + 0x48) == 12
                expected = [('originalPaint', origin + (0 if horizontal else row * 46 * direction),
                             origin + (row * 46 * direction if horizontal else 0), (9 if row == 0 else 4 if row == 1 else 7))
                            for row in (2, 1, 0)]
                assert seen == expected, (seen, expected)
                assert r32(uc, SELF + 0x44) == origin and r32(uc, SELF + 0x48) == origin
                assert r32(uc, SELF + 0x270) == 9
                for row in range(3):
                    x = origin + (50 if horizontal else 22 + row * 46 * direction)
                    y = origin + (22 + row * 46 * direction if horizontal else 50)
                    invoke(uc, symbol('mouseMoveHook'), [0, x | (y << 16)])
                    assert r32(uc, symbol('hoveredRow')) == row
                    seen.clear()
                    invoke(uc, symbol('tooltipHook'), [CANVAS])
                    assert seen == [('originalTooltip', origin + (0 if horizontal else row * 46 * direction),
                                     origin + (row * 46 * direction if horizontal else 0), (9 if row == 0 else 4 if row == 1 else 7))]
                    assert r32(uc, SELF + 0x270) == 9
                    assert r32(uc, SELF + 0x44) == origin and r32(uc, SELF + 0x48) == origin
                # Extra-row hover is sampled even without native mouse events.
                for row, page in ((1, 4), (2, 7)):
                    item = 0x50100000 + page * 12 * 0x1cc0
                    w32(uc, item + 0x1ca0, 1)
                    uc.mem_write(item + 0x14, ('Test item ' + str(row) + '\0').encode('utf-16le'))
                    titles.clear()
                    cursor_position = (origin + (50 if horizontal else 22 + row * 46 * direction),
                                       origin + (22 + row * 46 * direction if horizontal else 50))
                    invoke(uc, symbol('paintHook'), [CANVAS])
                    assert r32(uc, symbol('hoveredRow')) == row
                    assert r32(uc, SELF + 0x27c) == page * 12
                    assert seen[-1] == ('originalTooltip', origin + (0 if horizontal else row * 46 * direction),
                                        origin + (row * 46 * direction if horizontal else 0), page)
                    assert r32(uc, SELF + 0x270) == 9
                cursor_position = (origin + 600, origin + 600)
                invoke(uc, symbol('paintHook'), [CANVAS])
                assert r32(uc, SELF + 0x27c) == 0xffffffff
                cursor_position = None
        for modifier, expected_page in [({0x12}, 4), ({0x12, 0x11}, 7)]:
            modifiers.clear(); modifiers.update(modifier)
            seen.clear()
            w32(uc, SELF + 0x270, 9)
            assert invoke(uc, symbol('consoleHook'), [0x104, 0x70, 1 << 29], ecx=CONSOLE) == 1
            assert seen[-1] == ('originalConsole', 0x100, 0x70, expected_page)
            assert r32(uc, SELF + 0x270) == 9
            # Alt released before F1 still releases the original selected page.
            modifiers.clear()
            assert invoke(uc, symbol('consoleHook'), [0x101, 0x70, 0], ecx=CONSOLE) == 1
            assert seen[-1] == ('originalConsole', 0x101, 0x70, expected_page)
            assert r32(uc, SELF + 0x270) == 9
        for horizontal in (0, 1):
            w32(uc, SELF + 0x264, horizontal)
            for origin in (0, 200):
                w32(uc, SELF + 0x44, origin); w32(uc, SELF + 0x48, origin)
                direction = -1 if origin >= 92 else 1
                for row, name in ((1, 'secondPage'), (2, 'thirdPage')):
                    put_global(name, 9)
                    other = 'thirdPage' if row == 1 else 'secondPage'
                    put_global(other, 6)
                    for cross, expected in ((37, 0), (7, 9)):
                        x, y = ((origin + 20, origin + row * 46 * direction + cross)
                                if horizontal else (origin + row * 46 * direction + cross, origin + 20))
                        assert invoke(uc, symbol('mouseDownHook'), [1, x | (y << 16)]) == 1
                        assert r32(uc, symbol(name)) == expected
                        assert r32(uc, symbol(other)) == 6
                        assert r32(uc, SELF + 0x270) == 9
                        assert saved[-1] == (b'SecondPage' if row == 1 else b'ThirdPage',
                                              b'01' if expected == 0 else b'10')
                x, y = ((origin + 495, origin + 37) if horizontal else (origin + 37, origin + 495))
                pages = (r32(uc, symbol('secondPage')), r32(uc, symbol('thirdPage')))
                for expected in (1, 3):
                    invoke(uc, symbol('mouseDownHook'), [1, x | (y << 16)])
                    assert r32(uc, symbol('barCount')) == expected
                    assert saved[-1] == (b'Bars', str(expected).encode())
                    assert pages == (r32(uc, symbol('secondPage')), r32(uc, symbol('thirdPage')))
        # Real compiled potion logic: native calls mocked, health/slots are real layouts.
        put_global('__imp__GetTickCount@0', 0x70000800)
        put_global('potionL7getUserE', 0x70000810)
        put_global('potionL7useItemE', 0x70000820)
        w32(uc, 0x102c6ad4, CONSOLE)
        for at, value in [(CONSOLE+0x54,SELF+0x9000),(SELF+0x9058,SELF+0x9100),
                          (SELF+0x9138,SELF+0x9200),(SELF+0x9200,SELF+0x9300),
                          (SELF+0x933c,SELF+0x9400),(SELF+0x97a8,SELF+0x9800),(SELF+0x9860,777)]: w32(uc,at,value)
        put_global('potionL15lastCharacterIdE',777)
        for off,value in [(0x218,1308),(0x214,1508),(0x7c,100),(0x78,100),(0x84,100),(0x80,100)]:w32(uc,potion_user+off,value)
        w32(uc,SELF+0x270,0)
        for off,value in [(0,0x55000000),(0x1b18,1),(0x1c98,1),(0x1ca0,1),(0x1b1c,123)]:w32(uc,0x50100000+off,value)
        invoke(uc,symbol('paintHook'),[CANVAS])
        def panel_point(x,y):
            return (r32(uc,symbol('potionL6panelXE'))+x) | ((r32(uc,symbol('potionL6panelYE'))+y)<<16)
        # Legacy timing regression explicitly opts into a player-defined interval.
        assert r32(uc,symbol('potionL8settingsE'))==0
        put_global('potionL8settingsE',3000)
        put_global('potionL5modesE',2);put_global('potionL10draftModesE',2)
        put_global('potionL14draftIntervalsE',3000)
        # Arm CP binding, then select F1 in the original bar. Binding does not consume.
        invoke(uc,symbol('mouseDownHook'),[1,panel_point(15,35)])
        invoke(uc,symbol('mouseDownHook'),[1,250 | (222 << 16)])
        assert r32(uc,symbol('potionL5slotsE'))==0
        assert potion_requests==[]
        invoke(uc,symbol('mouseDownHook'),[1,panel_point(165,35)])
        assert uc.mem_read(symbol('potionL8settingsE')+8,1)==b'\x00', 'changes wait for Apply'
        invoke(uc,symbol('mouseDownHook'),[1,panel_point(150,241)])
        invoke(uc,symbol('paintHook'),[CANVAS]);assert potion_requests==[123]
        # Stationary hover never suppresses a due potion. Actual manual requests
        # reserve the native item path until a response, rejection or recovery.
        put_global('potionL5modesE',0)
        put_global('potionL15previousWndProcE',0x70000900)
        w32(uc,0x102c6ad0,123)
        request_start=len(potion_requests)
        for row in range(3):
            cursor_position=(210,210-row*46)
            invoke(uc,symbol('paintHook'),[CANVAS])
            assert len(potion_requests)==request_start+row+1
        inv=SELF+0xa000
        w32(uc,GAME+0x120,inv);w32(uc,inv+0x68,2)
        w32(uc,inv+0x44,800);w32(uc,inv+0x48,100)
        uc.mem_write(inv+0x4c,struct.pack('<ff',250,400))
        cursor_position=(850,200)
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert len(potion_requests)==request_start+4
        assert invoke(uc,symbol('manualUseItem'),[999],ecx=CONSOLE)==1
        assert potion_requests[-1]==999
        count_manual=len(potion_requests)
        for _ in range(3):invoke(uc,symbol('paintHook'),[CANVAS])
        assert len(potion_requests)==count_manual, 'automatic requests yield to actual manual use'
        put_global('originalItemUpdate',0x70000920)
        put_global('originalItemList',0x70000930)
        invoke(uc,symbol('manualItemUpdate'),[],ecx=CONSOLE)
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert len(potion_requests)==count_manual+1, 'resume on update with cursor still in bag'
        invoke(uc,symbol('manualUseItem'),[998],ecx=CONSOLE)
        invoke(uc,symbol('manualItemList'),[0],ecx=CONSOLE)
        assert uc.mem_read(symbol('manualRequestPending'),1)==b'\x00'
        invoke(uc,symbol('manualUseItem'),[997],ecx=CONSOLE)
        original_time=tick_now
        tick_now+=1999
        count_manual=len(potion_requests)
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert len(potion_requests)==count_manual
        tick_now+=1
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert len(potion_requests)==count_manual+1, 'missing response must not leave automation stopped'
        tick_now=original_time
        uc.mem_write(symbol('manualInputPending'),b'\x01')
        count_manual=len(potion_requests)
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert len(potion_requests)==count_manual
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert len(potion_requests)==count_manual+1
        assert uc.mem_read(symbol('potionL8settingsE')+8,1)==b'\x01'
        assert r32(uc,symbol('potionL8settingsE'))==3000
        del potion_requests[request_start:]
        cursor_position=None;w32(uc,GAME+0x120,0)
        put_global('potionL5modesE',2)
        # Status refresh may replace User without changing the character.
        old_user=potion_user;potion_user=SELF+0xd000
        uc.mem_write(potion_user,bytes(uc.mem_read(old_user,0x240)))
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert uc.mem_read(symbol('potionL8settingsE')+8,1)==b'\x01', 'status cache replacement must preserve ON'
        tick_now+=2999
        invoke(uc,symbol('paintHook'),[CANVAS]);assert potion_requests==[123]
        tick_now+=1
        invoke(uc,symbol('paintHook'),[CANVAS]);assert potion_requests==[123,123]
        tick_now+=3000;w32(uc,potion_user+0x7c,0)
        invoke(uc,symbol('paintHook'),[CANVAS]);assert len(potion_requests)==2
        w32(uc,potion_user+0x7c,100);w32(uc,0x50100000+0x1b1c,124)
        invoke(uc,symbol('paintHook'),[CANVAS]);assert len(potion_requests)==2
        assert uc.mem_read(symbol('potionL8settingsE')+8,1)==b'\x00'

        uc.mem_write(symbol('potionL12draftEnabledE'),b'\x00')
        # Viewport hook consumes both halves of a panel click, toggles exactly once.
        put_global('potionL15previousWndProcE', 0x70000900)
        window_proc = symbol('windowProc')
        packed = panel_point(165,35)
        assert invoke(uc,window_proc,[123,0x201,1,packed])==0
        assert uc.mem_read(symbol('potionL12draftEnabledE'),1)==b'\x01'
        assert invoke(uc,symbol('mouseDownHook'),[1,packed])==1
        assert uc.mem_read(symbol('potionL12draftEnabledE'),1)==b'\x01', 'native dispatch must not toggle twice'
        assert invoke(uc,window_proc,[123,0x202,0,packed])==0
        assert uc.mem_read(symbol('potionL8settingsE')+8,1)==b'\x00'
        invoke(uc,window_proc,[123,0x201,1,panel_point(150,241)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(150,241)])
        assert uc.mem_read(symbol('potionL8settingsE')+8,1)==b'\x01'
        # A native shortcut drag dropped into CP binds without deleting or using it.
        uc.mem_map(0x50200000,0x1000)
        w32(uc,SELF+0x278,0);w32(uc,SELF+0x260,1);w32(uc,SELF+0x25c,1)
        assert invoke(uc,window_proc,[123,0x202,0,panel_point(15,35)])==0
        assert r32(uc,symbol('potionL7itemIdsE'))==124
        assert r32(uc,SELF+0x260)==0 and r32(uc,SELF+0x278)==0xffffffff
        assert r32(uc,0x50100000+0x1ca0)==1 and len(potion_requests)==2
        # Recolher preserves 3 item cells, aligned to the original bar's right edge.
        invoke(uc,window_proc,[123,0x201,1,panel_point(290,10)])
        before_mouse=len(seen)
        assert invoke(uc,symbol('consoleHook'),[0x201,0,0],ecx=CONSOLE)==1
        assert len(seen)==before_mouse, 'closing panel must not dispatch a world click'
        assert invoke(uc,symbol('consoleHook'),[0x202,0,0],ecx=CONSOLE)==1
        assert len(seen)==before_mouse

        invoke(uc,window_proc,[123,0x202,0,panel_point(5,10)])
        assert uc.mem_read(symbol('potionL9collapsedE'),1)==b'\x01'
        w32(uc,SELF+0x44,300);w32(uc,SELF+0x48,400)
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert r32(uc,symbol('potionL6panelXE'))==594
        assert r32(uc,symbol('potionL6panelYE'))==262
        # A stale panel press must not steal the next physical shortcut click,
        # including while the potion channel is enabled.
        uc.mem_write(symbol('ownedClick'),b'\x01')
        uc.mem_write(symbol('worldClickOwned'),b'\x01')
        uc.mem_write(symbol('potionL8settingsE')+8,b'\x01')
        assert invoke(uc,window_proc,[123,0x201,1,400*65536+350])==37
        assert forwarded_mouse[-1]==0x201
        assert uc.mem_read(symbol('ownedClick'),1)==b'\x00'
        assert uc.mem_read(symbol('worldClickOwned'),1)==b'\x00'
        # Native bag drop needs no shortcut, clears only drag state, preserves item.
        inv,grid,entries,bag_item=SELF+0xa000,SELF+0xb000,SELF+0xc000,0x50110000
        w32(uc,GAME+0x120,inv);w32(uc,inv+0x10c,grid)
        w32(uc,grid+0x12c,entries);w32(uc,grid+0x130,1);w32(uc,entries,bag_item)
        w32(uc,bag_item,0x55000000);w32(uc,bag_item+0x1b1c,456)
        w32(uc,grid+0x138,1);w32(uc,grid+0x160,0)
        assert invoke(uc,symbol('bagUp'),[1,panel_point(15,20)],ecx=grid)==1
        assert r32(uc,symbol('potionL5slotsE'))==0xfffffffe
        assert r32(uc,symbol('potionL7itemIdsE'))==456
        assert r32(uc,grid+0x138)==0 and r32(uc,grid+0x160)==0xffffffff
        assert r32(uc,grid+0x130)==1 and r32(uc,entries)==bag_item
        invoke(uc,window_proc,[123,0x201,1,panel_point(15,20)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(15,20)])
        assert uc.mem_read(symbol('potionL9collapsedE'),1)==b'\x00'
        invoke(uc,window_proc,[123,0x201,1,panel_point(165,35)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(165,35)])
        invoke(uc,window_proc,[123,0x201,1,panel_point(150,241)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(150,241)])
        invoke(uc,symbol('paintHook'),[CANVAS]);assert potion_requests[-1]==456
        request_count=len(potion_requests)
        w32(uc,grid+0x130,0);tick_now+=10000
        invoke(uc,symbol('paintHook'),[CANVAS]);assert len(potion_requests)==request_count
        assert uc.mem_read(symbol('potionL8settingsE')+8,1)==b'\x00'
        # Percentage input is staged, validated and committed only by Apply.
        invoke(uc,window_proc,[123,0x201,1,panel_point(220,35)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(220,35)])
        invoke(uc,window_proc,[123,0x102,ord('7'),0])
        invoke(uc,window_proc,[123,0x102,ord('5'),0])
        assert r32(uc,symbol('potionL11percentagesE'))==90
        invoke(uc,window_proc,[123,0x201,1,panel_point(150,241)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(150,241)])
        assert r32(uc,symbol('potionL11percentagesE'))==75
        assert (b'CPPercent',b'75') in saved
        # Advanced interval edits stay pending until Apply.
        invoke(uc,window_proc,[123,0x201,1,panel_point(40,260)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(40,260)])
        invoke(uc,window_proc,[123,0x201,1,panel_point(255,287)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(255,287)])
        assert r32(uc,symbol('potionL8settingsE'))==3000
        invoke(uc,window_proc,[123,0x201,1,panel_point(150,241)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(150,241)])
        assert r32(uc,symbol('potionL8settingsE'))==3100
        assert (b'CPIntervalMs',b'3100') in saved
        # A typed non-multiple of 100 near the cap must saturate, not exceed it.
        put_global('potionL14draftIntervalsE',599950)
        invoke(uc,window_proc,[123,0x201,1,panel_point(255,287)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(255,287)])
        assert r32(uc,symbol('potionL14draftIntervalsE'))==600000
        put_global('potionL14draftIntervalsE',3100)
        # Fourth channel uses HP with its own binding and no default delay.
        w32(uc,grid+0x130,1);w32(uc,grid+0x138,1);w32(uc,grid+0x160,0)
        w32(uc,bag_item+0x1b1c,1540);w32(uc,bag_item+0x1b20,1540)
        w32(uc,0x102d57b4,1)
        assert invoke(uc,symbol('bagUp'),[1,panel_point(15,179)],ecx=grid)==1
        assert r32(uc,symbol('potionL7itemIdsE')+12)==1540
        assert r32(uc,0x102d57b4)==0, 'drop must unlock the native cursor'
        assert (b'QuickHPItemType',b'1540') in saved
        invoke(uc,window_proc,[123,0x201,1,panel_point(165,179)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(165,179)])
        invoke(uc,window_proc,[123,0x201,1,panel_point(150,241)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(150,241)])
        assert r32(uc,symbol('potionL8settingsE')+36)==0
        w32(uc,potion_user+0x7c,50)
        requests_before=len(potion_requests)
        invoke(uc,symbol('paintHook'),[CANVAS])
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert potion_requests[requests_before:]==[1540,1540], 'percentage mode has no hidden wait'
        w32(uc,potion_user+0x7c,100)
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert len(potion_requests)==requests_before+2
        # All four channels remain low: a CP deficit must not monopolize requests.
        w32(uc,grid+0x130,4)
        for i in range(4):
            ptr=bag_item+i*0x2000
            w32(uc,entries+i*4,ptr)
            for off,val in [(0x1b18,1),(0x1c98,1),(0x1ca0,10),(0x1b1c,10000+i),(0x1b20,20000+i)]:w32(uc,ptr+off,val)
            w32(uc,symbol('potionL5slotsE')+i*4,0xfffffffe)
            w32(uc,symbol('potionL7itemIdsE')+i*4,10000+i)
            w32(uc,symbol('potionL5modesE')+i*4,0)
            uc.mem_write(symbol('potionL8settingsE')+i*12+8,b'\x01')
            w32(uc,symbol('potionL11percentagesE')+i*4,90)
        for off in (0x218,0x7c,0x84):w32(uc,potion_user+off,1)
        put_global('potionL17nextPotionChannelE',0)
        start=len(potion_requests)
        for _ in range(8):invoke(uc,symbol('paintHook'),[CANVAS])
        assert len(potion_requests[start:])==32
        for j in range(8):
            assert set(potion_requests[start+j*4:start+j*4+4])=={10000,10001,10002,10003}, 'all due channels dispatch in the same update'
        assert [potion_requests[start+j*4] for j in range(8)]==[10000,10001,10002,10003]*2
        # Manual input yields without advancing the automatic turn.
        put_global('potionL18manualInputPendingE',1)
        before=len(potion_requests)
        invoke(uc,symbol('paintHook'),[CANVAS]);assert len(potion_requests)==before
        invoke(uc,symbol('paintHook'),[CANVAS]);assert potion_requests[before:]==[10000,10001,10002,10003]
        # Disabled CP is skipped, rather than delaying the other channels.
        uc.mem_write(symbol('potionL8settingsE')+8,b'\x00')
        start=len(potion_requests)
        for _ in range(6):invoke(uc,symbol('paintHook'),[CANVAS])
        assert len(potion_requests[start:])==18
        for j in range(6):assert set(potion_requests[start+j*3:start+j*3+3])=={10001,10002,10003}
        w32(uc,bag_item+0x1b20,1540)
        # New session: inventory may arrive after the actor.
        w32(uc,grid+0x130,0)
        # A real actor identity change still turns automation off.
        uc.mem_write(symbol('potionL8settingsE')+8,b'\x01')
        w32(uc,SELF+0x9860,778)
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert uc.mem_read(symbol('potionL8settingsE')+8,1)==b'\x00'
        assert uc.mem_read(symbol('potionL8settingsE')+44,1)==b'\x00'
        w32(uc,grid+0x130,1);w32(uc,bag_item+0x1b1c,9000)
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert r32(uc,symbol('potionL7itemIdsE')+12)==9000
        assert uc.mem_read(symbol('potionL8settingsE')+44,1)==b'\x01'
        assert (b'QuickHPEnabled',b'1') in saved
        # Renderer reloads must not disable an otherwise identical item.
        w32(uc,bag_item,0x55000100)
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert uc.mem_read(symbol('potionL8settingsE')+44,1)==b'\x01'
        # Replacing the stack/object ID without relogging restores by item type.
        w32(uc,bag_item+0x1b1c,9001)
        invoke(uc,symbol('paintHook'),[CANVAS])
        invoke(uc,symbol('paintHook'),[CANVAS])
        assert r32(uc,symbol('potionL7itemIdsE')+12)==9001
        assert uc.mem_read(symbol('potionL8settingsE')+44,1)==b'\x01'
        # Compact global toggle applies and persists directly, without Apply.
        invoke(uc,window_proc,[123,0x201,1,panel_point(290,10)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(290,10)])
        invoke(uc,window_proc,[123,0x201,1,panel_point(180,20)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(180,20)])
        assert uc.mem_read(symbol('potionL8settingsE')+44,1)==b'\x00'
        assert (b'QuickHPEnabled',b'0') in saved
        invoke(uc,window_proc,[123,0x201,1,panel_point(180,20)])
        invoke(uc,window_proc,[123,0x202,0,panel_point(180,20)])
        assert uc.mem_read(symbol('potionL8settingsE')+44,1)==b'\x01'
        assert uc.mem_read(symbol('potionL9collapsedE'),1)==b'\x01'
        print('x86 autopotion: cursor unlock, saved item type and delayed inventory restoration passed')
        print('x86 autopotion: compact anchor, inventory drop/use/depletion and click deduplication passed')
        print('x86 autopotion: bind/toggle, native item request ABI, cooldown, death and item replacement passed')
        assert credits == [], 'chat must not be modified while painting'
        def message(text, channel=5):
            uc.mem_write(SELF + 0xa000, (text + '\0').encode('utf-16le'))
            invoke(uc, symbol('chatHook'), [SELF + 0xa000, 0xffdcdcdc, channel, 0], ecx=GAME)
        message('Welcome to Lineage II Killer', 0)
        assert len(credits) == 1, 'player chat must not trigger credit'
        message('Other system message')
        assert len(credits) == 2
        message('Welcome to Lineage II Killer')
        assert credits[-2:] == ['Welcome to Lineage II Killer', '[ WT ] Patch by Wender | Enjoy the game!']
        message('Welcome to Lineage II Killer')
        assert credits.count('[ WT ] Patch by Wender | Enjoy the game!') == 1
    print(f'x86 DLL: {count} hit/ABI cases; paint/page restoration, local credit once and Alt/Ctrl+Alt release passed at 2 bases')


def verify_initialization(patched, helper):
    for mode in ('enabled', 'disabled', 'incompatible'):
        uc = emulator()
        nbase, dbase = 0x35000000, 0x25000000
        map_pe(uc, patched, nbase)
        map_pe(uc, helper, dbase)
        syms = symbols(helper, dbase)
        api_addresses = {}
        for desc in helper.imports():
            thunk, i = desc[0], 0
            while helper.u32(helper.offset(thunk + i * 4)):
                hint = helper.u32(helper.offset(thunk + i * 4))
                name = helper.cstring(hint + 2)
                at = 0x70000500 + len(api_addresses) * 16
                api_addresses[at] = name
                w32(uc, dbase + desc[4] + i * 4, at)
                i += 1
        if mode == 'incompatible':
            uc.mem_write(nbase + HIT_RVA, b'\x90')
        original_code = bytes(uc.mem_read(nbase + HIT_RVA, 6))
        original_table = bytes(uc.mem_read(nbase + TABLE_RVA, 0x114))
        logs = []
        calls = []

        def cstring(at):
            data = bytearray()
            while uc.mem_read(at, 1) != b'\0':
                data.extend(uc.mem_read(at, 1)); at += 1
            return bytes(data)

        def hook(uc, address, size, user):
            if address not in api_addresses:
                return
            name = api_addresses[address]
            calls.append(name)
            sp = uc.reg_read(UC_X86_REG_ESP)
            arg = lambda index: r32(uc, sp + 4 * index)
            result = 1
            argc = {'GetModuleFileNameA': 3, 'CreateFileA': 7, 'WriteFile': 5,
                    'FlushFileBuffers': 1, 'GetPrivateProfileIntA': 4,
                    'VirtualAlloc': 4, 'VirtualProtect': 4, 'VirtualFree': 3,
                    'GetCurrentProcess': 0, 'FlushInstructionCache': 3}[name]
            if name == 'GetModuleFileNameA':
                path = b'C:\\LineageII\\system\\NWindow.dll'
                assert arg(1) == nbase
                uc.mem_write(arg(2), path + b'\0'); result = len(path)
            elif name == 'CreateFileA':
                assert cstring(arg(1)).endswith(b'\\C4Bars.log')
                result = 123
            elif name == 'WriteFile':
                logs.append(bytes(uc.mem_read(arg(2), arg(3))))
                w32(uc, arg(4), arg(3))
            elif name == 'GetPrivateProfileIntA':
                key = cstring(arg(2))
                result = 0 if key == b'Enabled' and mode == 'disabled' else arg(3)
            elif name == 'VirtualAlloc':
                uc.mem_map(0x52000000, 4096); result = 0x52000000
            elif name == 'VirtualProtect':
                w32(uc, arg(4), 0x20)
            return_from_stub(uc, argc, result)

        uc.hook_add(UC_HOOK_CODE, hook)
        result = invoke(uc, syms['_C4BarsInitialize'], [nbase], cdecl=True)
        code = bytes(uc.mem_read(nbase + HIT_RVA, 6))
        table = bytes(uc.mem_read(nbase + TABLE_RVA, 0x114))
        if mode == 'enabled':
            assert result == 1 and code[0] == 0xe9 and code[-1] == 0x90
            assert original_table != table and b'hooks installed' in b''.join(logs)
            dest = nbase + HIT_RVA + 5 + struct.unpack('<i', code[1:5])[0]
            assert dest == syms['_C4BarsHitBridge']
            assert calls.count('VirtualAlloc') == 1
        else:
            assert result == (1 if mode == 'disabled' else 0)
            assert code == original_code and table == original_table
            assert 'VirtualAlloc' not in calls
        assert invoke(uc, syms['_C4BarsInitialize'], [nbase], cdecl=True)==result
    print('x86 initialization: install, disabled config and incompatible-version refusal passed')


def verify_native_text(original):
    uc=emulator();map_pe(uc,original,0x10000000)
    renderer,table,content=SELF+0x2000,SELF+0x3000,SELF+0x4000
    w32(uc,CANVAS+0x34,renderer);w32(uc,renderer,table)
    w32(uc,table+0xb8,0x70000900)
    w32(uc,CANVAS+0x38,530);w32(uc,CANVAS+0x3c,165)
    calls=[]
    def hook(uc,address,size,user):
        sp=uc.reg_read(UC_X86_REG_ESP)
        if address==0x10012ae0:
            out=r32(uc,sp+4);w32(uc,out,80);w32(uc,out+4,12)
            return_from_stub(uc,0,1)  # cdecl: caller removes eight arguments.
        elif address==0x70000900:
            assert uc.reg_read(UC_X86_REG_ECX)==renderer
            assert r32(uc,sp+4)==540 and r32(uc,sp+8)==172
            assert r32(uc,sp+16)==content
            assert all(r32(uc,sp+4*i)==0 for i in range(5,20))
            calls.append(bytes(uc.mem_read(content,100)))
            return_from_stub(uc,19,1)
    uc.hook_add(UC_HOOK_CODE,hook)
    for label in ('CP','HP','MANA','Ligar','Aplicar','Uso automático de poções'):
        data=(label+'\0').encode('utf-16le');uc.mem_write(content,data+b'\0'*(100-len(data)))
        assert invoke(uc,0x10012c20,[10,7,0xffdfbf78,content]+[0]*11,ecx=CANVAS)==1
        assert calls[-1].startswith(data)
    print('native NCanvas text: original x86 routine forwards complete labels; 15-argument stack verified')


if __name__ == '__main__':
    old, new, dll = verify_pe()
    verify_entry(old, new)
    verify_hooks(dll)
    verify_native_text(old)
    verify_initialization(new, dll)
