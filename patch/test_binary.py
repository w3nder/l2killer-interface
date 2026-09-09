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
                ('originalTooltip', 1), ('originalMouseMove', 2))):
            address = 0x70000200 + index * 16
            put_global(name, address)
            stub_targets[address] = (name, argc)
        get_key_state = 0x70000400
        w32(uc, symbol('__imp__GetKeyState@4'), get_key_state)
        save_ini = 0x70000410
        w32(uc, symbol('__imp__WritePrivateProfileStringA@16'), save_ini)
        saved = []
        button_calls = []
        cursor_position = None
        titles = []
        cursor_apis = {}
        for i, (name, argc) in enumerate((('GetForegroundWindow', 0), ('GetWindowThreadProcessId', 2),
                ('GetCurrentProcessId', 0), ('GetCursorPos', 1), ('ScreenToClient', 2))):
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

        def hook(uc, address, size, user):
            sp = uc.reg_read(UC_X86_REG_ESP)
            if address in cursor_apis:
                name, argc = cursor_apis[address]
                result = 1
                if name == 'GetForegroundWindow': result = 123 if cursor_position else 0
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
        assert credits == [], 'chat must not be modified while painting'
        def message(text, channel=5):
            uc.mem_write(SELF + 0xa000, (text + '\0').encode('utf-16le'))
            invoke(uc, symbol('chatHook'), [SELF + 0xa000, 0xffdcdcdc, channel, 0], ecx=GAME)
        message('Welcome to Lineage II Killer', 0)
        assert len(credits) == 1, 'player chat must not trigger credit'
        message('Other system message')
        assert len(credits) == 2
        message('Welcome to Lineage II Killer')
        assert credits[-2:] == ['Welcome to Lineage II Killer', '[ WT ] Patch desenvolvido por Wender | Bom jogo!']
        message('Welcome to Lineage II Killer')
        assert credits.count('[ WT ] Patch desenvolvido por Wender | Bom jogo!') == 1
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
    print('x86 initialization: install, disabled config and incompatible-version refusal passed')


if __name__ == '__main__':
    old, new, dll = verify_pe()
    verify_entry(old, new)
    verify_hooks(dll)
    verify_initialization(new, dll)
