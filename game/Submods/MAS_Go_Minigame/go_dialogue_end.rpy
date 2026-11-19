## Monika After Story submod: Go (Baduk) minigame
## File: game/Submods/MAS_Go_Minigame/go_dialogue_end.rpy
##
## Game over: scoring, difficulty announcements, rematch and cleanup.
## (The game flow itself is in go_dialogue.rpy.)
##
## Every exit path ends at label olunym_go_cleanup, which calls olunym_go.ctrl.quit().

## --------------------------------------------------------------------------
## Game over: scoring
## --------------------------------------------------------------------------
label olunym_go_finish:
    show screen olunym_go_view

    if olunym_go.ctrl.resigned_color is not None:
        jump olunym_go_show_end

    m 1eua "Let me see who has more territory..."

    if not olunym_go.ctrl.request_final_score():
        jump olunym_go_engine_lost

    call olunym_go_wait_result

    if olunym_go_result["type"] != "score":
        m 1rksdlb "Ahaha, I couldn't work out the final count. Let's call it a good game, and I won't count this one."
        jump olunym_go_show_end

    python:
        olunym_go.ui_state.dead = olunym_go_result["dead"]
        olunym_go_info = olunym_go_result["score"]
        olunym_go_winner = olunym_go_info["winner"]
        olunym_go_margin_text = olunym_go.fmt_margin(olunym_go_info["margin"])
        olunym_go_raw = olunym_go.escape(olunym_go_info["raw"])
        olunym_go_has_dead = len(olunym_go_result["dead"]) > 0

    show screen olunym_go_view

    if olunym_go_has_dead:
        m 1eua "I marked the dead stones with red crosses, since they don't count."

    if olunym_go_winner == "black":
        $ olunym_go_report = olunym_go.finalize("win")
        m 1wub "You won by [olunym_go_margin_text] points! The count says [olunym_go_raw]."
        m 1hub "Congratulations, [player]! That was a wonderful game."
    elif olunym_go_winner == "white":
        $ olunym_go_report = olunym_go.finalize("loss")
        m 1tuu "I won by [olunym_go_margin_text] points. The count says [olunym_go_raw]."
        m 1eka "You played well, [player]. We can play again whenever you want."
    else:
        $ olunym_go_report = olunym_go.finalize("draw")
        m 1wuo "It's a tie! That almost never happens in Go."
        m 1hub "A draw with you feels like a win for both of us, ehehe."

    call olunym_go_skill_note
    jump olunym_go_show_end


## --------------------------------------------------------------------------
## What Monika says when the difficulty changes. Expects olunym_go_report.
## Returns normally, so it is always used with "call".
## --------------------------------------------------------------------------
label olunym_go_skill_note:
    if not olunym_go_report.get("counted", False):
        return

    $ olunym_go_note_old = olunym_go_report.get("old_handicap", 0)
    $ olunym_go_note_new = olunym_go_report.get("new_handicap", 0)

    if olunym_go_report.get("changed"):
        if olunym_go_report.get("direction") == "up":
            if olunym_go_note_old >= 2 and olunym_go_note_new >= 2:
                m 1hua "You're improving! Next time I'll give you one stone less, so [olunym_go_note_new] handicap stones."
            elif olunym_go_note_old >= 2:
                m 1hub "You've outgrown the handicap, [player]! Next game will be an even one."
            else:
                m 1eub "You're getting stronger! I think I'll play a little more seriously next time."
        else:
            if olunym_go_note_new >= 2 and olunym_go_note_old >= 2:
                m 1eka "Let me even things out a bit. Next time you'll get [olunym_go_note_new] handicap stones."
            elif olunym_go_note_new >= 2:
                m 1eka "Let's try something different. Next time I'll give you [olunym_go_note_new] handicap stones to start with."
            else:
                m 1eka "I think I'll go a little easier on you next time."
    elif olunym_go_report.get("blocked"):
        if olunym_go_report.get("direction") == "up":
            m 1wuo "You've beaten me at full strength twice in a row! I can't play any harder than this, ahaha."
        else:
            m 1eka "I'm already giving you as many stones as I can. Maybe we can look at the lesson again? Just choose it from the menu."
    return


## --------------------------------------------------------------------------
## After the game: let the player look at the board, then offer a rematch
## --------------------------------------------------------------------------
label olunym_go_show_end:
    call screen olunym_go_board(phase="over")
    jump olunym_go_after_game


label olunym_go_after_game:
    hide screen olunym_go
    show monika 1eua at t11
    $ olunym_go.ctrl.quit()
    $ olunym_go.reset_ui()

    m 1eua "Would you like to play another game?{nw}"
    $ _history_list.pop()
    menu:
        m "Would you like to play another game?{fast}"
        "Yes, let's go again.":
            jump olunym_go_setup
        "That's enough for now.":
            m 1hua "Thank you for playing with me, [player]. I really enjoyed it."
            jump olunym_go_cleanup


## --------------------------------------------------------------------------
## The one exit point: every path ends here
## --------------------------------------------------------------------------
label olunym_go_cleanup:
    hide screen olunym_go
    show monika 1eua at t11
    $ olunym_go.ctrl.quit()
    $ olunym_go.reset_ui()
    $ olunym_go.shield_down()
    return
