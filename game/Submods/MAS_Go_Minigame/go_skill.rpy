## Monika After Story submod: Go (Baduk) minigame
## File: game/Submods/MAS_Go_Minigame/go_skill.rpy
##
## Adaptive difficulty. The player never picks a difficulty: Monika tracks
## their skill in persistent data and adjusts it after each finished game.
##
## The ladder, from easiest to hardest:
##   handicap 9, 8, ... 3, 2   (GNU Go level 0, player gets extra stones)
##   handicap 0, level 0, 1, 2, ... 10   (even games)
##
## A change only happens after olunym_go.STREAK_NEEDED wins (or losses) in a row.
## Compatible with Python 2.7 (Ren'Py 6.99) and Python 3.9+ (Ren'Py 8).

default persistent._olunym_go_skill = {
    "level": 0,
    "handicap": 0,
    "win_streak": 0,
    "loss_streak": 0,
    "assessed": False,
    "tutorial_done": False
}

init python in olunym_go_minigame:
    import store

    SKILL_DEFAULT = {
        "level": 0,
        "handicap": 0,
        "win_streak": 0,
        "loss_streak": 0,
        "assessed": False,
        "tutorial_done": False
    }

    STREAK_NEEDED = 2       # consecutive results before anything changes
    MAX_LEVEL = 10          # GNU Go's strongest level
    MIN_HANDICAP = 2        # smallest real handicap
    MAX_HANDICAP = 9        # largest handicap we ever give
    NEW_PLAYER = (0, 4)     # (level, handicap) for someone who just learned

    # What the player says about themselves -> (level, handicap)
    ASSESS = {
        "few": (0, 2),
        "casual": (2, 0),
        "regular": (5, 0),
        "experienced": (8, 0),
        "strong": (10, 0)
    }

    # ----------------------------------------------------------------------
    # persistent access
    # ----------------------------------------------------------------------
    def skill_all():
        """A complete copy of the skill data, with missing keys filled in."""
        data = dict(SKILL_DEFAULT)
        try:
            stored = store.persistent._olunym_go_skill
            if stored:
                data.update(stored)
        except Exception:
            pass
        return data

    def skill_get(key):
        return skill_all().get(key, SKILL_DEFAULT.get(key))

    def skill_save(data):
        """Assign a fresh dict (so Ren'Py notices the change) and flush it."""
        store.persistent._olunym_go_skill = dict(data)
        try:
            renpy.save_persistent()
        except Exception:
            pass

    def skill_set(level, handicap, assessed=True):
        data = skill_all()
        data["level"] = max(0, min(MAX_LEVEL, int(level)))
        h = int(handicap)
        if h < MIN_HANDICAP:
            h = 0
        data["handicap"] = min(h, MAX_HANDICAP)
        data["win_streak"] = 0
        data["loss_streak"] = 0
        if assessed:
            data["assessed"] = True
        skill_save(data)

    def skill_assess(key):
        """Apply the player's own description of their skill."""
        level, handicap = ASSESS.get(key, (0, 0))
        skill_set(level, handicap, True)

    def skill_new_player(tutorial_done=False):
        """Start point for someone who is new to Go."""
        skill_set(NEW_PLAYER[0], NEW_PLAYER[1], True)
        if tutorial_done:
            data = skill_all()
            data["tutorial_done"] = True
            skill_save(data)

    # ----------------------------------------------------------------------
    # the ladder
    # ----------------------------------------------------------------------
    def _step_harder(data):
        """Make the game harder. Returns True if anything changed."""
        if data["handicap"] >= MIN_HANDICAP:
            data["handicap"] -= 1
            if data["handicap"] < MIN_HANDICAP:
                data["handicap"] = 0
            return True
        if data["level"] < MAX_LEVEL:
            data["level"] += 1
            return True
        return False

    def _step_easier(data):
        """Make the game easier. Returns True if anything changed."""
        if data["handicap"] >= MIN_HANDICAP:
            if data["handicap"] < MAX_HANDICAP:
                data["handicap"] += 1
                return True
            return False
        if data["level"] > 0:
            data["level"] -= 1
            return True
        data["handicap"] = MIN_HANDICAP
        return True

    def skill_after(outcome):
        """Update the skill after a finished game.

        outcome: 'win', 'loss' or 'draw' (a resignation by the player is a 'loss').
        Returns a report dict:
            changed, direction ('up'/'down'/None), blocked (wanted to change
            but was already at the limit), old_level, new_level,
            old_handicap, new_handicap, win_streak, loss_streak
        """
        data = skill_all()
        report = {
            "changed": False, "direction": None, "blocked": False,
            "old_level": data["level"], "old_handicap": data["handicap"],
            "new_level": data["level"], "new_handicap": data["handicap"],
            "win_streak": 0, "loss_streak": 0
        }
        if outcome == "win":
            data["win_streak"] += 1
            data["loss_streak"] = 0
            if data["win_streak"] >= STREAK_NEEDED:
                report["direction"] = "up"
                report["changed"] = _step_harder(data)
                report["blocked"] = not report["changed"]
                data["win_streak"] = 0
        elif outcome == "loss":
            data["loss_streak"] += 1
            data["win_streak"] = 0
            if data["loss_streak"] >= STREAK_NEEDED:
                report["direction"] = "down"
                report["changed"] = _step_easier(data)
                report["blocked"] = not report["changed"]
                data["loss_streak"] = 0
        else:
            data["win_streak"] = 0
            data["loss_streak"] = 0
        report["new_level"] = data["level"]
        report["new_handicap"] = data["handicap"]
        report["win_streak"] = data["win_streak"]
        report["loss_streak"] = data["loss_streak"]
        skill_save(data)
        return report

    # ----------------------------------------------------------------------
    # finishing a game
    # ----------------------------------------------------------------------
    def player_moves():
        """How many stones the player actually played this game (passes excluded)."""
        count = 0
        for color, vertex in ctrl.moves:
            if color == "black" and vertex != "PASS":
                count += 1
        return count

    def finalize(outcome):
        """Record stats and adapt the skill. outcome: win/loss/draw/resign.

        A resignation before the player has played any stone is not counted
        at all, so backing out of a game never changes the difficulty.
        Returns the report from skill_after, plus 'counted'.
        """
        if outcome == "resign" and player_moves() == 0:
            return {"counted": False, "changed": False, "direction": None,
                    "blocked": False}
        record(outcome)
        if outcome == "resign":
            outcome = "loss"
        report = skill_after(outcome)
        report["counted"] = True
        return report

    # ----------------------------------------------------------------------
    # starting the engine for a game
    # ----------------------------------------------------------------------
    def apply_level(level):
        """Send GNU Go the GTP 'level' command (also given on the command line)."""
        try:
            ok, text = ctrl.command("level {0}".format(int(level)))
            if not ok:
                ctrl._log("level command refused: {0}".format(text))
        except Exception as e:
            renpy.write_log("MAS Go: level command failed: {0}".format(repr(e)))

    def start_game(size, level, handicap):
        """Start GNU Go. Returns (ok, handicap_actually_used).

        If GNU Go refuses a handicap (some board sizes only allow a few
        stones), the handicap is lowered one stone at a time, and finally
        dropped, so the game can still start. The saved skill is untouched.
        """
        used = int(handicap)
        if used < MIN_HANDICAP:
            used = 0
        while True:
            # The engine is launched at level 1 or higher; the real level
            # (including 0) is then set with the GTP "level" command.
            ok = ctrl.start(boardsize=size, level=max(1, int(level)), handicap=used)
            if ok:
                apply_level(level)
                return (True, used)
            if ctrl.error_code == "handshake_failed" and used >= MIN_HANDICAP:
                if used > MIN_HANDICAP:
                    used -= 1
                else:
                    used = 0
                continue
            return (False, used)
