"""
Syria TV AI Studio - Web Interface
=====================================
واجهة ويب: تشغّل المعالجة بالخلفية (background task)، والصفحة تستعلم
دورياً عن الحالة، لتفادي انقطاع الاتصال أثناء المعالجة الطويلة.
"""

import sys
import uuid
import asyncio
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from process_report_v2 import process_structured  # noqa: E402
from stv_studio.utils.checkpoint import CheckpointManager  # noqa: E402

app = FastAPI(title="Syria TV AI Studio")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

# ذاكرة مؤقتة لتتبع حالة كل مهمة شغّالة بالخلفية
JOBS: dict[str, dict] = {}


async def run_job(job_id: str, transcript: str, options: dict):
    """يشغّل المعالجة الكاملة بالخلفية، ويحدّث حالة الـ job."""
    try:
        result = await process_structured(transcript, run_id=job_id, **options)
        JOBS[job_id] = {"status": "done", "result": result, "error": None}
    except Exception as e:
        JOBS[job_id] = {"status": "error", "result": None, "error": f"{e}\n\n{traceback.format_exc()[-500:]}"}


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse(request, "index.html", {"result": None})


@app.post("/process")
async def process_transcript(
    request: Request,
    transcript: str = Form(...),
    include_titles: str = Form(default=None),
    include_description: str = Form(default=None),
    include_thumbnail: str = Form(default=None),
    include_evaluation: str = Form(default=None),
    include_social_media: str = Form(default=None),
):
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "running", "result": None, "error": None}

    options = {
        "include_titles": bool(include_titles),
        "include_description": bool(include_description),
        "include_thumbnail": bool(include_thumbnail),
        "include_evaluation": bool(include_evaluation),
        "include_social_media": bool(include_social_media),
    }

    asyncio.create_task(run_job(job_id, transcript, options))

    return templates.TemplateResponse(
        request, "processing.html", {"job_id": job_id}
    )


@app.get("/status/{job_id}")
async def check_status(job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse({"status": "not_found"})
    return JSONResponse({"status": job["status"]})


@app.get("/result/{job_id}", response_class=HTMLResponse)
async def show_result(request: Request, job_id: str):
    job = JOBS.get(job_id)
    if not job:
        return templates.TemplateResponse(
            request, "index.html", {"result": None, "error": "المهمة غير موجودة أو انتهت صلاحيتها"}
        )
    return templates.TemplateResponse(
        request,
        "index.html",
        {"result": job.get("result"), "error": job.get("error"), "transcript": ""},
    )


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    reports = CheckpointManager.list_complete()
    return templates.TemplateResponse(request, "history.html", {"reports": reports})


@app.get("/history/{run_id}", response_class=HTMLResponse)
async def history_detail(request: Request, run_id: str):
    from stv_studio.config import PROJECT_ROOT
    import json

    filepath = PROJECT_ROOT / "outputs" / "checkpoints" / f"checkpoint_{run_id}.json"
    if not filepath.exists():
        return templates.TemplateResponse(
            request, "index.html", {"result": None, "error": "التقرير غير موجود"}
        )

    with open(filepath, encoding="utf-8") as f:
        cp_data = json.load(f)

    data = cp_data.get("data", {})
    result_data = {
        "cost": cp_data.get("cost_so_far_usd", 0.0),
        "analysis": data.get("analysis"),
        "titles": data.get("titles"),
        "description": data.get("description"),
        "thumbnail": data.get("thumbnail"),
        "evaluation": data.get("evaluation"),
        "social_media": data.get("social_media"),
        "raw_text": json.dumps(data, ensure_ascii=False, indent=2),
    }

    return templates.TemplateResponse(
        request, "index.html", {"result": result_data, "transcript": ""}
    )



@app.post("/chat")
async def chat(request: Request):
    from stv_studio.config import settings
    body = await request.json()
    message = body.get("message", "").strip()
    model_choice = body.get("model", "claude")
    context = body.get("context", "")
    history = body.get("history", [])
    if not message:
        return JSONResponse({"error": "الرسالة فارغة"}, status_code=400)
    system_prompt = "أنت مساعد تحريري خبير في تلفزيون سوريا.\n\nالسياق:\n" + context + "\n\nاللغة: العربية. الأسلوب: مهني ومباشر."
    messages = [{"role": h["role"], "content": h["content"]} for h in history]
    messages.append({"role": "user", "content": message})
    try:
        if model_choice == "claude":
            from anthropic import Anthropic
            client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
            response = client.messages.create(model="claude-sonnet-4-6", max_tokens=2000, system=system_prompt, messages=messages)
            reply = response.content[0].text
            model_name = "Claude Sonnet"
        elif model_choice == "gpt":
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
            response = client.chat.completions.create(model="gpt-5.6-terra", messages=[{"role": "system", "content": system_prompt}] + messages, max_completion_tokens=2000)
            reply = response.choices[0].message.content
            model_name = "GPT"
        elif model_choice == "gemini":
            from google import genai
            from google.genai import types as gt
            client = genai.Client(api_key=settings.google_api_key.get_secret_value())
            full = system_prompt + "\n\n" + "\n".join([m["role"] + ": " + m["content"] for m in messages])
            response = client.models.generate_content(model="gemini-3.1-flash-lite", contents=full, config=gt.GenerateContentConfig(max_output_tokens=2000))
            reply = response.text
            model_name = "Gemini Flash"
        else:
            return JSONResponse({"error": "نموذج غير معروف"}, status_code=400)
        return JSONResponse({"reply": reply, "model_name": model_name})
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)

if __name__ == "__main__":
    import os
    import uvicorn
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
# Sun Jul 19 10:51:31 UTC 2026
