# Harvest Now or Wait? — NASA data for typhoon harvest decisions

Team Windfall Rice, NASA Space Apps Challenge 2026 (Tokyo). Challenge: "Field Shift: Adapting Farms with NASA Data".

## Summary

When a typhoon is forecast, many rice farmers in Japan harvest early, sometimes before the grain is fully ripe. They have no clear rule for when it is safe to wait. We built a small model that uses NASA GPM IMERG rainfall, NASA POWER wind and temperature, and GEOS-FP forecasts. It gives one simple signal: "harvest now" or "safe to wait". We tested it on 23 past typhoons in Ibaraki and Chiba, leaving one typhoon out at a time. It said "safe to wait" in 10 of the 16 typhoons that caused no major damage, and it missed 1 of the 7 that did. It runs on a laptop or on a Raspberry Pi Pico microcontroller. It is decision support, not a replacement for farmer judgment. The method is reusable: any region or crop with NASA data and a record of past damage can build its own rule the same way.

## Start here

Open the [`deliverable/`](deliverable/) folder. See [`deliverable/README.md`](deliverable/README.md) for how to run everything.

- `deliverable/model/`: the coefficients (`unified_model.json`) and a standalone `decide.py`.
- `deliverable/pico/`: MicroPython programs for a Raspberry Pi Pico H (`main.py`, `demo_main.py`).
- `deliverable/demo/`:
  - `index.html`: browser demo. It works offline.
  - `pico.html`: Web Serial page that sends inputs (about 20 bytes) to the Pico.
  - `serial.html`: serial page for the Pico.
- `deliverable/slides/`: 7-slide project deck (PDF) with the data analysis and validation.
- `deliverable/HISTORY.md`: development history in English (commit messages are in Japanese).

## Key results

We checked the model against 23 typhoons that came within 300 km of southern Kanto in August and September, 2004 to 2021. The reference answer is the MAFF disaster statistics: 7 typhoons caused paddy damage of 100 ha or more in Ibaraki and Chiba, and 16 did not. We left out one typhoon at a time, including from the national training data.

- Harvesting at every typhoon warning would mean 23 early harvests. 16 of them would be for typhoons with no major damage.
- Our model said "safe to wait" in 10 of those 16.
- It missed 1 of the 7 damaging typhoons: the 2019 Boso Peninsula typhoon. It was small and strong. The grid-based NASA wind was weak (6.9 m/s), so the model did not flag it. We report this miss openly.
- Across Japan (1,815 prefecture-typhoon records, 86 typhoons), adding wind to rain raised the AUC from 0.82 to 0.88. This is also leave-one-typhoon-out.
- Sensitivity: we changed rain by +/-25% and wind by +/-15%. At most one decision changed on a damaging typhoon. This check uses the model trained on all data, not leave-one-out.
- Over-forecasts of rain or wind only push the answer toward "harvest now". The risky case is a forecast that is much too weak.
- On the Pico, the 23 past typhoons gave the same decisions as on a PC (23 of 23). One decision takes about 0.6 to 1.2 ms.

## NASA data used

