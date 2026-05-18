$ErrorActionPreference = "Stop"

py -3.11 -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e .[dev]
pytest
Write-Host "Setup fertig. Starte mit: python -m predigt_uploader wizard"
