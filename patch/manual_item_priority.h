// Included inside namespace potion. Observe actual native item requests from
// both inventory and shortcuts, never cursor location or keyboard focus.
using ItemList = void (__thiscall *)(void *,int);
using ItemUpdate = void (__thiscall *)(void *);
ItemList originalItemList=nullptr;
ItemUpdate originalItemUpdate=nullptr;
bool manualPriorityAttempted=false,manualRequestPending=false;
unsigned manualRequestStarted=0,manualRequestSerial=0;

bool manualRequestWaiting() {
    if(!manualRequestPending)return false;
    // Rejected/lost requests need not produce an inventory update. This is a
    // recovery bound for a manual request, not an automatic potion interval.
    if(static_cast<unsigned>(GetTickCount()-manualRequestStarted)>=2000) {
        manualRequestPending=false;
        log("autopotion: manual request recovery\r\n");
    }
    return manualRequestPending;
}
unsigned __fastcall manualUseItem(void *console,void *,unsigned objectId) {
    const unsigned serial=++manualRequestSerial;
    manualRequestStarted=GetTickCount();
    manualRequestPending=true;
    const unsigned result=useItem(console,objectId);
    if(!result&&serial==manualRequestSerial)manualRequestPending=false;
    return result;
}
void __fastcall manualItemList(void *console,void *,int show) {
    const unsigned serial=manualRequestSerial;
    originalItemList(console,show);
    if(serial==manualRequestSerial)manualRequestPending=false;
}
void __fastcall manualItemUpdate(void *console,void *) {
    const unsigned serial=manualRequestSerial;
    originalItemUpdate(console);
    if(serial==manualRequestSerial)manualRequestPending=false;
}
void priorityJump(unsigned char *at,const void *target) {
    at[0]=0xe9;
    const unsigned delta=reinterpret_cast<uintptr_t>(target)-reinterpret_cast<uintptr_t>(at)-5;
    copyBytes(at+1,&delta,4);
}
__attribute__((noinline)) void installManualItemPriority() {
    if(manualPriorityAttempted)return;
    manualPriorityAttempted=true;
    unsigned char *entry=moduleBase+0x66480;
    auto *callbacks=reinterpret_cast<uintptr_t *>(moduleBase+0x1b3548);
    const unsigned char expected[5]={0x55,0x8b,0xec,0x6a,0xff};
    if(!equalBytes(entry,expected,5)||callbacks[0]!=reinterpret_cast<uintptr_t>(moduleBase+0x66570)
       ||callbacks[1]!=reinterpret_cast<uintptr_t>(moduleBase+0x66620))return;
    auto *bridge=static_cast<unsigned char *>(VirtualAlloc(nullptr,16,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
    if(!bridge)return;
    copyBytes(bridge,entry,5);
    priorityJump(bridge+5,entry+5);
    DWORD oldBridge,oldEntry,oldCallbacks;
    if(!VirtualProtect(bridge,16,PAGE_EXECUTE_READ,&oldBridge)) {
        VirtualFree(bridge,0,MEM_RELEASE);return;
    }
    if(!VirtualProtect(entry,5,PAGE_EXECUTE_READWRITE,&oldEntry)) {
        VirtualFree(bridge,0,MEM_RELEASE);return;
    }
    if(!VirtualProtect(callbacks,8,PAGE_READWRITE,&oldCallbacks)) {
        DWORD ignored;VirtualProtect(entry,5,oldEntry,&ignored);
        VirtualFree(bridge,0,MEM_RELEASE);return;
    }
    originalItemList=reinterpret_cast<ItemList>(callbacks[0]);
    originalItemUpdate=reinterpret_cast<ItemUpdate>(callbacks[1]);
    // Auto requests use the original trampoline directly. Only native/manual
    // callers traverse the entry hook and reserve the item path.
    useItem=reinterpret_cast<UseItem>(bridge);
    callbacks[0]=reinterpret_cast<uintptr_t>(&manualItemList);
    callbacks[1]=reinterpret_cast<uintptr_t>(&manualItemUpdate);
    priorityJump(entry,reinterpret_cast<void *>(&manualUseItem));
    DWORD ignored;
    VirtualProtect(callbacks,8,oldCallbacks,&ignored);
    VirtualProtect(entry,5,oldEntry,&ignored);
    FlushInstructionCache(GetCurrentProcess(),bridge,16);
    FlushInstructionCache(GetCurrentProcess(),entry,5);
    log("autopotion: native manual item priority installed\r\n");
}