| Data | Role |
|---|---|
| [GPM IMERG](https://gpm.nasa.gov/data/imerg) Daily, Final Run V07 (GPM_3IMERGDF); Late Run (GPM_3IMERGDL) for the latest days. Found through [NASA Earthdata CMR](https://cmr.earthdata.nasa.gov) | Rain that has already fallen. |
| [NASA POWER](https://power.larc.nasa.gov/api/temporal/daily/point) daily point API: T2M and WS10M_MAX | Temperature gives how ripe the crop is. Wind is an input to the national model. |
| [GEOS-FP](https://opendap.nccs.nasa.gov/dods/GEOS-5/fp/0.25_deg/fcast) forecasts (NASA GMAO, 0.25 degree) | Forecast rain and 10 m wind for the next 48 hours. |

## Repository map

Research scripts are at the repo root. Run them with `uv run`.

| Role | Files |
|---|---|
| Data fetching | `fetch_imerg.py`, `fetch_geos_forecast.py`, `fetch_amedas.py`, `fetch_maff_damage.py`, `fetch_disaster_damage.py`, `fetch_fude.py`; dataset builders `build_dataset.py`, `build_japan_dataset.py` |
| Analysis | `analyze_japan.py`, `analyze_japan_wind.py`, `analyze_japan_location.py`, `analyze_disasters.py`, `analyze_early_harvest.py`, `analyze_planting.py`, `analyze_enso.py`, `analyze_episodes.py`, `analyze_threshold.py`, `analyze_typhoon_stats.py` |
| Model training | `unified_model.py` (trains and validates, writes `results/unified_model.json`), `lodging_unified.py` (runtime, `decide()`), `lodging_model.py` (older Ibaraki/Chiba rule, kept for comparison) |
| Generators | `make_pico.py` (Pico programs), `make_demo.py` (browser demo), `make_promo.py` (demo video) |
| Checks | `check_demo.py` (browser logic vs. Python `decide()`), `check_robustness.py` (sensitivity), `review_lodging_model.py` |
| Live prediction | `predict_lodging.py` (fetches GEOS-FP, IMERG, POWER and decides; `--replay DATE` replays a past typhoon) |
| Failed attempts | `lodging_s1.py`, `lodging_parcel.py` (Sentinel-1 radar, no useful signal) |

Other folders:

- `results/`: reports, predictions and the trained model.
- `docs/`: design notes and reports. Many are in Japanese. They are the team's working notes. The English submission text is in `docs/submission/`.

The root also holds early API practice scripts (`apod.py`, `neows.py`, `nasa_common.py`) that are not part of the model.

## How to reproduce

You need Python and [uv](https://docs.astral.sh/uv/). Dependencies are declared at the top of each script.

```
uv run unified_model.py   # train and validate, write results/unified_model.json
uv run make_pico.py       # generate deliverable/pico/ and copy the model to deliverable/model/
uv run make_demo.py       # generate deliverable/demo/index.html
```

Fetching new data needs a NASA Earthdata token for IMERG. For other scripts, see each script's docstring. Fetched data is stored in `data/`, which is not committed.

## Limitations

- The reference is at prefecture level (Ibaraki and Chiba), not individual fields. Field-level records do not exist yet.
- The validation set has only 23 typhoons. One typhoon changes the picture.
- NASA's grid wind (about 50 km) can miss gusts from small, strong typhoons, as in 2019.
- The reference is total wind and flood damage to paddy rice, not lodging alone.
- The model was trained on observed rain and wind. We confirmed that it runs on GEOS-FP forecast data. We could not validate its decisions against real archived forecasts.
- The threshold was tuned on past data. "10 of 16" is a past result, not a promise.
- Soil health, water use, and crop rotation are not handled. Our planting comparison covers varieties and planting dates within rice only, and is a rough estimate.

## Use of SI

We used Anthropic's Claude (through Claude Code) widely: to write code, process data, run analyses, and draft documents and slides. The idea came from the team, based on a farmer friend's experience of harvesting early before typhoons. The team set the direction, decided what to adopt or drop, and checked the results. The voice in our demo video is text-to-speech (AI-generated). We did not generate any images. The photographs were taken by the team.

## Data credits and references

- NASA GPM IMERG, NASA POWER and NASA GEOS-FP (see above).
- Japan Meteorological Agency (JMA) RSMC Tokyo Best Track data: https://www.jma.go.jp/jma/jma-eng/jma-center/rsmc-hp-pub-eg/Besttracks/bst_all.zip
- MAFF disaster damage statistics for paddy rice (the reference answer), via e-Stat: https://www.e-stat.go.jp/stat-search/files
- JMA AMeDAS ground observations: https://www.data.jma.go.jp/stats/etrn/view/
- ESA Sentinel-1 via Microsoft Planetary Computer (tried; did not detect lodging): https://planetarycomputer.microsoft.com/api/stac/v1
- Harvest timing guidance: [Chiba Prefecture](https://www.pref.chiba.lg.jp/ninaite/gijyututaisaku/documents/240718harvest.pdf), [Ibaraki Prefecture](https://www.pref.ibaraki.jp/nourinsuisan/ounourin/keiei/fukyuuhp/documents/240820seiikujouhou05.pdf)
- Tools: Python, uv, httpx, NumPy, pandas, SciPy, scikit-learn, xarray, netCDF4, MicroPython; ffmpeg and Windows SAPI text-to-speech (AI-generated voice) for the demo video.
