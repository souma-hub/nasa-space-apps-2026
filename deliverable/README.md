# Deliverable: typhoon harvest-timing decision aid for rice

This folder holds the final deliverable. It answers one question: when a typhoon is coming, should a rice farmer harvest now, or is it safe to wait?

The decision is decision support only. It works at prefecture level, not at field level. It was validated on 23 typhoons: in 10 of 16 cases where waiting was safe, the model said "safe to wait", and it missed 1 of 7 damaging cases.

## Folders

- `demo/` - Browser demos. Plain HTML, no server, works offline.
  - `index.html` - the main demo screen (23 typhoons replayed).
  - `pico.html` - a screen that talks to the Raspberry Pi Pico over USB.
  - `serial.html` - a simpler serial test screen.
- `pico/` - MicroPython programs for Raspberry Pi Pico.
  - `demo_main.py` - the stand-alone demo program (use this one).
  - `main.py` - an earlier version with the same model.
- `model/` - The model without any hardware.
  - `unified_model.json` - the coefficients.
  - `decide.py` - a stand-alone Python decision function and CLI (standard library only).

## Browser demo

Open `deliverable/demo/index.html` in any browser. It needs no internet.

## Raspberry Pi Pico

1. Flash the program as `main.py`:
   `uvx mpremote connect COM3 cp deliverable/pico/demo_main.py :main.py`
   (the COM number differs per PC). You can also use Thonny: open `demo_main.py` and save it to the Pico as `main.py`.
2. Open `deliverable/demo/pico.html` in Edge or Chrome and press Connect. Choose the Pico.
3. Send one line: `pref,past,forecast,wind,gdd`
   - `茨城,0,40,10,750` -> harvest now (LED on)
   - `茨城,0,20,10,750` -> safe to wait (LED off)
4. Press the BOOTSEL button on the board. It alternates between two built-in scenarios.

### Serial format

Input is one line ending in a newline: `pref,rain_past_mm,rain_forecast_mm,wind_ms,gdd[,variety]`.
`pref` is a Japanese prefecture name such as `茨城`. `gdd` may be empty. `variety` is optional (default `koshihikari`).

Output is one JSON line:

```
{"src": "serial", "harvest": true, "decision": "刈る", "prob": 0.2014, "threshold": 0.1674, "us": 1234, "pref": "茨城"}
```

- `src`: `serial` or `button`.
- `harvest`: true means harvest now.
- `decision`: `刈る` (harvest now) or `待ってよい` (safe to wait).
- `prob`: estimated probability of lodging damage.
- `threshold`: the decision threshold. Harvest when `prob` is at or above it.
- `us`: computing time on the Pico, in microseconds.
- Bad input gives `{"error": "..."}`.

## decide.py

```
python deliverable/model/decide.py <pref> <rain_past_mm> <rain_forecast_mm> <wind_ms> [gdd] [variety]
python deliverable/model/decide.py 茨城 0 40 10 750
{"decision": "harvest now", "prob": 0.2014, "threshold": 0.1674}
```

`pref` accepts Japanese names (`茨城`, with or without 県/府/都) and romanized names (`ibaraki`). It reads `unified_model.json` in the same folder.

## Where the numbers come from

The coefficients come from `results/unified_model.json`, produced by `unified_model.py` at the repo root. `make_pico.py` embeds them into the Pico programs and copies the JSON to `model/`. `make_demo.py` builds `demo/index.html`.

## Credits

The code was written with the help of Anthropic Claude (Claude Code).
