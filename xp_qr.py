"""
xp_qr.py - a small QR code encoder, so the app can show a code you scan with your phone.

Byte mode, error correction level L or M, versions 1-10 (up to ~270 characters at L),
which is plenty for a http://192.168.x.x:port/ address. No dependencies.

Produces a list of rows of booleans; the GUI draws it on a canvas.
"""
from __future__ import annotations

# ---------------------------------------------------------------- tables
EC_CODEWORDS = {          # (version, level) -> ec codewords per block, blocks
    # level L
    (1, "L"): (7, 1), (2, "L"): (10, 1), (3, "L"): (15, 1), (4, "L"): (20, 1), (5, "L"): (26, 1),
    (6, "L"): (18, 2), (7, "L"): (20, 2), (8, "L"): (24, 2), (9, "L"): (30, 2), (10, "L"): (18, 4),
    # level M
    (1, "M"): (10, 1), (2, "M"): (16, 1), (3, "M"): (26, 1), (4, "M"): (18, 2), (5, "M"): (24, 2),
    (6, "M"): (16, 4), (7, "M"): (18, 4), (8, "M"): (22, 4), (9, "M"): (22, 5), (10, "M"): (26, 5),
}
TOTAL_CODEWORDS = {1: 26, 2: 44, 3: 70, 4: 100, 5: 134, 6: 172, 7: 196, 8: 242, 9: 292, 10: 346}
ALIGN_POS = {1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
             7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50]}
LEVEL_BITS = {"L": 0b01, "M": 0b00, "Q": 0b11, "H": 0b10}


def format_bits(level, mask):
    """The 15-bit format information: 5 data bits, BCH(15,5) error correction, then a fixed mask."""
    data = (LEVEL_BITS[level] << 3) | mask
    rem = data << 10
    g = 0b10100110111
    for i in range(4, -1, -1):
        if rem & (1 << (i + 10)):
            rem ^= g << i
    return ((data << 10) | rem) ^ 0b101010000010010


# ---------------------------------------------------------------- galois field
EXP = [0] * 512
LOG = [0] * 256
_x = 1
for _i in range(255):
    EXP[_i] = _x
    LOG[_x] = _i
    _x <<= 1
    if _x & 0x100:
        _x ^= 0x11D
for _i in range(255, 512):
    EXP[_i] = EXP[_i - 255]


def gf_mul(a, b):
    return 0 if a == 0 or b == 0 else EXP[LOG[a] + LOG[b]]


def rs_generator(n):
    g = [1]
    for i in range(n):
        g2 = [0] * (len(g) + 1)
        for j, c in enumerate(g):
            g2[j] ^= gf_mul(c, 1)
            g2[j + 1] ^= gf_mul(c, EXP[i])
        g = g2
    return g


def rs_ec(data, n):
    gen = rs_generator(n)
    rem = [0] * n
    for b in data:
        factor = b ^ rem[0]
        rem = rem[1:] + [0]
        for i, g in enumerate(gen[1:]):
            rem[i] ^= gf_mul(g, factor)
    return rem


# ---------------------------------------------------------------- encoding
def capacity_bits(version, level):
    ec_per_block, blocks = EC_CODEWORDS[(version, level)]
    return (TOTAL_CODEWORDS[version] - ec_per_block * blocks) * 8


def pick_version(n_bytes, level):
    for v in range(1, 11):
        header = 4 + (8 if v < 10 else 16)
        if header + n_bytes * 8 <= capacity_bits(v, level):
            return v
    raise ValueError("Too much text for this little encoder (keep it under ~270 characters).")


