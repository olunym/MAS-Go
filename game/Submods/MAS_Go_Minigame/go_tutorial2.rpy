## Monika After Story submod: Go (Baduk) minigame
## File: game/Submods/MAS_Go_Minigame/go_tutorial2.rpy
##
## Interactive tutorial, part 2: lessons 5-9 and the ending.
## (Helpers, the exercise loop and lessons 1-4 are in go_tutorial.rpy.)
## Compatible with Python 2.7 (Ren'Py 6.99) and Python 3.9+ (Ren'Py 8).

init python:

    # The settled position used for the territory and passing lessons.
    MAS_GO_TUT_SETTLED_BLACK = "C1 C2 C3 A4 B4"
    MAS_GO_TUT_SETTLED_WHITE = "G7 G8 G9 H6 J6"

    def mas_go_tut_mark_done():
        """Remember that the player has seen the lesson."""
        data = mas_go_skill_all()
        data["tutorial_done"] = True
        mas_go_skill_save(data)


## --------------------------------------------------------------------------
## Lesson 5: moves that are not allowed (suicide and ko)
## --------------------------------------------------------------------------
label mas_go_tut_illegal:
    $ mas_go_ui.lesson = "Illegal moves"
    $ mas_go_tut_setup(white="D5 F5 E6 E4", marks="E5")
    show screen mas_go_view
    m 1eua "A couple of moves are not allowed. The first is suicide: you can't place a stone that would have no liberties at all."
    m 1eub "The dotted point in the middle is surrounded by four white stones. Click it and see what happens."

    $ mas_go_ex = {
        "white": "D5 F5 E6 E4", "marks": "E5", "targets": "E5", "illegal": "suicide",
        "hint": "Click the dotted point in the middle. I want you to see what happens."
    }
    call mas_go_tut_exercise
    if mas_go_ex_status == "dead":
        jump mas_go_engine_lost

    show screen mas_go_view
    m 1hua "Nothing happened, right? The game refuses the move, because the stone would have no liberties."
    m 1eua "There is one exception. If a stone captures something, the captured stones give it liberties, so that move is fine."

    m 1eub "The second rule is called ko. Watch closely. Capture the white stone in the middle."
    $ mas_go_ex = {
        "black": "D6 C5 D4", "white": "D5 E6 F5 E4", "marks": "E5", "targets": "E5",
        "hint": "Click the dotted point to capture the white stone in the middle."
    }
    call mas_go_tut_exercise
    if mas_go_ex_status == "dead":
        jump mas_go_engine_lost

    $ mas_go_tut_clear_marks()
    show screen mas_go_view
    m 1wub "Captured! But look at your new stone. It has only one liberty, the point where my stone was."
    m 1tuu "I'd love to take it right back, so let me try."

    $ mas_go_res = mas_go_tut_try("D5", "white")
    show screen mas_go_view
    if mas_go_res["ok"]:
        $ go_ctrl.undo(1)
        show screen mas_go_view
        m 1etc "Hm, this version of the rules would have let me retake. But normally the ko rule forbids it, so let's pretend I couldn't."
    else:
        m 1eka "I can't. If I retook right away, the board would look exactly like it did before, and we could repeat that forever."
    m 1eua "That's the ko rule: you can't immediately recreate the previous position. You have to play somewhere else first."

    $ mas_go_tut_reply("G8 G2 C8 H5")
    show screen mas_go_view
    m 1eub "So I play elsewhere. Now the board is different, and if you don't deal with the ko, I'm allowed to retake it on my next turn."
    m 1hua "You can end a ko by connecting your stone, or you can play somewhere more important. Picking your battles is half of Go!"
    jump mas_go_tut_territory


## --------------------------------------------------------------------------
## Lesson 6: territory and two eyes
## --------------------------------------------------------------------------
label mas_go_tut_territory:
    $ mas_go_ui.lesson = "Territory"
    $ mas_go_tut_setup(black=MAS_GO_TUT_SETTLED_BLACK, white=MAS_GO_TUT_SETTLED_WHITE, marks="A1 B1 A2 B2 A3 B3")
    show screen mas_go_view
    m 1eua "Now, how do you actually win? By controlling more of the board than I do."
    m 1eub "Empty points that only one color surrounds are that player's territory. These six points in the corner belong to Black."
    $ mas_go_tut_setup(black=MAS_GO_TUT_SETTLED_BLACK, white=MAS_GO_TUT_SETTLED_WHITE, marks="H7 J7 H8 J8 H9 J9")
    m 1eua "And these six belong to White. At the end of the game, each player counts their territory and the stones they captured."
    m 1eka "White also gets a few extra points called komi, because Black has the advantage of moving first. In our games komi is 6.5 points, so there are never any ties."

    $ mas_go_ui.lesson = "Two eyes"
    $ mas_go_tut_setup(black="A1 C1 E1 A2 B2 C2 D2 E2", marks="B1 D1")
    show screen mas_go_view
    m 1eub "One more important idea: living and dying. These black stones have two separate empty points inside them, marked with dots. We call those eyes."
    m 1eua "I could surround this group completely, but I could never play on either eye, because it would be suicide for me."
    m 1hua "So the group can never be captured. A group with two eyes is alive. That's the secret of staying safe in Go."
    jump mas_go_tut_flow


