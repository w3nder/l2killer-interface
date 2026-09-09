// Version-specific RVAs. Original profile remains the default.
constexpr unsigned c4rva(unsigned original) {
#ifdef C4BARS_L2KILLER
    switch (original) {
    case 0x1cbd68: return 0x1ccdc0;
    case 0x5c2b0: return 0x5c340;
    case 0x52f40: return 0x52f90;
    case 0x2c39f4: return 0x2c6ad4;
    case 0x107b20: return 0x107dd0;
    case 0x349f0: return 0x349e0;
    case 0x107c00: return 0x107eb0;
    case 0x107c60: return 0x107f10;
    case 0x1097e0: return 0x109a90;
    case 0x1060f0: return 0x1063a0;
    case 0x1060f5: return 0x1063a5;
    case 0x1060f6: return 0x1063a6;
    case 0x75fe0: return 0x76090;
    case 0x75fe5: return 0x76095;
    case 0x13330: return 0x134b0;
    case 0x13340: return 0x134c0;
    case 0x13350: return 0x134d0;
    }
#endif
    return original;
}
