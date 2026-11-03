# Published by the leader on relay/roster.
uint8 WAITING=0
uint8 RUNNING=1
uint8 DONE=2

string leader_uuid
float64 leader_age   # seconds since the leader started
string[] members     # uuids in join order; index + 1 = member number
string[] hostnames
uint8 state