def encode_data(text, version, level):
    data = text.encode("utf-8")
    bits = []

    def put(value, length):
        for i in range(length - 1, -1, -1):
            bits.append((value >> i) & 1)

    put(0b0100, 4)                                  # byte mode
    put(len(data), 8 if version < 10 else 16)
    for b in data:
        put(b, 8)
    cap = capacity_bits(version, level)
    put(0, min(4, cap - len(bits)))                 # terminator
    while len(bits) % 8:
        bits.append(0)
    pad = [0xEC, 0x11]
    i = 0
    while len(bits) < cap:
        put(pad[i % 2], 8)
        i += 1
    codewords = [int("".join(str(b) for b in bits[i:i + 8]), 2) for i in range(0, len(bits), 8)]

    ec_per_block, blocks = EC_CODEWORDS[(version, level)]
    total_data = len(codewords)
    base, extra = divmod(total_data, blocks)
    groups, ecs = [], []
    pos = 0
    for b in range(blocks):
        n = base + (1 if b >= blocks - extra else 0)
        block = codewords[pos:pos + n]
        pos += n
        groups.append(block)
        ecs.append(rs_ec(block, ec_per_block))
    out = []
    for i in range(max(len(g) for g in groups)):
        for g in groups:
            if i < len(g):
                out.append(g[i])
    for i in range(ec_per_block):
        for e in ecs:
            out.append(e[i])
    return out


# ---------------------------------------------------------------- matrix
def _blank(size):
    return [[None] * size for _ in range(size)]


def _finder(m, r, c):
    for dr in range(-1, 8):
        for dc in range(-1, 8):
            rr, cc = r + dr, c + dc
            if 0 <= rr < len(m) and 0 <= cc < len(m):
                on = (0 <= dr <= 6 and dc in (0, 6)) or (0 <= dc <= 6 and dr in (0, 6)) or \
                     (2 <= dr <= 4 and 2 <= dc <= 4)
                m[rr][cc] = bool(on)


def _patterns(version):
    size = version * 4 + 17
    m = _blank(size)
    _finder(m, 0, 0)
    _finder(m, 0, size - 7)
    _finder(m, size - 7, 0)
    for i in range(size):                     # timing
        if m[6][i] is None:
            m[6][i] = i % 2 == 0
        if m[i][6] is None:
            m[i][6] = i % 2 == 0
    for r in ALIGN_POS[version]:              # alignment
        for c in ALIGN_POS[version]:
            if (r < 9 and c < 9) or (r < 9 and c > size - 10) or (r > size - 10 and c < 9):
                continue
            for dr in range(-2, 3):
                for dc in range(-2, 3):
                    m[r + dr][c + dc] = max(abs(dr), abs(dc)) != 1
    m[size - 8][8] = True                     # dark module
    return m


def version_bits(version):
    """18-bit version information: 6 data bits plus BCH(18,6). Only for version 7 and up."""
    rem = version << 12
    g = 0b1111100100101
    for i in range(5, -1, -1):
        if rem & (1 << (i + 12)):
            rem ^= g << i
    return (version << 12) | rem


def _reserved(version):
    """Where format (and version) information goes - these cells aren't for data."""
    size = version * 4 + 17
    res = [[False] * size for _ in range(size)]
    for i in range(9):
        res[8][i] = res[i][8] = True
    for i in range(8):
        res[8][size - 1 - i] = res[size - 1 - i][8] = True
    if version >= 7:
        for i in range(18):
            r, c = i // 3, i % 3
            res[r][size - 11 + c] = True
            res[size - 11 + c][r] = True
    return res


def _put_version(m, version):
    if version < 7:
        return m
    size = len(m)
    bits = version_bits(version)
    for i in range(18):
        bit = bool((bits >> i) & 1)
        r, c = i // 3, i % 3
        m[r][size - 11 + c] = bit
        m[size - 11 + c][r] = bit
    return m


def _place_data(m, res, codewords, version):
    size = len(m)
    bits = []
    for cw in codewords:
        for i in range(7, -1, -1):
            bits.append((cw >> i) & 1)
    idx = 0
    col = size - 1
    upward = True
    while col > 0:
        if col == 6:
            col -= 1
        rows = range(size - 1, -1, -1) if upward else range(size)
        for row in rows:
            for c in (col, col - 1):
                if m[row][c] is None and not res[row][c]:
                    m[row][c] = bool(bits[idx]) if idx < len(bits) else False
                    idx += 1
        upward = not upward
        col -= 2
    return m


