import os
import json
import tempfile
import random
from datetime import datetime, date, time, timedelta
import pdfkit
import io

from flask import (
    Flask,
    render_template,
    request,
    jsonify,
    session,
    redirect,
    url_for,
    send_file,
    flash,
    abort,
    make_response,
    abort,
)
from werkzeug.utils import secure_filename
    # noqa
from werkzeug.security import generate_password_hash, check_password_hash
from functools import wraps

from flask_sqlalchemy import SQLAlchemy
from sqlalchemy.pool import NullPool

import pdfkit 

from utils.evaluation import (
    evaluate_answer,
    transcribe_audio_whisper,
    gpt_evaluate_answer,
)
from utils.prep_generator import generate_prep_report
from utils.resume_review_generator import generate_resume_report
from openai import OpenAI


# ---------------------------------------------------------------------------
# Flask app + DB config
# ---------------------------------------------------------------------------

app = Flask(__name__)

# Secret key for sessions (needed to track used questions)
# In production, set FLASK_SECRET_KEY in your environment.
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "change-this-in-production")

# Supabase Session Pooler connection string.
# Prefer putting DATABASE_URL in your environment; otherwise it falls back
# to the literal URI below.

SUPABASE_URL = os.environ.get(
    "DATABASE_URL",
    "postgresql+psycopg://"
    "postgres.zbqzfmjdcfagobdyrvva:fabbofabbO1.."
    "@aws-1-us-east-2.pooler.supabase.com:5432/postgres?sslmode=require",
)

app.config["SQLALCHEMY_DATABASE_URI"] = SUPABASE_URL
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

db = SQLAlchemy(
    app,
    engine_options={
        "pool_pre_ping": True,
        "poolclass": NullPool,
    },
)

client = OpenAI()  # uses OPENAI_API_KEY from your environment


# ---------------------------------------------------------------------------
# SQLAlchemy models aligned with DB schema
# ---------------------------------------------------------------------------


class User(db.Model):
    __tablename__ = "users"

    id = db.Column(db.BigInteger, primary_key=True)
    email = db.Column(db.String(255), unique=True, nullable=False)
    username = db.Column(db.String(50), unique=True, nullable=False)
    password_hash = db.Column(db.Text, nullable=False)
    profile_image_url = db.Column(db.Text)

    opt_out_emails = db.Column(
        db.Boolean, nullable=False, server_default=db.text("FALSE")
    )
    streak_count = db.Column(
        db.Integer, nullable=False, server_default=db.text("0")
    )
    longest_streak = db.Column(
        db.Integer, nullable=False, server_default=db.text("0")
    )

    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )
    updated_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )


class UserAuthProvider(db.Model):
    __tablename__ = "user_auth_providers"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    provider = db.Column(db.String(50), nullable=False)
    provider_user_id = db.Column(db.String(255), nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )

    __table_args__ = (
        db.UniqueConstraint("provider", "provider_user_id", name="uq_provider_user"),
    )


class DailyQuestion(db.Model):
    __tablename__ = "daily_questions"

    id = db.Column(db.BigInteger, primary_key=True)
    question_text = db.Column(db.Text, nullable=False)
    ideal_answer = db.Column(db.Text)
    active_for_date = db.Column(db.Date, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )


class Answer(db.Model):
    __tablename__ = "answers"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_source = db.Column(db.String(20), nullable=False)
    question_id = db.Column(db.BigInteger)
    raw_question_text = db.Column(db.Text, nullable=False)
    answer_text = db.Column(db.Text, nullable=False)
    is_voice = db.Column(
        db.Boolean,
        nullable=False,
        server_default=db.text("FALSE"),
    )
    transcript = db.Column(db.Text)
    relevance_score = db.Column(db.Numeric(5, 2))
    confidence_score = db.Column(db.Numeric(5, 2))
    final_score = db.Column(db.Numeric(5, 2))
    feedback_text = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )


class Job(db.Model):
    __tablename__ = "jobs"

    id = db.Column(db.BigInteger, primary_key=True)
    title = db.Column(db.String(255), nullable=False)
    category = db.Column(db.String(100))
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )


