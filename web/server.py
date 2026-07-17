"""
Syria TV AI Studio - Web Interface
=====================================
واجهة ويب بسيطة: صفحة فيها مربع نص، تلصق التقرير، تضغط زر،
وتحصل على النتيجة الكاملة (تحليل + عناوين + وصف + ثمبنيل + تقييم).
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from process_report import process  # noqa: E402

app = FastAPI(title="Syria TV AI Studio")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"result": None})


@app.post("/process", response_class=HTMLResponse)
async def process_transcript(request: Request, transcript: str = Form(...)):
    error = None
    result_data = None

    try:
        filepath = await process(transcript)
        report_text = filepath.read_text(encoding="utf-8")
        result_data = {
            "filename": filepath.name,
            "content": report_text,
        }
    except Exception as e:
        error = str(e)

    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "result": result_data,
            "error": error,
            "transcript": transcript,
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
