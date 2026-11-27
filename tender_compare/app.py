"""Web app for comparing priced BOQs from several bidders.

Upload two or more CSV files, one per bidder, and get back a ranked
comparison with rate outliers flagged. The home page is a plain
upload form. /compare returns the report as HTML. /api/compare
returns the same comparison as JSON.
"""

import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse, JSONResponse

from .compare import (
    Bidder,
    compare_bidders,
    comparison_to_dict,
    parse_bidder_csv,
)
from .report import render_html

app = FastAPI(title="tender-compare")


def _bidder_name(filename: str, override: str | None) -> str:
    if override:
        return override.strip()
    stem = os.path.splitext(os.path.basename(filename or "bidder"))[0]
    return stem.replace("_", " ").replace("-", " ").title()


async def _load_bidders(
    files: list[UploadFile], bidder_names: str | None
) -> list[Bidder]:
    if len(files) < 2:
        raise HTTPException(
            status_code=400,
            detail="Upload at least two bidder CSV files.",
        )
    names = None
    if bidder_names:
        names = [name.strip() for name in bidder_names.split(",")]
        if len(names) != len(files):
            raise HTTPException(
                status_code=400,
                detail="Give one bidder name per file, in the same order.",
            )
    bidders: list[Bidder] = []
    for index, upload in enumerate(files):
        raw = await upload.read()
        try:
            text = raw.decode("utf-8-sig")
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail=f"{upload.filename}: the file is not readable text.",
            )
        override = names[index] if names else None
        name = _bidder_name(upload.filename or "bidder", override)
        try:
            bidders.append(parse_bidder_csv(name, text))
        except ValueError as error:
            raise HTTPException(status_code=400, detail=str(error))
    return bidders


@app.get("/", response_class=HTMLResponse)
async def home() -> str:
    return """<!DOCTYPE html>
<html lang="en">
<head><meta charset="utf-8"><title>tender-compare</title>
<style>
body { font-family: system-ui, sans-serif; margin: 2em; color: #222;
  max-width: 640px; }
input, button { font-size: 1em; margin: 0.5em 0; }
label { display: block; margin-top: 1em; }
</style></head>
<body>
<h1>tender-compare</h1>
<p>Upload one priced BOQ per bidder, as a CSV. I match the items by
item number, rank the bidders by total, and flag any rate more than
25% away from the median rate for that item.</p>
<p>Each CSV needs these columns: item_no, description, trade, unit,
quantity, rate.</p>
<form action="/compare" method="post" enctype="multipart/form-data">
<label>Bidder CSV files (two or more)
<input type="file" name="files" multiple required accept=".csv">
</label>
<label>Bidder names, comma separated, in the same order as the files
(optional, otherwise I use the file names)
<input type="text" name="bidder_names" size="60">
</label>
<button type="submit">Compare tenders</button>
</form>
<p>Want the result as data instead? Post the same files to
<code>/api/compare</code> and you get JSON back.</p>
</body>
</html>"""


@app.post("/compare", response_class=HTMLResponse)
async def compare_html(
    files: list[UploadFile] = File(...),
    bidder_names: str | None = Form(default=None),
) -> str:
    bidders = await _load_bidders(files, bidder_names)
    try:
        comparison = compare_bidders(bidders)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return render_html(comparison)


@app.post("/api/compare")
async def compare_json(
    files: list[UploadFile] = File(...),
    bidder_names: str | None = Form(default=None),
) -> JSONResponse:
    bidders = await _load_bidders(files, bidder_names)
    try:
        comparison = compare_bidders(bidders)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))
    return JSONResponse(content=comparison_to_dict(comparison))
