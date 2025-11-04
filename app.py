import os
import json
import tempfile

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

from utils.evaluation import (
    evaluate_answer,
    transcribe_audio_whisper,
    gpt_evaluate_answer,
)
from utils.prep_generator import generate_prep_report

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_PATH = os.path.join(BASE_DIR, "data", "questions.json")
JOBS_PATH = os.path.join(BASE_DIR, "data", "jobs.json")
JOB_QUESTIONS_PATH = os.path.join(BASE_DIR, "data", "job_questions.json")


def load_questions():
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_jobs():
    if not os.path.exists(JOBS_PATH):
        return []
    with open(JOBS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def load_job_questions():
    if not os.path.exists(JOB_QUESTIONS_PATH):
        return {}
    with open(JOB_QUESTIONS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


@app.route("/", methods=["GET"])
def index():
    """
    Main practice page: generic interview question with text/voice answer.
    """
    questions = load_questions()
    current_question = questions[0] if questions else None
    return render_template("index.html", question=current_question)


@app.route("/answer", methods=["POST"])
def answer():
    """
    Receive a text answer, evaluate it with GPT, and show feedback.
    """
    user_answer = request.form.get("answer", "").strip()
    question_id = request.form.get("question_id")

    if not user_answer:
        return render_template(
            "result.html",
            result={"error": "No answer received. Please type something."},
        )

    questions = load_questions()
    current_question = next(
        (q for q in questions if str(q["id"]) == str(question_id)),
        None,
    )

    if current_question is None:
        return render_template(
            "result.html",
            result={"error": "Question not found."},
        )

    # GPT based evaluation
    eval_result = gpt_evaluate_answer(
        question=current_question["question"],
        ideal_answer=current_question["ideal_answer"],
        user_answer=user_answer,
    )

    return render_template("result.html", result=eval_result)


@app.route("/audio", methods=["POST"])
def audio():
    """
    Receive audio, transcribe with Whisper, evaluate with GPT, return JSON.
    """
    question_id = request.form.get("question_id")

    if "audio" not in request.files:
        return jsonify({"error": "No audio file received."}), 400

    audio_file = request.files["audio"]

    if audio_file.filename == "":
        return jsonify({"error": "Empty audio filename."}), 400

    filename = secure_filename(audio_file.filename)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
            temp_path = tmp.name
            audio_file.save(temp_path)

        questions = load_questions()
        current_question = next(
            (q for q in questions if str(q["id"]) == str(question_id)),
            None,
        )

        if current_question is None:
            return jsonify({"error": "Question not found."}), 400

        transcript_text = transcribe_audio_whisper(temp_path)

        eval_result = gpt_evaluate_answer(
            question=current_question["question"],
            ideal_answer=current_question["ideal_answer"],
            user_answer=transcript_text,
        )

        eval_result["transcript"] = transcript_text
        return jsonify(eval_result), 200

    except Exception as e:
        return jsonify({"error": f"Error processing audio: {str(e)}"}), 500

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.route("/jobs", methods=["GET"])
def jobs():
    """
    Show a list of predefined jobs so the user can browse role specific questions.
    """
    jobs_list = load_jobs()
    return render_template("jobs.html", jobs=jobs_list)


@app.route("/jobs/<int:job_id>", methods=["GET"])
def job_detail(job_id: int):
    """
    Show questions for a specific job from job_questions.json.
    You will fill these questions manually over time.
    """
    jobs_list = load_jobs()
    job = next((j for j in jobs_list if j["id"] == job_id), None)

    job_questions_map = load_job_questions()
    job_questions_entry = job_questions_map.get(str(job_id))

    questions = []
    if job_questions_entry:
        questions = job_questions_entry.get("questions", [])

    return render_template(
        "job_detail.html",
        job=job,
        questions=questions,
    )


@app.route("/custom_prep", methods=["GET", "POST"])
def custom_prep():
    """
    Page where the user enters job title, company, job description, and resume.
    Backend calls GPT (with local fallback) to generate a tailored prep report.
    """
    report = None
    error = None

    if request.method == "POST":
        job_title = request.form.get("job_title", "").strip()
        company_name = request.form.get("company_name", "").strip() or None
        job_description = request.form.get("job_description", "").strip() or None
        resume = request.form.get("resume", "").strip() or None

        if not job_title:
            error = "Please enter at least the job position."
        else:
            report = generate_prep_report(
                job_title=job_title,
                company_name=company_name,
                job_description=job_description,
                resume=resume,
                use_gpt=True,
            )

            if report.get("error"):
                error = report["error"]

    return render_template(
        "custom_prep.html",
        report=report,
        error=error,
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
