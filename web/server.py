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
            try:
                return await history_detail(request, job_id)
            except Exception as e:
                import traceback
                print(f"[ERROR] history_detail failed: {e}\n{traceback.format_exc()}")
                return templates.TemplateResponse(request, "index.html", {"result": None, "error": f"خطأ في تحميل التقرير: {str(e)}"})
        return templates.TemplateResponse(request, "index.html", {"result": None, "error": "المهمة غير موجودة أو انتهت صلاحيتها"})
    result_with_id = job.get("result")
    if result_with_id and isinstance(result_with_id, dict):
        result_with_id["job_id"] = job_id
    return templates.TemplateResponse(request, "index.html", {"result": result_with_id, "error": job.get("error"), "transcript": ""})


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
        "content_type": cp_data.get("content_type"),
        "program_name": cp_data.get("program_name"),
        "raw_text": json.dumps(data, ensure_ascii=False, indent=2),
        "job_id": run_id,
    }

    return templates.TemplateResponse(request, "index.html", {"result": result_data, "transcript": ""})



# ==================== إعادة التوليد الجزئية ====================

async def _load_checkpoint(job_id: str):
    """يحمّل الـ checkpoint من ملف."""
    from stv_studio.config import PROJECT_ROOT
    filepath = PROJECT_ROOT / "outputs" / "checkpoints" / f"checkpoint_{job_id}.json"
    if not filepath.exists():
        return None
    with open(filepath, encoding="utf-8") as f:
        return json.load(f)


async def _save_checkpoint(job_id: str, cp_data: dict):
    """يحفظ الـ checkpoint المحدّث."""
    from stv_studio.config import PROJECT_ROOT
    filepath = PROJECT_ROOT / "outputs" / "checkpoints" / f"checkpoint_{job_id}.json"
    from datetime import datetime
    cp_data["last_updated"] = datetime.now().isoformat()
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(cp_data, f, ensure_ascii=False, indent=2)


def _build_context_block_regen(content_type, program_name):
    """يبني سياق تحريري - نسخة داخلية للـ regenerate."""
    if not content_type and not program_name:
        return ""
    parts = ["\n## السياق التحريري\n"]
    if content_type:
        parts.append(f"- **نوع النص:** {content_type}")
    if program_name:
        parts.append(f"- **البرنامج:** {program_name}")
    parts.append("\nضع هذا السياق في الاعتبار عند توليد كل مخرجاتك.\n")
    return "\n".join(parts)


