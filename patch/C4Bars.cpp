#define WIN32_LEAN_AND_MEAN
#include <windows.h>
#include <stdint.h>
#include "layout.h"
#include "profile.h"
#include "potion_policy.h"

// This DLL is specific to the SHA-256 recorded by build_patch.py. All addresses
// are RVAs, and original vtable entries/prologue bytes are checked before writes.
// No thread, network operation or LoadLibrary call occurs in initialization.
namespace {
using Paint = int (__thiscall *)(void *, void *);
using Hit = int (__thiscall *)(void *, int, int);
using Mouse = int (__thiscall *)(void *, unsigned, unsigned);
using Console = int (__thiscall *)(void *, unsigned, unsigned, unsigned);
using Clip = void (__thiscall *)(void *, int, int, int, int);
using PopClip = void (__thiscall *)(void *);
Paint originalPaint;
Paint originalTooltip;
Mouse originalMouseMove;
int hoveredRow = 0;
Hit originalHit, originalBounds;
Mouse originalMouseDown;
Console originalConsole;
Clip pushClip;
PopClip popClip;
int barCount = 3;
int secondPage = 1, thirdPage = 2;
int thirdModifier = 0;
int heldPages[12] = {-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1,-1};
char iniPath[MAX_PATH];
HANDLE logFile = INVALID_HANDLE_VALUE;
bool loggedPaint = false;
bool creditShown = false;
bool creditEnabled = true;
using Chat = void (__thiscall *)(void *, const wchar_t *, unsigned, unsigned, unsigned);
Chat originalChat;
LONG initialized = 0;

template <class T> T &field(void *object, unsigned offset) {
    return *reinterpret_cast<T *>(static_cast<unsigned char *>(object) + offset);
}
void copyBytes(void *to, const void *from, unsigned size) {
    auto *d = static_cast<unsigned char *>(to);
    auto *s = static_cast<const unsigned char *>(from);
    for (unsigned i = 0; i < size; ++i) d[i] = s[i];
}
bool equalBytes(const void *a, const void *b, unsigned size) {
    auto *x = static_cast<const unsigned char *>(a);
    auto *y = static_cast<const unsigned char *>(b);
    for (unsigned i = 0; i < size; ++i) if (x[i] != y[i]) return false;
    return true;
}
unsigned length(const char *s) { unsigned n = 0; while (s[n]) ++n; return n; }
void log(const char *s) {
    if (logFile == INVALID_HANDLE_VALUE) return;
    // Bound diagnostics and let Windows buffer writes; never fsync the game
    // thread for each fragment. Process teardown closes the handle normally.
    static unsigned total=0;
    const unsigned size=length(s);
    if(size>65536-total)return;
    DWORD written=0;
    if(WriteFile(logFile,s,size,&written,nullptr))total+=written;

}
void number(int value) {
    char text[16];
    unsigned n = 0;
    unsigned v = value < 0 ? 0u - static_cast<unsigned>(value) : static_cast<unsigned>(value);
    do { text[n++] = static_cast<char>('0' + v % 10); v /= 10; } while (v);
    if (value < 0) text[n++] = '-';
    for (unsigned a = 0, b = n - 1; a < b; ++a, --b) {
        char temp = text[a]; text[a] = text[b]; text[b] = temp;
    }
    text[n] = 0; log(text);
}
bool supported(void *self) {
    return self && field<int>(self, 0x1f8) == 0
        && field<int>(self, 0x268) == c4bars::kSlots
        && field<int>(self, 0x26c) == c4bars::kPages
        && field<int>(self, 0x274) == c4bars::kSlotSize
        && field<int>(self, 0x270) >= 0 && field<int>(self, 0x270) < c4bars::kPages
        && field<void *>(self, 0x200) && field<void *>(self, 0x1fc);
}
c4bars::Layout layout(void *self) {
    return {field<int>(self, 0x44), field<int>(self, 0x48),
            field<int>(self, 0x270), barCount, field<int>(self, 0x264) != 0,
            secondPage, thirdPage};
}

#include "auto_potion.h"
#include "target_equipment.h"
void putJump(unsigned char *at, const void *target);
#include "local_appearance.h"

bool containsAscii(const wchar_t *text, const char *needle) {
    if (!text) return false;
    for (unsigned i = 0; i < 1024 && text[i]; ++i) {
        unsigned j = 0;
        while (needle[j] && i + j < 1024) {
            wchar_t c = text[i + j];
            if (c >= L'A' && c <= L'Z') c += L'a' - L'A';
            if (c != static_cast<unsigned char>(needle[j])) break;
            ++j;
        }
        if (!needle[j]) return true;
    }
    return false;
}

void __fastcall chatHook(void *self, void *, const wchar_t *text,
                        unsigned color, unsigned channel, unsigned attribute) {
    const bool welcome = creditEnabled && !creditShown && (channel == 5 || channel == 10)
        && containsAscii(text, "welcome") && containsAscii(text, "lineage");
    if (welcome) creditShown = true; // prevent reentrant duplicate messages
    originalChat(self, text, color, channel, attribute);
    if (welcome) {
        originalChat(self, L"[ WT ] Patch by Wender | Enjoy the game!", 0xffffd36a, 5, 0xffb09b79);
        log("credit: added immediately after Welcome\r\n");
    }
}

int __fastcall tooltipHook(void *self, void *, void *canvas);

int __fastcall paintHook(void *self, void *, void *canvas) {
    if (!supported(self)) return originalPaint(self, canvas);
    const auto geometry = layout(self);
    // Native UI dispatch does not deliver hover events outside the original
    // rectangle. Sample client coordinates for the two additional rectangles.
    POINT cursor;
    HWND window = GetForegroundWindow();
    DWORD owner = 0;
    if (window) GetWindowThreadProcessId(window, &owner);
    if (owner == GetCurrentProcessId() && GetCursorPos(&cursor)
        && ScreenToClient(window, &cursor)) {
        const int row = geometry.rowAt(cursor.x, cursor.y);
        if (row > 0) {
            hoveredRow = row;
            field<int>(self, 0x27c) = geometry.hit(cursor.x, cursor.y);
        } else if (hoveredRow > 0) {
            hoveredRow = 0;
            field<int>(self, 0x27c) = -1;
        }
    }
    if (!loggedPaint) {
        loggedPaint = true;
        log("first paint: x="); number(geometry.x);
        log(" y="); number(geometry.y);
        log(" horizontal="); number(geometry.horizontal);
        log(" bars="); number(barCount); log("\r\n");
    }
    // One native object and one shared set of 120 slots. Render it at three
    // temporary origins; restore its identity/page before dispatching any input.
    int result = 1;
    for (int row = barCount - 1; row >= 0; --row) {
        field<int>(self, 0x44) = geometry.x + geometry.dx(row);
        field<int>(self, 0x48) = geometry.y + geometry.dy(row);
        field<int>(self, 0x270) = geometry.rowPage(row);
        result = originalPaint(self, canvas);
        if (row > 0) {
            const int oldX = field<int>(canvas, 0x38), oldY = field<int>(canvas, 0x3c);
            field<int>(canvas, 0x38) = geometry.x + geometry.dx(row);
            field<int>(canvas, 0x3c) = geometry.y + geometry.dy(row);
            pushClip(canvas, field<int>(self, 0x44), field<int>(self, 0x48),
                     static_cast<int>(field<float>(self, 0x4c)),
                     static_cast<int>(field<float>(self, 0x50)));
            for (unsigned offset = 0x24c; offset <= 0x250; offset += 4) {
                void *button = field<void *>(self, offset);
                if (!button) continue;
                const int bx = field<int>(button, 0x44), by = field<int>(button, 0x48);
                const int cross = offset == 0x24c ? 31 : 1;
                field<int>(button, 0x44) = geometry.x + geometry.dx(row) + (geometry.horizontal ? 13 : cross);
                field<int>(button, 0x48) = geometry.y + geometry.dy(row) + (geometry.horizontal ? cross : 13);
                auto *vtable = field<uintptr_t *>(button, 0);
                reinterpret_cast<Paint>(vtable[0xf8 / 4])(button, canvas);
                field<int>(button, 0x44) = bx;
                field<int>(button, 0x48) = by;
            }
            popClip(canvas);
            field<int>(canvas, 0x38) = oldX;
            field<int>(canvas, 0x3c) = oldY;
        }
    }
    field<int>(self, 0x44) = geometry.x;
    field<int>(self, 0x48) = geometry.y;
    field<int>(self, 0x270) = geometry.page;
    // The original controls occupy 489,1 and 489,16 (horizontal). Use the
    // remaining 15x15 area for a native-font expand/collapse button.
    const int oldX = field<int>(canvas, 0x38), oldY = field<int>(canvas, 0x3c);
    field<int>(canvas, 0x38) = geometry.x;
    field<int>(canvas, 0x3c) = geometry.y;
    pushClip(canvas, geometry.x, geometry.y, static_cast<int>(field<float>(self, 0x4c)),
             static_cast<int>(field<float>(self, 0x50)));
    void *toggle = field<void *>(self, barCount > 1 ? 0x24c : 0x250);
    if (toggle) {
        const int bx = field<int>(toggle, 0x44), by = field<int>(toggle, 0x48);
        field<int>(toggle, 0x44) = geometry.x + (geometry.horizontal ? 489 : 31);
        field<int>(toggle, 0x48) = geometry.y + (geometry.horizontal ? 31 : 489);
        auto *vtable = field<uintptr_t *>(toggle, 0);
        reinterpret_cast<Paint>(vtable[0xf8 / 4])(toggle, canvas);
        field<int>(toggle, 0x44) = bx;
        field<int>(toggle, 0x48) = by;
    }
    popClip(canvas);
    field<int>(canvas, 0x38) = oldX;
    field<int>(canvas, 0x3c) = oldY;
    if (hoveredRow > 0 && hoveredRow < barCount && field<int>(self, 0x27c) >= 0)
        tooltipHook(self, nullptr, canvas);
    targetEquipment::install();
    appearance::install();
    appearance::apply();
    potion::paint(self, canvas);
    return result;
}

int __fastcall boundsHook(void *self, void *, int x, int y) {
    if (!supported(self)) return originalBounds(self, x, y);
    if ((!potion::configWindow||potion::collapsed)&&potion::inside(x, y)) return 1;
    const auto geometry = layout(self);
    for (int row = 0; row < barCount; ++row)
        if (originalBounds(self, x - geometry.dx(row), y - geometry.dy(row))) return 1;
    return 0;
}

int __fastcall mouseMoveHook(void *self, void *, unsigned flags, unsigned packed) {
    hoveredRow = 0;
    if (supported(self)) {
        const auto g = layout(self);
        const int x = packed & 0xffff, y = packed >> 16;
        const int row = g.rowAt(x, y);
        hoveredRow = row < 0 ? 0 : row;
    }
    const int result = originalMouseMove(self, flags, packed);
    return result;
}

int __fastcall tooltipHook(void *self, void *, void *canvas) {
    if (!supported(self) || hoveredRow == 0 || hoveredRow >= barCount)
        return originalTooltip(self, canvas);
    const auto g = layout(self);
    field<int>(self, 0x44) = g.x + g.dx(hoveredRow);
    field<int>(self, 0x48) = g.y + g.dy(hoveredRow);
    field<int>(self, 0x270) = g.rowPage(hoveredRow);
    const int result = originalTooltip(self, canvas);
    field<int>(self, 0x270) = g.page;
    field<int>(self, 0x44) = g.x;
    field<int>(self, 0x48) = g.y;
    return result;
}

int __fastcall mouseDownHook(void *self, void *, unsigned flags, unsigned packed) {
    if (supported(self)) {
        // Once the viewport owns potion input, native dispatch must not execute
        // the same button action a second time.
        if (potion::previousWndProc) {
            if (((!potion::configWindow||potion::collapsed)&&
                 potion::inside(packed & 0xffff, packed >> 16)) || potion::ownedClick) return 1;
        } else if (potion::click(self, packed & 0xffff, packed >> 16)) return 1;
    }
    if (supported(self)) {
        const auto geometry = layout(self);
        const int x = static_cast<int>(packed & 0xffff) - geometry.x;
        const int y = static_cast<int>(packed >> 16) - geometry.y;
        const int along = geometry.horizontal ? x : y;
        const int cross = geometry.horizontal ? y : x;
        for (int row = 1; row < barCount; ++row) {
            const int rx = x - geometry.dx(row), ry = y - geometry.dy(row);
            const int a = geometry.horizontal ? rx : ry;
            const int c = geometry.horizontal ? ry : rx;
            if (a >= 0 && a < 33 && c >= 0 && c < 46) {
                int &page = row == 1 ? secondPage : thirdPage;
                page = (page + (c < 23 ? 9 : 1)) % c4bars::kPages;
                field<int>(self, 0x278) = field<int>(self, 0x27c) = -1;
                field<int>(self, 0x260) = field<int>(self, 0x25c) = 0;
                char value[3] = {static_cast<char>('0' + (page + 1) / 10),
                                 static_cast<char>('0' + (page + 1) % 10), 0};
                WritePrivateProfileStringA("C4Bars", row == 1 ? "SecondPage" : "ThirdPage", value, iniPath);
                log("page selector: row="); number(row + 1); log(" page="); number(page + 1); log("\r\n");
                return 1;
            }
        }
        if (along >= 489 && along < 504 && cross >= 31 && cross < 46) {
            barCount = barCount > 1 ? 1 : 3;
            hoveredRow = 0;
            field<int>(self, 0x278) = field<int>(self, 0x27c) = -1;
            field<int>(self, 0x260) = field<int>(self, 0x25c) = 0;
            char value[2] = {static_cast<char>('0' + barCount), 0};
            WritePrivateProfileStringA("C4Bars", "Bars", value, iniPath);
            log("visible bars="); number(barCount); log("\r\n");
            return 1;
        }
    }
    const int result = originalMouseDown(self, flags, packed);
    return result;
}

int __fastcall consoleHook(void *self, void *, unsigned message, unsigned key, unsigned flags) {
    if((message==WM_KEYDOWN||message==WM_SYSKEYDOWN)&&key>=VK_F1&&key<=VK_F12)
        potion::manualInputPending=true;
    if(potion::consumeWorldMouse(message,key))return 1;
    if(potion::editing>=0 && (message==WM_CHAR ||
       ((message==WM_KEYDOWN||message==WM_KEYUP) &&
        ((key>='0'&&key<='9')||(key>=VK_NUMPAD0&&key<=VK_NUMPAD9)||
         key==VK_BACK||key==VK_RETURN||key==VK_ESCAPE))))return 1;
    const bool down = message == WM_KEYDOWN || message == WM_SYSKEYDOWN;
    const bool up = message == WM_KEYUP || message == WM_SYSKEYUP;
    if ((!down && !up) || key < VK_F1 || key > VK_F12)
        return originalConsole(self, message, key, flags);
    void *game = field<void *>(self, 0x3bf4);
    void *shortcut = game ? field<void *>(game, 0x15c) : nullptr;
    if (!supported(shortcut)) return originalConsole(self, message, key, flags);
    const unsigned slot = key - VK_F1;
    int page = heldPages[slot];
    if (down && page < 0) {
        const bool alt = (GetKeyState(VK_MENU) & 0x8000) != 0;
        const bool ctrl = (GetKeyState(VK_CONTROL) & 0x8000) != 0;
        const bool shift = (GetKeyState(VK_SHIFT) & 0x8000) != 0;
        int row = 0;
        if ((thirdModifier == 0 && ctrl && alt) || (thirdModifier == 1 && shift && !alt)) row = 2;
        else if (alt && !ctrl) row = 1;
        if (row == 0 || row >= barCount) return originalConsole(self, message, key, flags);
        page = layout(shortcut).rowPage(row);
        heldPages[slot] = page;
        log("key: page="); number(page + 1); log(" slot="); number(slot + 1); log("\r\n");
    }
    if (page < 0) return originalConsole(self, message, key, flags);
    const int savedPage = field<int>(shortcut, 0x270);
    field<int>(shortcut, 0x270) = page;
    // Route Alt system-key events through the same native shortcut path as F1.
    // Remember the page until key-up, even if Alt is released first.
    originalConsole(self, down ? WM_KEYDOWN : WM_KEYUP, key, flags & ~(1u << 29));
    field<int>(shortcut, 0x270) = savedPage;
    if (up) heldPages[slot] = -1;
    return 1;
}

void putJump(unsigned char *at, const void *to) {
    at[0] = 0xe9;
    const uint32_t delta = static_cast<uint32_t>(reinterpret_cast<uintptr_t>(to)
                        - reinterpret_cast<uintptr_t>(at) - 5);
    copyBytes(at + 1, &delta, 4);
}
}

