# Helium Acrylic

A [Windhawk](https://windhawk.net) mod that brings acrylic/Mica transparency to the
[Helium](https://github.com/imputnet/helium) browser on Windows. It is a Helium port of
[bardelyne's Brave Acrylic](https://github.com/bardelyne/brave-acrylic) (MIT) and needs
[Translucent Windows](https://windhawk.net/mods/translucent-windows) configured for Helium's `chrome.exe`.

## How Helium updates are handled

The mod hooks internal Chromium functions, so it needs their exact locations for each Helium build.
Helium publishes debug symbols for every Windows build as a GitHub Actions artifact that is deleted after 4 days.

`.github/workflows/symbol-cache.yml` runs every hour:

1. finds new successful *Build and release binaries* runs in `imputnet/helium-windows`,
2. downloads that build's `chrome.dll` + `chrome.dll.pdb` on GitHub's runner,
3. `tools/make_cache.py` checks the PDB matches the DLL and extracts the needed function addresses,
4. publishes a small text file to the `symbol-cache` branch under `helium-acrylic-cache-v1/pdb_<GUID><age>.txt`.

Windhawk downloads only that small file for your installed build. After a Helium update,
restart Helium (if the effect is missing, wait for the next hourly run and restart again).

To process a specific build by hand: **Actions → Helium symbol cache → Run workflow**, optionally with a helium-windows run id.

## Files

- `helium-acrylic.wh.cpp` – the mod (paste into Windhawk's editor as a local mod)
- `tools/make_cache.py` – builds a Windhawk symbol-cache file from a DLL/PDB pair
- `tools/update.sh` – the workflow logic
