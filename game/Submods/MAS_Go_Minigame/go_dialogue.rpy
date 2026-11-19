## Monika After Story submod: Go (Baduk) minigame
## File: game/Submods/MAS_Go_Minigame/go_dialogue.rpy
##
## Monika's dialogue and the game flow: first-time questions, skill
## assessment, board size menu, and the turn loop.
## (Game over, scoring and cleanup are in go_dialogue_end.rpy.)
## Compatible with Python 2.7 (Ren'Py 6.99) and Python 3.9+ (Ren'Py 8).
##
## Every exit path ends at label olunym_go_cleanup, which calls olunym_go.ctrl.quit().

init python in olunym_go_minigame:
    import store

    LINES = {
        "player_capture": [
            "Oh! You captured some of my stones. Nicely done.",
            "Hm, you got me there. Those stones are yours now.",
            "You captured my stones... I didn't see that coming, ehehe.",
            "Well played. I'll have to be more careful around you."
        ],
        "monika_capture": [
            "Sorry, [player]. I captured some of your stones.",
            "Those stones ran out of liberties, so I'll take them.",
            "Careful there. I managed to capture a few of your stones.",
            "I think I just captured some of your stones. Ehehe."
        ],
        "undo_ok": [
            "Okay, I took those moves back. Try again, [player].",
            "Moves undone. Take your time and think it over.",
            "No problem. We can go back a step."
        ],
        "undo_many": [
            "That's quite a few take-backs, [player]. Ahaha, I'm only teasing.",
            "You really like that undo button, don't you? It's all right."
        ]
    }

    def pick(key):
        """Random line for a key, with [player] already filled in."""
        lines = LINES.get(key) or [""]
        text = renpy.random.choice(lines)
        try:
            name = str(store.player).replace("{", "{{")
        except Exception:
            name = "you"
        return text.replace("[player]", name)

    def escape(text):
        """Make arbitrary text safe to show through [interpolation]."""
        try:
            value = text if text else ""
            return value.replace("{", "{{")
        except Exception:
            return "unknown error"

    def fmt_margin(value):
        try:
            number = float(value)
            if number == int(number):
                return str(int(number))
            return str(number)
        except Exception:
            return str(value)

    def record(outcome):
        """outcome: 'win', 'loss', 'draw' or 'resign' (you resigned)."""
        try:
            stats = store.persistent._olunym_go_stats
            for key in ("games", "wins", "losses", "draws", "resigned"):
                stats.setdefault(key, 0)
            stats["games"] += 1
            if outcome == "win":
                stats["wins"] += 1
            elif outcome == "draw":
                stats["draws"] += 1
            elif outcome == "resign":
                stats["losses"] += 1
                stats["resigned"] += 1
            else:
                stats["losses"] += 1
        except Exception as e:
            renpy.write_log("MAS Go: could not record stats: {0}".format(repr(e)))

    def block_rb():
        try:
            renpy.block_rollback()
        except Exception:
            pass

    # Best-effort protection against MAS overlays/hotkeys during the game.
    # Each helper is looked up by name, so a missing one is simply skipped.
    def _call_if_present(names):
        for name in names:
            try:
                func = getattr(store, name, None)
                if func is not None and callable(func):
                    func()
            except Exception as e:
                renpy.write_log("MAS Go: {0} failed: {1}".format(name, repr(e)))

    def shield_up():
        _call_if_present(
            ("HKBHideButtons", "disable_esc", "mas_MUMURaiseShield"))

    def shield_down():
        _call_if_present(
            ("mas_MUMUDropShield", "enable_esc", "HKBShowButtons"))


## --------------------------------------------------------------------------
## Entry point (this is the label registered in header.rpy)
## --------------------------------------------------------------------------
label olunym_go_game_start:
    $ olunym_go.shield_up()
    $ olunym_go.reset_ui()
    $ olunym_go_undos = 0

    if not olunym_go.skill_get("assessed"):
        jump olunym_go_first_time

    m 1hub "Another game of Go? Let's play!"
    jump olunym_go_setup


## --------------------------------------------------------------------------
## First time: does the player know the game?
## --------------------------------------------------------------------------
label olunym_go_first_time:
    m 1hua "A game of Go! I've always liked how much hides inside such simple rules."
    m 1eua "We take turns placing stones on a grid. You're Black and I'm White."
    m 1eua "Do you already know how to play Go?{nw}"
    $ _history_list.pop()
    menu:
        m "Do you already know how to play Go?{fast}"
        "Yes, I've played before.":
            m 1hub "Wonderful! I'm so happy to hear that."
            jump olunym_go_ask_skill
        "No, I'm new to Go.":
            jump olunym_go_offer_lesson
        "Never mind.":
            m 1eka "Okay. Maybe another time."
            jump olunym_go_cleanup


