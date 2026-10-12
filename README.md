# hiddriver360-PeerPressure
Rework of the hiddriver360 plugin to work on PeerPressure modded Xbox 360s


This is an AI-driven rework of the plugin that lets you use any controller on an Xbox 360.


Let me be clear- this may be AI-made, but I'm not an idiot. I'm a Unix system administrator of 12 years.


I may not be a strictly software development oriented tech, but I know a thing or two, so there was plenty of hand-holding.



The old version needed to be used with DashLauncher as a plugin because of how it used system calls.
Some of how PeerPressure patches the kernel was RE'd, in conjunction with a chain-load to Aurora. 
I also helped the model fix an issue with the driver that would allow a 3rd party controller to work in Aurora, but cause the IO stack to panic when you tried to launch a game.
This took a combination of a questionably sourced SDK, and some really oddball testing.

The first working version was a 4-byte patch to the kernel (an extra entry in PeerPressure's kernel_patches.bin), and a custom .xex that loaded with Aurora.
It worked, but I realized that having people patch their kernels just to use a controller is bad practice, so I geared it towards a less-intrusive method instead.

The result? It now loads through PeerPressure's own DLL sideloading .ini files (plus PeerPressure's built-in Aurora hook, since Aurora can't be sideloaded by .ini).
Nothing in your PeerPressure install gets modified - the loader only flips that one kernel check in memory while the driver loads, then puts it back - so it works with dashboards other than Aurora, installs as a PeerPressure Softmod Extra, and uninstalling is just deleting files.
It lets you use anything from a DDR dance mat for the Gamecube to a DS5.


This was really fun to get working. 

---

## Credits

This project stands on two others:

- **[hiddriver360](https://github.com/EinTim23/hiddriver360) by EinTim23** — the controller driver
  itself: USB HID support, DualShock / DualSense / Switch Pro handling, controller mapping and the
  XInput integration. Everything a controller actually does here is their work. This project only
  adds a memory fix for running outside DashLaunch, and a loader for PeerPressure. GPL-3.0.
- **[PeerPressure](https://github.com/grimdoomer/Xbox360PeerPressure) by grimdoomer** — the
  softmod that makes any of this possible on 17559: its DLL sideloader, the Aurora hook, the
  removed memory protections the loader relies on, and the Softmod Extras installer this package
  plugs into.

**None of PeerPressure's code or files are part of this project.** The one PeerPressure file the
Aurora setup needs (`AuroraFixer.xex`) is always taken from your own console or your own
PeerPressure download, never shipped here.

Also thanks to Team Resurgent for [XexTool](https://github.com/Team-Resurgent/XexTool), used to
build the loaders.

---

Use **DualShock 3/4, DualSense, Switch Pro and other USB HID controllers** on an Xbox 360 running
the [PeerPressure](https://github.com/grimdoomer/Xbox360PeerPressure) softmod — in the dashboard
**and in games**, including unplugging/replugging a controller mid-game.

It packages [hiddriver360](https://github.com/EinTim23/hiddriver360) (v0.6-beta) with:

- **a fix** that makes hiddriver survive the dashboard → game switch when it isn't loaded by
  DashLaunch (see [Why a patched hiddriver](#why-a-patched-hiddriver)), and
- **a small loader** that lets PeerPressure load it at boot, for Aurora or any other dashboard,
  **without modifying any PeerPressure file**.

Install it as a **PeerPressure Softmod Extra** (on the console, from the PeerPressure installer)
or over FTP. Uninstalling is just deleting the files.

Tested on hardware (17559, PeerPressure + Aurora): DualShock 3 and DualSense in Aurora, in Gears
of War, through Guide → Xbox Home and back, and hot-plugged mid-game. No rumble (a hiddriver
limitation).

## Install

### As a Softmod Extra (on the console)

**Easiest — with Aurora support, from a PC:** point the tool at your PeerPressure download and
your USB stick; it builds the Extra (taking PeerPressure's `AuroraFixer.xex` from *your* download)
and registers it in the stick's `SoftmodExtras.ini`:

```
./build.sh --peerpressure <SoftmodInstaller.zip or BadUpdatePayload> --install-into <USB>\BadUpdatePayload
```

That Extra contains your copy of PeerPressure's `AuroraFixer.xex`: it's for your console, don't share it.

**Or with the shareable Extra** (from the [Releases](../../releases) page or `make-extra.py --release`):
copy its `HidDriver360` folder into `BadUpdatePayload\SoftmodExtras\` and add the section from
`SoftmodExtras-entry.ini` to `BadUpdatePayload\SoftmodExtras\SoftmodExtras.ini`. It contains no
PeerPressure files, so **Aurora needs one extra step afterwards** — run `install.py` (below) or follow
`HidDriver\README-AURORA.txt` (two file operations in Aurora's file manager). The MS dashboard,
FreeStyle Dash and XeXMenu work straight away.

Then run the PeerPressure installer (Rock Band Blitz demo), choose **Install Softmod** → tick
**Install Extras** → select **hiddriver360** → **Extras Only** (or include it in a Full Install), and
reboot with a controller plugged in.

The Extra copies its files into `Hdd1:\PeerPressure\SideLoading\`:

| File | Purpose |
|---|---|
| `fffe07d1.ini`, `f5d20000.ini`, `c0de9999.ini` | sideload `HidLoader.xex` into the MS dashboard, FreeStyle Dash, XeXMenu |
| `HidDriver\HidLoader.xex` | loader for dashboards with a title ID |
| `HidDriver\hiddriver.xex` | hiddriver360 with the fix |
| `HidDriver\CREDITS.txt` | credits for hiddriver360 and PeerPressure |
| `AuroraFixer.xex` *(Aurora setup)* | our loader for **Aurora**: runs PeerPressure's real fixer, then hiddriver |
| `AuroraFixer.orig.xex` *(Aurora setup)* | PeerPressure's own `AuroraFixer.xex`, from your console / your download |

### Over FTP (no USB stick / installer run needed)

With the console in Aurora (FTP on, default login `xboxftp`/`xboxftp`) and Python 3.8+ on a PC:

```
python tools/install.py install <console-ip>        # add --dry-run to preview
python tools/install.py status <console-ip>
python tools/install.py uninstall <console-ip>
```

It installs the same files including the Aurora setup (using the console's **own**
`AuroraFixer.xex` as `.orig`, so it works with the shareable Extra too), backs up
everything it changes, verifies every upload (Aurora's FTP stalls now and then; it retries and
never leaves a half-written file), and also cleans up the older `kernel_patches.bin`-based install.

### Uninstall

`tools/install.py uninstall <ip>`, or by hand in `Hdd1:\PeerPressure\SideLoading\`: delete the three
`.ini` files and the `HidDriver` folder, delete `AuroraFixer.xex` and rename `AuroraFixer.orig.xex`
back to `AuroraFixer.xex`. Controller mappings in `Hdd1:\hiddriver.json` can stay or go.

### Recovery

If the console ever fails to reach the dashboard: power on with the **disc tray open**. Both loaders
then skip hiddriver entirely; uninstall as above.

## Using it

Plug controllers in any time. A controller hiddriver doesn't recognise starts a short on-screen
mapping process; mappings are saved to `Hdd1:\hiddriver.json`.

- **Guide → Xbox Home** always goes to the MS dashboard (PeerPressure behaviour); the **first button
  in the guide's Home tab** quick-launches your homebrew dashboard (Aurora) again.
- Logs: `Hdd1:\PeerPressure\SideLoading\HidDriver\aurora-loader.log` / `sideload-loader.log`
  (rewritten at each dashboard start; the last line is the load result, `00000000` = success).
- **After a PeerPressure update** that restores its `AuroraFixer.xex`, re-run the Extra or
  `tools/install.py install` (Aurora only; other dashboards keep working).
- Another dashboard: copy `extra/dashboards/fffe07d1.ini` to `<its title id>.ini` (8 lowercase hex
  digits) and set `TitleID`. Dashboards without a title ID can only be reached through
  `AuroraFixer.xex` (see below).

## How it works

**Loading.** PeerPressure's `KernelExpansion.bin` sideloads DLLs into titles at launch:
`SideLoading\<title id>.ini` → our `HidLoader.xex`. Two things found by reverse engineering it
(17559):

- The ini sideloader **skips titles without an execution-info header** — Aurora has none, so it can
  never be ini-sideloaded. Aurora's only hook is PeerPressure's hard-coded
  `SideLoading\AuroraFixer.xex` (matched by the PE name `Aurora.exe`), hence the chain loader.
- An entry **only matches if `ModuleVersion` (or both `MinVersion` and `MaxVersion`) is set**; an
  omitted `ModuleVersion` is compared as `0.0.0.0`. Our INIs use `ModuleVersion = "*.*.*.*"`.
  The filename is `%08x` — lowercase.

**Loading a system module from a title.** hiddriver is a system DLL; the kernel's module loader
refuses to load one from a title process with a single branch (`0x80078FAC` on 17559,
`bne cr6,+0x2C` → `STATUS_ACCESS_DENIED`). PeerPressure removes memory protections, so the loader
checks that instruction, flips it to the success path, calls `XexLoadImage(hiddriver, 8)`, then
puts the original instruction back. On any other kernel it does nothing.

**Why a patched hiddriver.** Loaded this way, hiddriver's `DllMain` runs in the dashboard's title
process, so its CRT heap is title memory. The USB interrupt TRB and transfer buffer it keeps queued
with the USB stack lived in that heap and were freed when a game launched → hard hang. The fix
moves all of hiddriver's allocations into a fixed arena inside its own image (system DLL region,
spinlock-protected so it works from the DISPATCH-level USB callbacks). Two smaller fixes: vibration
requests for the virtual controllers are no longer forwarded to XAM, and a missing return in the
capabilities hook. Details: [`hiddriver/0001-*.patch`](hiddriver/).

## Building

| Part | Tools | Reproducible from this repo |
|---|---|---|
| `loader/` → `AuroraFixer.xex`, `HidLoader.xex` | clang, ld.lld, [XexTool](https://github.com/Team-Resurgent/XexTool) | yes — byte-identical, hashes in `loader/SHA256SUMS` |
| `hiddriver.xex` | an Xbox 360 XDK (not redistributable) | source patch here; prebuilt binary in `hiddriver/prebuilt/` |
| the Extra | Python 3.8+ | yes — `--release` needs nothing else; `--peerpressure` uses your own PeerPressure download |

```
tools/build-xextool.sh                  # once: builds XexTool into build/xextool (or set XEXTOOL)
./build.sh --release                    # shareable Extra -> dist/release/
./build.sh --peerpressure <SoftmodInstaller.zip | BadUpdatePayload folder>   # personal -> dist/personal/
python -m unittest discover -s tests    # installer tests
```

`build.sh` builds the loaders, checks them against `loader/SHA256SUMS`, and assembles the Extra
(`HidDriver360/` + `SoftmodExtras-entry.ini`). Only `dist/release/` is meant to be shared: the
personal build contains your copy of PeerPressure's `AuroraFixer.xex`. See
[`hiddriver/BUILDING.md`](hiddriver/BUILDING.md) for rebuilding `hiddriver.xex`.

## Licenses

- This repository is GPL-3.0 ([`LICENSE`](LICENSE)), like hiddriver360 by EinTim23, which it
  patches and redistributes (`hiddriver/prebuilt/hiddriver.xex`; source in `hiddriver/`).
- PeerPressure by grimdoomer is not included in any form. A *personal* Extra built with
  `--peerpressure` contains your own copy of its `AuroraFixer.xex`, with PeerPressure's license
  notice (`HidDriver\PEERPRESSURE-NOTICE.txt`); don't redistribute that build.
- XexTool by Team Resurgent is a build tool only and isn't distributed.

See [Credits](#credits) at the top.
