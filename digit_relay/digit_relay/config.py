N_MEMBERS = 6
TURN_TOPIC = 'relay/turn'

COLORS = {
    1: (255, 0, 0),      # red
    2: (0, 170, 0),      # green
    3: (0, 255, 255),      # kuning
    4: (255, 140, 0),    # orange
    5: (150, 0, 200),    # purple
    6: (0, 170, 170),    # teal
}
PEN_WIDTH = 3

COLS = 3
X0 = 0.6
DX = 3.4
Y_ROWS = [6.0, 1.0]

DIGIT_W = 1.3
DIGIT_H = 3.6
DIGIT_GAP = 0.35

HELLO_TOPIC = 'relay/hello'
ROSTER_TOPIC = 'relay/roster'

TICK_SEC = 0.5          # how often hello / roster are published
DISCOVERY_TIME = 3.0    # how long a new node listens for a leader before electing itself
PEER_TIMEOUT = 3.0      # a member silent this long (before start) is dropped from the lobby
LEADER_TIMEOUT = 3.0    # a leader silent this long is considered gone
TIE_EPS = 0.25          # start times closer than this are a tie, broken by uuid
