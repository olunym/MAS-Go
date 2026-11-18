# Third-party notices

## GNU Go

This submod bundles precompiled copies of GNU Go for Windows
(`bin/windows/gnugo.exe`) and Linux (`bin/linux/gnugo`). The submod starts
GNU Go as a separate program and talks to it through the Go Text Protocol
(GTP) over standard input and output. It does not link against GNU Go.

- Program: GNU Go, a program that plays the game of Go
- Copyright: the GNU Go authors and the Free Software Foundation
- License: GNU General Public License (GPL), see `bin/GNUGO_LICENSE.txt`
- Project page: https://www.gnu.org/software/gnugo/
- Source code (all released versions): https://ftp.gnu.org/gnu/gnugo/

GNU Go is free software. You may redistribute it and modify it under the terms
of the GNU General Public License. GNU Go comes with ABSOLUTELY NO WARRANTY.

### Source code offer

The complete corresponding source code for the version of GNU Go included in
this submod can be downloaded from the GNU FTP server linked above. If you
cannot obtain it there, open an issue in this repository and the source will
be provided to you on request. This offer is valid for at least three years
after the release that contains the binaries.

### Using your own GNU Go

You do not have to use the bundled binaries. The submod checks the
`bin/<platform>/` folders first and then looks for `gnugo` on your system
PATH, so a copy you installed yourself will also work.

## Monika After Story and Doki Doki Literature Club

This is an unofficial fan-made submod. It is not affiliated with or endorsed
by Team Salvato or the Monika After Story team. It contains no assets from
Doki Doki Literature Club or Monika After Story. You need your own copy of
Doki Doki Literature Club and an installation of Monika After Story to use it.

## Images and sounds

The board, stone, marker and interface images and the two stone sounds were
generated for this project with scripts and are covered by the MIT license
in `LICENSE`.