class JobSpecificQuestion(db.Model):
    __tablename__ = "job_specific_questions"

    id = db.Column(db.BigInteger, primary_key=True)
    job_id = db.Column(
        db.BigInteger,
        db.ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_text = db.Column(db.Text, nullable=False)
    ideal_answer = db.Column(db.Text)
    tags = db.Column(db.ARRAY(db.Text))
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )


class PrepReport(db.Model):
    __tablename__ = "prep_reports"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    job_title = db.Column(db.String(255), nullable=False)
    company_name = db.Column(db.String(255))
    job_description = db.Column(db.Text)
    resume_text = db.Column(db.Text)
    report_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )


class ResumeReport(db.Model):
    __tablename__ = "resume_reports"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    resume_text = db.Column(db.Text)
    target_role = db.Column(db.String(255))
    report_json = db.Column(db.JSON, nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )


class Course(db.Model):
    __tablename__ = "courses"

    id = db.Column(db.BigInteger, primary_key=True)
    slug = db.Column(db.String(100), unique=True, nullable=False)
    title = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    level = db.Column(db.String(50))
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )


class CourseLesson(db.Model):
    __tablename__ = "course_lessons"

    id = db.Column(db.BigInteger, primary_key=True)
    course_id = db.Column(
        db.BigInteger,
        db.ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    title = db.Column(db.String(255), nullable=False)
    content_md = db.Column(db.Text)
    sort_order = db.Column(
        db.Integer, nullable=False, server_default=db.text("0")
    )
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )


class CourseQuiz(db.Model):
    __tablename__ = "course_quizzes"

    id = db.Column(db.BigInteger, primary_key=True)
    course_id = db.Column(
        db.BigInteger,
        db.ForeignKey("courses.id", ondelete="CASCADE"),
        nullable=False,
    )
    question_text = db.Column(db.Text, nullable=False)
    correct_answer = db.Column(db.Text)
    wrong_answers = db.Column(db.ARRAY(db.Text))
    sort_order = db.Column(
        db.Integer, nullable=False, server_default=db.text("0")
    )
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )


class Badge(db.Model):
    __tablename__ = "badges"

    id = db.Column(db.BigInteger, primary_key=True)
    code = db.Column(db.String(100), unique=True, nullable=False)
    name = db.Column(db.String(255), nullable=False)
    description = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )


class UserBadge(db.Model):
    __tablename__ = "user_badges"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    badge_id = db.Column(
        db.BigInteger,
        db.ForeignKey("badges.id", ondelete="CASCADE"),
        nullable=False,
    )
    awarded_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "badge_id", name="uq_user_badge"),
    )


class StreakHistory(db.Model):
    __tablename__ = "streak_history"

    id = db.Column(db.BigInteger, primary_key=True)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
    )
    date = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(20), nullable=False)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )

    __table_args__ = (
        db.UniqueConstraint("user_id", "date", name="uq_user_streak_date"),
    )


class Winner(db.Model):
    __tablename__ = "winners"

    id = db.Column(db.BigInteger, primary_key=True)
    winner_date = db.Column(db.Date, nullable=False)
    user_id = db.Column(
        db.BigInteger,
        db.ForeignKey("users.id", ondelete="SET NULL"),
        nullable=True,
    )
    question_text = db.Column(db.Text, nullable=False)
    answer_text = db.Column(db.Text, nullable=False)
    final_score = db.Column(db.Numeric(5, 2))
    feedback_text = db.Column(db.Text)
    created_at = db.Column(
        db.DateTime, nullable=False, server_default=db.func.now()
    )

    __table_args__ = (
        db.UniqueConstraint("winner_date", name="uq_winner_date"),
    )


# ---------------------------------------------------------------------------
# JSON data paths (still used for job library etc.)
# ---------------------------------------------------------------------------

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

