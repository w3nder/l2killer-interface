// Included inside namespace potion. Addresses apply only to the locked C4 build.
// Each instance retains the client's UObject allocation and window-manager node.
namespace native {
using Action = int (__thiscall *)(void *);
using Position = void (__thiscall *)(void *,int,int,int,int,int,int,int);
using Event = int (__thiscall *)(void *,unsigned,unsigned,unsigned);
using Allocate = void *(__cdecl *)(void *,void *,unsigned,unsigned,void *,void *,void *,void *);
using Package = void *(__cdecl *)();
using Constructor = void *(__thiscall *)(void *);
using Register = void *(__thiscall *)(void *,void *,unsigned);
using Title = void (__thiscall *)(void *,const wchar_t *);
uintptr_t windowTable[1+0x128/4]={},frameTable[1+0x13c/4]={};
bool creating=false;
int lastHeight=0;
bool dragging=false;
int dragOffsetX=0,dragOffsetY=0;

void keepVisible(int &x,int &y) {
    RECT area{};
    HWND window=field<HWND>(moduleBase,0x2c6ad0);
    if(!window||!GetClientRect(window,&area)||area.right<=0||area.bottom<=0)return;
    const int maxX=area.right>width?area.right-width:0;
    const int maxY=area.bottom>panelHeight()+20?area.bottom-panelHeight():20;
    if(x<0)x=0;
    if(x>maxX)x=maxX;
    if(y<20)y=20;
    if(y>maxY)y=maxY;
}

template<class Fn> Fn method(void *object,unsigned offset) {
    return reinterpret_cast<Fn>(field<uintptr_t>(field<void *>(object,0),offset));
}
void syncPosition() {
    if(configWindow&&!collapsed) {
        panelX=field<int>(configWindow,0x44);
        panelY=field<int>(configWindow,0x48);
    }
}
int __fastcall draw(void *,void *,void *canvas) {
    void *self=shortcut();
    if(!self||collapsed||!configWindow)return 1;
    nativePainting=true;
    paint(self,canvas);
    nativePainting=false;
    return 1;
}
int __fastcall down(void *window,void *,unsigned,unsigned packed) {
    method<Action>(window,0x74)(window);
    syncPosition();
    const int y=static_cast<short>(packed>>16);
    if(y<field<int>(window,0x48)+28) {
        // The native frame forwards title presses to its parent. Preserve the
        // NCWnd drag state/capture that our custom button handler used to skip.
        return reinterpret_cast<Mouse>(moduleBase+0x36330)(window,0,packed);
    }
    void *self=shortcut();
    if(self)click(self,static_cast<short>(packed),static_cast<short>(packed>>16));
    return 1;
}
int __fastcall up(void *window,void *,unsigned flags,unsigned packed) {
    if(field<int>(window,0x6c))return reinterpret_cast<Mouse>(moduleBase+0x363f0)(window,flags,packed);
    return 1;
}
int __fastcall close(void *,void *) {hideNativeWindow();return 1;}
int __fastcall hide(void *self,void *) {
    reinterpret_cast<Action>(moduleBase+0x35a90)(self);
    collapsed=true;editing=-1;binding=-1;
    return 1;
}
int __fastcall destroy(void *self,void *) {
    // The native manager owns destruction; never keep a pointer across teardown.
    if(self==configWindow){
        configWindow=nullptr;dialogBackdrop=nullptr;collapsed=true;lastHeight=0;
        dragging=false;editing=-1;binding=-1;
        ownedClick=false;worldClickOwned=false;nativeClickSequence=false;
        if(inputWindow&&GetCapture()==inputWindow)ReleaseCapture();
    }
    return reinterpret_cast<Action>(moduleBase+0x36140)(self);
}
bool create(void *self) {
    void *console=field<void *>(moduleBase,0x2c6ad4);
    void *parent=console?field<void *>(console,0x3bf4):nullptr;
    if(!parent||!field<void *>(parent,0x74)||creating)return false;
    // Verify the native class registration, also avoiding calls before startup.
    if(field<void *>(moduleBase,0x2c9ca4)!=moduleBase+0x2c9ca8)return false;
    creating=true;
    anchor(self);
    int x=panelX,y=panelY<20?20:panelY;
    RECT viewport{};
    HWND hwnd=field<HWND>(moduleBase,0x2c6ad0);
    if(hwnd&&GetClientRect(hwnd,&viewport)) {
        x=(viewport.right-width)/2;
        y=(viewport.bottom-panelHeight())/2;
    }
    keepVisible(x,y);
    auto allocate=field<Allocate>(moduleBase,0x19e2d8);
    auto package=field<Package>(moduleBase,0x19e2e0);
    void *error=field<void *>(field<void *>(moduleBase,0x19e2b4),0);
    void *object=allocate(moduleBase+0x2c9ca8,package(),0,0,nullptr,error,nullptr,nullptr);
    if(!object){creating=false;return false;}
    reinterpret_cast<Constructor>(moduleBase+0x36d00)(object);
    // Preserve the native RTTI slot as well as all unmodified virtual methods.
    copyBytes(windowTable,moduleBase+0x19f8b8-4,sizeof(windowTable));
    uintptr_t *table=windowTable+1;
    table[0xf8/4]=reinterpret_cast<uintptr_t>(&draw);
    table[0x110/4]=reinterpret_cast<uintptr_t>(&down);
    table[0x114/4]=reinterpret_cast<uintptr_t>(&up);
    table[0xc4/4]=reinterpret_cast<uintptr_t>(&hide);
    table[0x98/4]=reinterpret_cast<uintptr_t>(&destroy);
    field<void *>(object,0)=table;
    method<Position>(object,0xa0)(object,x,y,width,panelHeight(),0,0,3);
    void *node=reinterpret_cast<Register>(moduleBase+0x35820)(parent,object,0x401082);
    if(!node) {
        using Delete=void (__thiscall *)(void *,unsigned);
        method<Delete>(object,0xc)(object,1);
        creating=false;return false;
    }
    field<void *>(object,0x74)=node;
    field<int>(object,0x44)+=field<int>(parent,0x44);
    field<int>(object,0x48)+=field<int>(parent,0x48);
    configWindow=object;
    method<Event>(object,0x64)(object,1,0,0);
    using LoadTexture=void *(__thiscall *)(void *,const wchar_t *,int);
    dialogBackdrop=reinterpret_cast<LoadTexture>(moduleBase+0x2b490)
        (object,L"L2UI_ch3.dialog.system_back",0);
    void *frame=field<void *>(object,0x7c);
    if(frame) {
        // Base NCWnd creates an invisible drag frame. Enable its regular title
        // skin, then create its native close control (the first call made none).
        field<int>(frame,0x264)=1;
        copyBytes(frameTable,moduleBase+0x1a2b40-4,sizeof(frameTable));
        frameTable[1+0x130/4]=reinterpret_cast<uintptr_t>(&close);
        field<void *>(frame,0)=frameTable+1;
        reinterpret_cast<Title>(moduleBase+0x11940)(frame,L"Auto Potion Settings");
        method<Action>(frame,0x94)(frame);
    }
    lastHeight=panelHeight();
    method<Action>(object,0x74)(object);
    creating=false;
    log("autopotion: native configuration window registered\r\n");
    return true;
}
}
bool nativeDragInput(HWND window,UINT message,WPARAM,LPARAM lparam) {
    if(native::dragging) {
        if(message==WM_MOUSEMOVE&&configWindow&&!collapsed) {
            int x=static_cast<short>(LOWORD(lparam))-native::dragOffsetX;
            int y=static_cast<short>(HIWORD(lparam))-native::dragOffsetY;
            native::keepVisible(x,y);
            native::method<native::Position>(configWindow,0xa0)
                (configWindow,x,y,width,panelHeight(),0,0,3);
            native::syncPosition();
            return true;
        }
        if(message==WM_LBUTTONUP||message==WM_CANCELMODE||message==WM_KILLFOCUS||message==WM_CAPTURECHANGED) {
            native::dragging=false;
            if(configWindow&&field<int>(configWindow,0x6c))
                reinterpret_cast<Mouse>(moduleBase+0x363f0)(configWindow,0,static_cast<unsigned>(lparam));
            if(GetCapture()==window)ReleaseCapture();
            nativeClickSequence=false;ownedClick=false;worldClickOwned=false;
            return message==WM_LBUTTONUP;
        }
    }
    if(message!=WM_LBUTTONDOWN||!configWindow||collapsed)return false;
    const int x=static_cast<short>(LOWORD(lparam)),y=static_cast<short>(HIWORD(lparam));
    const int left=field<int>(configWindow,0x44),top=field<int>(configWindow,0x48);
    // Consume the frame close click here: native button dispatch can retain
    // stale focus after reopening. Keep its release out of the world handler.
    if(x>=left+width-20&&x<left+width&&y>=top-15&&y<top+5) {
        hideNativeWindow();
        nativeClickSequence=false;ownedClick=true;worldClickOwned=true;
        return true;
    }
    // Leave item/control rows to normal dispatch.
    if(x<left||x>=left+width-20||y<top-15||y>=top+28)return false;
    native::dragOffsetX=x-left;native::dragOffsetY=y-top;
    native::method<native::Action>(configWindow,0x74)(configWindow);
    reinterpret_cast<Mouse>(moduleBase+0x36330)(configWindow,0,static_cast<unsigned>(lparam));
    native::dragging=true;
    SetCapture(window);
    nativeClickSequence=false;ownedClick=false;worldClickOwned=false;
    return true;
}
void hideNativeWindow() {
    if(configWindow)native::method<native::Action>(configWindow,0xc4)(configWindow);
    else {collapsed=true;editing=-1;binding=-1;}
}
__attribute__((noinline)) void syncNativeWindow(void *self) {
    if(collapsed)return;
    if(!configWindow&&!native::create(self))return;
    if(!(field<unsigned>(configWindow,0x68)&2)) {
        native::method<native::Action>(configWindow,0xc0)(configWindow);
        native::method<native::Action>(configWindow,0x74)(configWindow);
    }
    native::syncPosition();
    int x=panelX,y=panelY;
    native::keepVisible(x,y);
    if(native::lastHeight!=panelHeight()||x!=panelX||y!=panelY) {
        // SetPosition uses integer dimensions; avoid treating them as float bits.
        native::method<native::Position>(configWindow,0xa0)
            (configWindow,x,y,width,panelHeight(),0,0,3);
        native::lastHeight=panelHeight();
    }
}
