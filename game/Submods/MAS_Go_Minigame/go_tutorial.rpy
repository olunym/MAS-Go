## Monika After Story submod: Go (Baduk) minigame
## File: game/Submods/MAS_Go_Minigame/go_tutorial.rpy
##
## Interactive tutorial, part 1: helpers, the exercise loop, lessons 1-4.
## (Lessons 5-9 and the ending are in go_tutorial2.rpy.)
##
## The tutorial runs on a 9x9 board. Monika sets up positions by playing
## stones for both colours through GTP, so GNU Go still decides what is
## legal. Pass, Resign and Undo are handled by the lesson, never by a game:
##   Undo   - always on, restarts the current exercise
##   Pass   - only enabled in the lesson that explains passing
##   Resign - only enabled in the lesson that explains resigning
## Compatible with Python 2.7 (Ren'Py 6.99) and Python 3.9+ (Ren'Py 8).

init python in olunym_go_minigame:

    TUT_LINES = {
        "undo": [
            "No problem, I set the exercise up again for you.",
            "Sure, back to the start of this exercise.",
            "Here's a fresh board. Take your time."
        ]
    }

    def tut_pick(key):
        return renpy.random.choice(TUT_LINES.get(key) or [""])

    def tut_points(text):
        """'E5 D4' -> [(col, row), ...]. Unknown words are ignored."""
        points = []
        for token in (text or "").replace(",", " ").split():
            idx = GnuGoController.vertex_to_index(token, 9)
            if idx is not None:
                points.append(idx)
        return points

    def tut_setup(black="", white="", marks="", to_move="black"):
        """Clear the board and place the given stones (white first, then black).

        Positions are chosen so that no stone is captured while setting up.
        marks: points to highlight with blue dots. Returns True on success.
        """
        if not ctrl.is_ready or ctrl.thinking:
            return False
        ok = True
        with ctrl._io_lock:
            sent, text = ctrl._send("clear_board")
            if not sent:
                return False
            ctrl.moves = []
            ctrl.last_move = None
            ctrl.last_captured = frozenset()
            ctrl.passes_in_a_row = 0
            ctrl.game_over = False
            ctrl.resigned_color = None
            ctrl.handicap_stones = 0
            for color, text_points in (("white", white), ("black", black)):
                for (col, row) in tut_points(text_points):
                    vertex = GnuGoController.index_to_vertex(col, row, ctrl.size)
                    sent, text = ctrl._send("play {0} {1}".format(color, vertex))
                    if sent:
                        ctrl.moves.append((color, vertex))
                    else:
                        ok = False
            ctrl.to_move = to_move
            ctrl._sync_locked(False)
        ui_state.marks = frozenset(tut_points(marks))
        ui_state.dead = frozenset()
        ui_state.hover = None
        ui_state.seen_moves = len(ctrl.moves)   # setup stones make no sound
        return ok

    def tut_apply(ex):
        """Set up an exercise (a dict, see the lessons) and its button rules."""
        ok = tut_setup(ex.get("black", ""), ex.get("white", ""),
                              ex.get("marks", ""))
        needs = ex.get("needs")
        ui_state.allow_pass = (needs == "pass")
        ui_state.allow_resign = (needs == "resign")
        ui_state.allow_board = bool(ex.get("board", True))
        return ok

    def tut_is_target(ex, col, row):
        targets = ex.get("targets")
        if not targets:
            return True
        return (col, row) in tut_points(targets)

    def tut_try(vertex, color):
        """Try a move for a colour. Returns the ctrl.play() result dict."""
        idx = GnuGoController.vertex_to_index(vertex, ctrl.size)
        if idx is None:
            return {"ok": False, "reason": "illegal", "captured": 0,
                    "vertex": vertex, "text": ""}
        return ctrl.play(idx[0], idx[1], color)

    def tut_reply(candidates):
        """Monika plays White on the first free point of the list.
        Returns the vertex she played, or None."""
        for vertex in candidates.split():
            idx = GnuGoController.vertex_to_index(vertex, ctrl.size)
            if idx is None:
                continue
            if idx in ctrl.black_stones or idx in ctrl.white_stones:
                continue
            res = ctrl.play(idx[0], idx[1], "white")
            if res["ok"]:
                return vertex
        return None

    def tut_clear_marks():
        ui_state.marks = frozenset()


