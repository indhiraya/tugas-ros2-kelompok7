from . import config

DIGIT_SEGMENTS = {
    '0': 'abcdef', '1': 'bc',     '2': 'abged',  '3': 'abgcd',  '4': 'fgbc',
    '5': 'afgcd',  '6': 'afgedc', '7': 'abc',    '8': 'abcdefg', '9': 'abcdfg',
}


def segment_coords(seg, w, h):
    m = h / 2.0
    return {
        'a': (0, h, w, h), 'b': (w, h, w, m), 'c': (w, m, w, 0),
        'd': (0, 0, w, 0), 'e': (0, 0, 0, m), 'f': (0, m, 0, h),
        'g': (0, m, w, m),
    }[seg]


def slot_origin(member_id):
    i = member_id - 1
    row, col = divmod(i, config.COLS)
    return config.X0 + col * config.DX, config.Y_ROWS[row]


def number_to_strokes(number, member_id):
    ox, oy = slot_origin(member_id)
    strokes = []
    for k, ch in enumerate(str(number)):
        dx = ox + k * (config.DIGIT_W + config.DIGIT_GAP)
        for seg in DIGIT_SEGMENTS[ch]:
            x1, y1, x2, y2 = segment_coords(seg, config.DIGIT_W, config.DIGIT_H)
            strokes.append((dx + x1, oy + y1, dx + x2, oy + y2))
    return strokes
