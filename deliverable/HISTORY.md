# Development history

The original commit messages in this repository are written in Japanese, the team's working language. This file gives an English summary and a line-by-line translation of them. All dates are in JST. The first commit (Nov 9, 2026) was practice with NASA APIs before the hackathon. The rest of the work was done during the hackathon (Nov 14-15, 2026).

Note: the log is shown in the order of the repository history. Two work streams (analysis and documents/slides) were merged, so some timestamps are slightly out of order.

## Timeline at a glance

### Phase 1. API practice and project setup (Nov 9 - Nov 14)
- Wrote practice scripts for NASA APIs (APOD, NeoWs) and a guide for working away from the desk.
- Added the plan (timetable, tools, working method) and a team description in Japanese and English.
- Added a first theme, available data, and a draft working method to the plan.

### Phase 2. Problem definition and change of direction (Nov 14)
- Wrote down the problem: farmers have no clear rule for when it is safe to wait, so they harvest early. Added hypotheses and a presentation outline.
- Interviewed a farmer friend. Added variety-specific growth stages (`phenology.py`).
- Changed direction: focus on NASA data and predict lodging when heavy rain is forecast, using disaster statistics as the reference answer.
- Narrowed the hackathon scope to "predict from the forecast whether damage will occur". Planting planning became an outlook item.
- Aligned the goal and documents with the Field Shift challenge: reduce early harvests that were not needed.
- Negative result: El Nino / La Nina showed no relationship with damage, so the product was set as a short-term lodging prediction.

### Phase 3. Satellite radar attempt (Sentinel-1) that failed (Nov 14)
- Tried change detection of lodging with Sentinel-1 radar (attempt 1).
- Tried averaging over individual field polygons (attempt 2).
- Built a list of lodging events and training data, and tested thresholds.
- Negative result: neither attempt gave a usable signal (the submission page reports a correlation of about 0.05). We then separated lodging from flooding and moved to official damage statistics (AMeDAS and MAFF) as the reference.

### Phase 4. Ibaraki/Chiba analysis with IMERG, POWER and GEOS-FP (Nov 14)
- Added scripts to fetch MAFF paddy-rice disaster statistics and GPM IMERG rain. Compared storms against the statistics (`analyze_disasters.py`).
- Added a GEOS-FP forecast fetcher and a light Ibaraki/Chiba lodging model with scripts for forecast and replay.
- Fixed several bugs in the statistics parser (missing years 2004, 2006, 2007; a prefecture-name column mistaken for the paddy-rice column, which gave all-zero damage). Fixed a best-track year misreading found in review.
- Learned: the analysis was significant, but the prediction on 23 typhoons was not clearly significant (permutation test p=0.06).

### Phase 5. National dataset and unified model (Nov 14)
- Built a nationwide prefecture x typhoon dataset (`build_japan_dataset.py`): 47 prefectures, 100 typhoons near Japan in Aug-Sep 2004-2021, 2,243 rows.
- Compared models on the national data: rain plus wind reached AUC 0.88, so the method generalizes.
- Tested location variables (prefecture helped calibration; latitude/longitude did not) and whether wind is just a proxy for distance (it is not; wind helps beyond distance).
- Merged the national and Ibaraki/Chiba models into one equation. It said "safe to wait" in 10 of 16 harmless typhoons but missed the Boso Peninsula typhoon. The team adopted the unified model and switched the prediction script to it.

### Phase 6. Validation and robustness (Nov 14 - Nov 15)
- Corrected a recorded Fisher value and regenerated reports for 23 typhoons. Aligned numbers in all documents and slides.
- Added a rough comparison of four planting options over 113 typhoons (1981-2025). Only the early variety reduced overlap with the vulnerable stage.
- Had the work reviewed by a separate AI model (21 findings). Responded to them: a 0.999 safety margin on the threshold, explicit UTF-8 encoding, and updates to slides and scripts.
- Added a sensitivity analysis (V1), a permutation test and negative control (V3), and a review against past winners and judging criteria.
- Fixed an overstatement ("green rice") in wording and regenerated the Pico program and demo.

