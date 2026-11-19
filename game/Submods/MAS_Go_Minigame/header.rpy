## Monika After Story submod: Go (Baduk) minigame powered by GNU Go (GTP)
## File: game/Submods/MAS_Go_Minigame/header.rpy
## Copyright (c) 2026 olunym. MIT License, see LICENSE.
##
## All of this submod's Python lives in the store "olunym_go_minigame", and
## every label, screen, style, variable and persistent key starts with
## "olunym_go". The alias below lets labels and screens reach the store as
## "olunym_go.something".

init -990 python in mas_submod_utils:
    Submod(
        author="olunym",
        name="Go Minigame",
        description=(
            "Play Go (Baduk) against Monika on 9x9, 13x13 or 19x19 boards. "
            "Includes an interactive lesson and adaptive difficulty. "
            "Powered by the GNU Go engine over the Go Text Protocol."
        ),
        version="1.0.1"
    )

## Alias for the store (a module object, so it is never saved).
define olunym_go = store.olunym_go_minigame

## Persistent data used by the minigame.
default persistent._olunym_go_stats = {
    "games": 0,
    "wins": 0,
    "losses": 0,
    "draws": 0,
    "resigned": 0
}

## Early version of this submod used other persistent names and a different
## label for the Play menu entry. Carry the player's data over and remove the
## old menu entry, so nothing is lost and no dead entry is left behind.
init 4 python in olunym_go_minigame:
    import store
    try:
        _pers = store.persistent
        if _pers._olunym_go_skill is None and _pers._mas_go_skill is not None:
            _pers._olunym_go_skill = dict(_pers._mas_go_skill)
        if _pers._olunym_go_stats is None and _pers._mas_go_stats is not None:
            _pers._olunym_go_stats = dict(_pers._mas_go_stats)
        _database = _pers._mas_game_database
        if _database is not None and "mas_go_game_start" in _database:
            del _database["mas_go_game_start"]
    except Exception as _legacy_error:
        renpy.write_log(
            "Go minigame: could not migrate older data: {0}".format(
                repr(_legacy_error)
            )
        )

## Register the game so it shows up in Monika's "Play" menu.
init 5 python in olunym_go_minigame:
    import store
    try:
        store.addEvent(
            store.Event(
                store.persistent._mas_game_database,
                eventlabel="olunym_go_game_start",
                prompt="Go",
                unlocked=True
            ),
            code="GME",
            restartBlacklist=True
        )
    except Exception as _register_error:
        renpy.write_log(
            "Go minigame: could not register game: {0}".format(
                repr(_register_error)
            )
        )
