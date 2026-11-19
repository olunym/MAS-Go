## Monika After Story submod: Go (Baduk) minigame
## File: game/Submods/MAS_Go_Minigame/go_screen.rpy
##
## PNG board and stones, MAS-style HUD, stone-placement sounds, and the
## tutorial hooks (hint dots, lesson title, Pass/Resign gating).
## Compatible with Python 2.7 (Ren'Py 6.99) and Python 3.9+ (Ren'Py 8).
##
## Needs the assets folder next to this file:
##   assets/board_9.png  board_13.png  board_19.png
##   assets/stone_black_N.png  stone_white_N.png  ghost_N.png
##   assets/marker_N.png  dead_N.png  hint_N.png   (N = 9, 13, 19)
##   assets/hud_panel.png  hud_panel_d.png  glow.png
##   assets/icon_black.png  icon_white.png
##   assets/sfx/stone_player.ogg  stone_monika.ogg
##
## The screen ends an interaction by returning one of these tuples:
##   ("play", col, row)  - player clicked an empty intersection (row 0 = bottom)
##   ("pass",)           - Pass button
##   ("undo",)           - Undo button
##   ("resign",)         - Resign button
##   ("ai_done",)        - a background GNU Go job finished (see olunym_go.ctrl.take_result())
##   ("done",)           - Continue button (only shown when phase == "over")