QUESTIONS_PATH = os.path.join(BASE_DIR, "data", "questions.json")
JOBS_PATH = os.path.join(BASE_DIR, "data", "jobs.json")
JOB_QUESTIONS_PATH = os.path.join(BASE_DIR, "data", "job_questions.json")
WINNERS_PATH = os.path.join(BASE_DIR, "data", "winners.json")


# ---------------------------------------------------------------------------
# Helpers / auth utilities
# ---------------------------------------------------------------------------


def get_current_user():
    """Return the logged in user object or None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return User.query.get(user_id)


def login_required(view_func):
    """Decorator to protect routes that require authentication."""

    @wraps(view_func)
    def wrapped(*args, **kwargs):
        if not session.get("user_id"):
            next_url = request.path
            return redirect(url_for("login", next=next_url))
        return view_func(*args, **kwargs)

    return wrapped


@app.context_processor
def inject_globals():
    """Make current_user and current_year available in all templates."""
    return {
        "current_user": get_current_user(),
        "current_year": datetime.utcnow().year,
    }


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


def load_winners():
    if not os.path.exists(WINNERS_PATH):
        return []
    with open(WINNERS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_today_daily_question():
    """
    Fetch today's daily question from the daily_questions table
    using active_for_date = today.
    """
    today = date.today()
    return DailyQuestion.query.filter_by(active_for_date=today).first()


def update_streak_for_user(user: User):
    """
    Update the user's streak when they answer today's daily question
    before 20:00 (8 pm). Uses streak_history and users.streak_count/longest_streak.
    """
    if not user:
        return

    now = datetime.now()
    today = now.date()
    cutoff = time(20, 0)  # 8 pm

    if now.time() >= cutoff:
        return

    existing_today = StreakHistory.query.filter_by(
        user_id=user.id, date=today
    ).first()
    if existing_today:
        return

    yesterday = today - timedelta(days=1)
    yesterday_kept = StreakHistory.query.filter_by(
        user_id=user.id, date=yesterday, status="kept"
    ).first()

    if yesterday_kept:
        current = user.streak_count or 0
        user.streak_count = current + 1
    else:
        user.streak_count = 1

    longest = user.longest_streak or 0
    if user.streak_count > longest:
        user.longest_streak = user.streak_count

    today_record = StreakHistory(
        user_id=user.id,
        date=today,
        status="kept",
    )
    db.session.add(today_record)

    try:
        db.session.commit()
    except Exception:
        db.session.rollback()


def get_next_question():
    """
    Return a random question from questions.json, avoiding recent repeats
    within this browser session. (Still used for generic practice/audio.)
    """
    questions = load_questions()
    if not questions:
        return None

    used_ids = session.get("used_question_ids", [])
    available = [q for q in questions if str(q["id"]) not in used_ids]

    if not available:
        used_ids = []
        available = questions

    question = random.choice(available)
    used_ids.append(str(question["id"]))
    session["used_question_ids"] = used_ids

    return question


def save_answer_to_db(
    *,
    source: str,
    question_type: str,
    question_text: str,
    user_answer_text: str,
    eval_result: dict,
    transcript: str = None,
    user_id: int = None,
    job_id: int = None,
    job_question_id: int = None,
    daily_question_id: int = None,
) -> None:
    """
    Best-effort helper to store an evaluated answer in the answers table.
    """
    try:
        scores = eval_result.get("scores") or {}

        relevance = eval_result.get("relevance_score")
        if relevance is None:
            relevance = scores.get("relevance")

        confidence = eval_result.get("confidence_score")
        if confidence is None:
            confidence = scores.get("confidence") or scores.get("clarity")

        final = eval_result.get("final_score")
        if final is None:
            final = scores.get("overall")

        feedback = (
            eval_result.get("feedback")
            or eval_result.get("feedback_text")
            or None
        )

        question_id_val = None
        if job_question_id is not None:
            question_id_val = job_question_id
        elif daily_question_id is not None:
            question_id_val = daily_question_id

        answer = Answer(
            user_id=user_id if user_id is not None else (session.get("user_id") or None),
            question_source=source,
            question_id=question_id_val,
            raw_question_text=question_text,
            answer_text=user_answer_text,
            is_voice=bool(transcript),
            transcript=transcript,
            relevance_score=relevance,
            confidence_score=confidence,
            final_score=final,
            feedback_text=feedback,
        )

        db.session.add(answer)
        db.session.commit()

    except Exception:
        db.session.rollback()


# ---------------------------------------------------------------------------
# Auth routes (register / login / logout)
# ---------------------------------------------------------------------------


@app.route("/register", methods=["GET", "POST"])
def register():
    """
    Simple registration with email, username, password, optional profile image,
    and opt out checkbox.
    """
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()
        username = request.form.get("username", "").strip()
        password = request.form.get("password", "")
        confirm = request.form.get("confirm_password", "")
        profile_image_url = request.form.get("profile_image_url", "").strip() or None
        opt_out_emails = bool(request.form.get("opt_out_emails"))

        error = None

        if not email or not username or not password:
            error = "Please fill in email, username, and password."
        elif password != confirm:
            error = "Passwords do not match."
        else:
            existing_email = User.query.filter_by(email=email).first()
            existing_username = User.query.filter_by(username=username).first()
            if existing_email:
                error = "That email is already registered."
            elif existing_username:
                error = "That username is already taken."

        if error:
            flash(error, "error")
            return render_template("register.html")

        hashed = generate_password_hash(password)
        user = User(
            email=email,
            username=username,
            password_hash=hashed,
            profile_image_url=profile_image_url,
        )
        db.session.add(user)
        db.session.commit()

        try:
            if opt_out_emails:
                db.session.execute(
                    db.text(
                        "UPDATE users SET opt_out_emails = :opt_out WHERE id = :uid"
                    ),
                    {"opt_out": True, "uid": user.id},
                )
                db.session.commit()
        except Exception:
            db.session.rollback()

        session["user_id"] = user.id
        flash("Welcome to NextStep.AI! Your account has been created.", "success")
        return redirect(url_for("index"))

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """
    Login with email OR username plus password.
    """
    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip().lower()
        password = request.form.get("password", "")

        user = (
            User.query.filter(db.func.lower(User.email) == identifier).first()
            or User.query.filter(db.func.lower(User.username) == identifier).first()
        )

        if not user or not check_password_hash(user.password_hash, password):
            flash("Invalid credentials. Please try again.", "error")
            return render_template("login.html")

        session["user_id"] = user.id

        next_url = request.args.get("next") or url_for("index")
        return redirect(next_url)

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log the user out by clearing the session."""
    session.pop("user_id", None)
    flash("You have been logged out.", "success")
    return redirect(url_for("index"))


