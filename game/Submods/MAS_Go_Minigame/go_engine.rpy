## Monika After Story submod: Go (Baduk) minigame
## File: game/Submods/MAS_Go_Minigame/go_engine.rpy
##
## GnuGoController: owns the GNU Go process and talks GTP to it
## Compatible with Python 2.7 (Ren'Py 6) and Python 3.9+ (Ren'Py 8)
##
## Coordinate convention used by this controller:
##   col: 0..size-1, left to right  (GTP letters A-T, skipping I)
##   row: 0..size-1, BOTTOM to top  (row 0 == GTP row 1)
## The screen file flips rows when drawing

init -5 python:
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
            return (_mas_go_get_controller, ())

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
            self._kill_process()
            worker = self._worker
            if worker is not None and worker.is_alive():
                try:
                    worker.join(1.0)
                except Exception:
                    pass
            self._worker = None
            self.thinking = False

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
        # starting a game
        # ------------------------------------------------------------------
        def _handshake(self, boardsize, handicap, komi):
            with self._io_lock:
                ok, text = self._send("name")
                if not ok:
                    return (False, "name failed: " + text)
                self.engine_name = text
                ok, text = self._send("version")
                self.engine_version = text if ok else ""
                ok, text = self._send("boardsize {0}".format(boardsize))
                if not ok:
                    return (False, "boardsize failed: " + text)
                ok, text = self._send("clear_board")
                if not ok:
                    return (False, "clear_board failed: " + text)
                ok, text = self._send("komi {0}".format(komi))
                if not ok:
                    return (False, "komi failed: " + text)
                if handicap >= 2:
                    ok, text = self._send("fixed_handicap {0}".format(handicap))
                    if not ok:
                        return (False, "fixed_handicap failed: " + text)
                    self.to_move = "white"
                self._sync_locked(False)
            return (True, "")

        def start(self, boardsize=9, level=3, handicap=0, komi=None):
            """Start GNU Go and set up a fresh game. Returns True on success.

            On failure see self.error (friendly text) and self.error_code.
            handicap: 0 or 2-9. A value of 1 is treated as 0 (Black simply
            moves first). Komi defaults to 6.5 (even) or 0.5 (handicap).
            """
            self.quit()
            self._quitting = False
            self._reset_game_state()
            self._clear_error()
            self.pending_result = None
            self.thinking = False

            try:
                boardsize = int(boardsize)
            except (TypeError, ValueError):
                boardsize = 9
            if boardsize not in self.BOARD_SIZES:
                boardsize = 9
            try:
                level = int(level)
            except (TypeError, ValueError):
                level = 3
            level = max(1, min(10, level))
            try:
                handicap = int(handicap)
            except (TypeError, ValueError):
                handicap = 0
            if handicap < 2:
                handicap = 0
            handicap = min(handicap, 9)
            if komi is None:
                komi = 0.5 if handicap else 6.5

            self.size = boardsize
            self.level = level
            self.handicap_stones = handicap
            self.komi = komi
            self.to_move = "white" if handicap else "black"

            try:
                if self.LOG_TO_FILE:
                    open(os.path.join(self._submod_dir(), "go_engine.log"), "wb").close()
            except Exception:
                pass
            self._log("start size={0} level={1} handicap={2} komi={3}".format(
                boardsize, level, handicap, komi))

            info = self.detect_platform()
            if info["key"] is None:
                self._set_error("unsupported_os", "")
                return False

            candidates = self._candidates(info)
            if not candidates:
                self._set_error("binary_missing", self.expected_locations_text())
                return False

            for path, bundled in candidates:
                self.binary_path = path
                self.binary_source = "bundled" if bundled else "system"
                if bundled:
                    self._prepare_bundled(path)
                self._clear_error()
                if not self._launch(path, level):
                    self._kill_process()
                    continue
                finished, outcome = self._run_with_timeout(
                    lambda: self._handshake(boardsize, handicap, komi),
                    self.HANDSHAKE_TIMEOUT
                )
                if not finished:
                    self._kill_process()
                    self._set_error("timeout", "")
                    continue
                ok, why = outcome
                if ok:
                    self.alive = True
                    self._clear_error()
                    self._log("engine ready: {0} {1} ({2})".format(
                        self.engine_name, self.engine_version, path))
                    return True
                self._kill_process()
                self._set_error("handshake_failed", why)

            return False

        def self_test(self):
            """Launch the engine briefly. Returns (ok, multi-line report)."""
            info = self.detect_platform()
            lines = [
                "OS key: {0}".format(info["key"]),
                "Machine: {0}".format(info["machine"]),
                "Expected: {0}".format(self.expected_locations_text())
            ]
            ok = self.start(boardsize=9, level=1, handicap=0)
            if ok:
                lines.append("Binary: {0} ({1})".format(
                    self.binary_path, self.binary_source))
                lines.append("Engine: {0} {1}".format(
                    self.engine_name, self.engine_version))
                lines.append("RESULT: OK")
            else:
                lines.append("Binary tried: {0}".format(self.binary_path))
                lines.append("RESULT: FAILED ({0})".format(self.error_code))
                lines.append(str(self.error))
            self.quit()
            return (ok, "\n".join(lines))

        # ------------------------------------------------------------------
        # board state sync (callers must hold self._io_lock)
        # ------------------------------------------------------------------
        def _sync_locked(self, track_capture=True):
            ok_b, text_b = self._send("list_stones black")
            ok_w, text_w = self._send("list_stones white")
            if not (ok_b and ok_w):
                return False
            black = self._parse_vertices(text_b)
            white = self._parse_vertices(text_w)
            previous = self.black_stones | self.white_stones
            current = black | white
            if track_capture:
                self.last_captured = frozenset(previous - current)
            else:
                self.last_captured = frozenset()
            self.black_stones = black
            self.white_stones = white

            white_plays = 0
            black_plays = self.handicap_stones
            for color, vertex in self.moves:
                if vertex == "PASS":
                    continue
                if color == "white":
                    white_plays += 1
                else:
                    black_plays += 1
            self.captures_by_black = max(0, white_plays - len(white))
            self.captures_by_white = max(0, black_plays - len(black))

            for name in ("black", "white"):
                ok, text = self._send("captures {0}".format(name))
                if ok:
                    try:
                        self.raw_captures[name] = int(text.strip().split()[0])
                    except (ValueError, IndexError):
                        self.raw_captures[name] = None
            return True

        def refresh(self):
            """Re-sync stones and captures from GNU Go (not while thinking)."""
            if self.thinking or not self.is_ready:
                return False
            with self._io_lock:
                return self._sync_locked(False)

        def _count_trailing_passes(self):
            count = 0
            for color, vertex in reversed(self.moves):
                if vertex == "PASS":
                    count += 1
                else:
                    break
            return count

        def _recompute_turn(self):
            if self.moves:
                self.to_move = self.opposite(self.moves[-1][0])
            else:
                self.to_move = "white" if self.handicap_stones >= 2 else "black"

        def _recompute_last_move(self):
            if not self.moves:
                self.last_move = None
                return
            color, vertex = self.moves[-1]
            if vertex == "PASS":
                self.last_move = {"color": color, "pass": True}
            else:
                idx = self.vertex_to_index(vertex, self.size)
                if idx is None:
                    self.last_move = None
                else:
                    self.last_move = {"color": color, "col": idx[0],
                                      "row": idx[1], "pass": False}

        def _classify_illegal(self, col, row, color):
            if (col, row) in self.black_stones or (col, row) in self.white_stones:
                return "occupied"
            last = self.last_move
            if (len(self.last_captured) == 1 and (col, row) in self.last_captured
                    and last is not None and last.get("color") != color):
                return "ko"
            return "suicide"

        # ------------------------------------------------------------------
        # player actions (synchronous and fast)
        # ------------------------------------------------------------------
        def play(self, col, row, color="black"):
            """Play a stone. Returns a dict:
            ok, reason (None/'occupied'/'ko'/'suicide'/'illegal'/'busy'/
            'game_over'/'engine'), captured (int), vertex, text."""
            res = {"ok": False, "reason": None, "captured": 0,
                   "vertex": None, "text": ""}
            if not self.is_ready:
                res["reason"] = "engine"
                return res
            if self.thinking:
                res["reason"] = "busy"
                return res
            if self.game_over:
                res["reason"] = "game_over"
                return res
            vertex = self.index_to_vertex(col, row, self.size)
            res["vertex"] = vertex
            if vertex is None:
                res["reason"] = "illegal"
                return res
            if (col, row) in self.black_stones or (col, row) in self.white_stones:
                res["reason"] = "occupied"
                return res
            with self._io_lock:
                ok, text = self._send("play {0} {1}".format(color, vertex))
                res["text"] = text
                if not ok:
                    if not self.is_ready:
                        res["reason"] = "engine"
                    else:
                        res["reason"] = self._classify_illegal(col, row, color)
                    return res
                self.moves.append((color, vertex))
                self.to_move = self.opposite(color)
                self.last_move = {"color": color, "col": col, "row": row,
                                  "pass": False}
                self.passes_in_a_row = 0
                self._sync_locked(True)
            res["ok"] = True
            res["captured"] = len(self.last_captured)
            return res

        def pass_turn(self, color="black"):
            """Pass. Returns dict: ok, game_over, text."""
            res = {"ok": False, "game_over": False, "text": ""}
            if not self.is_ready or self.thinking or self.game_over:
                return res
            with self._io_lock:
                ok, text = self._send("play {0} pass".format(color))
                res["text"] = text
                if not ok:
                    return res
                self.moves.append((color, "PASS"))
                self.to_move = self.opposite(color)
                self.last_move = {"color": color, "pass": True}
                self.passes_in_a_row = self._count_trailing_passes()
                if self.passes_in_a_row >= 2:
                    self.game_over = True
            res["ok"] = True
            res["game_over"] = self.game_over
            return res

        def resign(self, color="black"):
            """Record a resignation (no GTP needed)."""
            self.game_over = True
            self.resigned_color = color

        @property
        def can_undo(self):
            if self.thinking or not self.is_ready:
                return False
            for color, vertex in self.moves:
                if color == "black":
                    return True
            return False

        def undo(self, plies=2):
            """Undo with gg-undo (default 2 plies: Monika's reply and yours).
            Returns dict: ok, undone, needs_ai_move, text."""
            res = {"ok": False, "undone": 0, "needs_ai_move": False, "text": ""}
            if not self.can_undo:
                res["text"] = "nothing to undo"
                return res
            try:
                plies = int(plies)
            except (TypeError, ValueError):
                plies = 2
            count = max(1, min(plies, len(self.moves)))
            with self._io_lock:
                done = 0
                ok, text = self._send("gg-undo {0}".format(count))
                if ok:
                    done = count
                else:
                    for _i in range(count):
                        ok2, text2 = self._send("undo")
                        if not ok2:
                            text = text2
                            break
                        done += 1
                res["text"] = text
                if done > 0:
                    del self.moves[-done:]
                    self.game_over = False
                    self.resigned_color = None
                    self.passes_in_a_row = self._count_trailing_passes()
                    self._recompute_turn()
                    self._recompute_last_move()
                    self._sync_locked(False)
                    res["ok"] = True
                    res["undone"] = done
                    res["needs_ai_move"] = (self.to_move == "white")
            return res

        # ------------------------------------------------------------------
        # asynchronous work (runs GNU Go in a background thread)
        # ------------------------------------------------------------------
        def _start_worker(self, target):
            if self.thinking or not self.is_ready:
                return False
            self.pending_result = None
            self.thinking = True
            thread = _go_threading.Thread(target=target)
            thread.daemon = True
            self._worker = thread
            thread.start()
            return True

        def request_move(self, color="white"):
            """Ask GNU Go to move for `color` in the background."""
            return self._start_worker(lambda: self._think_move(color))

        def request_final_score(self):
            """Ask GNU Go for final_score and dead stones in the background."""
            return self._start_worker(self._think_score)

        def take_result(self):
            """Return the finished background result once, else None."""
            result = self.pending_result
            if result is not None and not self.thinking:
                self.pending_result = None
                return result
            return None

        @property
        def result_ready(self):
            return self.pending_result is not None and not self.thinking

        def _think_move(self, color):
            result = {"type": "error", "text": "unknown error"}
            try:
                with self._io_lock:
                    ok, text = self._send("genmove {0}".format(color))
                    if self._quitting:
                        result = {"type": "cancelled"}
                    elif not ok:
                        result = {"type": "error", "text": text}
                    else:
                        word = text.strip().upper()
                        if word == "RESIGN":
                            self.game_over = True
                            self.resigned_color = color
                            result = {"type": "resign", "color": color}
                        elif word == "PASS":
                            self.moves.append((color, "PASS"))
                            self.to_move = self.opposite(color)
                            self.last_move = {"color": color, "pass": True}
                            self.passes_in_a_row = self._count_trailing_passes()
                            if self.passes_in_a_row >= 2:
                                self.game_over = True
                            result = {"type": "pass", "color": color,
                                      "game_over": self.game_over}
                        else:
                            idx = self.vertex_to_index(word, self.size)
                            if idx is None:
                                result = {"type": "error",
                                          "text": "unreadable move: " + text}
                            else:
                                self.moves.append((color, word))
                                self.to_move = self.opposite(color)
                                self.last_move = {"color": color, "col": idx[0],
                                                  "row": idx[1], "pass": False}
                                self.passes_in_a_row = 0
                                self._sync_locked(True)
                                result = {
                                    "type": "move",
                                    "color": color,
                                    "col": idx[0],
                                    "row": idx[1],
                                    "vertex": word,
                                    "captured": len(self.last_captured),
                                    "game_over": self.game_over
                                }
            except Exception as e:
                result = {"type": "error", "text": repr(e)}
            self.pending_result = result
            self.thinking = False

        def _think_score(self):
            result = {"type": "error", "text": "unknown error"}
            try:
                with self._io_lock:
                    ok, text = self._send("final_score")
                    if self._quitting:
                        result = {"type": "cancelled"}
                    elif not ok:
                        result = {"type": "error", "text": text}
                    else:
                        score = self.parse_score(text)
                        ok2, dead_text = self._send("final_status_list dead")
                        dead = self._parse_vertices(dead_text) if ok2 else frozenset()
                        result = {"type": "score", "score": score, "dead": dead}
            except Exception as e:
                result = {"type": "error", "text": repr(e)}
            self.pending_result = result
            self.thinking = False

        def final_score(self):
            """Blocking final_score. Returns parsed dict or None."""
            if self.thinking or not self.is_ready:
                return None
            with self._io_lock:
                ok, text = self._send("final_score")
            if not ok:
                return None
            return self.parse_score(text)


    def _mas_go_get_controller():
        return go_ctrl


    # The one shared controller. Created once at init and never reassigned,
    # so it is not stored in save files.
    go_ctrl = GnuGoController()