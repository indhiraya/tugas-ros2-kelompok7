DONE_MEMBER = 0


def next_turn(number, member, n_members):
    if number >= 2 * n_members:
        return number + 1, DONE_MEMBER
    return number + 1, member % n_members + 1


def needs_clear(number, member, n_members):
    return member == 1 and number == n_members + 1