# ---------------------------------------------------------------------------
# Profile route
# ---------------------------------------------------------------------------


@app.route("/profile")
@login_required
def profile():
    """
    Show profile info plus recent answers and recent prep reports.
    """
    user = get_current_user()

    recent_answers = (
        Answer.query.filter_by(user_id=user.id)
        .order_by(Answer.created_at.desc())
        .limit(20)
        .all()
    )

    recent_reports = (
        PrepReport.query.filter_by(user_id=user.id)
        .order_by(PrepReport.created_at.desc())
        .limit(10)
        .all()
    )

    recent_resume_reports = (
        ResumeReport.query.filter_by(user_id=user.id)
        .order_by(ResumeReport.created_at.desc())
        .limit(10)
        .all()
    )

    return render_template(
        "profile.html",
        user=user,
        answers=recent_answers,
        prep_reports=recent_reports,
        resume_reports=recent_resume_reports,
    )


# ---------------------------------------------------------------------------
# Main practice routes
# ---------------------------------------------------------------------------


@app.route("/", methods=["GET"])
def index():
    """
    Home page showing today's daily question from the database.
    """
    daily_question = get_today_daily_question()
    return render_template("index.html", question=daily_question)


@app.route("/next_question", methods=["POST"])
def next_question():
    """
    Endpoint used by a 'Change question' button for generic practice (if used).
    Returns a new random question from questions.json as JSON.
    """
    question = get_next_question()
    if question is None:
        return jsonify({"error": "No questions available."}), 400

    return jsonify(
        {
            "id": question["id"],
            "question": question["question"],
        }
    )