def _mask_fn(k):
    return [lambda r, c: (r + c) % 2 == 0,
            lambda r, c: r % 2 == 0,
            lambda r, c: c % 3 == 0,
            lambda r, c: (r + c) % 3 == 0,
            lambda r, c: (r // 2 + c // 3) % 2 == 0,
            lambda r, c: (r * c) % 2 + (r * c) % 3 == 0,
            lambda r, c: ((r * c) % 2 + (r * c) % 3) % 2 == 0,
            lambda r, c: ((r + c) % 2 + (r * c) % 3) % 2 == 0][k]


def _apply_mask(m, res, patt, k):
    fn = _mask_fn(k)
    size = len(m)
    out = [row[:] for row in m]
    for r in range(size):
        for c in range(size):
            if patt[r][c] is None and not res[r][c] and fn(r, c):
                out[r][c] = not out[r][c]
    return out


def _put_format(m, level, mask):
    """15 bits, twice: bit 14 first at (8,0) and at the bottom of column 8."""
    size = len(m)
    bits = format_bits(level, mask)
    copy1 = [(8, 0), (8, 1), (8, 2), (8, 3), (8, 4), (8, 5), (8, 7), (8, 8),
             (7, 8), (5, 8), (4, 8), (3, 8), (2, 8), (1, 8), (0, 8)]
    copy2 = [(size - 1 - i, 8) for i in range(7)] + [(8, size - 8 + i) for i in range(8)]
    for i, (a, b) in enumerate(zip(copy1, copy2)):
        bit = bool((bits >> (14 - i)) & 1)
        m[a[0]][a[1]] = bit
        m[b[0]][b[1]] = bit
    m[size - 8][8] = True          # the dark module is always set
    return m


def _penalty(m):
    size = len(m)
    score = 0
    for line in list(m) + [list(col) for col in zip(*m)]:
        run, prev = 1, line[0]
        for cell in line[1:]:
            if cell == prev:
                run += 1
            else:
                if run >= 5:
                    score += 3 + (run - 5)
                run, prev = 1, cell
        if run >= 5:
            score += 3 + (run - 5)
    for r in range(size - 1):
        for c in range(size - 1):
            block = (m[r][c], m[r][c + 1], m[r + 1][c], m[r + 1][c + 1])
            if all(block) or not any(block):
                score += 3
    # patterns that look like a finder (1:1:3:1:1 with light space) confuse scanners
    finder = [True, False, True, True, True, False, True]
    light = [False] * 4
    for line in list(m) + [list(col) for col in zip(*m)]:
        for i in range(len(line) - 6):
            if line[i:i + 7] == finder:
                before = line[max(0, i - 4):i]
                after = line[i + 7:i + 11]
                if (len(before) == 4 and before == light) or (len(after) == 4 and after == light):
                    score += 40
    dark = sum(1 for row in m for cell in row if cell)
    pct = dark * 100 / (size * size)
    score += 10 * int(abs(pct - 50) / 5)
    return score


def matrix(text, level="M"):
    """QR code for this text as a list of rows of booleans (True = dark)."""
    version = pick_version(len(text.encode("utf-8")), level)
    codewords = encode_data(text, version, level)
    patt = _patterns(version)
    res = _reserved(version)
    m = _place_data([row[:] for row in patt], res, codewords, version)
    best, best_score = None, None
    for k in range(8):
        cand = _apply_mask(m, res, patt, k)
        cand = _put_format([row[:] for row in cand], level, k)
        cand = _put_version(cand, version)
        sc = _penalty(cand)
        if best_score is None or sc < best_score:
            best, best_score = cand, sc
    return [[bool(x) for x in row] for row in best]


def as_text(m, on="##", off="  "):
    return "\n".join("".join(on if c else off for c in row) for row in m)