## --------------------------------------------------------------------------
## Lesson 7: how a game flows
## --------------------------------------------------------------------------
label mas_go_tut_flow:
    $ mas_go_ui.lesson = "Flow of a game"
    $ mas_go_tut_setup(marks="C3 G3 C7 G7 E5")
    show screen mas_go_view
    m 1eub "Let's talk about how a game usually goes. The opening usually starts in the corners, like at the dotted points. Corners are the easiest places to make territory, because the edges help you."
    m 1eua "Then players extend along the sides, and finally the center, where there's more room but fewer walls to lean on."
    m 1eua "After that comes the fighting. Stones touch, groups try to connect, attack, and capture each other. Staying connected and making two eyes is how you keep your groups safe."
    m 1eua "Near the end, all the borders are settled, and the last moves are about squeezing out a few more points."
    m 1hua "You don't need to win every fight. You just need to end up with more territory than your opponent."
    jump mas_go_tut_pass


## --------------------------------------------------------------------------
## Lesson 8: passing
## --------------------------------------------------------------------------
label mas_go_tut_pass:
    $ mas_go_ui.lesson = "Passing"
    $ mas_go_tut_setup(black=MAS_GO_TUT_SETTLED_BLACK, white=MAS_GO_TUT_SETTLED_WHITE)
    show screen mas_go_view
    m 1eua "Now the Pass button. Sometimes the best move is no move. If every border is settled, and any stone you'd place would only lose points, you pass instead."
    m 1eub "Pretend the game is finished here. Nothing useful is left to play. That's the time to pass, so press the Pass button."

    $ mas_go_ex = {
        "black": MAS_GO_TUT_SETTLED_BLACK, "white": MAS_GO_TUT_SETTLED_WHITE,
        "needs": "pass", "board": False
    }
    call mas_go_tut_exercise
    if mas_go_ex_status == "dead":
        jump mas_go_engine_lost

    show screen mas_go_view
    m 1hub "Exactly! And I'll pass too. When both players pass one after the other, the game is over, and we count the score."
    m 1eua "Don't pass too early, though. If I still have a good move, I'll keep playing, and you can always keep going as well."
    jump mas_go_tut_resign


## --------------------------------------------------------------------------
## Lesson 9: resigning
## --------------------------------------------------------------------------
label mas_go_tut_resign:
    $ mas_go_ui.lesson = "Resigning"
    show screen mas_go_view
    m 1eua "The last button is Resign. If you're far behind and don't see a way back, you can resign and end the game right away."
    m 1eka "It isn't a bad thing! Strong players resign all the time, because they can see the result before the end."
    m 1eub "For this lesson, press Resign to see how it works. Nothing will end, I promise."

    $ mas_go_ex = {
        "black": MAS_GO_TUT_SETTLED_BLACK, "white": MAS_GO_TUT_SETTLED_WHITE,
        "needs": "resign", "board": False
    }
    call mas_go_tut_exercise
    if mas_go_ex_status == "dead":
        jump mas_go_engine_lost

    show screen mas_go_view
    m 1hua "That's all there is to it! In a real game that would end it, and I'd count it as my win."
    jump mas_go_tut_wrapup


## --------------------------------------------------------------------------
## Wrap-up
## --------------------------------------------------------------------------
label mas_go_tut_wrapup:
    $ mas_go_ui.lesson = "Done!"
    $ mas_go_tut_setup()
    show screen mas_go_view
    m 1hub "And that's everything! Stones, liberties, capture, atari, ko, territory, eyes, passing and resigning. You know the whole game now."
    m 1eua "The rest is practice. A few quick tips: keep your stones connected, watch your liberties, and don't be afraid to lose a few stones for a better position."
    jump mas_go_tut_done


label mas_go_tut_done:
    hide screen mas_go
    $ go_ctrl.quit()
    $ mas_go_ui_reset()
    show monika 1eua at t11

    if not mas_go_skill_get("assessed"):
        $ mas_go_skill_new_player(True)
        $ mas_go_new_handi = mas_go_skill_get("handicap")
        m 1eua "Since you're just starting out, I'll go easy on you. You'll get [mas_go_new_handi] handicap stones, which are extra black stones placed before I move."
        m 1eub "Every time you win twice in a row, I'll take away one stone, and once they're gone, I'll start playing a little stronger."
        m 1eka "And if a game turns out too hard, I'll make things easier. You won't have to choose a difficulty, I'll just adjust as we play."
    else:
        $ mas_go_tut_mark_done()
        m 1eua "I hope that was a good refresher! Your difficulty hasn't changed, so we can pick up where we left off."
    jump mas_go_setup
