// Included inside namespace potion. Observe actual native item requests from
// both inventory and shortcuts, never cursor location or keyboard focus.
bool manualPriorityAttempted=false,manualRequestPending=false;
bool manualRequestWaiting(){return manualRequestPending;}
unsigned __fastcall manualUseItem(void *console,void *,unsigned objectId) {
    // Protect only a reentrant tick during this native call. No response wait.
    const bool outer=manualRequestPending;
    manualRequestPending=true;
    const unsigned result=useItem(console,objectId);
    manualRequestPending=outer;
    return result;
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
    const unsigned char expected[5]={0x55,0x8b,0xec,0x6a,0xff};
    if(!equalBytes(entry,expected,5))return;
    auto *bridge=static_cast<unsigned char *>(VirtualAlloc(nullptr,16,MEM_RESERVE|MEM_COMMIT,PAGE_READWRITE));
    if(!bridge)return;
    copyBytes(bridge,entry,5);
    priorityJump(bridge+5,entry+5);
    DWORD oldBridge,oldEntry;
    if(!VirtualProtect(bridge,16,PAGE_EXECUTE_READ,&oldBridge)) {
        VirtualFree(bridge,0,MEM_RELEASE);return;
    }
    if(!VirtualProtect(entry,5,PAGE_EXECUTE_READWRITE,&oldEntry)) {
        VirtualFree(bridge,0,MEM_RELEASE);return;
    }
    useItem=reinterpret_cast<UseItem>(bridge);
    priorityJump(entry,reinterpret_cast<void *>(&manualUseItem));
    DWORD ignored;
    VirtualProtect(entry,5,oldEntry,&ignored);
    FlushInstructionCache(GetCurrentProcess(),bridge,16);
    FlushInstructionCache(GetCurrentProcess(),entry,5);
    log("autopotion: native manual item priority installed\r\n");
}
