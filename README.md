# Go Minigame for Monika After Story

Play Go (Baduk) with Monika. This submod adds Go to Monika's "Play" menu,
powered by the GNU Go engine.

## Features

- Play on 9x9, 13x13 or 19x19 boards, with a wooden board, smooth stones and stone-click sounds.
- An interactive lesson on a 9x9 board for people who have never played. It covers liberties, capturing, atari, the suicide and ko rules, territory, living groups with two eyes, how a game flows, and when to pass or resign.
- Adaptive difficulty. You never pick a difficulty. Monika tracks how you do and adjusts (see "How the difficulty works").
- Full rules handled by GNU Go: captures, ko, suicide prevention, handicap stones and final scoring.
- Monika keeps thinking in the background, so her idle animation and the music never freeze while she plans a move.
- Undo, Pass and Resign buttons in the same style as MAS's own game buttons, with light and dark mode support.

## Requirements

- Monika After Story 0.12.0 or newer (developed and tested with version 0.12.20, Ren'Py 6.99).
- Windows or Linux. A GNU Go program for each is bundled, so no extra install is needed.
- macOS works if you install GNU Go yourself (see below).

The code is written to run on both Python 2.7 (Ren'Py 6) and Python 3 (Ren'Py 8), but it has only been tested on the Ren'Py 6 build of MAS so far. If you try it on a Ren'Py 8 build, please report how it goes.

## Installation (Windows and Linux)

1. Close Monika After Story.
2. Download the latest `MAS_Go_Minigame-vX.Y.Z.zip` from the Releases page.
3. Extract it into your MAS folder, the one that contains the `game` folder. Say yes if your system asks to merge folders. You should end up with `game/Submods/MAS_Go_Minigame/`.
4. Start MAS. "Go Minigame" should appear on the Submods screen.
5. Open Monika's Play menu and choose Go.

The first time you play, Monika asks if you know the game. If you do not, she gives you a short interactive lesson.

## Installation on macOS

I do not ship a macOS build, because few people in the community use it. You can still play by installing GNU Go yourself. This has not been tested by the author, so please report anything that does not work.

1. Install GNU Go with Homebrew: `brew install gnu-go`
2. Check that it runs: `gnugo --version`
3. Install the submod as described above. The bundled Windows and Linux files will be ignored on your system.

The submod looks for `gnugo` on your PATH and also in `/opt/homebrew/bin` and `/usr/local/bin`, so a normal Homebrew install is found automatically, even though apps started from Finder do not see your shell PATH.

If you would rather keep the program with the submod, copy it to one of these folders:

- Apple Silicon: `game/Submods/MAS_Go_Minigame/bin/macos-arm/gnugo`
- Intel: `game/Submods/MAS_Go_Minigame/bin/macos-intel/gnugo`

If macOS refuses to run a copied or downloaded `gnugo`, clear the quarantine flag and make it executable:

```
xattr -dr com.apple.quarantine game/Submods/MAS_Go_Minigame/bin
chmod +x game/Submods/MAS_Go_Minigame/bin/macos-arm/gnugo
```

On Apple Silicon, a binary that was modified or re-downloaded may also need a fresh signature: `codesign --force --sign - gnugo`.

## How to play

- You are Black and move first. Click an intersection to place a stone.
- Pass ends your turn without playing. If Monika passes and then you pass (or the other way round), the game ends and the score is counted.
- Undo takes back your last move and Monika's reply.
- Resign ends the game as a loss.
- After a game, dead stones are marked with red crosses and Monika announces the result and the margin.
- White gets 6.5 points of komi in even games. In handicap games komi is 0.5.

## How the difficulty works

Monika remembers your skill between games and changes it automatically.

- The difficulty is a GNU Go level from 0 to 10, plus an optional handicap of 2 to 9 stones for beginners.
- After two wins in a row, Monika gets a little tougher. After two losses in a row, she goes easier. A win followed by a loss, or the other way round, changes nothing.
- If you are losing at the lowest level, Monika starts giving you handicap stones, from 2 up to 9.
- When you start winning again, the handicap stones are removed one at a time. Only when you are back to an even game does her level start to rise.
- When you tell Monika you have played before, she asks how good you are and starts from there.
- Resigning before you have played a stone does not count, so backing out never changes the difficulty.

You can change your starting point at any time with "Tell Monika how well I play" in the Go menu, and you can repeat the lesson with "Go over the basics again".

## Troubleshooting

**Monika says she cannot set up the board.** She also shows the reason. The most common ones:

- GNU Go was not found. Check that `game/Submods/MAS_Go_Minigame/bin/windows/gnugo.exe` (Windows) or `bin/linux/gnugo` (Linux) exists. On macOS, see the macOS section.
- Permission denied. On Linux, make the file executable: `chmod +x game/Submods/MAS_Go_Minigame/bin/linux/gnugo`. On Windows, antivirus software or SmartScreen sometimes blocks a program it does not know. Check its quarantine list and allow the file.
- The bundled Linux file does not run on your distribution. Install GNU Go from your package manager (for example `sudo apt install gnugo`). The submod will find it automatically.

**Other problems.** Look at `game/Submods/MAS_Go_Minigame/go_engine.log`, which records the conversation with GNU Go, and at `traceback.txt` in the MAS folder. Please attach both when you open an issue.

**Test GNU Go by hand.** Open a terminal in the folder that holds the program and run it with `--version`. If that does not print a version, the program itself cannot start on your system.

## Known limitations

- The final score comes from GNU Go and is an estimate. It can occasionally misjudge a dead group. The red crosses show which stones it considered dead.
- GNU Go is a modest player by modern standards, and a 19x19 game at a high level can make Monika think for a while.
- A saved game in progress cannot be resumed after loading. Monika ends that game politely and you can start a new one.
- Only Windows and Linux builds of GNU Go are bundled.

## Uninstalling

Close MAS and delete `game/Submods/MAS_Go_Minigame`. If MAS reports a problem with the missing Go entry afterwards, please open an issue.

## For developers

Repository layout:

```
game/Submods/MAS_Go_Minigame/
    header.rpy          submod registration and Play menu entry
    go_engine.rpy       GnuGoController: process handling and GTP
    go_screen.rpy       board, HUD and click handling
    go_skill.rpy        adaptive difficulty
    go_dialogue.rpy     game flow and Monika's dialogue
    go_dialogue_end.rpy scoring, difficulty announcements, cleanup
    go_tutorial.rpy     interactive lesson, part 1
    go_tutorial2.rpy    interactive lesson, part 2
    assets/             board, stones, markers, panels, sounds
    bin/                bundled GNU Go (windows/ and linux/)
tools/build_release.py  builds the release zip
```

To build a release, make sure both GNU Go binaries are in place, then run
`python3 tools/build_release.py`. The zip is written to `dist/`.

## Credits and licenses

- The Go engine is GNU Go, copyright the GNU Go authors and the Free Software Foundation, used under the GNU General Public License. Source code: https://ftp.gnu.org/gnu/gnugo/ and https://www.gnu.org/software/gnugo/
- The submod code, images, sounds and documentation are copyright 2026 olunym and released under the MIT License (see `LICENSE`).
- Full details are in `THIRD_PARTY_NOTICES.md`.

This is an unofficial fan project. It is not affiliated with Team Salvato or the Monika After Story team, and it contains no assets from either.
