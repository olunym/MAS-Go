## Monika After Story submod: Go (Baduk) minigame
## File: game/Submods/MAS_Go_Minigame/go_engine.rpy
## Copyright (c) 2026 olunym. MIT License, see LICENSE.
##
## GnuGoController: owns the GNU Go process and talks GTP to it.
## Lives in the store "olunym_go_minigame"; the shared controller is
## olunym_go_minigame.ctrl (reached as olunym_go.ctrl from labels and screens).
## Compatible with Python 2.7 (Ren'Py 6) and Python 3.9+ (Ren'Py 8).
##
## Coordinate convention used by this controller:
##   col: 0..size-1, left to right  (GTP letters A-T, skipping I)
##   row: 0..size-1, BOTTOM to top  (row 0 == GTP row 1)
## The screen file flips rows when drawing.

init -5 python in olunym_go_minigame:
    import os
    import re as _go_re
    import time as _go_time
    import errno as _go_errno
    import atexit as _go_atexit
    import platform as _go_platform
    import threading as _go_threading
    import subprocess as _go_subprocess

    # The real builtin "object": a plain class that Ren'Py does not try to
    # roll back or pickle. This keeps the subprocess handle and the worker
    # thread out of save files and rollback.
    try:
        import builtins as _go_builtins
    except ImportError:
        import __builtin__ as _go_builtins
    _GoPlainBase = _go_builtins.object


    class GnuGoController(_GoPlainBase):

        SUBMOD_FOLDER = "MAS_Go_Minigame"
        GTP_LETTERS = "ABCDEFGHJKLMNOPQRST"
        BOARD_SIZES = (9, 13, 19)
        DIFFICULTIES = (
            ("Beginner", 1),
            ("Casual", 4),
            ("Club Player", 8),
            ("Strong", 10)
        )
        HANDICAP_CHOICES = (0, 2, 3, 4)
        LOG_TO_FILE = True
        HANDSHAKE_TIMEOUT = 15.0

        # ------------------------------------------------------------------
        # construction / state
        # ------------------------------------------------------------------
        def __init__(self):
            self._io_lock = _go_threading.RLock()
            self._log_lock = _go_threading.Lock()
            self.proc = None
            self._devnull = None
            self._worker = None
            self._quitting = False
            self._generation = 0
            self.alive = False
            self.thinking = False
            self.pending_result = None
            self.debug_log = []
            self.binary_path = None
            self.binary_source = None
            self.engine_name = ""
            self.engine_version = ""
            self.error = None
            self.error_code = None
            self.error_detail = ""
            self._reset_game_state()
            try:
                _go_atexit.register(self._safe_quit)
            except Exception:
                pass
            self._hook_renpy_quit()

        def _reset_game_state(self):
            self.size = 9
            self.level = 3
            self.komi = 6.5
            self.handicap_stones = 0
            self.moves = []              # list of (color, vertex or "PASS")
            self._cap_log = []           # stones captured by each move
            self.black_stones = frozenset()
            self.white_stones = frozenset()
            self.captures_by_black = 0   # white stones black has captured
            self.captures_by_white = 0   # black stones white has captured
            self.raw_captures = {"black": None, "white": None}
            self.to_move = "black"
            self.last_move = None        # dict or None
            self.last_captured = frozenset()
            self.passes_in_a_row = 0
            self.game_over = False
            self.resigned_color = None

        def _hook_renpy_quit(self):
            try:
                callbacks = getattr(renpy.config, "quit_callbacks", None)
                if callbacks is not None:
                    callbacks.append(self._safe_quit)
            except Exception:
                pass

        def __reduce__(self):
            # Never try to pickle the live process; resolve to the singleton.
            return (_get_controller, ())

        # ------------------------------------------------------------------
        # tiny helpers
        # ------------------------------------------------------------------
        @staticmethod
        def _to_bytes(text):
            if isinstance(text, bytes):
                return text
            return text.encode("utf-8", "replace")

        @staticmethod
        def opposite(color):
            return "white" if color == "black" else "black"

        @staticmethod
        def index_to_vertex(col, row, size=19):
            """(col, row) -> GTP vertex such as 'D4'. None if off-board."""
            if col < 0 or row < 0 or col >= size or row >= size:
                return None
            if col >= len(GnuGoController.GTP_LETTERS):
                return None
            return "{0}{1}".format(GnuGoController.GTP_LETTERS[col], row + 1)

        @staticmethod
        def vertex_to_index(vertex, size=19):
            """GTP vertex -> (col, row). None for PASS/RESIGN/garbage."""
            if not vertex:
                return None
            v = vertex.strip().upper()
            if v in ("PASS", "RESIGN", ""):
                return None
            col = GnuGoController.GTP_LETTERS.find(v[0])
            if col < 0:
                return None
            try:
                number = int(v[1:])
            except ValueError:
                return None
            if number < 1 or number > size or col >= size:
                return None
            return (col, number - 1)

        @staticmethod
        def parse_score(text):
            """Parse GTP final_score text such as 'W+4.5' or 'B+12' or '0'."""
            raw = (text or "").strip()
            info = {"raw": raw, "winner": None, "margin": 0.0}
            match = _go_re.match(r"^([BWbw])\s*\+\s*([0-9]+(?:\.[0-9]+)?)", raw)
            if match:
                if match.group(1).upper() == "B":
                    info["winner"] = "black"
                else:
                    info["winner"] = "white"
                info["margin"] = float(match.group(2))
            return info

        def _parse_vertices(self, text):
            result = set()
            if not text:
                return frozenset()
            for token in text.replace("\n", " ").split():
                idx = self.vertex_to_index(token, self.size)
                if idx is not None:
                    result.add(idx)
            return frozenset(result)

        def _submod_dir(self):
            return os.path.join(renpy.config.gamedir, "Submods", self.SUBMOD_FOLDER)

        def _log(self, message):
            try:
                line = "[{0}] {1}".format(_go_time.strftime("%H:%M:%S"), message)
                with self._log_lock:
                    self.debug_log.append(line)
                    if len(self.debug_log) > 300:
                        del self.debug_log[:100]
                    if self.LOG_TO_FILE:
                        path = os.path.join(self._submod_dir(), "go_engine.log")
                        handle = open(path, "ab")
                        try:
                            handle.write(self._to_bytes(line + "\n"))
                        finally:
                            handle.close()
            except Exception:
                pass

        def get_debug_text(self):
            with self._log_lock:
                return "\n".join(self.debug_log[-60:])

        # ------------------------------------------------------------------
        # errors
        # ------------------------------------------------------------------
        def _clear_error(self):
            self.error = None
            self.error_code = None
            self.error_detail = ""

        def _set_error(self, code, detail=""):
            self.error_code = code
            self.error_detail = detail
            path = self.binary_path or ""
            folder = os.path.dirname(path) if path else ""
            hint_mac = ""
            if renpy.macintosh:
                hint_mac = (
                    " On macOS you may also need to clear the quarantine flag: "
                    "xattr -dr com.apple.quarantine \"{0}\"".format(folder)
                )
            if code == "unsupported_os":
                text = ("This operating system is not supported. The Go "
                        "minigame works on Windows, Linux and macOS.")
            elif code == "binary_missing":
                text = ("I couldn't find the GNU Go program. Put the gnugo "
                        "file in one of these folders: {0} or install GNU Go "
                        "so that it is on your PATH.").format(detail)
            elif code == "permission":
                text = ("GNU Go was found at {0} but the system refuses to "
                        "run it. Make it executable (chmod +x) and check "
                        "your antivirus.{1} Details: {2}").format(
                            path, hint_mac, self._short(detail))
            elif code == "bad_architecture":
                text = ("The GNU Go file at {0} is the wrong kind of program "
                        "for this computer (for example an Intel-only build "
                        "on Apple Silicon without Rosetta, or a Windows file "
                        "on Linux).").format(path)
            elif code == "launch_failed":
                text = "GNU Go could not be started: {0}".format(
                    self._short(detail))
            elif code == "handshake_failed":
                text = ("GNU Go started but did not answer correctly: "
                        "{0}.{1}").format(self._short(detail), hint_mac)
            elif code == "timeout":
                text = "GNU Go started but did not answer in time."
            elif code == "engine_died":
                text = "GNU Go stopped unexpectedly."
            else:
                text = "Something went wrong with GNU Go: {0}".format(
                    self._short(detail))
            self.error = text
            self._log("ERROR {0}: {1}".format(code, self._short(detail)))

        @staticmethod
        def _short(text, limit=200):
            text = str(text)
            if len(text) > limit:
                return text[:limit] + "..."
            return text

        def _mark_dead(self, reason):
            self.alive = False
            if not self._quitting:
                self._set_error("engine_died", reason)

        # ------------------------------------------------------------------
        # OS detection and binary discovery
        # ------------------------------------------------------------------
        @staticmethod
        def detect_platform():
            machine = (_go_platform.machine() or "").lower()
            info = {"key": None, "exe": "gnugo", "folders": [], "machine": machine}
            if renpy.windows:
                info["key"] = "windows"
                info["exe"] = "gnugo.exe"
                info["folders"] = ["windows"]
            elif renpy.macintosh:
                info["key"] = "macos"
                if machine in ("arm64", "aarch64"):
                    info["folders"] = ["macos-arm", "macos-intel", "macos"]
                else:
                    info["folders"] = ["macos-intel", "macos-arm", "macos"]
            elif renpy.linux:
                info["key"] = "linux"
                if machine.startswith("arm") or machine == "aarch64":
                    info["folders"] = ["linux-arm", "linux"]
                else:
                    info["folders"] = ["linux"]
            return info

        def _candidates(self, info):
            """List of (path, is_bundled) to try, best first."""
            result = []
            seen = set()
            base = os.path.join(self._submod_dir(), "bin")
            for folder in info["folders"]:
                path = os.path.join(base, folder, info["exe"])
                if os.path.isfile(path) and path not in seen:
                    seen.add(path)
                    result.append((path, True))
            search_dirs = []
            for entry in (os.environ.get("PATH") or "").split(os.pathsep):
                if entry:
                    search_dirs.append(entry)
            if not renpy.windows:
                for extra in ("/usr/games", "/usr/local/bin", "/opt/homebrew/bin",
                              "/opt/local/bin", "/usr/bin"):
                    search_dirs.append(extra)
            for directory in search_dirs:
                path = os.path.join(directory, info["exe"])
                if os.path.isfile(path) and path not in seen:
                    seen.add(path)
                    result.append((path, False))
            return result

        def expected_locations_text(self):
            info = self.detect_platform()
            base = os.path.join(self._submod_dir(), "bin")
            parts = []
            for folder in info["folders"]:
                parts.append(os.path.join(base, folder, info["exe"]))
            return "; ".join(parts) if parts else base

        def _prepare_bundled(self, path):
            """chmod 0o755 on Unix and try to clear the macOS quarantine flag."""
            if renpy.windows:
                return
            try:
                os.chmod(path, 0o755)
            except (OSError, IOError) as e:
                self._log("chmod failed for {0}: {1}".format(path, repr(e)))
            if renpy.macintosh:
                self._clear_quarantine(path)

        def _clear_quarantine(self, path):
            try:
                null = open(os.devnull, "wb")
                try:
                    _go_subprocess.call(
                        ["xattr", "-d", "com.apple.quarantine", path],
                        stdout=null, stderr=null
                    )
                finally:
                    null.close()
            except Exception as e:
                self._log("xattr failed: {0}".format(repr(e)))

        # ------------------------------------------------------------------
        # process lifecycle
        # ------------------------------------------------------------------
        @property
        def is_ready(self):
            proc = self.proc
            try:
                return bool(self.alive and proc is not None and proc.poll() is None)
            except Exception:
                return False

        def _launch(self, path, level):
            self._quitting = False
            args = [path, "--mode", "gtp", "--level", str(level)]
            kwargs = {}
            if renpy.windows:
                try:
                    kwargs["creationflags"] = getattr(
                        _go_subprocess, "CREATE_NO_WINDOW", 0x08000000)
                    startup = _go_subprocess.STARTUPINFO()
                    startup.dwFlags |= getattr(
                        _go_subprocess, "STARTF_USESHOWWINDOW", 1)
                    startup.wShowWindow = 0
                    kwargs["startupinfo"] = startup
                except Exception as e:
                    self._log("startupinfo setup failed: {0}".format(repr(e)))
            try:
                self._devnull = open(os.devnull, "wb")
            except Exception:
                self._devnull = None
            try:
                self.proc = _go_subprocess.Popen(
                    args,
                    stdin=_go_subprocess.PIPE,
                    stdout=_go_subprocess.PIPE,
                    stderr=(self._devnull if self._devnull is not None
                            else _go_subprocess.STDOUT),
                    cwd=os.path.dirname(path),
                    bufsize=0,
                    close_fds=(os.name != "nt"),
                    **kwargs
                )
            except OSError as e:
                self.proc = None
                code = getattr(e, "errno", None)
                winerr = getattr(e, "winerror", None)
                if code in (_go_errno.EACCES, _go_errno.EPERM) or winerr == 5:
                    self._set_error("permission", repr(e))
                elif code == _go_errno.ENOEXEC or winerr == 193:
                    self._set_error("bad_architecture", repr(e))
                else:
                    self._set_error("launch_failed", repr(e))
                self._close_devnull()
                return False
            except Exception as e:
                self.proc = None
                self._set_error("launch_failed", repr(e))
                self._close_devnull()
                return False
            self._log("launched {0}".format(" ".join(args)))
            return True

        def _close_devnull(self):
            try:
                if self._devnull is not None:
                    self._devnull.close()
            except Exception:
                pass
            self._devnull = None

        def _kill_process(self):
            proc = self.proc
            self.proc = None
            self.alive = False
            if proc is not None:
                try:
                    proc.stdin.write(self._to_bytes("quit\n"))
                    proc.stdin.flush()
                except Exception:
                    pass
                try:
                    proc.stdin.close()
                except Exception:
                    pass
                try:
                    if proc.poll() is None:
                        proc.terminate()
                except Exception:
                    pass
                for _i in range(20):
                    try:
                        if proc.poll() is not None:
                            break
                    except Exception:
                        break
                    _go_time.sleep(0.05)
                try:
                    if proc.poll() is None:
                        proc.kill()
                except Exception:
                    pass
                if not self.thinking:
                    try:
                        proc.stdout.close()
                    except Exception:
                        pass
            self._close_devnull()

        def quit(self):
            """Stop GNU Go. Safe to call any number of times, from anywhere."""
            self._quitting = True
            self._generation += 1
            self._kill_process()
            worker = self._worker
            if worker is not None and worker.is_alive():
                try:
                    worker.join(1.0)
                except Exception:
                    pass
            self._worker = None
            self.thinking = False
            self.pending_result = None

        def _safe_quit(self):
            try:
                self.quit()
            except Exception:
                pass

        def _run_with_timeout(self, func, timeout):
            box = {}

            def runner():
                try:
                    box["value"] = func()
                except Exception as e:
                    box["error"] = e

            thread = _go_threading.Thread(target=runner)
            thread.daemon = True
            thread.start()
            thread.join(timeout)
            if thread.is_alive():
                return (False, None)
            if "error" in box:
                return (True, (False, repr(box["error"])))
            return (True, box.get("value", (False, "no result")))

        # ------------------------------------------------------------------
        # GTP I/O (callers must hold self._io_lock)
        # ------------------------------------------------------------------
        def _send(self, command):
            """Send one GTP command. Returns (ok, text)."""
            proc = self.proc
            if proc is None or proc.poll() is not None:
                return (False, "engine is not running")
            self._log("> " + command)
            try:
                proc.stdin.write(self._to_bytes(command.strip() + "\n"))
                proc.stdin.flush()
            except (IOError, OSError, ValueError) as e:
                self._mark_dead("write failed: " + repr(e))
                return (False, "write failed")
            lines = []
            while True:
                try:
                    raw = proc.stdout.readline()
                except (IOError, OSError, ValueError) as e:
                    self._mark_dead("read failed: " + repr(e))
                    return (False, "read failed")
                if not raw:
                    self._mark_dead("engine closed its output")
                    return (False, "engine closed its output")
                line = str(raw.decode("ascii", "ignore")).rstrip("\r\n")
                if line.strip() == "":
                    if lines:
                        break
                    continue
                lines.append(line)
            self._log("< " + " | ".join(lines))
            head = lines[0]
            if head.startswith("="):
                ok = True
            elif head.startswith("?"):
                ok = False
            else:
                return (False, head)
            body = [head[1:].strip()] + [l.strip() for l in lines[1:]]
            text = "\n".join([b for b in body if b != ""])
            return (ok, text)

        def command(self, text):
            """Run any raw GTP command (debugging). Not allowed while thinking."""
            if self.thinking:
                return (False, "engine is busy")
            with self._io_lock:
                return self._send(text)

        # ------------------------------------------------------------------
        # board model helpers
        # ------------------------------------------------------------------
        def _neighbors(self, col, row):
            for dc, dr in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                c = col + dc
                r = row + dr
                if 0 <= c < self.size and 0 <= r < self.size:
                    yield (c, r)

        def _group_and_liberties(self, start, own, other):
            """Flood fill the group at 'start' inside the set 'own'."""
            group = set([start])
            liberties = set()
            stack = [start]
            while stack:
                point = stack.pop()
                for n in self._neighbors(point[0], point[1]):
                    if n in own:
                        if n not in group:
                            group.add(n)
                            stack.append(n)
                    elif n not in other:
                        liberties.add(n)
            return group, liberties

        def _classify_illegal(self, col, row, color):
            """Why did GNU Go refuse this move? 'occupied', 'suicide' or 'ko'."""
            point = (col, row)
            if point in self.black_stones or point in self.white_stones:
                return "occupied"
            if color == "black":
                own = set(self.black_stones)
                other = set(self.white_stones)
            else:
                own = set(self.white_stones)
                other = set(self.black_stones)
            own.add(point)
            # remove opposing groups this stone would capture
            checked = set()
            for n in self._neighbors(col, row):
                if n in other and n not in checked:
                    group, libs = self._group_and_liberties(n, other, own)
                    checked |= group
                    if not libs:
                        other -= group
            group, libs = self._group_and_liberties(point, own, other)
            if not libs:
                return "suicide"
            return "ko"

        def _align_capture_log(self):
            """Keep the per-move capture log the same length as the move list."""
            while len(self._cap_log) < len(self.moves):
                self._cap_log.append(0)
            del self._cap_log[len(self.moves):]

        def _recount_captures(self):
            black = 0
            white = 0
            for index, entry in enumerate(self.moves):
                count = self._cap_log[index] if index < len(self._cap_log) else 0
                if entry[0] == "black":
                    black += count
                else:
                    white += count
            self.captures_by_black = black
            self.captures_by_white = white

        def _recompute_after_history_change(self):
            """Derive to_move, passes, last_move from self.moves."""
            self._align_capture_log()
            self._recount_captures()
            passes = 0
            for color, vertex in reversed(self.moves):
                if vertex == "PASS":
                    passes += 1
                else:
                    break
            self.passes_in_a_row = passes
            if self.moves:
                color, vertex = self.moves[-1]
                self.to_move = self.opposite(color)
                if vertex == "PASS":
                    self.last_move = {"color": color, "pass": True,
                                      "col": -1, "row": -1, "vertex": "PASS"}
                else:
                    idx = self.vertex_to_index(vertex, self.size)
                    if idx is None:
                        self.last_move = None
                    else:
                        self.last_move = {"color": color, "pass": False,
                                          "col": idx[0], "row": idx[1],
                                          "vertex": vertex}
            else:
                self.to_move = "white" if self.handicap_stones else "black"
                self.last_move = None
            self.last_captured = frozenset()
            self.game_over = (self.resigned_color is not None
                              or self.passes_in_a_row >= 2)

        def _sync_locked(self, track_captures=True):
            """Refresh the stone sets from GNU Go. Caller holds the I/O lock.

            With track_captures False (used when a position is set up by hand)
            the capture history is cleared instead of being kept.
            """
            ok_b, text_b = self._send("list_stones black")
            if not ok_b:
                return False
            ok_w, text_w = self._send("list_stones white")
            if not ok_w:
                return False
            self.black_stones = self._parse_vertices(text_b)
            self.white_stones = self._parse_vertices(text_w)
            if not track_captures:
                self._cap_log = []
                self.last_captured = frozenset()
                self.captures_by_black = 0
                self.captures_by_white = 0
            return True

        # ------------------------------------------------------------------
        # starting a game
        # ------------------------------------------------------------------
        def _handshake(self, size, handicap):
            """Talk to a freshly launched engine. Returns (ok, stage, detail).

            stage is 'hello' if GNU Go did not behave like GNU Go and
            'setup' if it was fine but refused the board settings.
            """
            with self._io_lock:
                ok, text = self._send("name")
                if not ok:
                    return (False, "hello", text)
                self.engine_name = text.strip()
                if "gnu go" not in self.engine_name.lower():
                    return (False, "hello",
                            "unexpected engine name: " + self.engine_name)
                ok, text = self._send("version")
                if ok:
                    self.engine_version = text.strip()
                ok, text = self._send("boardsize {0}".format(size))
                if not ok:
                    return (False, "setup", "boardsize refused: " + text)
                ok, text = self._send("clear_board")
                if not ok:
                    return (False, "setup", "clear_board refused: " + text)
                self.size = size
                if handicap >= 2:
                    self.komi = 0.5
                else:
                    self.komi = 6.5
                ok, text = self._send("komi {0}".format(self.komi))
                if not ok:
                    return (False, "setup", "komi refused: " + text)
                if handicap >= 2:
                    ok, text = self._send("fixed_handicap {0}".format(handicap))
                    if not ok:
                        return (False, "setup", "handicap refused: " + text)
                    self.handicap_stones = handicap
                    self.to_move = "white"
                if not self._sync_locked(False):
                    return (False, "setup", "could not read the board")
                return (True, "ready", "")

        def start(self, boardsize=9, level=3, handicap=0, komi=None):
            """Launch GNU Go and set up a new game. Returns True on success.

            On failure, self.error holds a message for the player and
            self.error_code a short code (see _set_error).
            """
            self.quit()
            self._reset_game_state()
            self._clear_error()
            self.engine_name = ""
            self.engine_version = ""
            self.binary_path = None
            self.binary_source = None
            try:
                size = int(boardsize)
            except (TypeError, ValueError):
                size = 9
            if size not in self.BOARD_SIZES:
                size = 9
            try:
                level = int(level)
            except (TypeError, ValueError):
                level = 3
            level = max(0, min(10, level))
            try:
                handicap = int(handicap)
            except (TypeError, ValueError):
                handicap = 0
            if handicap < 2:
                handicap = 0
            self.level = level

            info = self.detect_platform()
            if info["key"] is None:
                self._set_error("unsupported_os")
                return False
            candidates = self._candidates(info)
            if not candidates:
                self._set_error("binary_missing", self.expected_locations_text())
                return False

            for path, bundled in candidates:
                self.binary_path = path
                self.binary_source = "bundled" if bundled else "system"
                self._clear_error()
                if bundled:
                    self._prepare_bundled(path)
                if not self._launch(path, level):
                    continue
                done, result = self._run_with_timeout(
                    lambda: self._handshake(size, handicap),
                    self.HANDSHAKE_TIMEOUT)
                if not done:
                    self._kill_process()
                    self._set_error("timeout")
                    continue
                ok, stage, detail = result
                if ok:
                    self.alive = True
                    self._clear_error()
                    self._log("ready: {0} {1} (size {2}, level {3}, handicap {4})".format(
                        self.engine_name, self.engine_version, size, level,
                        handicap))
                    return True
                self._kill_process()
                self._set_error("handshake_failed", detail)
                if stage == "setup":
                    # The program is fine; it just refused these settings.
                    # Trying another copy of GNU Go would not help.
                    return False
            return False

        # ------------------------------------------------------------------
        # moves
        # ------------------------------------------------------------------
        def _fail(self, reason, vertex="", text=""):
            return {"ok": False, "reason": reason, "captured": 0,
                    "vertex": vertex, "text": text}

        def _record_move(self, color, vertex, captured, removed):
            """Append a move to the history. Caller holds the I/O lock."""
            self._align_capture_log()
            self.moves.append((color, vertex))
            self._cap_log.append(captured)
            self._recount_captures()
            self.passes_in_a_row = 0
            self.to_move = self.opposite(color)
            self.last_captured = removed
            idx = self.vertex_to_index(vertex, self.size)
            if idx is None:
                self.last_move = None
            else:
                self.last_move = {"color": color, "pass": False,
                                  "col": idx[0], "row": idx[1],
                                  "vertex": vertex}

        def _apply_stone_locked(self, color, vertex):
            """After GNU Go accepted a stone: refresh and work out captures.

            Returns (captured_count, removed_points) or None if the board
            could not be read.
            """
            if color == "black":
                before = self.white_stones
            else:
                before = self.black_stones
            if not self._sync_locked(True):
                return None
            if color == "black":
                after = self.white_stones
            else:
                after = self.black_stones
            removed = frozenset(before - after)
            self._record_move(color, vertex, len(removed), removed)
            return (len(removed), removed)

        def play(self, col, row, color="black"):
            """Place a stone for 'color'. Returns a dict:
            {"ok", "reason", "captured", "vertex", "text"}
            reason: None, 'occupied', 'ko', 'suicide', 'illegal', 'engine',
            'game_over', 'busy' or 'off_board'.
            """
            if self.game_over:
                return self._fail("game_over")
            if self.thinking:
                return self._fail("busy")
            if not self.is_ready:
                return self._fail("engine")
            vertex = self.index_to_vertex(col, row, self.size)
            if vertex is None:
                return self._fail("off_board")
            with self._io_lock:
                if (col, row) in self.black_stones or (col, row) in self.white_stones:
                    return self._fail("occupied", vertex)
                ok, text = self._send("play {0} {1}".format(color, vertex))
                if not ok:
                    if not self.is_ready:
                        return self._fail("engine", vertex, text)
                    reason = self._classify_illegal(col, row, color)
                    return self._fail(reason, vertex, text)
                outcome = self._apply_stone_locked(color, vertex)
                if outcome is None:
                    return self._fail("engine", vertex, "could not read the board")
                return {"ok": True, "reason": None, "captured": outcome[0],
                        "vertex": vertex, "text": ""}

        def pass_turn(self, color="black"):
            """Pass for 'color'. Two passes in a row end the game.
            Returns {"ok", "game_over", "text"}."""
            if self.game_over or self.thinking or not self.is_ready:
                return {"ok": False, "game_over": self.game_over, "text": "busy"}
            with self._io_lock:
                ok, text = self._send("play {0} pass".format(color))
                if not ok:
                    return {"ok": False, "game_over": False, "text": text}
                self._record_pass_locked(color)
                return {"ok": True, "game_over": self.game_over, "text": ""}

        def _record_pass_locked(self, color):
            self._align_capture_log()
            self.moves.append((color, "PASS"))
            self._cap_log.append(0)
            self.passes_in_a_row += 1
            self.to_move = self.opposite(color)
            self.last_captured = frozenset()
            self.last_move = {"color": color, "pass": True, "col": -1,
                              "row": -1, "vertex": "PASS"}
            if self.passes_in_a_row >= 2:
                self.game_over = True

        def resign(self, color="black"):
            """Record a resignation. No GTP command is needed."""
            self.resigned_color = color
            self.game_over = True
            return True

        @property
        def can_undo(self):
            if self.thinking or not self.is_ready:
                return False
            for color, vertex in self.moves:
                if color == "black":
                    return True
            return False

        def undo(self, count=2):
            """Take back up to 'count' moves. Returns {"ok", "undone", "text"}."""
            if self.thinking or not self.is_ready:
                return {"ok": False, "undone": 0, "text": "busy"}
            with self._io_lock:
                count = max(0, min(int(count), len(self.moves)))
                if count == 0:
                    return {"ok": False, "undone": 0, "text": "nothing to undo"}
                done = 0
                text = ""
                for _i in range(count):
                    ok, text = self._send("gg-undo")
                    if not ok:
                        break
                    done += 1
                if done:
                    del self.moves[len(self.moves) - done:]
                    self.resigned_color = None
                    self._recompute_after_history_change()
                    if not self._sync_locked(True):
                        return {"ok": False, "undone": done,
                                "text": "could not read the board"}
                return {"ok": done > 0, "undone": done, "text": text}

        # ------------------------------------------------------------------
        # background jobs (genmove and scoring)
        # ------------------------------------------------------------------
        @property
        def result_ready(self):
            return self.pending_result is not None

        def take_result(self):
            """Return the finished background result once, then clear it."""
            result = self.pending_result
            self.pending_result = None
            return result

        def _start_job(self, func):
            if self.thinking or self.pending_result is not None:
                return False
            if not self.is_ready:
                return False
            generation = self._generation
            self.thinking = True
            self.pending_result = None

            def runner():
                try:
                    result = func()
                except Exception as e:
                    self._log("job crashed: " + repr(e))
                    result = {"type": "error", "text": repr(e)}
                if generation != self._generation or self._quitting:
                    # The game was torn down while GNU Go was thinking.
                    if generation == self._generation:
                        self.pending_result = {"type": "cancelled"}
                        self.thinking = False
                    return
                # Publish the result first, then clear the flag, so the main
                # thread never sees "not thinking" without a result.
                self.pending_result = result
                self.thinking = False

            thread = _go_threading.Thread(target=runner)
            thread.daemon = True
            self._worker = thread
            thread.start()
            return True

        def request_move(self, color="white"):
            """Ask GNU Go for a move in the background. False if it can't start."""
            if self.game_over:
                return False
            return self._start_job(lambda: self._genmove_job(color))

        def _genmove_job(self, color):
            with self._io_lock:
                ok, text = self._send("genmove {0}".format(color))
                if not ok:
                    if self._quitting:
                        return {"type": "cancelled"}
                    return {"type": "error", "text": text or "genmove failed"}
                answer = text.strip().upper()
                if answer == "PASS":
                    self._record_pass_locked(color)
                    return {"type": "pass", "game_over": self.game_over}
                if answer == "RESIGN":
                    self.resigned_color = color
                    self.game_over = True
                    return {"type": "resign"}
                idx = self.vertex_to_index(answer, self.size)
                if idx is None:
                    return {"type": "error",
                            "text": "unreadable move: " + self._short(text)}
                outcome = self._apply_stone_locked(color, answer)
                if outcome is None:
                    return {"type": "error", "text": "could not read the board"}
                return {"type": "move", "col": idx[0], "row": idx[1],
                        "vertex": answer, "captured": outcome[0]}

        def request_final_score(self):
            """Ask GNU Go for the final score and dead stones in the background."""
            return self._start_job(self._score_job)

        def _score_job(self):
            with self._io_lock:
                ok, text = self._send("final_score")
                if not ok:
                    if self._quitting:
                        return {"type": "cancelled"}
                    return {"type": "error", "text": text or "final_score failed"}
                score = self.parse_score(text)
                ok, dead_text = self._send("final_status_list dead")
                dead = self._parse_vertices(dead_text) if ok else frozenset()
                return {"type": "score", "score": score, "dead": dead}


    def _get_controller():
        return ctrl


    ctrl = GnuGoController()
