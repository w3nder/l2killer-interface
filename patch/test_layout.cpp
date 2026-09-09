#include "layout.h"
#include <cassert>
#include <cstdio>
#include <initializer_list>

int main() {
    int cases = 0;
    for (bool horizontal : {false, true}) {
        for (int origin : {0, 30, 92, 700}) {
            for (int bars = 1; bars <= 3; ++bars) {
                for (int page = 0; page < 10; ++page) {
                    c4bars::Layout l{origin, origin, page, bars, horizontal, 4, 7};
                    for (int row = 0; row < bars; ++row) {
                        for (int slot = 0; slot < 12; ++slot) {
                            const int p = c4bars::Layout::slotStart(slot);
                            const int target = (row == 0 ? page : row == 1 ? 4 : 7) * 12 + slot;
                            for (int edge : {0, 16, 32}) {
                                const int x = origin + l.dx(row) + (horizontal ? p + edge : 22);
                                const int y = origin + l.dy(row) + (horizontal ? 22 : p + edge);
                                assert(l.hit(x, y) == target);
                                assert(l.rowAt(x, y) == row);
                                ++cases;
                            }
                            // Pixel immediately after a slot is a gap, never the next item.
                            int x = origin + l.dx(row) + (horizontal ? p + 33 : 22);
                            int y = origin + l.dy(row) + (horizontal ? 22 : p + 33);
                            assert(l.hit(x, y) == -1);
                        }
                    }
                    assert(l.hit(origin - 500, origin - 500) == -1);
                }
            }
        }
    }
    std::printf("layout: %d slot positions/edges passed\n", cases);
}