extern "C" int __cdecl C4BarsHitC(void *self, int x, int y) {
    if (!supported(self)) return originalHit(self, x, y);
    return layout(self).hit(x, y);
}

// The original private hit routine preserves ECX. OnMouseDown relies on that
// stronger-than-thiscall contract. Preserve ECX/EDX explicitly around C++ code.
extern "C" __attribute__((naked)) int C4BarsHitBridge() {
    __asm__ volatile(
        "push %ecx\n"
        "push %edx\n"
        "push 16(%esp)\n" // y
        "push 16(%esp)\n" // x, after the previous push
        "push %ecx\n"
        "call _C4BarsHitC\n"
        "add $12, %esp\n"
        "pop %edx\n"
        "pop %ecx\n"
        "ret $8\n");
}

extern "C" __declspec(dllexport) int __cdecl C4BarsInitialize(HMODULE module) {
    const LONG previous=InterlockedCompareExchange(&initialized,-1,0);
    if(previous)return previous==1; // Never report success after a failed install.
    char path[MAX_PATH];
    const DWORD n = GetModuleFileNameA(module, path, MAX_PATH);
    if (n == 0 || n >= MAX_PATH) return 0;
    unsigned start = n;
    while (start && path[start - 1] != '\\' && path[start - 1] != '/') --start;
    if (start + 16 >= MAX_PATH) return 0;
    copyBytes(path + start, "C4Bars.log", 11);
    logFile = CreateFileA(path, GENERIC_WRITE, FILE_SHARE_READ, nullptr, CREATE_ALWAYS,
                          FILE_ATTRIBUTE_NORMAL, nullptr);
    log("C4Bars independent pages - initialization\r\n");
    copyBytes(path + start, "C4Bars.ini", 11);
    copyBytes(iniPath, path, length(path) + 1);
    if (!GetPrivateProfileIntA("C4Bars", "Enabled", 1, path)) {
        log("disabled by C4Bars.ini\r\n"); initialized=1;return 1;
    }
    barCount = static_cast<int>(GetPrivateProfileIntA("C4Bars", "Bars", 3, path));
    if (barCount < 1 || barCount > 3) barCount = 3;
    thirdModifier = GetPrivateProfileIntA("C4Bars", "ThirdModifier", 0, path) == 1 ? 1 : 0;
    creditEnabled = GetPrivateProfileIntA("C4Bars", "ShowCredit", 1, path) != 0;
    secondPage = GetPrivateProfileIntA("C4Bars", "SecondPage", 2, path) - 1;
    thirdPage = GetPrivateProfileIntA("C4Bars", "ThirdPage", 3, path) - 1;
    if (secondPage < 0 || secondPage >= 10) secondPage = 1;
    if (thirdPage < 0 || thirdPage >= 10) thirdPage = 2;
    auto *base = reinterpret_cast<unsigned char *>(module);
    potion::init(base);
    auto *table = reinterpret_cast<uintptr_t *>(base + c4rva(0x1cbd68));
    const unsigned char expectedHit[6] = {0x8b, 0x91, 0x64, 0x02, 0x00, 0x00};
    const unsigned char expectedConsole[5] = {0x55, 0x8b, 0xec, 0x6a, 0xff};
    const unsigned char expectedMessage[5] = {0x55, 0x8b, 0x6c, 0x24, 0x10};
    const uintptr_t address = reinterpret_cast<uintptr_t>(base);
    if (table[0xf8 / 4] != address + c4rva(0x107b20) || table[0x6c / 4] != address + c4rva(0x349f0)
        || table[0xfc / 4] != address + c4rva(0x1097e0)
        || table[0x10c / 4] != address + c4rva(0x107c60)
        || table[0x110 / 4] != address + c4rva(0x107c00)
        || !equalBytes(base + c4rva(0x1060f0), expectedHit, 6)
        || !equalBytes(base + c4rva(0x75fe0), expectedConsole, 5)
        || !equalBytes(base + c4rva(0x52f40), expectedMessage, 5)) {
        log("ERROR: incompatible addresses; no hooks installed\r\n"); return 0;
    }
    auto *trampoline = static_cast<unsigned char *>(VirtualAlloc(nullptr, 48,
                        MEM_RESERVE | MEM_COMMIT, PAGE_READWRITE));
    if (!trampoline) { log("ERROR: trampoline allocation\r\n"); return 0; }
    copyBytes(trampoline, base + c4rva(0x1060f0), 6);
    putJump(trampoline + 6, base + c4rva(0x1060f6));
    copyBytes(trampoline + 16, base + c4rva(0x75fe0), 5);
    putJump(trampoline + 21, base + c4rva(0x75fe5));
    copyBytes(trampoline + 32, base + c4rva(0x52f40), 5);
    putJump(trampoline + 37, base + c4rva(0x52f40) + 5);
    DWORD oldTrampoline, oldTable, oldCode, oldConsole, oldChat;
    if (!VirtualProtect(trampoline, 48, PAGE_EXECUTE_READ, &oldTrampoline)) {
        VirtualFree(trampoline, 0, MEM_RELEASE); return 0;
    }
    if (!VirtualProtect(table, 0x114, PAGE_READWRITE, &oldTable)) {
        log("ERROR: vtable protection\r\n"); VirtualFree(trampoline, 0, MEM_RELEASE); return 0;
    }
    if (!VirtualProtect(base + c4rva(0x1060f0), 6, PAGE_EXECUTE_READWRITE, &oldCode)) {
        DWORD ignored; VirtualProtect(table, 0x114, oldTable, &ignored);
        log("ERROR: code protection\r\n"); VirtualFree(trampoline, 0, MEM_RELEASE); return 0;
    }
    if (!VirtualProtect(base + c4rva(0x75fe0), 5, PAGE_EXECUTE_READWRITE, &oldConsole)) {
        DWORD ignored;
        VirtualProtect(base + c4rva(0x1060f0), 6, oldCode, &ignored);
        VirtualProtect(table, 0x114, oldTable, &ignored);
        log("ERROR: keyboard code protection\r\n"); VirtualFree(trampoline, 0, MEM_RELEASE); return 0;
    }
    if (!VirtualProtect(base + c4rva(0x52f40), 5, PAGE_EXECUTE_READWRITE, &oldChat)) {
        DWORD ignored;
        VirtualProtect(base + c4rva(0x75fe0), 5, oldConsole, &ignored);
        VirtualProtect(base + c4rva(0x1060f0), 6, oldCode, &ignored);
        VirtualProtect(table, 0x114, oldTable, &ignored);
        VirtualFree(trampoline, 0, MEM_RELEASE); return 0;
    }
    originalChat = reinterpret_cast<Chat>(trampoline + 32);
    originalPaint = reinterpret_cast<Paint>(table[0xf8 / 4]);
    originalTooltip = reinterpret_cast<Paint>(table[0xfc / 4]);
    originalMouseMove = reinterpret_cast<Mouse>(table[0x10c / 4]);
    originalBounds = reinterpret_cast<Hit>(table[0x6c / 4]);
    originalMouseDown = reinterpret_cast<Mouse>(table[0x110 / 4]);
    originalHit = reinterpret_cast<Hit>(trampoline);
    originalConsole = reinterpret_cast<Console>(trampoline + 16);
    pushClip = reinterpret_cast<Clip>(base + c4rva(0x13330));
    popClip = reinterpret_cast<PopClip>(base + c4rva(0x13340));
    table[0xf8 / 4] = reinterpret_cast<uintptr_t>(&paintHook);
    table[0xfc / 4] = reinterpret_cast<uintptr_t>(&tooltipHook);
    table[0x10c / 4] = reinterpret_cast<uintptr_t>(&mouseMoveHook);
    table[0x6c / 4] = reinterpret_cast<uintptr_t>(&boundsHook);
    table[0x110 / 4] = reinterpret_cast<uintptr_t>(&mouseDownHook);
    putJump(base + c4rva(0x1060f0), reinterpret_cast<void *>(&C4BarsHitBridge));
    base[c4rva(0x1060f5)] = 0x90;
    putJump(base + c4rva(0x75fe0), reinterpret_cast<void *>(&consoleHook));
    putJump(base + c4rva(0x52f40), reinterpret_cast<void *>(&chatHook));
    DWORD ignored;
    VirtualProtect(base + c4rva(0x52f40), 5, oldChat, &ignored);
    FlushInstructionCache(GetCurrentProcess(), base + c4rva(0x52f40), 5);
    VirtualProtect(base + c4rva(0x1060f0), 6, oldCode, &ignored);
    VirtualProtect(table, 0x114, oldTable, &ignored);
    VirtualProtect(base + c4rva(0x75fe0), 5, oldConsole, &ignored);
    FlushInstructionCache(GetCurrentProcess(), trampoline, 48);
    FlushInstructionCache(GetCurrentProcess(), base + c4rva(0x1060f0), 6);
    FlushInstructionCache(GetCurrentProcess(), base + c4rva(0x75fe0), 5);
    log("hooks installed: paint, bounds, hit, mouse, keyboard, tooltip\r\n");
    initialized=1;
    return 1;
}

extern "C" BOOL WINAPI DllMain(HINSTANCE, DWORD reason, LPVOID) {
    if (reason == DLL_PROCESS_DETACH && logFile != INVALID_HANDLE_VALUE) {
        CloseHandle(logFile); logFile = INVALID_HANDLE_VALUE;
    }
    return TRUE;
}
