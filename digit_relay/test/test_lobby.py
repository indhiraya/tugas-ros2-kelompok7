from digit_relay.lobby import member_id_of, started_before


def test_earlier_start_wins():
    assert started_before(1.0, 'b', 5.0, 'a')
    assert not started_before(5.0, 'a', 1.0, 'b')


def test_tie_broken_by_uuid():
    assert started_before(1.0, 'a', 1.1, 'b')
    assert not started_before(1.1, 'b', 1.0, 'a')


def test_member_id_follows_join_order():
    roster = ['leader', 'second', 'third']
    assert member_id_of('leader', roster) == 1
    assert member_id_of('third', roster) == 3
    assert member_id_of('stranger', roster) == 0