label olunym_go_offer_lesson:
    m 1hub "Then let me teach you! It's easier than it looks, and I'd love to show you."
    m 1eua "It only takes a few minutes, and you'll place stones on the board yourself as we go.{nw}"
    $ _history_list.pop()
    menu:
        m "It only takes a few minutes, and you'll place stones on the board yourself as we go.{fast}"
        "Yes, teach me the basics.":
            jump olunym_go_tutorial
        "No thanks, I'll learn as I play.":
            $ olunym_go.skill_new_player(False)
            m 1eka "Okay! I'll go easy on you, and I'll explain if you try a move that isn't allowed."
            jump olunym_go_setup


## --------------------------------------------------------------------------
## How good is the player? (also used to update it later)
## --------------------------------------------------------------------------
label olunym_go_ask_skill:
    m 1eua "How well would you say you play?{nw}"
    $ _history_list.pop()
    menu:
        m "How well would you say you play?{fast}"
        "I've only played a few games.":
            $ olunym_go.skill_assess("few")
        "I play casually, now and then.":
            $ olunym_go.skill_assess("casual")
        "I play regularly.":
            $ olunym_go.skill_assess("regular")
        "I'm quite experienced.":
            $ olunym_go.skill_assess("experienced")
        "I'm very strong.":
            $ olunym_go.skill_assess("strong")
        "Never mind.":
            m 1eka "Okay, we'll leave it as it is."
            jump olunym_go_setup

    m 1hua "Thank you, I'll start from there."
    m 1eua "You won't need to choose a difficulty. I'll adjust as we play, depending on how our games go."
    jump olunym_go_setup


## --------------------------------------------------------------------------
## Board size (the difficulty is automatic)
## --------------------------------------------------------------------------
label olunym_go_setup:
    python:
        olunym_go_size = 9

    m 1eua "Which board would you like to play on?{nw}"
    $ _history_list.pop()
    menu:
        m "Which board would you like to play on?{fast}"
        "9x9 - a quick game":
            $ olunym_go_size = 9
        "13x13 board - a medium game":
            $ olunym_go_size = 13
        "19x19 - the full game":
            $ olunym_go_size = 19
        "Go over the basics again.":
            jump olunym_go_tutorial
        "Tell Monika how well I play.":
            jump olunym_go_ask_skill
        "Never mind.":
            m 1eka "Okay. Maybe another time."
            jump olunym_go_cleanup

    jump olunym_go_launch


## --------------------------------------------------------------------------
## Start the engine
## --------------------------------------------------------------------------
label olunym_go_launch:
    python:
        olunym_go_level = olunym_go.skill_get("level")
        olunym_go_handi = olunym_go.skill_get("handicap")

    m 1eua "Give me a moment to set up the board..."

    if olunym_go_size == 19 and olunym_go_level >= 8:
        m 1rksdlb "A full board against a strong opponent can make me think for a while, so please be patient with me."

    $ olunym_go_ok, olunym_go_real_handi = olunym_go.start_game(olunym_go_size, olunym_go_level, olunym_go_handi)

    if not olunym_go_ok:
        jump olunym_go_start_failed

    $ olunym_go.reset_ui()
    $ olunym_go_undos = 0
    show monika 1eua at t21
    show screen olunym_go_view

    if olunym_go_real_handi >= 2:
        if olunym_go_real_handi != olunym_go_handi:
            m 1rksdla "This board can't take as many handicap stones as I wanted to give you, so you'll get [olunym_go_real_handi] this time."
        m 1eua "All set. You get [olunym_go_real_handi] handicap stones, so I'll play first as White."
    else:
        m 1eua "All set. You're Black, so you move first. Click an intersection to place a stone."

    jump olunym_go_turn


label olunym_go_start_failed:
    $ olunym_go_err_safe = olunym_go.escape(olunym_go.ctrl.error or "GNU Go could not be started.")
    m 1ekc "I'm sorry, [player]. I couldn't set up the board."
    m 1rksdlc "[olunym_go_err_safe]"
    m 1eka "Details are saved in go_engine.log in the Go submod folder. We can try again after that's fixed."
    jump olunym_go_cleanup


label olunym_go_engine_lost:
    $ olunym_go_err_safe = olunym_go.escape(olunym_go.ctrl.error or "GNU Go is no longer running.")
    m 1ekc "Oh no... something went wrong and the game had to stop."
    m 1rksdlc "[olunym_go_err_safe]"
    m 1eka "I'm sorry, [player]. This game can't be continued, but we can start a new one whenever you like."
    jump olunym_go_cleanup


## --------------------------------------------------------------------------
## Main turn loop
## --------------------------------------------------------------------------
label olunym_go_turn:
    $ olunym_go.block_rb()
    show monika 1eua

    if not olunym_go.ctrl.is_ready:
        jump olunym_go_engine_lost

    if olunym_go.ctrl.game_over:
        jump olunym_go_finish

    if olunym_go.ctrl.to_move == "white":
        jump olunym_go_monika_turn

    call screen olunym_go_board
    $ olunym_go_act = _return

    if olunym_go_act is None:
        jump olunym_go_turn

    if olunym_go_act[0] == "play":
        jump olunym_go_player_move
    elif olunym_go_act[0] == "pass":
        jump olunym_go_player_pass
    elif olunym_go_act[0] == "undo":
        jump olunym_go_player_undo
    elif olunym_go_act[0] == "resign":
        jump olunym_go_player_resign

    jump olunym_go_turn


