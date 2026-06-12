# MVA Tool V2

Internal Flask app for turning Tenable SC and Tenable IO CSV exports into an analyst-ready Excel workbook.

## What is included

- Upload UI for Tenable SC and Tenable IO CSV files
- Live processing screen with progress updates
- Two-sheet Excel output:
  - `Raw Data`
  - `Analysed`
- SC and IO field mapping
- Patch priority based on the exploit/severity matrix
- Asset exposure scoring out of 1000
- Large-file friendly processing using streamed CSV reads, SQLite staging, and constant-memory Excel writing
- Sample files for testing in [samples](/Users/mohammedshahid/Documents/New%20project/MVA-tool-V2/samples)

## Quick Start

```bash
cd MVA-tool-V2
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python app.py
```

Open [http://localhost:5000](http://localhost:5000)

## Test With The Included Samples

Use either of these files from the `samples/` folder:

- `samples/tenable_sc_full_sample.csv`
- `samples/tenable_io_full_sample.csv`

The sample data is designed to exercise:

- SC field mapping
- IO field mapping
- The `Exploit?` vs `definition.exploitability_ease` priority logic
- The per-IP summary banner
- Critical, high, medium, and low findings

## Expected Sample Summary

For the main sample host, the analysed sheet should show a banner close to:

```text
10.20.1.234     3 Critical | 4 High | 1 Medium     Total: 8     Immediate Patch Needed: 4
```

## Main Files

- [app.py](/Users/mohammedshahid/Documents/New%20project/MVA-tool-V2/app.py)
- [parser.py](/Users/mohammedshahid/Documents/New%20project/MVA-tool-V2/parser.py)
- [excel_builder.py](/Users/mohammedshahid/Documents/New%20project/MVA-tool-V2/excel_builder.py)
- [templates/upload.html](/Users/mohammedshahid/Documents/New%20project/MVA-tool-V2/templates/upload.html)
- [templates/processing.html](/Users/mohammedshahid/Documents/New%20project/MVA-tool-V2/templates/processing.html)
- [templates/results.html](/Users/mohammedshahid/Documents/New%20project/MVA-tool-V2/templates/results.html)
