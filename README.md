# Dragon's Dream Revival Server

A revival server for **Dragon's Dream** (Fujitsu x SEGA, 1997) — a Japan-only Sega Saturn MMORPG that connected via the NetLink modem to NIFTY-Serve. The original servers were shut down in the early 2000s.

This project restores online functionality through complete protocol-level reverse engineering of the unmodified Saturn client binary, enabling play on original hardware.

## Status

| Component | Status |
|-----------|--------|
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
│   ├── run_server.bat                        # Launch script
│   ├── config.ini                            # Server config
│   ├── netlink.py                            # DreamPi netlink module
│   ├── bridge.py                             # Network bridge
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
└── skill/
    └── saturn-dragonsdream-developer/        # Claude Code skill
        ├── skill.md
        └── references/
```

## Running the Server

**Requirements:** Python 3.10+

```bash
cd server
python -m dragons_dream_server_v4 --port 8020
```

The server binds to port 8020 by default. An admin GUI is available at launch for managing game state.

## Connecting from Saturn Hardware

1. Set up a [DreamPi](https://github.com/Kazade/dreampi) with the `transparent` handler on your local network
2. Configure `config.ini` with `handler = transparent` and `port = 8020`
3. On the Saturn, enter `::host=<server_ip>` as the phone number to bypass modem dialing and connect via TCP directly

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