### Phase 7. Demo, Raspberry Pi Pico H, slides and video (Nov 14 - Nov 15)
- Added a MicroPython decision program for Raspberry Pi Pico H. On the board, 10 scenarios matched the PC version, at 0.6-1.2 ms per decision.
- Built a single-file offline HTML demo, with a check script comparing it to the Python `decide()` (33/33 matches). Later simplified the demo screen.
- Added a Pico stand-alone demo (button and USB serial), a Web Serial page, and a Pico display page.
- Prepared a 30-second promotional video (instructions, photos, Pico LED photo, prototype with synthetic voice) and a 2-minute talk draft. HTML slides were drafted.

### Phase 8. Submission packaging (Nov 15)
- Wrote the English submission page draft.
- Moved all deliverables into `deliverable/` (model coefficients, stand-alone `decide.py`, Pico program, demo). Rewrote the root README in English for judges.
- Updated the draft for method reusability, the Pico price (about US$5) and the tools list.

## Commit log (translated)

| Date | Commit | Summary (English) |
|---|---|---|
| 2026-11-09 | bf0e5a4 | Add NASA API practice scripts and a guide for working remotely (apod.py with the new endpoint, neows.py, nasa_common.py; README with API availability as of 2026-11-09, CLAUDE.md, REMOTE.md) |
| 2026-11-14 | 7e519d1 | Add the push policy to CLAUDE.md |
| 2026-11-14 | f99dcbe | Add PLAN.md: timetable, resources used, working method (SDD, tentative) |
| 2026-11-14 | 1a13b16 | Add TEAM.md: description for team registration (Japanese and English) |
| 2026-11-14 | 31aac1a | Add theme, usable data and a draft working method to PLAN.md |
| 2026-11-14 | 1aeff72 | Add lodging change detection with Sentinel-1 (attempt 1) |
| 2026-11-14 | 501aac9 | Add analysis by field-polygon averages (Fude polygons) (attempt 2) |
| 2026-11-14 | cb9b626 | Add lodging event list, training data creation and threshold tests |
| 2026-11-14 | 3fdf04e | Add AMeDAS and MAFF statistics; record per-storm analysis and future plans |
| 2026-11-14 | 2614431 | Separate lodging from flooding; record the plan for interactions and candidate extra variables |
| 2026-11-14 | aa1951d | Add paddy-rice damage statistics by disaster and a GPM IMERG fetch script |
| 2026-11-14 | 8ff8a9d | fetch_imerg.py: close the files that were opened |
| 2026-11-14 | bae2aad | Read IMERG sequentially and add it to the training data; get disaster statistics from the yearly list |
| 2026-11-14 | f6f1d7c | Add analyze_disasters.py: use disaster statistics as the reference answer and compare weather per storm |
| 2026-11-14 | 5cea77e | fetch_disaster_damage.py: add download retries and caching |
| 2026-11-14 | a44b288 | Reflect the interview: add variety-specific growth stages (phenology.py) and record in PLAN |
| 2026-11-14 | 71fb0aa | PLAN: reorient to NASA-data-centered lodging prediction for heavy-rain forecasts |
| 2026-11-14 | 0cc1863 | Add fetch_geos_forecast.py to fetch NASA GEOS-FP forecasts over an area |
| 2026-11-14 | 1734693 | Add an analysis counting unnecessary early harvests in past typhoons; record the goal |
| 2026-11-14 | 22fe4cd | Test the link with El Nino / La Nina (no relationship); decide the deliverable is lodging prediction |
| 2026-11-14 | f727418 | PLAN: fix the short-term lodging prediction model as top priority; planting plan becomes an outlook |
| 2026-11-14 | 8544513 | Add a light Ibaraki/Chiba lodging prediction model and scripts for forecast and replay |
| 2026-11-14 | d7975f8 | fetch_disaster_damage.py: add --all-prefs to extract all prefectures |
| 2026-11-14 | cc2e54d | Record the review of the Ibaraki/Chiba model; fix a misread year in the best-track data |
| 2026-11-14 | 021555b | fetch_disaster_damage.py: fix tables without a year (2004, 2006, 2007); take the year from the e-Stat list title and cache it; prefer files with a paddy-rice column; accept more disaster names; add --offline |
| 2026-11-14 | e920b4e | fetch_disaster_damage.py: fix a bug that mistook the prefecture-name column for the paddy-rice column (all damage areas were 0 for 2004-2007; values from 2008 on unchanged) |
| 2026-11-14 | 2c3e227 | PLAN: record the separation of analysis (significant) and prediction (not significant) |
| 2026-11-14 | 9460e5b | Commit build_japan_dataset.py (work in progress) as a backup; a sub-agent was still working on it |
| 2026-11-14 | 2675426 | build_japan_dataset.py complete: prefecture x typhoon training data, 2,243 rows (47 prefectures, 100 typhoons within 500 km in Aug-Sep 2004-2021; 455 damaged rows with paddy damage of 100 ha or more; no missing weather) |
| 2026-11-14 | 860fd9b | Reflect disaster-statistics fixes and update the Ibaraki/Chiba early-harvest analysis (add 2007 No. 9) |
| 2026-11-14 | 5909b99 | docs: add the problem statement, hypotheses and presentation outline |
| 2026-11-14 | 5ba1f68 | docs: write up why we aim for a light model as a design policy; reflect in the presentation outline |
| 2026-11-14 | 754c064 | docs: organize questions for the farmer friend; add extension to extreme environments and the role of OSS |
| 2026-11-14 | 58b131e | docs: add generalization as a method (4-step skeleton, axes of generalization, limits of farmer-level granularity) |
| 2026-11-14 | 9867c86 | docs: add the idea of supporting harvest-timing decisions; reflect in questions and presentation outline |
| 2026-11-14 | 855dacc | docs: narrow the hackathon scope to "predicting from the forecast whether lodging will occur" |
| 2026-11-14 | bb053a2 | docs: organize into three layers (dream, path, goal) and how to place them in the talk |
| 2026-11-14 | 3547a73 | docs: update materials to the new direction (NASA-data-centered, disaster statistics as reference) |
| 2026-11-14 | ef7046c | docs: add the definition of priorities (short term = finish the lodging model), what to drop, and mapping to the official Objectives |
| 2026-11-14 | 34e6c69 | docs: fully revise priorities and presentation outline for Field Shift and the final goal (reduce unnecessary early harvests) |
| 2026-11-14 | a396bf8 | Rewrite TEAM.md for Field Shift and the final goal; clean up old challenge names in docs |
| 2026-11-14 | 95abbca | docs: reorganize story and outline around the problem (no decision rule, early harvest, yield loss) |
| 2026-11-14 | 30d6c91 | docs: add the difference between the best harvest time and the time harvest is possible (public sources) and link to Field Shift |
| 2026-11-14 | 099688a | docs: set the core of the problem as "farmers are forced to harvest at times different from what they decided"; make the claim not depend on numbers |
| 2026-11-14 | 637a9b1 | docs: add a prototype of HTML slides for the first half (problem and design premises), 5 slides |
| 2026-11-14 | 5cfe819 | Add a test script for damage vs. no damage in 22 typhoons; record the current state of the analysis slides |
| 2026-11-14 | 9479d1a | Add analyze_japan.py: nationwide prefecture x typhoon analysis and model comparison |
| 2026-11-14 | e94e95c | Update the Ibaraki/Chiba model review (permutation test over 23 typhoons, p=0.06) |
| 2026-11-14 | 346ac30 | Record nationwide analysis and model comparison (rain plus wind gives AUC 0.88; the method generalizes) |
| 2026-11-14 | c46cd53 | Add cross-validated predictions of the national model (results/japan_predictions.csv) |
| 2026-11-14 | 35c41b0 | Compare location variables (prefecture improves probability calibration; latitude/longitude do not help) |
| 2026-11-14 | edd164d | Test whether wind in the national model is a proxy for distance (it is not; wind matters beyond distance) |
| 2026-11-14 | edb94fd | Test a single model unifying the national and Ibaraki/Chiba equations (can wait in 10 of 16, but misses the Boso Peninsula typhoon) |
| 2026-11-14 | c7408c5 | Correct the Fisher value in the unified-model record |
| 2026-11-14 | 03f3ead | Adopt the unified model; add a demo (fictional input) and a report; switch the prediction script to the unified model |
| 2026-11-14 | 270a2f9 | Update numbers in story.md to the unified model (23 typhoons, can wait 10/16, national AUC 0.88, missed Boso Peninsula typhoon) |
| 2026-11-14 | afd7aeb | Align numbers in docs and slides to the unified model and 23 typhoons (priorities, presentation, slides, explanation of the old rule) |
| 2026-11-14 | aca0b2a | Regenerate the test report for the analysis slides with 23 typhoons |
| 2026-11-14 | efc58c6 | Add the decision program for Raspberry Pi Pico (MicroPython) and instructions |
| 2026-11-14 | 0f699a7 | Add the demo screen for the talk (docs/demo/index.html) with generator and check scripts; record the Pico H test (make_demo.py builds a self-contained offline HTML from unified_model.json and the 23 past typhoons; check_demo.py matches the HTML decision function against Python decide(), 33/33; Pico H with MicroPython v1.29.0 matched the PC on 10 scenarios, 0.6-1.2 ms per run) |
| 2026-11-14 | c3749e3 | Reduce the demo screen: title becomes "for demo"; remove scenarios, typhoon replay and reasons; pass initial values by URL query |
| 2026-11-14 | 0e53ae2 | Add comparison of four planting options (analyze_planting.py) and a review by another model (Fable 5.2): with variety and transplanting date changed, count typhoons overlapping the vulnerable stage (400-1,500 degC after heading) over 113 typhoons in 1981-2025 (only the early variety reduces overlap, 54 to 38); the review lists 21 findings on implementation, talk, validation, analysis, prediction and microcontroller, with status |
| 2026-11-15 | 22cbaf6 | Apply a 0.999x safety margin to the threshold; set read/write encoding to utf-8 explicitly (items M1, I4) |
| 2026-11-15 | 942db15 | Update review status: reflect P1, P2, P3, A2 in slides and script; show R1 on the outlook slide |
| 2026-11-15 | d401242 | Add working instructions for the 30-second promotional video and materials (2 photos, demo screen) |
| 2026-11-15 | f6af1c7 | Reflect the official submission requirements in the video instructions (30 seconds or less, English, public link, AI voice disclosed); align the script with the recommended flow |
| 2026-11-15 | 9046514 | Add a real photo of the Pico H LED to the video materials (cropped, metadata removed) |
| 2026-11-15 | f77c6bb | Add a review comparing with past winners and judging criteria |
| 2026-11-15 | 9aa5f76 | Fix the exaggerated expression "green rice" to "not fully ripened" and similar (immature rice turns yellow early); change scenario names, decision reasons and documents; regenerate pico/main.py and docs/demo/index.html; keep quotes of the friend and terms such as green kernels |
| 2026-11-15 | b867e36 | Add the English submission page draft (docs/submission/project-page-en.md) |
| 2026-11-15 | 53ab1b5 | Add scripts and reports for V1 sensitivity analysis and V3 permutation test with negative control |
| 2026-11-15 | 9c0f4a7 | Add a prototype 30-second promotional video (SAPI voice, make_promo.py); last line changed to match the challenge wording; IMERG/POWER shown on screen only, not read aloud; not yet approved, needs owner check in the morning |
| 2026-11-15 | 0fd9992 | Add a stand-alone Pico demo (button decision, USB serial) and a Web Serial page (make_pico.py shares the decide part and also generates pico/demo_main.py; the BOOTSEL button alternates two scenarios and the board answers a one-line serial input with JSON; docs/demo/serial.html is a single-file Web Serial page; docs/pico.md gets the steps for presentation day) |
| 2026-11-15 | f44626f | Add a draft script for the 2-minute talk |
| 2026-11-15 | a902898 | Add the display page docs/demo/pico.html (split into a page that sends input and a page for the board button) |
| 2026-11-15 | f6b21d4 | Gather deliverables into deliverable/ and make the README English (deliverable/model gets the coefficients unified_model.json and a stand-alone decide.py; Pico program and demo moved to deliverable/pico and deliverable/demo; make_pico.py / make_demo.py output paths and references updated; README rewritten in English for judges and deliverable/README.md added; English submission draft updated for method reusability, Pico about US$5, and tools) |
| 2026-11-15 | 50a9d13 | Remove mention of untracked files from deliverable/README |
