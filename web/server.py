"""
Syria TV AI Studio - Web Interface
"""
import sys
import uuid
import json
import asyncio
import traceback
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "src"))
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from fastapi import FastAPI, Form, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates

from process_report_v2 import process_structured
from stv_studio.utils.checkpoint import CheckpointManager

app = FastAPI(title="Syria TV AI Studio")
templates = Jinja2Templates(directory=str(Path(__file__).parent / "templates"))

JOBS: dict[str, dict] = {}


async def run_job(job_id: str, transcript: str, options: dict):
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
    content_type: str = Form(default=None),
    program_name: str = Form(default=None),
    include_titles: str = Form(default=None),
    include_description: str = Form(default=None),
    include_thumbnail: str = Form(default=None),
    include_evaluation: str = Form(default=None),
    include_social_media: str = Form(default=None),
    include_trend_context: str = Form(default=None),
):
    job_id = uuid.uuid4().hex[:12]
    JOBS[job_id] = {"status": "running", "result": None, "error": None}

    options = {
        "content_type": content_type or None,
        "program_name": program_name or None,
        "include_titles": bool(include_titles),
        "include_description": bool(include_description),
        "include_thumbnail": bool(include_thumbnail),
        "include_evaluation": bool(include_evaluation),
        "include_social_media": bool(include_social_media),
        "include_trend_context": bool(include_trend_context),
    }

    # نمرّر الخيارات لصفحة المعالجة لبناء شريط التقدّم
    asyncio.create_task(run_job(job_id, transcript, options))
    return templates.TemplateResponse(request, "processing.html", {
        "job_id": job_id,
        "include_titles": bool(include_titles),
        "include_description": bool(include_description),
        "include_thumbnail": bool(include_thumbnail),
        "include_evaluation": bool(include_evaluation),
        "include_social_media": bool(include_social_media),
        "include_trend_context": bool(include_trend_context),
    })


@app.get("/status/{job_id}")
async def check_status(job_id: str):
    """
    Enhanced status endpoint - يقرأ من الـ checkpoint لعرض:
    - الخطوة الحالية
    - الخطوات المكتملة
    - التكلفة حتى الآن
    """
    job = JOBS.get(job_id)
    if not job:
        return JSONResponse({"status": "not_found"})

    # قراءة الـ checkpoint إذا موجود
    from stv_studio.config import PROJECT_ROOT
    checkpoint_path = PROJECT_ROOT / "outputs" / "checkpoints" / f"checkpoint_{job_id}.json"

    checkpoint_data = {
        "steps_completed": [],
        "cost_so_far": 0.0,
        "current_step": None,
    }

    if checkpoint_path.exists():
        try:
            with open(checkpoint_path, encoding="utf-8") as f:
                cp = json.load(f)
                checkpoint_data["steps_completed"] = cp.get("steps_completed", [])
                checkpoint_data["cost_so_far"] = cp.get("cost_so_far_usd", 0.0)

                # تحديد الخطوة الحالية = آخر خطوة مكتملة + 1
                all_steps = ["analysis", "titles", "description", "thumbnail", "evaluation", "social_media", "trend_context"]
                completed = checkpoint_data["steps_completed"]
                next_step = None
                for step in all_steps:
                    if step not in completed:
                        next_step = step
                        break
                checkpoint_data["current_step"] = next_step
        except Exception:
            pass

    return JSONResponse({
        "status": job["status"],
        "steps_completed": checkpoint_data["steps_completed"],
        "current_step": checkpoint_data["current_step"],
        "cost_so_far": checkpoint_data["cost_so_far"],
    })


@app.get("/result/{job_id}", response_class=HTMLResponse)
async def show_result(request: Request, job_id: str):
    job = JOBS.get(job_id)
    if not job:
        # حاول القراءة من الـ checkpoint حتى لو JOBS انمسحت
        from stv_studio.config import PROJECT_ROOT
        checkpoint_path = PROJECT_ROOT / "outputs" / "checkpoints" / f"checkpoint_{job_id}.json"
        if checkpoint_path.exists():
            return await history_detail(request, job_id)
        return templates.TemplateResponse(request, "index.html", {"result": None, "error": "المهمة غير موجودة أو انتهت صلاحيتها"})
    return templates.TemplateResponse(request, "index.html", {"result": job.get("result"), "error": job.get("error"), "transcript": ""})


@app.get("/history", response_class=HTMLResponse)
async def history(request: Request):
    reports = CheckpointManager.list_complete()
    return templates.TemplateResponse(request, "history.html", {"reports": reports})


@app.get("/history/{run_id}", response_class=HTMLResponse)
async def history_detail(request: Request, run_id: str):
    from stv_studio.config import PROJECT_ROOT

    filepath = PROJECT_ROOT / "outputs" / "checkpoints" / f"checkpoint_{run_id}.json"
    if not filepath.exists():
        return templates.TemplateResponse(request, "index.html", {"result": None, "error": "التقرير غير موجود"})

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
        "trend_context": data.get("trend_context"),
        "content_type": cp_data.get("content_type"),
        "program_name": cp_data.get("program_name"),
        "raw_text": json.dumps(data, ensure_ascii=False, indent=2),
    }

    return templates.TemplateResponse(request, "index.html", {"result": result_data, "transcript": ""})


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

    system_prompt = f"""أنت مساعد تحريري خبير في تلفزيون سوريا.
لديك سياق كامل عن التقرير الذي تمت معالجته:

{context}

مهمتك مساعدة المحرر في تحسين المحتوى، اقتراح بدائل، الإجابة على أسئلته، وتقديم رأيك التحريري المهني.
اللغة: العربية الفصحى دائماً.
الأسلوب: مهني، مباشر، مفيد."""

    messages = []
    for h in history:
        messages.append({"role": h["role"], "content": h["content"]})
    messages.append({"role": "user", "content": message})

    try:
        if model_choice == "claude":
            from anthropic import Anthropic
            client = Anthropic(api_key=settings.anthropic_api_key.get_secret_value())
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=2000,
                system=system_prompt,
                messages=messages,
            )
            reply = response.content[0].text
            model_name = "Claude Sonnet"

        elif model_choice == "gpt":
            from openai import OpenAI
            client = OpenAI(api_key=settings.openai_api_key.get_secret_value())
            all_messages = [{"role": "system", "content": system_prompt}] + messages
            response = client.chat.completions.create(
                model="gpt-5.6-terra",
                messages=all_messages,
                max_completion_tokens=2000,
            )
            reply = response.choices[0].message.content
            model_name = "GPT"

        elif model_choice == "gemini":
            from google import genai
            from google.genai import types as genai_types
            client = genai.Client(api_key=settings.google_api_key.get_secret_value())
            full_prompt = system_prompt + "\n\n" + "\n".join([f"{m['role']}: {m['content']}" for m in messages])
            response = client.models.generate_content(
                model="gemini-3.1-flash-lite",
                contents=full_prompt,
                config=genai_types.GenerateContentConfig(max_output_tokens=2000),
            )
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
