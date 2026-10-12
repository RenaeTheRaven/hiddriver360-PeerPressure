# hiddriver360-PeerPressure
Rework of the hiddriver360 plugin to work on PressurePoint modded Xbox 360s


This is an AI-driven rework of the plugin that let's you use any controller on an Xbox 360.


Let me be clear- this may be AI-made, but I'm not an idiot. I'm a Unix system administrator of 12 years.


I may not be a strictly software development oriented tech, but I know a thing or two, so there was plenty of hand-holding.



The old version needed to be used with DashLauncher as a plugin because of how it used system calls.
Some of how PeerPressure patches the kernel was RE'd, in conjunction with a chain-load to Aurora. 
I also helped the model fix an issue with the driver that would allow a 3rd party controller to work in Aurora, but cause the IO stack to panic when you tried to launch a game.Did
This took a combination of a questionably sourced SDK, and some really oddball testing.

The result? A 4KB patch to the kernel, and a custom .xex that loads with Aurora and lets you use anything from a DDR dance mat for the Gamecube to a DS5.


This was really fun to get working. 

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

1. Get the `HidDriver360` Extra: from the [Releases](../../releases) page, or build it (below).
2. On the USB stick you use for PeerPressure, copy the `HidDriver360` folder into
   `BadUpdatePayload\SoftmodExtras\` and add the section from `SoftmodExtras-entry.ini` to
   `BadUpdatePayload\SoftmodExtras\SoftmodExtras.ini`
   (`tools/make-extra.py --install-into <USB>\BadUpdatePayload` does both).
3. Run the PeerPressure installer (Rock Band Blitz demo), choose **Install Softmod** → tick
   **Install Extras** → select **hiddriver360** → **Extras Only** (or include it in a Full Install).
4. Reboot with a controller plugged in.

The Extra copies its files into `Hdd1:\PeerPressure\SideLoading\`:

| File | Purpose |
|---|---|
| `AuroraFixer.xex` | loader for **Aurora**: runs PeerPressure's real fixer, then hiddriver |
| `AuroraFixer.orig.xex` | PeerPressure's own `AuroraFixer.xex`, unmodified |
| `fffe07d1.ini`, `f5d20000.ini`, `c0de9999.ini` | sideload `HidLoader.xex` into the MS dashboard, FreeStyle Dash, XeXMenu |
| `HidDriver\HidLoader.xex` | loader for dashboards with a title ID |
| `HidDriver\hiddriver.xex` | hiddriver360 with the fix |

### Over FTP (no USB stick / installer run needed)

With the console in Aurora (FTP on, default login `xboxftp`/`xboxftp`) and Python 3.8+ on a PC:

```
python tools/install.py install <console-ip>        # add --dry-run to preview
python tools/install.py status <console-ip>
python tools/install.py uninstall <console-ip>
```

It installs the same files, keeps the console's **own** `AuroraFixer.xex` as `.orig`, backs up
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
| the Extra | Python 3.8+ | yes, given a PeerPressure download (for its `AuroraFixer.xex`) |

```
tools/build-xextool.sh                  # once: builds XexTool into build/xextool (or set XEXTOOL)
./build.sh --peerpressure <SoftmodInstaller.zip | BadUpdatePayload folder>
python -m unittest discover -s tests    # installer tests
```

`build.sh` builds the loaders, checks them against `loader/SHA256SUMS`, and assembles
`dist/SoftmodExtras/HidDriver360` (+ `SoftmodExtras-entry.ini`). See
[`hiddriver/BUILDING.md`](hiddriver/BUILDING.md) for rebuilding `hiddriver.xex`.

## Credits and licenses

- hiddriver360 by EinTim23 — GPL-3.0. This repository is GPL-3.0 too ([`LICENSE`](LICENSE)).
- PeerPressure by grimdoomer — "You owe me a beer" License v1.0; the Extra bundles PeerPressure's
  `AuroraFixer.xex` unmodified, with its notice (`HidDriver\PEERPRESSURE-NOTICE.txt`).
- XexTool by Team Resurgent (build tool only, not distributed).
