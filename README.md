# Settlers7 Man's Upgrade

A gameplay patch for **The Settlers 7 – History Edition** that lifts some of the
game's tighter restrictions, plus the toolchain used to build it.

| Change | Default | Patched |
|---|---|---|
| Max army size per general | 35 | **100** |
| Carrier movement speed | 0.4 | **2.0** (5×) |

The patch applies to **all** generals, including the AI's.

> This repository contains **no game files**. It is a patcher: it reads the
> archive from your own installed copy, rewrites two values, and writes it back.
> Nothing copyrighted is redistributed.

## Install

Requirements: **Python 3.8+** and an installed copy of the game.

```bash
git clone https://github.com/krivalex/settlers7-mans-upgrade.git
cd settlers7-mans-upgrade/tools
python build_mod.py
```

The script finds the game automatically (Steam libraries on any drive). If it
cannot, point it at the folder yourself:

```bash
python build_mod.py --game "D:\Steam\steamapps\common\The Settlers 7 - History Edition"
```

On the first run it saves an untouched backup next to the archive as
`Interface.bba.orig`, and every later build starts from that backup — so you can
re-run it any number of times without stacking changes.

After writing, the script re-opens the archive with its own reader and verifies
the CRC of all 325 entries. You should see:

```
[verify] 325 entries checked, 0 broken
[result] OK
```

## Uninstall

```bash
python restore.py
```

## Tuning

Open `tools/build_mod.py` and edit the two constants at the top:

```python
ARMY_SIZE = 100          # was 35
CARRIER_SPEED_MULT = 5   # base velocity 0.4 -> 2.0
```

Then run `build_mod.py` again. For scale: base speeds in the game are 0.4 for
workers, 0.6 for clerics, 0.8 for soldiers and 1.2 for cavalry — so a 5× carrier
is faster than cavalry and looks it. Drop to 3 if that bothers you.

## Steam / Ubisoft Connect notes

- **Do not use "Verify integrity of game files."** It restores the original
  archive and removes the patch. If it happens, just run `build_mod.py` again.
- The game launches through Ubisoft Connect. When that client asks to update
  itself, it is safe — it does not touch `Data/Base/BBA`.

## How it works

Two obstacles sit between you and the game's balance data:

1. **The `.bba` container.** Ubisoft's archive format: XXTEA-encrypted directory,
   gzip-compressed entries with the first 16 bytes of each 1 MiB chunk XOR-masked.
   `tools/bba.py` reads it; `tools/bbapatch.py` writes a single entry back by
   appending the new blob and rewriting only the directory, so every untouched
   file keeps its original bytes.
2. **Obfuscated Lua.** The game's scripts replace every literal with a call
   `e(N)` into a lazily decoded constant table. Numbers are stored as
   `value + (#constants % 256) + 555`; strings use running-delta character
   coding. `tools/deobf.py` reverses it.

The balance itself lives in `Interface.bba` as Lua. Army size is one constant in
`Script/profiles/settlers.lua`:

```lua
o.setGeneralDefaults = function(o)
    o:SetArmySize(100)   -- was 35
    ...
end
```

Carriers share `setDefaultSpeed` with all 29 worker types, so the shared constant
cannot be touched; the patch appends a profile-specific override instead.

### Tools

| File | Purpose |
|---|---|
| `build_mod.py` | apply the patch set (start here) |
| `restore.py` | roll back to the backup |
| `bba.py` | read `.bba` archives |
| `bbapatch.py` | surgically rewrite one entry |
| `extract.py` | unpack an archive to a folder |
| `deobf.py` / `deobf_all.py` | turn obfuscated Lua back into readable Lua |
| `rtti.py` / `strs.py` | engine RE helpers (RTTI classes, vftables, disassembly) |

Unpack and read the game's own scripts:

```bash
python extract.py "<game>/Data/Base/BBA/Interface.bba" ./out
python deobf_all.py ./out ./out_readable
```

## Known limits

Some restrictions are **not** in the data and cannot be changed this way — they
are compiled into the engine, which exposes only getters for them:

- carrier capacity (3 goods per trip);
- the 20-item queue limit for unit training, research and trade.

Changing those would mean patching `Settlers7R.exe`, whose `.text` section is
encrypted by the Uplay DRM wrapper, so it is out of scope here.

---

## По-русски

Патч для **The Settlers 7 – History Edition**: максимум армии у генерала 35 → **100**,
скорость носильщиков в **5 раз** выше. Действует и на ИИ-противников.

Репозиторий **не содержит файлов игры** — это патчер, который правит ваш
собственный установленный экземпляр.

Нужен Python 3.8+. Установка:

```bash
git clone https://github.com/krivalex/settlers7-mans-upgrade.git
cd settlers7-mans-upgrade/tools
python build_mod.py
```

Путь к игре определяется сам; если нет — укажите через `--game "путь"`.
Оригинал сохраняется рядом как `Interface.bba.orig`, откат — `python restore.py`.

Значения настраиваются в начале `tools/build_mod.py` (`ARMY_SIZE`,
`CARRIER_SPEED_MULT`), после правки запустите сборку заново.

**Важно:** не используйте в Steam «Проверить целостность файлов игры» — она
вернёт оригинал и снесёт патч (лечится повторным запуском `build_mod.py`).
Обновление клиента Ubisoft Connect безопасно, файлы игры оно не трогает.

## Credits

See [NOTICE.md](NOTICE.md). The `.bba` format implementation is a Python port of
[S7Packer](https://github.com/Eisenmonoxid/S7Packer) by Eisenmonoxid (MIT).
