## Monika After Story submod: Go (Baduk) minigame powered by GNU Go (GTP)
## File: game/Submods/MAS_Go_Minigame/header.rpy
## Copyright (c) 2026 olunym. MIT License, see LICENSE.

init -990 python in mas_submod_utils:
    Submod(
        author="olunym",
        name="Go Minigame",
        description=(
            "Play Go (Baduk) against Monika on 9x9, 13x13 or 19x19 boards. "
            "Includes an interactive lesson and adaptive difficulty. "
            "Powered by the GNU Go engine over the Go Text Protocol."
        ),
        version="1.0.0"
    )

## Persistent data used by the minigame.
default persistent._mas_go_stats = {
    "games": 0,
    "wins": 0,
    "losses": 0,
    "draws": 0,
    "resigned": 0
}

## Remembers the last chosen setup (kept for compatibility with older saves).
default persistent._mas_go_last_setup = {
    "size": 9,
    "difficulty": 1,
    "handicap": 0
}

## Register the game so it shows up in Monika's "Play" menu.
init 5 python:
    try:
        addEvent(
            Event(
                persistent._mas_game_database,
                eventlabel="mas_go_game_start",
                prompt="Go",
                unlocked=True
            ),
            code="GME",
            restartBlacklist=True
        )
    except Exception as _mas_go_reg_error:
        renpy.write_log(
            "MAS Go minigame: could not register game: {0}".format(
                repr(_mas_go_reg_error)
            )
        )