@app.route("/answer", methods=["POST"])
def answer():
    """
    Receive a text answer for today's daily question, evaluate it with GPT,
    store it in the DB as a 'daily' answer, and update the user's streak.
    """
    user_answer = request.form.get("answer", "").strip()
    question_id = request.form.get("question_id")

    if not user_answer:
        return render_template(
            "result.html",
            result={"error": "No answer received. Please type something."},
        )

    if not question_id:
        return render_template(
            "result.html",
            result={"error": "Missing question ID."},
        )

    daily_q = DailyQuestion.query.get(question_id)
    if daily_q is None:
        return render_template(
            "result.html",
            result={"error": "Daily question not found."},
        )

    eval_result = gpt_evaluate_answer(
        question=daily_q.question_text,
        ideal_answer=daily_q.ideal_answer or "",
        user_answer=user_answer,
    )

    current_user = get_current_user()

    save_answer_to_db(
        source="daily",
        question_type="daily",
        question_text=daily_q.question_text,
        user_answer_text=user_answer,
        eval_result=eval_result,
        user_id=current_user.id if current_user else None,
        daily_question_id=daily_q.id,
    )

    if current_user:
        update_streak_for_user(current_user)

    return render_template("result.html", result=eval_result)


@app.route("/audio", methods=["POST"])
def audio():
    """
    Receive audio, transcribe with Whisper, evaluate with GPT, return JSON.
    Generic practice using questions.json.
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
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(filename)[1]
        ) as tmp:
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
            ideal_answer=current_question.get("ideal_answer", ""),
            user_answer=transcript_text,
        )

        eval_result["transcript"] = transcript_text

        current_user = get_current_user()
        save_answer_to_db(
            source="practice",
            question_type="generic",
            question_text=current_question["question"],
            user_answer_text=transcript_text,
            eval_result=eval_result,
            transcript=transcript_text,
            user_id=current_user.id if current_user else None,
        )

        return jsonify(eval_result), 200

    except Exception as e:
        return jsonify({"error": f"Error processing audio: {str(e)}"}), 500

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Job-specific practice
# ---------------------------------------------------------------------------


@app.route("/job_answer", methods=["POST"])
def job_answer():
    """
    Receive a text answer for a job specific question, evaluate it with GPT,
    and show feedback. Questions are loaded from the database, not JSON.
    """
    user_answer = request.form.get("answer", "").strip()
    job_id = request.form.get("job_id")
    question_id = request.form.get("question_id")

    if not user_answer:
        return render_template(
            "result.html",
            result={"error": "No answer received. Please type something."},
        )

    if not question_id:
        return render_template(
            "result.html",
            result={"error": "Missing question ID."},
        )

    question = JobSpecificQuestion.query.get(question_id)
    if question is None:
        return render_template(
            "result.html",
            result={"error": "Job-specific question not found."},
        )

    eval_result = gpt_evaluate_answer(
        question=question.question_text,
        ideal_answer=question.ideal_answer or "",
        user_answer=user_answer,
    )

    current_user = get_current_user()

    save_answer_to_db(
        source="job",
        question_type="job_specific",
        question_text=question.question_text,
        user_answer_text=user_answer,
        eval_result=eval_result,
        user_id=current_user.id if current_user else None,
        job_id=int(job_id) if job_id else None,
        job_question_id=question.id,
    )

    return render_template("result.html", result=eval_result)


@app.route("/job_audio", methods=["POST"])
def job_audio():
    """
    Receive audio for a job specific question, transcribe and evaluate with GPT,
    return JSON. Uses DB-backed JobSpecificQuestion.
    """
    job_id = request.form.get("job_id")
    question_id = request.form.get("question_id")

    if "audio" not in request.files:
        return jsonify({"error": "No audio file received."}), 400

    audio_file = request.files["audio"]
    if audio_file.filename == "":
        return jsonify({"error": "Empty audio filename."}), 400

    if not question_id:
        return jsonify({"error": "Missing question ID."}), 400

    question = JobSpecificQuestion.query.get(question_id)
    if question is None:
        return jsonify({"error": "Job-specific question not found."}), 400

    filename = secure_filename(audio_file.filename)
    temp_path = None

    try:
        with tempfile.NamedTemporaryFile(
            delete=False, suffix=os.path.splitext(filename)[1]
        ) as tmp:
            temp_path = tmp.name
            audio_file.save(temp_path)

        transcript_text = transcribe_audio_whisper(temp_path)

        eval_result = gpt_evaluate_answer(
            question=question.question_text,
            ideal_answer=question.ideal_answer or "",
            user_answer=transcript_text,
        )

        eval_result["transcript"] = transcript_text

        current_user = get_current_user()
        save_answer_to_db(
            source="job",
            question_type="job_specific",
            question_text=question.question_text,
            user_answer_text=transcript_text,
            eval_result=eval_result,
            transcript=transcript_text,
            user_id=current_user.id if current_user else None,
            job_id=int(job_id) if job_id else None,
            job_question_id=question.id,
        )

        return jsonify(eval_result), 200

    except Exception as e:
        return jsonify({"error": f"Error processing audio: {str(e)}"}), 500

    finally:
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


# ---------------------------------------------------------------------------
# Jobs library
# ---------------------------------------------------------------------------


@app.route("/jobs", methods=["GET"])
def jobs():
    """
    Show a list of jobs from the database so the user can browse role-specific questions.
    """
    jobs_list = Job.query.order_by(Job.title.asc()).all()
    return render_template("jobs.html", jobs=jobs_list)


@app.route("/jobs/<int:job_id>", methods=["GET"])
def job_detail(job_id: int):
    """
    Show questions for a specific job from the database.
    """
    job = Job.query.get(job_id)
    if not job:
        return render_template("job_detail.html", job=None, questions=[])

    db_questions = (
        JobSpecificQuestion.query
        .filter_by(job_id=job.id)
        .order_by(JobSpecificQuestion.id.asc())
        .all()
    )

    questions = [
        {
            "id": q.id,
            "question": q.question_text,
            "ideal_answer": q.ideal_answer,
            "tags": q.tags or [],
        }
        for q in db_questions
    ]

    return render_template("job_detail.html", job=job, questions=questions)


# ---------------------------------------------------------------------------
# Custom prep reports
# ---------------------------------------------------------------------------


@app.route("/custom_prep", methods=["GET", "POST"])
def custom_prep():
    """
    Page where the user enters job title, company, job description, and resume.
    Backend calls GPT to generate a tailored prep report.
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
            else:
                current_user = get_current_user()
                try:
                    prep = PrepReport(
                        user_id=current_user.id if current_user else None,
                        job_title=job_title,
                        company_name=company_name,
                        job_description=job_description,
                        resume_text=resume,
                        report_json=report,
                    )
                    db.session.add(prep)
                    db.session.commit()
                except Exception:
                    db.session.rollback()

    return render_template(
        "custom_prep.html",
        report=report,
        error=error,
    )