init python in olunym_go_minigame:
    import store
    try:
        import pygame_sdl2 as _go_pygame
    except ImportError:
        import pygame as _go_pygame

    # ----------------------------------------------------------------------
    # Layout constants. The screen is designed for MAS's 1280x720 window.
    # BOARD_PX, MARGIN and STONE must match the PNGs
    # in the assets folder.
    # ----------------------------------------------------------------------
    ASSETS = "Submods/MAS_Go_Minigame/assets/"
    SFX_PLAYER = ASSETS + "sfx/stone_player.ogg"
    SFX_MONIKA = ASSETS + "sfx/stone_monika.ogg"

    BOARD_PX = 520
    MARGIN = 36
    BOARD_X = 568
    BOARD_Y = 16
    HUD_X = 1100
    HUD_Y = 16
    HUD_W = 168

    # board size -> (stone diameter, stone image size in pixels)
    STONE = {
        9: (52, 58),
        13: (35, 41),
        19: (23, 29)
    }


    class UiState(_GoPlainBase):
        """Small shared UI state (hover point, dead stones, sound counter).

        Plain object, created once and never reassigned, so it stays out of
        save files and rollback.
        """

        def __init__(self):
            self.reset()

        def reset(self):
            self.hover = None
            self.dead = frozenset()
            # tutorial mode (see go_tutorial.rpy)
            self.tutorial = False
            self.lesson = ""
            self.marks = frozenset()     # points highlighted by hint dots
            self.allow_board = True      # may the player click the board?
            self.allow_pass = False      # Pass button, tutorial only
            self.allow_resign = False    # Resign button, tutorial only
            try:
                self.seen_moves = len(ctrl.moves)
            except Exception:
                self.seen_moves = 0

        def __reduce__(self):
            return (_get_ui, ())


    def _get_ui():
        return ui_state


    ui_state = UiState()


    # ----------------------------------------------------------------------
    # Coordinate helpers
    # ----------------------------------------------------------------------
    def index_to_vertex(col, row, size=19):
        """(col, row) -> GTP vertex like 'D4'. Skips the letter I (A-T, 1-19).
        col 0 is the left column, row 0 is the BOTTOM row. None if off-board."""
        return GnuGoController.index_to_vertex(col, row, size)


    def vertex_to_index(vertex, size=19):
        """GTP vertex like 'D4' -> (col, row). None for PASS/RESIGN/garbage."""
        return GnuGoController.vertex_to_index(vertex, size)


    def hoshi_points(size):
        """Star points (hoshi) as a list of (col, row) for 9, 13 and 19.
        The board PNGs already contain them; kept for reference."""
        if size == 9:
            return [(2, 2), (6, 2), (2, 6), (6, 6), (4, 4)]
        if size == 13:
            return [(3, 3), (9, 3), (3, 9), (9, 9), (6, 6)]
        if size == 19:
            points = []
            for c in (3, 9, 15):
                for r in (3, 9, 15):
                    points.append((c, r))
            return points
        return []


    def reset_ui():
        ui_state.reset()


    def is_dark():
        """True when MAS is in dark mode (picks the _dark styles and panel)."""
        try:
            return bool(store.mas_globals.dark_mode)
        except Exception:
            return False


    def can_pass(interactive):
        """Pass button rule. In the tutorial only when a lesson asks for it."""
        if not interactive:
            return False
        if ui_state.tutorial:
            return bool(ui_state.allow_pass)
        return bool(ctrl.is_ready and not ctrl.thinking
                    and not ctrl.game_over and ctrl.to_move == "black")


    def can_resign(interactive):
        """Resign button rule. In the tutorial only when a lesson asks for it."""
        if not interactive:
            return False
        if ui_state.tutorial:
            return bool(ui_state.allow_resign)
        return bool(ctrl.is_ready and not ctrl.thinking
                    and not ctrl.game_over)


    def can_undo(interactive):
        """Undo button rule. Always on in the tutorial (it restarts the exercise)."""
        if not interactive:
            return False
        if ui_state.tutorial:
            return bool(ctrl.is_ready)
        return bool(ctrl.can_undo and not ctrl.game_over)


    def poll():
        """Used by the screen timer. Returning a value ends the interaction."""
        if ctrl.result_ready:
            return ("ai_done",)
        return None


    def last_move_text():
        last = ctrl.last_move
        if not last:
            return "No moves yet."
        if last.get("color") == "black":
            who = "You"
        else:
            who = "Monika"
        if last.get("pass"):
            return "Last move: {0} passed.".format(who)
        vertex = GnuGoController.index_to_vertex(
            last.get("col", -1), last.get("row", -1), ctrl.size)
        if vertex is None:
            return "Last move: {0} played.".format(who)
        return "Last move: {0} played {1}.".format(who, vertex)


    def status_widget(st, at, phase="play"):
        """DynamicDisplayable callback: current turn / thinking status."""
        if ui_state.tutorial:
            label = "Lesson"
        elif phase == "over" or ctrl.game_over:
            label = "Game over"
        elif not ctrl.is_ready and ctrl.error:
            label = "Engine stopped"
        elif ctrl.thinking:
            label = "Monika is thinking..."
        elif ctrl.to_move == "black":
            label = "Your Turn"
        else:
            label = "Monika's turn"
        if is_dark():
            style_name = "olunym_go_status_dark"
        else:
            style_name = "olunym_go_status"
        return (store.Text(label, style=style_name), 0.3)


    # ----------------------------------------------------------------------
    # The board displayable
    # ----------------------------------------------------------------------
    class Board(renpy.Displayable):

        def __init__(self, phase="play", enabled=True, **kwargs):
            renpy.Displayable.__init__(self, **kwargs)
            self.phase = phase
            self.enabled = enabled

        # -- geometry -------------------------------------------------------
        def _step(self, size):
            span = BOARD_PX - 2 * MARGIN
            return float(span) / float(size - 1)

        def _pos(self, col, row, size, step):
            x = MARGIN + col * step
            y = MARGIN + (size - 1 - row) * step
            return (x, y)

        def _hit(self, x, y):
            size = ctrl.size
            step = self._step(size)
            gx = (x - MARGIN) / step
            gy = (y - MARGIN) / step
            col = int(round(gx))
            grid_row = int(round(gy))
            if col < 0 or col >= size or grid_row < 0 or grid_row >= size:
                return None
            return (col, size - 1 - grid_row)

        def _can_play(self):
            return bool(
                self.enabled
                and self.phase == "play"
                and ctrl.is_ready
                and not ctrl.thinking
                and not ctrl.game_over
                and ctrl.to_move == "black"
                and ui_state.allow_board
            )

        # -- drawing helpers ------------------------------------------------
        def _blit(self, r, name, cx, cy, img_size, st, at):
            rend = renpy.render(store.Image(ASSETS + name),
                                img_size, img_size, st, at)
            r.blit(rend, (int(round(cx - img_size / 2.0)),
                          int(round(cy - img_size / 2.0))))

        # -- sound ----------------------------------------------------------
        def _check_sound(self):
            """Play a click for every newly placed stone.

            Black (you) always uses stone_player.ogg and White (Monika)
            always uses stone_monika.ogg. Passes are silent. If both of
            your stone and her reply show up in the same frame, the first
            plays now and the second is queued right behind it.
            """
            try:
                moves = list(ctrl.moves)
                count = len(moves)
                seen = ui_state.seen_moves
                ui_state.seen_moves = count
                if count <= seen:
                    return
                fresh = []
                for entry in moves[seen:]:
                    if entry[1] != "PASS":
                        fresh.append(entry)
                fresh = fresh[-2:]
                first = True
                for entry in fresh:
                    if entry[0] == "black":
                        path = SFX_PLAYER
                    else:
                        path = SFX_MONIKA
                    if first:
                        renpy.play(path, channel="sound")
                        first = False
                    else:
                        try:
                            renpy.music.queue(path, channel="sound",
                                              loop=False, clear_queue=False)
                        except Exception:
                            renpy.play(path, channel="sound")
            except Exception as e:
                renpy.write_log("MAS Go: sound failed: {0}".format(repr(e)))

        # -- Displayable API ------------------------------------------------
        def per_interact(self):
            self._check_sound()
            renpy.redraw(self, 0)

        def visit(self):
            return []

        def render(self, width, height, st, at):
            px = BOARD_PX
            size = ctrl.size
            if size not in STONE:
                size = 9
            step = self._step(size)
            diameter, img_size = STONE[size]

            r = renpy.Render(px, px)

            # board (wood, frame, grid, star points and labels are in the PNG)
            board = renpy.render(store.Image(ASSETS + "board_{0}.png".format(size)),
                                 px, px, st, at)
            r.blit(board, (0, 0))

            black = ctrl.black_stones
            white = ctrl.white_stones

            # hover preview (only on empty points when it is the player's turn)
            hover = ui_state.hover
            if hover is not None and self._can_play():
                if hover not in black and hover not in white:
                    hx, hy = self._pos(hover[0], hover[1], size, step)
                    self._blit(r, "ghost_{0}.png".format(size), hx, hy, img_size, st, at)

            # stones
            for (sc, sr) in black:
                sx, sy = self._pos(sc, sr, size, step)
                self._blit(r, "stone_black_{0}.png".format(size), sx, sy, img_size, st, at)
            for (sc, sr) in white:
                sx, sy = self._pos(sc, sr, size, step)
                self._blit(r, "stone_white_{0}.png".format(size), sx, sy, img_size, st, at)

            # dead-stone marks (after scoring)
            for (dc, dr) in ui_state.dead:
                dx, dy = self._pos(dc, dr, size, step)
                self._blit(r, "dead_{0}.png".format(size), dx, dy, img_size, st, at)

            # tutorial hint dots (empty points a lesson wants you to look at)
            for (kc, kr) in ui_state.marks:
                kx, ky = self._pos(kc, kr, size, step)
                self._blit(r, "hint_{0}.png".format(size), kx, ky, img_size, st, at)

            # last-move marker
            last = ctrl.last_move
            if last and not last.get("pass") and "col" in last:
                lx, ly = self._pos(last["col"], last["row"], size, step)
                self._blit(r, "marker_{0}.png".format(size), lx, ly, img_size, st, at)

            # backup trigger in case per_interact was not called
            self._check_sound()

            return r

        def event(self, ev, x, y, st):
            if not self.enabled:
                return None

            if ev.type == _go_pygame.MOUSEMOTION:
                new_hover = None
                if self._can_play():
                    new_hover = self._hit(x, y)
                if new_hover != ui_state.hover:
                    ui_state.hover = new_hover
                    renpy.redraw(self, 0)
                return None

            if ev.type == _go_pygame.MOUSEBUTTONUP and ev.button == 1:
                if not self._can_play():
                    return None
                hit = self._hit(x, y)
                if hit is None:
                    return None
                if hit in ctrl.black_stones or hit in ctrl.white_stones:
                    return None
                ui_state.hover = None
                return ("play", hit[0], hit[1])

            return None