## --------------------------------------------------------------------------
## The exercise loop. Set olunym_go_ex first, then "call olunym_go_tut_exercise".
##
## olunym_go_ex keys (all optional):
##   black, white  stones, as text like "D5 F5"
##   marks         points to highlight
##   targets       the point(s) that solve it (default: any legal move)
##   illegal       "suicide": the exercise is solved by trying that illegal move
##   needs         "pass" or "resign": solved by pressing that button
##   board         False to switch off board clicks
##   hint          what Monika says after a wrong move
##
## Afterwards olunym_go_ex_status is "ok", or "dead" if GNU Go stopped.
## --------------------------------------------------------------------------
label olunym_go_tut_exercise:
    $ olunym_go_ex_status = "ok"
    $ olunym_go.tut_apply(olunym_go_ex)

label olunym_go_tut_ex_wait:
    $ olunym_go.block_rb()
    if not olunym_go.ctrl.is_ready:
        $ olunym_go_ex_status = "dead"
        return
    call screen olunym_go_board
    $ olunym_go_act = _return
    if olunym_go_act is None:
        jump olunym_go_tut_ex_wait
    if olunym_go_act[0] == "play":
        jump olunym_go_tut_ex_play
    if olunym_go_act[0] == "undo":
        jump olunym_go_tut_ex_undo
    if olunym_go_act[0] == olunym_go_ex.get("needs"):
        return
    jump olunym_go_tut_ex_wait

label olunym_go_tut_ex_play:
    $ olunym_go_res = olunym_go.ctrl.play(olunym_go_act[1], olunym_go_act[2], "black")
    show screen olunym_go_view
    if olunym_go_res["reason"] == "engine":
        $ olunym_go_ex_status = "dead"
        return
    $ olunym_go_ex_hit = olunym_go.tut_is_target(olunym_go_ex, olunym_go_act[1], olunym_go_act[2])
    if olunym_go_ex.get("illegal"):
        if olunym_go_res["reason"] == olunym_go_ex["illegal"]:
            return
    elif olunym_go_res["ok"] and olunym_go_ex_hit:
        return
    jump olunym_go_tut_ex_wrong

label olunym_go_tut_ex_wrong:
    if olunym_go_res["reason"] == "occupied":
        m 1rksdlb "There's already a stone there, ahaha. Pick an empty point."
    else:
        $ olunym_go_line = olunym_go_ex.get("hint", "Not quite. Look at the dotted point.")
        m 1eka "[olunym_go_line]"
        $ olunym_go.tut_apply(olunym_go_ex)
        show screen olunym_go_view
    jump olunym_go_tut_ex_wait

label olunym_go_tut_ex_undo:
    $ olunym_go.tut_apply(olunym_go_ex)
    show screen olunym_go_view
    $ olunym_go_line = olunym_go.tut_pick("undo")
    m 1eua "[olunym_go_line]"
    jump olunym_go_tut_ex_wait


## --------------------------------------------------------------------------
## Start of the lesson
## --------------------------------------------------------------------------
label olunym_go_tutorial:
    $ olunym_go.reset_ui()
    $ olunym_go_tut_ok, olunym_go_tut_dummy = olunym_go.start_game(9, 1, 0)
    if not olunym_go_tut_ok:
        jump olunym_go_start_failed

    $ olunym_go.ui_state.tutorial = True
    $ olunym_go.ui_state.lesson = "The board"
    $ olunym_go.tut_setup()
    show monika 1eua at t21
    show screen olunym_go_view

    m 1hub "Okay, let's start the lesson! We'll use a small 9x9 board, so it's easy to see everything."
    m 1eua "You'll place stones yourself as we go. If you want to redo an exercise, press Undo. It's always available."
    m 1eub "Pass and Resign stay switched off until I explain what they're for."
    m 1eua "First, the board. Stones go on the crossings of the lines, not inside the little squares."
    m 1eua "Black always moves first, and then we take turns, one stone each. You're Black."
    m 1eka "Once a stone is placed, it never moves. The only way it leaves is by being captured."
    m 1hua "Let's try it. Click any crossing to place a black stone."

    $ olunym_go_ex = {"hint": "Click any crossing on the board."}
    call olunym_go_tut_exercise
    if olunym_go_ex_status == "dead":
        jump olunym_go_engine_lost

    $ olunym_go.tut_reply("E5 D4 F6 E3 C5 G5 C3")
    show screen olunym_go_view
    m 1hub "Nice! And now I put down a white stone. See how we alternate?"
    m 1eua "The goal of the game is to surround more empty space than I do. Space you surround is your territory."
    m 1eua "But first, we need to talk about how stones survive."
    jump olunym_go_tut_liberties


