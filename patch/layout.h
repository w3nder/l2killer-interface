#pragma once

namespace c4bars {
constexpr int kSlots = 12;
constexpr int kPages = 10;
constexpr int kPitch = 46;
constexpr int kSlotSize = 32;

struct Layout {
    int x, y, page, bars;
    bool horizontal;
    int secondPage = 1, thirdPage = 2;

    int direction() const {
        return (horizontal ? y : x) >= (bars - 1) * kPitch ? -1 : 1;
    }
    int dx(int row) const { return horizontal ? 0 : direction() * row * kPitch; }
    int dy(int row) const { return horizontal ? direction() * row * kPitch : 0; }
    int rowPage(int row) const { return row == 0 ? page : row == 1 ? secondPage : thirdPage; }
    int rowAt(int screenX, int screenY) const {
        for (int row = 0; row < bars; ++row) {
            const int lx = screenX - x - dx(row), ly = screenY - y - dy(row);
            if (lx >= 0 && ly >= 0 && lx < (horizontal ? 504 : 46)
                && ly < (horizontal ? 46 : 504)) return row;
        }
        return -1;
    }
    static int slotStart(int slot) { return 33 + slot * 37 + (slot / 4) * 5; }

    // Match the original C4 inclusive slot edges and the gaps after slots 4/8.
    int hit(int screenX, int screenY) const {
        for (int row = 0; row < bars; ++row) {
            const int localX = screenX - x - dx(row);
            const int localY = screenY - y - dy(row);
            const int cross = horizontal ? localY : localX;
            const int along = horizontal ? localX : localY;
            if (cross <= 5 || cross > 6 + kSlotSize) continue;
            for (int slot = 0; slot < kSlots; ++slot) {
                const int start = slotStart(slot);
                if (along >= start && along <= start + kSlotSize)
                    return rowPage(row) * kSlots + slot;
            }
        }
        return -1;
    }
};
}
