## Monika After Story submod: Go (Baduk) minigame
## File: game/Submods/MAS_Go_Minigame/go_dialogue.rpy
##
## Monika's dialogue and the game flow: first-time questions, skill
## assessment, board size menu, and the turn loop.
## (Game over, scoring and cleanup are in go_dialogue_end.rpy.)
## Compatible with Python 2.7 (Ren'Py 6.99) and Python 3.9+ (Ren'Py 8).
##
## Every exit path ends at label mas_go_cleanup, which calls go_ctrl.quit().

init python:

    MAS_GO_LINES = {
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

    def mas_go_pick(key):
        """Random line for a key, with [player] already filled in."""
        lines = MAS_GO_LINES.get(key) or [""]
        text = renpy.random.choice(lines)
        try:
            name = str(store.player).replace("{", "{{")
        except Exception:
            name = "you"
        return text.replace("[player]", name)

    def mas_go_escape(text):
        """Make arbitrary text safe to show through [interpolation]."""
        try:
            value = text if text else ""
            return value.replace("{", "{{")
        except Exception:
            return "unknown error"

    def mas_go_fmt_margin(value):
        try:
            number = float(value)
            if number == int(number):
                return str(int(number))
            return str(number)
        except Exception:
            return str(value)

    def mas_go_record(outcome):
        """outcome: 'win', 'loss', 'draw' or 'resign' (you resigned)."""
        try:
            stats = persistent._mas_go_stats
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

    def mas_go_block_rb():
        try:
            renpy.block_rollback()
        except Exception:
            pass

    # Best-effort protection against MAS overlays/hotkeys during the game.
    # Each helper is looked up by name, so a missing one is simply skipped.
    def _mas_go_call_if_present(names):
        for name in names:
            try:
                func = globals().get(name)
                if func is not None and callable(func):
                    func()
            except Exception as e:
                renpy.write_log("MAS Go: {0} failed: {1}".format(name, repr(e)))

    def mas_go_shield_up():
        _mas_go_call_if_present(
            ("HKBHideButtons", "disable_esc", "mas_MUMURaiseShield"))

    def mas_go_shield_down():
        _mas_go_call_if_present(
            ("mas_MUMUDropShield", "enable_esc", "HKBShowButtons"))


## --------------------------------------------------------------------------
## Entry point (this is the label registered in header.rpy)
## --------------------------------------------------------------------------
label mas_go_game_start:
    $ mas_go_shield_up()
    $ mas_go_ui_reset()
    $ mas_go_undos = 0

    if not mas_go_skill_get("assessed"):
        jump mas_go_first_time

    m 1hub "Another game of Go? Let's play!"
    jump mas_go_setup


## --------------------------------------------------------------------------
## First time: does the player know the game?
## --------------------------------------------------------------------------
label mas_go_first_time:
    m 1hua "A game of Go! I've always liked how much hides inside such simple rules."
    m 1eua "We take turns placing stones on a grid. You're Black and I'm White."
    m 1eua "Do you already know how to play Go?{nw}"
    $ _history_list.pop()
    menu:
        m "Do you already know how to play Go?{fast}"
        "Yes, I've played before.":
            m 1hub "Wonderful! I'm so happy to hear that."
            jump mas_go_ask_skill
        "No, I'm new to Go.":
            jump mas_go_offer_lesson
        "Never mind.":
            m 1eka "Okay. Maybe another time."
            jump mas_go_cleanup


label mas_go_offer_lesson:
    m 1hub "Then let me teach you! It's easier than it looks, and I'd love to show you."
    m 1eua "It only takes a few minutes, and you'll place stones on the board yourself as we go.{nw}"
    $ _history_list.pop()
    menu:
        m "It only takes a few minutes, and you'll place stones on the board yourself as we go.{fast}"
        "Yes, teach me the basics.":
            jump mas_go_tutorial
        "No thanks, I'll learn as I play.":
            $ mas_go_skill_new_player(False)
            m 1eka "Okay! I'll go easy on you, and I'll explain if you try a move that isn't allowed."
            jump mas_go_setup


## --------------------------------------------------------------------------
## How good is the player? (also used to update it later)
## --------------------------------------------------------------------------
label mas_go_ask_skill:
    m 1eua "How well would you say you play?{nw}"
    $ _history_list.pop()
    menu:
        m "How well would you say you play?{fast}"
        "I've only played a few games.":
            $ mas_go_skill_assess("few")
        "I play casually, now and then.":
            $ mas_go_skill_assess("casual")
        "I play regularly.":
            $ mas_go_skill_assess("regular")
        "I'm quite experienced.":
            $ mas_go_skill_assess("experienced")
        "I'm very strong.":
            $ mas_go_skill_assess("strong")
        "Never mind.":
            m 1eka "Okay, we'll leave it as it is."
            jump mas_go_setup

    m 1hua "Thank you, I'll start from there."
    m 1eua "You won't need to choose a difficulty. I'll adjust as we play, depending on how our games go."
    jump mas_go_setup


## --------------------------------------------------------------------------
## Board size (the difficulty is automatic)
## --------------------------------------------------------------------------
label mas_go_setup:
    python:
        mas_go_size = 9

    m 1eua "What would you like to do?{nw}"
    $ _history_list.pop()
    menu:
        m "What would you like to do?{fast}"
        "Play on a 9x9 board - a quick game":
            $ mas_go_size = 9
        "Play on a 13x13 board - a medium game":
            $ mas_go_size = 13
        "Play on a 19x19 board - the full game":
            $ mas_go_size = 19
        "Go over the basics again.":
            jump mas_go_tutorial
        "Tell Monika how well I play.":
            jump mas_go_ask_skill
        "Never mind.":
            m 1eka "Okay. Maybe another time."
            jump mas_go_cleanup

    jump mas_go_launch


## --------------------------------------------------------------------------
## Start the engine
## --------------------------------------------------------------------------
label mas_go_launch:
    python:
        mas_go_level = mas_go_skill_get("level")
        mas_go_handi = mas_go_skill_get("handicap")
        persistent._mas_go_last_setup = {
            "size": mas_go_size,
            "difficulty": mas_go_level,
            "handicap": mas_go_handi
        }

    m 1eua "Give me a moment to set up the board..."

    if mas_go_size == 19 and mas_go_level >= 8:
        m 1rksdlb "A full board against a strong opponent can make me think for a while, so please be patient with me."

    $ mas_go_ok, mas_go_real_handi = mas_go_start_game(mas_go_size, mas_go_level, mas_go_handi)

    if not mas_go_ok:
        jump mas_go_start_failed

    $ mas_go_ui_reset()
    $ mas_go_undos = 0
    show monika 1eua at t21
    show screen mas_go_view

    if mas_go_real_handi >= 2:
        if mas_go_real_handi != mas_go_handi:
            m 1rksdla "This board can't take as many handicap stones as I wanted to give you, so you'll get [mas_go_real_handi] this time."
        m 1eua "All set. You get [mas_go_real_handi] handicap stones, so I'll play first as White."
    else:
        m 1eua "All set. You're Black, so you move first. Click an intersection to place a stone."

    jump mas_go_turn


label mas_go_start_failed:
    $ mas_go_err_safe = mas_go_escape(go_ctrl.error or "GNU Go could not be started.")
    m 1ekc "I'm sorry, [player]. I couldn't set up the board."
    m 1rksdlc "[mas_go_err_safe]"
    m 1eka "Details are saved in go_engine.log in the Go submod folder. We can try again after that's fixed."
    jump mas_go_cleanup


label mas_go_engine_lost:
    $ mas_go_err_safe = mas_go_escape(go_ctrl.error or "GNU Go is no longer running.")
    m 1ekc "Oh no... something went wrong and the game had to stop."
    m 1rksdlc "[mas_go_err_safe]"
    m 1eka "I'm sorry, [player]. This game can't be continued, but we can start a new one whenever you like."
    jump mas_go_cleanup


## --------------------------------------------------------------------------
## Main turn loop
## --------------------------------------------------------------------------
label mas_go_turn:
    $ mas_go_block_rb()
    show monika 1eua

    if not go_ctrl.is_ready:
        jump mas_go_engine_lost

    if go_ctrl.game_over:
        jump mas_go_finish

    if go_ctrl.to_move == "white":
        jump mas_go_monika_turn

    call screen mas_go_board
    $ mas_go_act = _return

    if mas_go_act is None:
        jump mas_go_turn

    if mas_go_act[0] == "play":
        jump mas_go_player_move
    elif mas_go_act[0] == "pass":
        jump mas_go_player_pass
    elif mas_go_act[0] == "undo":
        jump mas_go_player_undo
    elif mas_go_act[0] == "resign":
        jump mas_go_player_resign

    jump mas_go_turn


## --------------------------------------------------------------------------
## The player's actions
## --------------------------------------------------------------------------
label mas_go_player_move:
    $ mas_go_res = go_ctrl.play(mas_go_act[1], mas_go_act[2], "black")

    if mas_go_res["ok"]:
        if mas_go_res["captured"] > 0:
            show screen mas_go_view
            $ mas_go_line = mas_go_pick("player_capture")
            m 1wuo "[mas_go_line]"
        jump mas_go_turn

    show screen mas_go_view

    if mas_go_res["reason"] == "ko":
        m 1eka "That's a Ko, [player]. You can't retake right away because the board would repeat itself."
        m 1eub "Play somewhere else first, then you can come back to it."
    elif mas_go_res["reason"] == "suicide":
        m 1rksdla "That stone would have no liberties and wouldn't capture anything, so it isn't allowed."
        m 1eua "Try another spot."
    elif mas_go_res["reason"] == "occupied":
        m 1rksdlb "There's already a stone there, ahaha."
    elif mas_go_res["reason"] == "engine":
        jump mas_go_engine_lost
    elif mas_go_res["reason"] == "game_over":
        jump mas_go_finish
    else:
        m 1rksdla "Hm, I couldn't place a stone there. Please try another spot."

    jump mas_go_turn


label mas_go_player_pass:
    $ mas_go_res = go_ctrl.pass_turn("black")

    if not mas_go_res["ok"]:
        jump mas_go_turn

    if mas_go_res["game_over"]:
        show screen mas_go_view
        m 1eua "You passed right after I did, so we're both done. Let me count the territory."
        jump mas_go_finish

    jump mas_go_turn


label mas_go_player_undo:
    $ mas_go_res = go_ctrl.undo(2)
    $ mas_go_ui.hover = None
    show screen mas_go_view

    if mas_go_res["ok"]:
        $ mas_go_undos += 1
        if mas_go_undos == 4:
            $ mas_go_line = mas_go_pick("undo_many")
        else:
            $ mas_go_line = mas_go_pick("undo_ok")
        m 1eka "[mas_go_line]"
    else:
        m 1rksdla "There's nothing to take back yet, [player]."

    jump mas_go_turn


label mas_go_player_resign:
    show screen mas_go_view

    m 1ekc "Are you sure you want to resign?{nw}"
    $ _history_list.pop()
    menu:
        m "Are you sure you want to resign?{fast}"
        "Yes, I resign.":
            $ go_ctrl.resign("black")
            $ mas_go_report = mas_go_finalize("resign")
            m 1eka "That's okay, [player]. Every game teaches something."
            m 1hua "Thank you for playing with me."
            call mas_go_skill_note
            jump mas_go_show_end
        "No, let's keep playing.":
            m 1hub "That's the spirit!"
            jump mas_go_turn


## --------------------------------------------------------------------------
## Monika's turn (GNU Go thinks in the background; the screen keeps running)
## --------------------------------------------------------------------------
label mas_go_wait_result:
    $ mas_go_result = None
    while mas_go_result is None:
        $ mas_go_block_rb()
        if go_ctrl.result_ready:
            $ mas_go_result = go_ctrl.take_result()
        elif go_ctrl.thinking:
            call screen mas_go_board
        else:
            $ mas_go_result = {"type": "error", "text": "no result from GNU Go"}
    return


label mas_go_monika_turn:
    $ mas_go_block_rb()

    if not go_ctrl.request_move("white"):
        jump mas_go_engine_lost

    call mas_go_wait_result
    $ mas_go_ai = mas_go_result

    if mas_go_ai["type"] == "move":
        if mas_go_ai["captured"] > 0:
            show screen mas_go_view
            $ mas_go_line = mas_go_pick("monika_capture")
            m 1tuu "[mas_go_line]"
        jump mas_go_turn

    elif mas_go_ai["type"] == "pass":
        show screen mas_go_view
        if mas_go_ai.get("game_over"):
            m 1eua "I pass as well, so we're both done. Let me count the territory."
            jump mas_go_finish
        m 1eua "I think I'll pass this turn."
        m 1etc "If you pass too, the game ends and we count the score."
        jump mas_go_turn

    elif mas_go_ai["type"] == "resign":
        show screen mas_go_view
        $ mas_go_report = mas_go_finalize("win")
        m 1wud "I... I don't see a way back from here. I resign!"
        m 1hub "Congratulations, [player]! You won!"
        call mas_go_skill_note
        jump mas_go_show_end

    elif mas_go_ai["type"] == "cancelled":
        jump mas_go_cleanup

    jump mas_go_engine_lost