@app.route("/custom_prep/report/<int:report_id>", methods=["GET"])
@login_required
def view_saved_prep_report(report_id: int):
    """
    Full-page viewer for a previously generated prep report.
    Used by the profile page cards.
    """
    user = get_current_user()
    if not user:
        return redirect(url_for("login", next=request.path))

    prep_report = PrepReport.query.filter_by(
        id=report_id,
        user_id=user.id,
    ).first()

    if not prep_report:
        abort(404)

    return render_template(
        "saved_prep_report.html",
        prep_report=prep_report,
        report=prep_report.report_json,
    )


# --- PDF download for a saved prep report (ONLY the report area) ---
@app.route("/custom_prep/report/<int:report_id>/pdf", methods=["GET"])
@login_required
def download_saved_prep_report_pdf(report_id: int):
    prep_report = PrepReport.query.get_or_404(report_id)

    # 1) Render the same HTML used on the screen
    html = render_template(
        "saved_prep_report.html",
        prep_report=prep_report,
        report=prep_report.report_json,
        for_pdf=True,   # small hint flag if you want any tiny print tweaks in the template
    )

    # 2) Absolute paths to your CSS on disk
    base_dir = os.path.dirname(os.path.abspath(__file__))
    css_files = [
        os.path.join(base_dir, "static", "css", "base.css"),
        os.path.join(base_dir, "static", "css", "saved_prep_report.css"),
    ]

    # 3) wkhtmltopdf path (adjust if your install path differs)
    import pdfkit
    config = pdfkit.configuration(
        wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    )

    # 4) Options so CSS loads and page looks clean
    options = {
        "enable-local-file-access": None,
        "page-size": "Letter",
        "margin-top": "10mm",
        "margin-right": "10mm",
        "margin-bottom": "12mm",
        "margin-left": "10mm",
        "print-media-type": None,
        "quiet": "",
    }

    pdf_bytes = pdfkit.from_string(
        html, False, css=css_files, options=options, configuration=config
    )

    filename = f"prep_report_{report_id}.pdf"
    return (
        pdf_bytes,
        200,
        {
            "Content-Type": "application/pdf",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


@app.route("/custom_prep/report/<int:report_id>/download", methods=["GET"])
@login_required
def download_saved_prep_report(report_id: int):
    """
    Download the raw JSON of a saved prep report for the current user.
    """
    user = get_current_user()
    if not user:
        return redirect(url_for("login", next=request.path))

    report_row = PrepReport.query.filter_by(
        id=report_id, user_id=user.id
    ).first()

    if not report_row:
        abort(404)

    json_str = json.dumps(report_row.report_json or {}, ensure_ascii=False, indent=2)

    response = make_response(json_str)
    response.headers["Content-Type"] = "application/json"
    response.headers["Content-Disposition"] = (
        f"attachment; filename=prep_report_{report_row.id}.json"
    )
    return response


# ---------------------------------------------------------------------------
# Resume check
# ---------------------------------------------------------------------------


@app.route("/resume_check", methods=["GET", "POST"])
def resume_check():
    """
    Page where the user uploads a resume PDF and optionally a target role.
    Backend calls GPT to generate a structured resume review report.
    """
    report = None
    error = None

    if request.method == "POST":
        target_role = request.form.get("target_role", "").strip() or None
        resume_file = request.files.get("resume_file")

        resume_text = ""

        if not resume_file or resume_file.filename == "":
            error = "Please upload your resume as a PDF."
        else:
            filename = secure_filename(resume_file.filename)
            if not filename.lower().endswith(".pdf"):
                error = "Please upload a PDF file."
            else:
                temp_path = None
                try:
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                        temp_path = tmp.name
                        resume_file.save(temp_path)

                    # Lazy import so app still starts even if PyPDF2 is not installed yet
                    try:
                        from PyPDF2 import PdfReader  # type: ignore

                        reader = PdfReader(temp_path)
                        pages_text = []
                        for page in reader.pages:
                            try:
                                pages_text.append(page.extract_text() or "")
                            except Exception:
                                continue
                        resume_text = "\n".join(pages_text).strip()
                    except Exception as e:
                        # If PDF parsing fails, still attempt report generation with empty text
                        resume_text = ""
                        if not error:
                            error = f"Could not read the PDF text. The AI will still try based on limited information. ({str(e)})"
                finally:
                    if temp_path and os.path.exists(temp_path):
                        try:
                            os.remove(temp_path)
                        except Exception:
                            pass

        if not error:
            report = generate_resume_report(
                resume_text=resume_text,
                target_role=target_role,
                use_gpt=True,
            )

            if report.get("error"):
                error = report["error"]

            current_user = get_current_user()
            try:
                row = ResumeReport(
                    user_id=current_user.id if current_user else None,
                    resume_text=resume_text,
                    target_role=target_role,
                    report_json=report,
                )
                db.session.add(row)
                db.session.commit()
                # pass id so template can show a link if you want later
                report["saved_id"] = row.id
            except Exception:
                db.session.rollback()

    return render_template(
        "resume_check.html",
        report=report,
        error=error,
    )


@app.route("/resume_check/report/<int:report_id>", methods=["GET"])
@login_required
def view_saved_resume_report(report_id: int):
    """
    Full-page viewer for a previously generated resume report.
    Used by the profile page cards.
    """
    user = get_current_user()
    if not user:
        return redirect(url_for("login", next=request.path))

    resume_report = ResumeReport.query.filter_by(
        id=report_id,
        user_id=user.id,
    ).first()

    if not resume_report:
        abort(404)

    return render_template(
        "saved_resume_report.html",
        resume_report=resume_report,
        report=resume_report.report_json,
    )


@app.route("/resume_check/report/<int:report_id>/pdf", methods=["GET"])
@login_required
def download_saved_resume_report_pdf(report_id: int):
    """
    Download a nicely formatted PDF for a saved resume report.
    """
    resume_report = ResumeReport.query.get_or_404(report_id)

    html = render_template(
        "saved_resume_report.html",
        resume_report=resume_report,
        report=resume_report.report_json,
        for_pdf=True,
    )

    base_dir = os.path.dirname(os.path.abspath(__file__))
    css_files = [
        os.path.join(base_dir, "static", "css", "base.css"),
        os.path.join(base_dir, "static", "css", "saved_resume_report.css"),
    ]

    config = pdfkit.configuration(
        wkhtmltopdf=r"C:\Program Files\wkhtmltopdf\bin\wkhtmltopdf.exe"
    )

    options = {
        "enable-local-file-access": None,
        "page-size": "Letter",
        "margin-top": "10mm",
        "margin-right": "10mm",
        "margin-bottom": "12mm",
        "margin-left": "10mm",
        "print-media-type": None,
        "quiet": "",
    }

    pdf_bytes = pdfkit.from_string(
        html, False, css=css_files, options=options, configuration=config
    )

    filename = f"resume_report_{report_id}.pdf"
    return (
        pdf_bytes,
        200,
        {
            "Content-Type": "application/pdf",
            "Content-Disposition": f'attachment; filename="{filename}"',
        },
    )


# ---------------------------------------------------------------------------
# Winners and Courses
# ---------------------------------------------------------------------------


@app.route("/winners", methods=["GET"])
def winners():
    """
    Show the last 20 winning answers for the daily question.
    Still using winners.json for now.
    """
    winners_data = load_winners()

    try:
        winners_data = sorted(
            winners_data,
            key=lambda w: w.get("date", ""),
            reverse=True,
        )
    except Exception:
        pass

    winners_data = winners_data[:20]

    return render_template("winners.html", winners=winners_data)


@app.route("/courses", methods=["GET"])
def courses():
    """
    Display the Courses page (static for now).
    """
    return render_template("courses.html")

@app.route("/mock_interview")
@login_required
def mock_interview():
    return render_template("mock_interview.html")


@app.route("/api/tts_question", methods=["POST"])
@login_required
def tts_question():
    data = request.get_json() or {}
    text = data.get("text", "").strip()

    if not text:
        return jsonify({"error": "No text provided"}), 400

    try:
        # Use OpenAI Text to Speech with streaming response
        with client.audio.speech.with_streaming_response.create(
            model="gpt-4o-mini-tts",  # or "tts-1"
            voice="alloy",
            input=text,
        ) as response:
            audio_buffer = io.BytesIO()
            for chunk in response.iter_bytes():
                audio_buffer.write(chunk)
            audio_buffer.seek(0)

        return send_file(
            audio_buffer,
            mimetype="audio/mpeg",
            as_attachment=False,
            download_name="question.mp3",
        )

    except Exception as e:
        print("TTS error in /api/tts_question:", e)
        return jsonify({"error": "TTS failed"}), 500



# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    # debug=False so Flask does not spawn extra processes that open extra DB connections
    app.run(host="0.0.0.0", port=5000, debug=False)