## --------------------------------------------------------------------------
## Lesson 2: liberties and chains
## --------------------------------------------------------------------------
label olunym_go_tut_liberties:
    $ olunym_go.ui_state.lesson = "Liberties"
    $ olunym_go.tut_setup(black="E5", marks="E6 E4 D5 F5")
    show screen olunym_go_view
    m 1eub "Every stone needs room to breathe. The empty points right next to it, above, below, left and right, are called liberties."
    m 1eua "I've marked them with blue dots. This stone has four. Diagonal points don't count."

    $ olunym_go.tut_setup(black="A5", marks="A6 A4 B5")
    m 1eua "On the edge there is less room: only three liberties."

    $ olunym_go.tut_setup(black="A1", marks="A2 B1")
    m 1rksdla "And in the corner, just two. Remember that. Stones near the edge are easier to capture."

    $ olunym_go.tut_setup(black="E5 E4", marks="E6 E3 D5 F5 D4 F4")
    m 1eub "When stones touch each other, they form a chain, and they share their liberties. This chain of two stones has six."
    m 1hua "Now you try. Add a stone next to this one by clicking a dotted point."

    $ olunym_go_ex = {
        "black": "E5", "marks": "D5 F5 E6 E4", "targets": "D5 F5 E6 E4",
        "hint": "Click one of the dotted points, right next to the stone."
    }
    call olunym_go_tut_exercise
    if olunym_go_ex_status == "dead":
        jump olunym_go_engine_lost

    $ olunym_go.tut_clear_marks()
    show screen olunym_go_view
    m 1hub "Perfect! Now those two stones are connected, and they share all their liberties."
    jump olunym_go_tut_capture


## --------------------------------------------------------------------------
## Lesson 3: capturing
## --------------------------------------------------------------------------
label olunym_go_tut_capture:
    $ olunym_go.ui_state.lesson = "Capturing"
    $ olunym_go.tut_setup(black="D5 F5 E6", white="E5", marks="E4")
    show screen olunym_go_view
    m 1eua "Here is the important part. When a stone loses its last liberty, it is captured and removed from the board."
    m 1eub "This white stone is surrounded on three sides. Only one liberty is left, at the dotted point."
    m 1hua "Take it! Click the dotted point."

    $ olunym_go_ex = {
        "black": "D5 F5 E6", "white": "E5", "marks": "E4", "targets": "E4",
        "hint": "That white stone has just one liberty left. Click the dotted point to fill it."
    }
    call olunym_go_tut_exercise
    if olunym_go_ex_status == "dead":
        jump olunym_go_engine_lost

    $ olunym_go.tut_clear_marks()
    show screen olunym_go_view
    m 1wub "You captured it! The stone is gone, and the captured stones are counted on the right."
    m 1eua "A stone with only one liberty left is in atari. It's a warning: the next move could capture it."
    m 1eua "Captured stones count in the final score, so every one of them matters."

    m 1eub "Now a harder one. Stones in a chain are captured together. Capture these two white stones."
    $ olunym_go_ex = {
        "black": "A3 A6 B4", "white": "A4 A5", "marks": "B5", "targets": "B5",
        "hint": "Those two white stones share one liberty. Click the dotted point."
    }
    call olunym_go_tut_exercise
    if olunym_go_ex_status == "dead":
        jump olunym_go_engine_lost

    $ olunym_go.tut_clear_marks()
    show screen olunym_go_view
    m 1hub "Two at once! Stones in a chain live and die together."
    jump olunym_go_tut_atari


## --------------------------------------------------------------------------
## Lesson 4: atari and running away
## --------------------------------------------------------------------------
label olunym_go_tut_atari:
    $ olunym_go.ui_state.lesson = "Atari"
    $ olunym_go.tut_setup(black="E5", white="D5 F5 E6", marks="E4")
    show screen olunym_go_view
    m 1rksdla "Now I'll turn it around. This time it's your stone that's in atari. It has one liberty left, and if I play there, I capture it."
    m 1eua "You have two choices when that happens. Capture the stones that surround it, or run away by extending."
    m 1eub "Let's try running. Click the dotted point to extend your stone."

    $ olunym_go_ex = {
        "black": "E5", "white": "D5 F5 E6", "marks": "E4", "targets": "E4",
        "hint": "Extend to the dotted point, so the stone gets more liberties."
    }
    call olunym_go_tut_exercise
    if olunym_go_ex_status == "dead":
        jump olunym_go_engine_lost

    $ olunym_go.tut_clear_marks()
    show screen olunym_go_view
    m 1hub "Safe, for now! Your chain has three liberties again."
    m 1eua "Running doesn't always work, but checking your stones for atari is a habit worth building."
    jump olunym_go_tut_illegal