## --------------------------------------------------------------------------
## Styles. Buttons reuse MAS's own generic button styles, so they look like
## the buttons in the chess game (including dark mode).
## --------------------------------------------------------------------------
style olunym_go_button is generic_button_light:
    xysize (148, None)
    padding (4, 5, 4, 5)

style olunym_go_button_dark is generic_button_dark:
    xysize (148, None)
    padding (4, 5, 4, 5)

style olunym_go_button_text is generic_button_text_light:
    xalign 0.5
    text_align 0.5
    layout "subtitle"

style olunym_go_button_text_dark is generic_button_text_dark:
    xalign 0.5
    text_align 0.5
    layout "subtitle"

style olunym_go_text is default:
    font gui.default_font
    size 18
    color "#ffffff"
    outlines [(2, "#b59", 0, 0)]

style olunym_go_text_dark is default:
    font gui.default_font
    size 18
    color "#FFD9E8"
    outlines [(2, "#DE367E", 0, 0)]

style olunym_go_status is olunym_go_text:
    size 20
    xmaximum 140

style olunym_go_status_dark is olunym_go_text_dark:
    size 20
    xmaximum 140


## --------------------------------------------------------------------------
## Shared drawing code used by both screens below.
## --------------------------------------------------------------------------
screen olunym_go_contents(phase="play", interactive=True):
    $ olunym_go_dk = olunym_go.is_dark()
    if olunym_go_dk:
        $ olunym_go_ts = "olunym_go_text_dark"
        $ olunym_go_bs = "olunym_go_button_dark"
        $ olunym_go_bts = "olunym_go_button_text_dark"
        $ olunym_go_panel = olunym_go.ASSETS + "hud_panel_d.png"
    else:
        $ olunym_go_ts = "olunym_go_text"
        $ olunym_go_bs = "olunym_go_button"
        $ olunym_go_bts = "olunym_go_button_text"
        $ olunym_go_panel = olunym_go.ASSETS + "hud_panel.png"

    # soft drop shadow, then the board itself
    add Solid("#00000055") xpos (olunym_go.BOARD_X + 5) ypos (olunym_go.BOARD_Y + 6) size (olunym_go.BOARD_PX, olunym_go.BOARD_PX)
    add olunym_go.Board(phase, interactive) xpos olunym_go.BOARD_X ypos olunym_go.BOARD_Y

    # HUD column on the right, like the chess game
    vbox:
        xpos olunym_go.HUD_X
        ypos olunym_go.HUD_Y
        xsize olunym_go.HUD_W
        spacing 8

        if phase == "over":
            textbutton "Continue":
                style olunym_go_bs
                text_style olunym_go_bts
                action Return(("done",))
                sensitive (interactive and not olunym_go.ctrl.thinking)
        else:
            textbutton "Pass":
                style olunym_go_bs
                text_style olunym_go_bts
                action Return(("pass",))
                sensitive olunym_go.can_pass(interactive)
            textbutton "Undo":
                style olunym_go_bs
                text_style olunym_go_bts
                action Return(("undo",))
                sensitive olunym_go.can_undo(interactive)
            textbutton "Resign":
                style olunym_go_bs
                text_style olunym_go_bts
                action Return(("resign",))
                sensitive olunym_go.can_resign(interactive)

        frame:
            background Frame(olunym_go_panel, 3, 3)
            xsize olunym_go.HUD_W
            padding (14, 12, 14, 12)

            vbox:
                spacing 5

                add DynamicDisplayable(olunym_go.status_widget, phase)

                null height 4
                text "Captured stones" style olunym_go_ts size 16

                hbox:
                    spacing 6
                    fixed:
                        xsize 40
                        ysize 40
                        if olunym_go.ctrl.to_move == "black" and not olunym_go.ctrl.game_over and not olunym_go.ctrl.thinking:
                            add (olunym_go.ASSETS + "glow.png") align (0.5, 0.5)
                        add (olunym_go.ASSETS + "icon_black.png") align (0.5, 0.5)
                    text ("You: {0}".format(olunym_go.ctrl.captures_by_black)) style olunym_go_ts yalign 0.5

                hbox:
                    spacing 6
                    fixed:
                        xsize 40
                        ysize 40
                        if (olunym_go.ctrl.to_move == "white" or olunym_go.ctrl.thinking) and not olunym_go.ctrl.game_over:
                            add (olunym_go.ASSETS + "glow.png") align (0.5, 0.5)
                        add (olunym_go.ASSETS + "icon_white.png") align (0.5, 0.5)
                    text ("Monika: {0}".format(olunym_go.ctrl.captures_by_white)) style olunym_go_ts yalign 0.5

                null height 4
                if olunym_go.ui_state.tutorial:
                    text ("Lesson: {0}".format(olunym_go.ui_state.lesson)) style olunym_go_ts size 15 xmaximum 140
                else:
                    text ("{0}x{0} board, komi {1}".format(olunym_go.ctrl.size, olunym_go.ctrl.komi)) style olunym_go_ts size 15
                    if olunym_go.ctrl.handicap_stones >= 2:
                        text ("Handicap: {0} stones".format(olunym_go.ctrl.handicap_stones)) style olunym_go_ts size 15
                    text olunym_go.last_move_text() style olunym_go_ts size 15 xmaximum 140

    # Poll while GNU Go works so the UI reacts the moment its answer is ready.
    if interactive and (olunym_go.ctrl.thinking or olunym_go.ctrl.result_ready):
        timer 0.15 repeat True action Function(olunym_go.poll)


## Interactive and modal. Used with "call screen olunym_go_board".
screen olunym_go_board(phase="play", interactive=True):
    tag olunym_go
    modal True
    zorder -1
    use olunym_go_contents(phase, interactive)


## Display only and not modal, so Monika's dialogue still advances.
## Used with "show screen olunym_go_view".
screen olunym_go_view(phase="play"):
    tag olunym_go
    zorder -1
    use olunym_go_contents(phase, False)
