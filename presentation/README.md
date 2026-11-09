# Presentation

| File | What it is |
|---|---|
| `TDR_Cable_Fault_Detection.pptx` | the final presentation (95 slides, editable; speaker notes on every content slide) |
| `TDR_Cable_Fault_Detection.pdf` | PDF export of the same deck |
| `diagrams/d01–d12_*.png` | original architecture, workflow, ML/NN, localization, detection, sequence, integration, timeline and dataset diagrams (`make_diagrams.py`) |
| `screens/s01–s06_*.png` | screenshots of the running dashboard with the final models (`screenshots.py`) |
| `deck_data.json` | every number shown in the deck, collected from `report/results/*` (`collect_data.py`) |

The title slide uses placeholders: [Team members], [Guide], [Institution] and [Course]. Replace them in PowerPoint.

Other deliverables the deck draws on:
- **Performance analysis:** [docs/ML_ANALYSIS.md](../docs/ML_ANALYSIS.md), `report/results/`, `report/figures/` (fig1–fig10, a1–a6, zfig1–3).
- **Technical appendix and source references:** [docs/TECHNICAL_APPENDIX.md](../docs/TECHNICAL_APPENDIX.md).
- **Circuit and wiring diagrams:** [hardware/circuits/](../hardware/circuits/).

## Rebuild

```powershell
.venv\Scripts\python presentation\make_diagrams.py          # diagrams (reads analysis_model_config.csv)
<python with playwright> presentation\screenshots.py       # optional: new dashboard screenshots (Chrome)
.venv\Scripts\python presentation\collect_data.py          # numbers -> deck_data.json
cd presentation
npm install pptxgenjs@3.12.0                               # once
$env:NODE_PATH = "$PWD\node_modules"; node build_deck.js    # -> TDR_Cable_Fault_Detection.pptx
powershell -ExecutionPolicy Bypass -File export_pdf.ps1 [-Images]   # PDF (and PNG renders) via PowerPoint
```

After the lab session, run `lab-dataset`, `train --rebuild`, `evaluate` and `analyze`, then rebuild the deck. The E3/E4 slides then switch from PROXY to LAB data automatically. Add the setup photo to the hardware section.
