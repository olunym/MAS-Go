## Monika After Story submod: Go (Baduk) minigame
## File: game/Submods/MAS_Go_Minigame/go_dialogue_end.rpy
##
## Game over: scoring, difficulty announcements, rematch and cleanup.
## (The game flow itself is in go_dialogue.rpy.)
##
## Every exit path ends at label mas_go_cleanup, which calls go_ctrl.quit().

## --------------------------------------------------------------------------
## Game over: scoring
## --------------------------------------------------------------------------
label mas_go_finish:
    show screen mas_go_view

    if go_ctrl.resigned_color is not None:
        jump mas_go_show_end

    m 1eua "Let me see who has more territory..."

    if not go_ctrl.request_final_score():
        jump mas_go_engine_lost

    call mas_go_wait_result

    if mas_go_result["type"] != "score":
        m 1rksdlb "Ahaha, I couldn't work out the final count. Let's call it a good game, and I won't count this one."
        jump mas_go_show_end

    python:
        mas_go_ui.dead = mas_go_result["dead"]
        mas_go_info = mas_go_result["score"]
        mas_go_winner = mas_go_info["winner"]
        mas_go_margin_text = mas_go_fmt_margin(mas_go_info["margin"])
        mas_go_raw = mas_go_escape(mas_go_info["raw"])
        mas_go_has_dead = len(mas_go_result["dead"]) > 0

    show screen mas_go_view

    if mas_go_has_dead:
        m 1eua "I marked the dead stones with red crosses, since they don't count."

    if mas_go_winner == "black":
        $ mas_go_report = mas_go_finalize("win")
        m 1wub "You won by [mas_go_margin_text] points! The count says [mas_go_raw]."
        m 1hub "Congratulations, [player]! That was a wonderful game."
    elif mas_go_winner == "white":
        $ mas_go_report = mas_go_finalize("loss")
        m 1tuu "I won by [mas_go_margin_text] points. The count says [mas_go_raw]."
        m 1eka "You played well, [player]. We can play again whenever you want."
    else:
        $ mas_go_report = mas_go_finalize("draw")
        m 1wuo "It's a tie! That almost never happens in Go."
        m 1hub "A draw with you feels like a win for both of us, ehehe."

    call mas_go_skill_note
    jump mas_go_show_end


## --------------------------------------------------------------------------
## What Monika says when the difficulty changes. Expects mas_go_report.
## Returns normally, so it is always used with "call".
## --------------------------------------------------------------------------
label mas_go_skill_note:
    if not mas_go_report.get("counted", False):
        return

    $ mas_go_note_old = mas_go_report.get("old_handicap", 0)
    $ mas_go_note_new = mas_go_report.get("new_handicap", 0)

    if mas_go_report.get("changed"):
        if mas_go_report.get("direction") == "up":
            if mas_go_note_old >= 2 and mas_go_note_new >= 2:
                m 1hua "You're improving! Next time I'll give you one stone less, so [mas_go_note_new] handicap stones."
            elif mas_go_note_old >= 2:
                m 1hub "You've outgrown the handicap, [player]! Next game will be an even one."
            else:
                m 1eub "You're getting stronger! I think I'll play a little more seriously next time."
        else:
            if mas_go_note_new >= 2 and mas_go_note_old >= 2:
                m 1eka "Let me even things out a bit. Next time you'll get [mas_go_note_new] handicap stones."
            elif mas_go_note_new >= 2:
                m 1eka "Let's try something different. Next time I'll give you [mas_go_note_new] handicap stones to start with."
            else:
                m 1eka "I think I'll go a little easier on you next time."
    elif mas_go_report.get("blocked"):
        if mas_go_report.get("direction") == "up":
            m 1wuo "You've beaten me at full strength twice in a row! I can't play any harder than this, ahaha."
        else:
            m 1eka "I'm already giving you as many stones as I can. Maybe we can look at the lesson again? Just choose it from the menu."
    return


## --------------------------------------------------------------------------
## After the game: let the player look at the board, then offer a rematch
## --------------------------------------------------------------------------
label mas_go_show_end:
    call screen mas_go_board(phase="over")
    jump mas_go_after_game


label mas_go_after_game:
    hide screen mas_go
    show monika 1eua at t11
    $ go_ctrl.quit()
    $ mas_go_ui_reset()

    m 1eua "Would you like to play another game?{nw}"
    $ _history_list.pop()
    menu:
        m "Would you like to play another game?{fast}"
        "Yes, let's go again.":
            jump mas_go_setup
        "That's enough for now.":
            m 1hua "Thank you for playing with me, [player]. I really enjoyed it."
            jump mas_go_cleanup


## --------------------------------------------------------------------------
## The one exit point: every path ends here
## --------------------------------------------------------------------------
label mas_go_cleanup:
    hide screen mas_go
    show monika 1eua at t11
    $ go_ctrl.quit()
    $ mas_go_ui_reset()
    $ mas_go_shield_down()
    return
