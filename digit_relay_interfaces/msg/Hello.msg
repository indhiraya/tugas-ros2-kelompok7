# Heartbeat every relay node publishes on relay/hello.
string uuid        # unique id of this process
string hostname
float64 age        # seconds since this node started (clock-independent)
int32 member_id    # member number this node believes it has (0 = none yet)
