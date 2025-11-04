import os
import json
import tempfile

from flask import Flask, render_template, request, jsonify
from werkzeug.utils import secure_filename

from utils.evaluation import evaluate_answer, transcribe_audio_whisper, gpt_evaluate_answer

app = Flask(__name__)

# Path to questions file
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
QUESTIONS_PATH = os.path.join(BASE_DIR, "data", "questions.json")


def load_questions():
    """
    Load interview questions from the JSON file.
    Returns a list of question dicts.
    Structure of each item:
    {
        "id": 1,
        "question": "...",
        "ideal_answer": "...",
        "skills": ["..."]
    }
    """
    with open(QUESTIONS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data


@app.route("/", methods=["GET"])
def index():
    """
    Show the interview question and a form to answer.
    Right now we serve the first question.
    You can later change this to pick a random one or by id.
    """
    questions = load_questions()
    current_question = questions[0] if questions else None
    return render_template("index.html", question=current_question)


@app.route("/answer", methods=["POST"])
def answer():
    """
    Receive a text answer from the user.
    Run the evaluation and render the result page.
    """
    user_answer = request.form.get("answer", "").strip()
    question_id = request.form.get("question_id")

    if not user_answer:
        return render_template(
            "result.html",
            result={
                "error": "No answer received. Please type something.",
            },
        )

    questions = load_questions()
    current_question = next(
        (q for q in questions if str(q["id"]) == str(question_id)),
        None,
    )

    if current_question is None:
        return render_template(
            "result.html",
            result={
                "error": "Question not found.",
            },
        )

    eval_result = gpt_evaluate_answer(
        question=current_question["question"],
        ideal_answer=current_question["ideal_answer"],
        user_answer=user_answer,
    )

    return render_template("result.html", result=eval_result)


@app.route("/audio", methods=["POST"])
def audio():
    """
    Receive an audio file from the browser, transcribe it with Whisper,
    then evaluate the transcription.
    Returns JSON so the front end can update the page.
    """
    question_id = request.form.get("question_id")

    if "audio" not in request.files:
        return jsonify({"error": "No audio file received."}), 400

    audio_file = request.files["audio"]

    if audio_file.filename == "":
        return jsonify({"error": "Empty audio filename."}), 400

    filename = secure_filename(audio_file.filename)

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(filename)[1]) as tmp:
            temp_path = tmp.name
            audio_file.save(temp_path)

        # Load question
        questions = load_questions()
        current_question = next(
            (q for q in questions if str(q["id"]) == str(question_id)),
            None,
        )

        if current_question is None:
            return jsonify({"error": "Question not found."}), 400

        # Transcribe audio using Whisper
        transcript_text = transcribe_audio_whisper(temp_path)

        # Evaluate the transcribed answer with GPT
        eval_result = gpt_evaluate_answer(
            question=current_question["question"],
            ideal_answer=current_question["ideal_answer"],
            user_answer=transcript_text,
        )

        # Add transcript to the result so front end can show it
        eval_result["transcript"] = transcript_text

        return jsonify(eval_result), 200

    except Exception as e:
        return jsonify({"error": f"Error processing audio: {str(e)}"}), 500

    finally:
        # Clean up temporary file
        try:
            if os.path.exists(temp_path):
                os.remove(temp_path)
        except Exception:
            pass


if __name__ == "__main__":
    # For local development
    app.run(host="0.0.0.0", port=5000, debug=True)