## --------------------------------------------------------------------------
## The player's actions
## --------------------------------------------------------------------------
label olunym_go_player_move:
    $ olunym_go_res = olunym_go.ctrl.play(olunym_go_act[1], olunym_go_act[2], "black")

    if olunym_go_res["ok"]:
        if olunym_go_res["captured"] > 0:
            show screen olunym_go_view
            $ olunym_go_line = olunym_go.pick("player_capture")
            m 1wuo "[olunym_go_line]"
        jump olunym_go_turn

    show screen olunym_go_view

    if olunym_go_res["reason"] == "ko":
        m 1eka "That's a Ko, [player]. You can't retake right away because the board would repeat itself."
        m 1eub "Play somewhere else first, then you can come back to it."
    elif olunym_go_res["reason"] == "suicide":
        m 1rksdla "That stone would have no liberties and wouldn't capture anything, so it isn't allowed."
        m 1eua "Try another spot."
    elif olunym_go_res["reason"] == "occupied":
        m 1rksdlb "There's already a stone there, ahaha."
    elif olunym_go_res["reason"] == "engine":
        jump olunym_go_engine_lost
    elif olunym_go_res["reason"] == "game_over":
        jump olunym_go_finish
    else:
        m 1rksdla "Hm, I couldn't place a stone there. Please try another spot."

    jump olunym_go_turn


label olunym_go_player_pass:
    $ olunym_go_res = olunym_go.ctrl.pass_turn("black")

    if not olunym_go_res["ok"]:
        jump olunym_go_turn

    if olunym_go_res["game_over"]:
        show screen olunym_go_view
        m 1eua "You passed right after I did, so we're both done. Let me count the territory."
        jump olunym_go_finish

    jump olunym_go_turn


label olunym_go_player_undo:
    $ olunym_go_res = olunym_go.ctrl.undo(2)
    $ olunym_go.ui_state.hover = None
    show screen olunym_go_view

    if olunym_go_res["ok"]:
        $ olunym_go_undos += 1
        if olunym_go_undos == 4:
            $ olunym_go_line = olunym_go.pick("undo_many")
        else:
            $ olunym_go_line = olunym_go.pick("undo_ok")
        m 1eka "[olunym_go_line]"
    else:
        m 1rksdla "There's nothing to take back yet, [player]."

    jump olunym_go_turn


label olunym_go_player_resign:
    show screen olunym_go_view

    m 1ekc "Are you sure you want to resign?{nw}"
    $ _history_list.pop()
    menu:
        m "Are you sure you want to resign?{fast}"
        "Yes, I resign.":
            $ olunym_go.ctrl.resign("black")
            $ olunym_go_report = olunym_go.finalize("resign")
            m 1eka "That's okay, [player]. Every game teaches something."
            m 1hua "Thank you for playing with me."
            call olunym_go_skill_note
            jump olunym_go_show_end
        "No, let's keep playing.":
            m 1hub "That's the spirit!"
            jump olunym_go_turn


## --------------------------------------------------------------------------
## Monika's turn (GNU Go thinks in the background; the screen keeps running)
## --------------------------------------------------------------------------
label olunym_go_wait_result:
    $ olunym_go_result = None
    while olunym_go_result is None:
        $ olunym_go.block_rb()
        if olunym_go.ctrl.result_ready:
            $ olunym_go_result = olunym_go.ctrl.take_result()
        elif olunym_go.ctrl.thinking:
            call screen olunym_go_board
        else:
            $ olunym_go_result = {"type": "error", "text": "no result from GNU Go"}
    return


label olunym_go_monika_turn:
    $ olunym_go.block_rb()

    if not olunym_go.ctrl.request_move("white"):
        jump olunym_go_engine_lost

    call olunym_go_wait_result
    $ olunym_go_ai = olunym_go_result

    if olunym_go_ai["type"] == "move":
        if olunym_go_ai["captured"] > 0:
            show screen olunym_go_view
            $ olunym_go_line = olunym_go.pick("monika_capture")
            m 1tuu "[olunym_go_line]"
        jump olunym_go_turn

    elif olunym_go_ai["type"] == "pass":
        show screen olunym_go_view
        if olunym_go_ai.get("game_over"):
            m 1eua "I pass as well, so we're both done. Let me count the territory."
            jump olunym_go_finish
        m 1eua "I think I'll pass this turn."
        m 1etc "If you pass too, the game ends and we count the score."
        jump olunym_go_turn

    elif olunym_go_ai["type"] == "resign":
        show screen olunym_go_view
        $ olunym_go_report = olunym_go.finalize("win")
        m 1wud "I... I don't see a way back from here. I resign!"
        m 1hub "Congratulations, [player]! You won!"
        call olunym_go_skill_note
        jump olunym_go_show_end

    elif olunym_go_ai["type"] == "cancelled":
        jump olunym_go_cleanup

    jump olunym_go_engine_lost
