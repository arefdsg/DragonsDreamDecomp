# Dragon's Dream Revival Server

A revival server for **Dragon's Dream** (Fujitsu x SEGA, 1997) — a Japan-only Sega Saturn MMORPG that connected via the NetLink modem to NIFTY-Serve. The original servers were shut down in the early 2000s.

This project restores online functionality through complete protocol-level reverse engineering of the unmodified Saturn client binary, enabling play on original hardware.

## Status

| Component | Status |
|-----------|--------|
| Windows 95 client startup | **SUPPORTED** - auto-detects Saturn/BBS vs Win95 direct TCP |
| Protocol stack (5 layers) | **COMPLETE** — fully decompiled from binary |
| 197 server→client handlers | **COMPLETE** — 173 substantive + 24 empty |
| 104 client→server messages | **COMPLETE** — all payload layouts documented |
| Revival server (v4) | **FUNCTIONAL** — login, tavern entry confirmed on real Saturn HW |
| Tavern sit mechanic | **PENDING** — corrected payloads ready for HW test |

## Repository Structure

```
DragonsDreamDecomp/
├── README.md
├── docs/
│   └── Dragons_Dream_Engineering_Manual.md   # Facts-only protocol reference
├── extracted/
│   ├── 0.BIN                                 # Saturn binary (504,120 bytes, SH-2 BE)
│   ├── IP.BIN                                # Boot sector
│   └── *.MFD, *.TXT                          # Metadata
├── server/
│   ├── dragons_dream_server_v4/              # Revival server (22 Python modules)
│   ├── Dragon's Dream Server.bat             # Double-click to launch Admin GUI
│   ├── run_server.bat                        # CLI launch with options (--gui, --port, etc.)
│   ├── dd_admin_config.json                  # Admin GUI settings (host, port, db path)
│   └── dump_dispatch_table.py                # Binary analysis utility
├── tools/
│   ├── disasm.py                             # SH-2 disassembler
│   └── decode_sh2.py                         # SH-2 instruction decoder
├── memory/                                   # Binary analysis documentation
│   ├── MEMORY.md                             # Master index
│   ├── handler-payloads-detailed.md          # All 197 handler payloads
│   ├── client-sent-payloads.md               # All 104 client messages
│   ├── wire-format.md                        # Wire format proof
│   ├── sv-framing.md                         # SV library analysis
│   ├── tavern-flow.md                        # Tavern sit flow
│   ├── game-flow.md                          # Post-login game flow
│   └── ... (21 analysis files total)
├── saves/
│   └── GS-7114.zip                          # Pre-made Saturn save file
└── skill/
    └── saturn-dragonsdream-developer/        # Claude Code skill
        ├── skill.md
        └── references/
```

## Running the Server

**Requirements:** Python 3.10+ (standard library only — no pip packages needed)

Double-click **`server/Dragon's Dream Server.bat`** to launch the Admin GUI. From there you can start/stop the server, view connected players, and manage game state.

The server binds to `0.0.0.0:8020` by default. Settings are saved in `dd_admin_config.json`.

For CLI usage: `cd server && python -m dragons_dream_server_v4 --port 8020 --client-mode auto`

Client mode controls the startup transport:

- `auto` - accept Saturn/NetLink BBS setup or Windows 95 direct TCP on the same port.
- `saturn` - require the Saturn/NIFTY-style `P` / `SET` / `C NETRPG` command phase before IV framing.
- `windows` - skip the BBS command phase and send the IV session establishment immediately for the Windows 95 Internet client.

## Connecting from Saturn Hardware

Use the default [DreamPi](https://github.com/Kazade/dreampi) configuration and add the following entry to your `netlink_config.ini` file (on your Pi or PC tunnel), substituting the host/IP for your actual server address:

```ini
[server:199403]
name = DRAGON
host = 192.168.50.180
port = 8020
handler = transparent
```

The `transparent` handler provides raw TCP passthrough — no PPP or protocol translation. The Saturn's `::host=` direct TCP mode is also supported for development.

## Connecting from Windows 95

The Windows 95 Internet client can connect to the same revival server on TCP port `8020`. Start the server in `auto` mode, or choose `windows` mode in the Admin GUI if this port will be dedicated to the Win95 client:

```bat
cd server
python -m dragons_dream_server_v4 --host 0.0.0.0 --port 8020 --client-mode auto
```

The Win95 executable contains the original `IPADR` and `8020` settings. Point the client environment/settings dialog at your server IP address and use port `8020`. If you are testing a NIFTY-style Windows install that sends `C HRPG` / `C NETRPG`, leave the server on `auto`; the command prelude is accepted before the normal IV session starts.

### Pre-made Save File

A ready-to-use Saturn backup RAM save is included in `saves/GS-7114.zip`. Load this onto your Saturn's internal memory or backup cartridge to skip initial character creation. This save contains a character that can connect to the revival server immediately.

## Claude Code Skill

This project includes a Claude Code skill for AI-assisted development. To install:

1. Copy `skill/saturn-dragonsdream-developer/` to `~/.claude/skills/`
2. Restart Claude Code

Or use the packaged installer from the [skill-distribution](skill-distribution/) directory.

The skill provides protocol knowledge, handler reference data, and binary analysis methodology for continued server development.

## Documentation

- **[Engineering Manual](docs/Dragons_Dream_Engineering_Manual.md)** — Complete protocol reference with binary offset citations
- **[memory/](memory/)** — 21 detailed analysis files covering every protocol layer

## Game Info

- **Title:** Dragon's Dream (ドラゴンズドリーム)
- **Developer:** Fujitsu
- **Publisher:** SEGA
- **Product:** GS-7114, V1.003
- **Release:** 1997-10-27, Japan
- **Platform:** Sega Saturn (SH-2 big-endian)
- **Connection:** NetLink modem → NIFTY-Serve BBS → game server