@app.post("/regenerate/titles/{job_id}")
async def regenerate_titles(job_id: str):
    """يعيد توليد العناوين فقط."""
    cp_data = await _load_checkpoint(job_id)
    if not cp_data:
        return JSONResponse({"error": "التقرير غير موجود"}, status_code=404)

    transcript = cp_data.get("transcript", "")
    if not transcript:
        return JSONResponse({"error": "نص التقرير غير محفوظ"}, status_code=400)

    content_type = cp_data.get("content_type")
    program_name = cp_data.get("program_name")
    context_block = _build_context_block_regen(content_type, program_name)

    try:
        from stv_studio.agents.analyzer import TranscriptAnalyzer
        from stv_studio.agents.title_generator import TitleAgent

        analyzer = TranscriptAnalyzer()
        analysis = await analyzer.analyze(transcript, context_block=context_block)

        title_agent = TitleAgent(router=analyzer.router)
        titles_result = await title_agent.generate(analysis, context_block=context_block)

        # تحديث الـ checkpoint
        cp_data["data"]["titles"] = titles_result.model_dump()
        cp_data["cost_so_far_usd"] = cp_data.get("cost_so_far_usd", 0.0) + analyzer.router.get_stats()["total_cost_usd"]
        await _save_checkpoint(job_id, cp_data)
        if job_id in JOBS: JOBS[job_id]["result"] = cp_data["data"]

        return JSONResponse({
            "success": True,
            "titles": titles_result.model_dump(),
            "new_cost": cp_data["cost_so_far_usd"],
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/regenerate/description/{job_id}")
async def regenerate_description(job_id: str):
    """يعيد توليد الوصف والكلمات المفتاحية والهاشتاغات."""
    cp_data = await _load_checkpoint(job_id)
    if not cp_data:
        return JSONResponse({"error": "التقرير غير موجود"}, status_code=404)

    transcript = cp_data.get("transcript", "")
    if not transcript:
        return JSONResponse({"error": "نص التقرير غير محفوظ"}, status_code=400)

    content_type = cp_data.get("content_type")
    program_name = cp_data.get("program_name")
    context_block = _build_context_block_regen(content_type, program_name)

    try:
        from stv_studio.agents.analyzer import TranscriptAnalyzer
        from stv_studio.agents.description_generator import DescriptionAgent

        analyzer = TranscriptAnalyzer()
        analysis = await analyzer.analyze(transcript, context_block=context_block)

        # نأخذ العنوان الحالي من الـ checkpoint
        titles_data = cp_data["data"].get("titles", {})
        if titles_data and titles_data.get("titles"):
            recommended_idx = titles_data.get("recommended", {}).get("index", 0)
            chosen_title = titles_data["titles"][recommended_idx]["text"]
        else:
            chosen_title = analysis.title_focus or analysis.topic[:70]

        desc_agent = DescriptionAgent(router=analyzer.router)
        desc_result = await desc_agent.generate(analysis, chosen_title, context_block=context_block)

        cp_data["data"]["description"] = desc_result.model_dump()
        cp_data["cost_so_far_usd"] = cp_data.get("cost_so_far_usd", 0.0) + analyzer.router.get_stats()["total_cost_usd"]
        await _save_checkpoint(job_id, cp_data)
        if job_id in JOBS: JOBS[job_id]["result"] = cp_data["data"]

        return JSONResponse({
            "success": True,
            "description": desc_result.model_dump(),
            "new_cost": cp_data["cost_so_far_usd"],
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/regenerate/thumbnail/{job_id}")
async def regenerate_thumbnail(job_id: str):
    """يعيد توليد أفكار الثمبنيل."""
    cp_data = await _load_checkpoint(job_id)
    if not cp_data:
        return JSONResponse({"error": "التقرير غير موجود"}, status_code=404)

    transcript = cp_data.get("transcript", "")
    if not transcript:
        return JSONResponse({"error": "نص التقرير غير محفوظ"}, status_code=400)

    content_type = cp_data.get("content_type")
    program_name = cp_data.get("program_name")
    context_block = _build_context_block_regen(content_type, program_name)

    try:
        from stv_studio.agents.analyzer import TranscriptAnalyzer
        from stv_studio.agents.thumbnail_generator import ThumbnailAgent

        analyzer = TranscriptAnalyzer()
        analysis = await analyzer.analyze(transcript, context_block=context_block)

        titles_data = cp_data["data"].get("titles", {})
        if titles_data and titles_data.get("titles"):
            recommended_idx = titles_data.get("recommended", {}).get("index", 0)
            chosen_title = titles_data["titles"][recommended_idx]["text"]
        else:
            chosen_title = analysis.title_focus or analysis.topic[:70]

        thumb_agent = ThumbnailAgent(router=analyzer.router)
        thumb_result = await thumb_agent.generate(analysis, chosen_title, context_block=context_block)

        cp_data["data"]["thumbnail"] = thumb_result.model_dump()
        cp_data["cost_so_far_usd"] = cp_data.get("cost_so_far_usd", 0.0) + analyzer.router.get_stats()["total_cost_usd"]
        await _save_checkpoint(job_id, cp_data)
        if job_id in JOBS: JOBS[job_id]["result"] = cp_data["data"]

        return JSONResponse({
            "success": True,
            "thumbnail": thumb_result.model_dump(),
            "new_cost": cp_data["cost_so_far_usd"],
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


@app.post("/regenerate/social_media/{job_id}")
async def regenerate_social_media(job_id: str):
    """يعيد توليد حزمة السوشيال ميديا."""
    cp_data = await _load_checkpoint(job_id)
    if not cp_data:
        return JSONResponse({"error": "التقرير غير موجود"}, status_code=404)

    transcript = cp_data.get("transcript", "")
    if not transcript:
        return JSONResponse({"error": "نص التقرير غير محفوظ"}, status_code=400)

    content_type = cp_data.get("content_type")
    program_name = cp_data.get("program_name")
    context_block = _build_context_block_regen(content_type, program_name)

    try:
        from stv_studio.agents.analyzer import TranscriptAnalyzer
        from stv_studio.agents.social_media_generator import SocialMediaAgent

        analyzer = TranscriptAnalyzer()
        analysis = await analyzer.analyze(transcript, context_block=context_block)

        social_agent = SocialMediaAgent(router=analyzer.router)
        social_result = await social_agent.generate(transcript, analysis, context_block=context_block)

        cp_data["data"]["social_media"] = social_result.model_dump()
        cp_data["cost_so_far_usd"] = cp_data.get("cost_so_far_usd", 0.0) + analyzer.router.get_stats()["total_cost_usd"]
        await _save_checkpoint(job_id, cp_data)
        if job_id in JOBS: JOBS[job_id]["result"] = cp_data["data"]

        return JSONResponse({
            "success": True,
            "social_media": social_result.model_dump(),
            "new_cost": cp_data["cost_so_far_usd"],
        })
    except Exception as e:
        return JSONResponse({"error": str(e)}, status_code=500)


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
