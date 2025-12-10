import os
import json
from typing import Dict

from openai import OpenAI

# Single OpenAI client (uses OPENAI_API_KEY from env)
client = OpenAI()

# System prompt for GPT based evaluation
SYSTEM_PROMPT = """
You are a very strict interview coach.
Your job is to evaluate a candidate's answer to a behavioral interview question.

You MUST:
- Use the STAR framework as the gold standard (Situation, Task, Action, Result).
- Be conservative with scores. A typical decent answer should be in the 55-70 range.
- Only give scores above 80 for truly excellent answers that are structured, concise,
  specific, and clearly demonstrate impact.

Scoring rules (0-100):

Relevance:
- 90-100: Directly answers the question, stays tightly on topic, clear STAR structure. Only give a grade here when the answer seems perfect to you, make it so difficult to get these grades.
- 75-89: Mostly on topic but missing some elements or mild wandering.
- 50-74: Partially answers, missing important parts of the question or STAR.
- 0-49: Largely off topic or fails to answer.

Confidence (communication and delivery quality):
- 90-100: Very clear, confident, structured, minimal filler, strong ownership. Only give a grade here when the answer seems perfect to you, make it so difficult to get these grades.
- 75-89: Clear overall but something is missing, maybe there are filler, hesitations, or weak structure.
- 50-74: Understandable but rambling, vague, or weak structure.
- 0-49: Very unclear, disorganized, or very low ownership.

Final score:
- Roughly an average of relevance and confidence, but penalize heavily if:
  - There is no clear Result.
  - There are no specific actions or impact.
  - The answer is very generic.

Be especially tough on:
- Missing STAR elements (no Result, no Actions, no context).
- Very generic phrasing with no concrete details.
- Casual or unprofessional language in a professional context.

Return a JSON object with exactly these fields:
{
  "relevance_score": <number 0-100>,
  "confidence_score": <number 0-100>,
  "final_score": <number 0-100>,
  "strengths": [ "<short bullet>", ... ],
  "improvements": [ "<short bullet>", ... ]
}
"""


def transcribe_audio_whisper(file_path: str) -> str:
    """
    Transcribe an audio file using OpenAI's transcription API.

    file_path - absolute or relative path to an audio file on disk.
    Returns the raw transcript text.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file does not exist: {file_path}")

    with open(file_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",  # or "whisper-1"
            file=f,
        )

    return resp.text


def gpt_evaluate_answer(
    question: str,
    ideal_answer: str,
    user_answer: str,
    model: str = "gpt-4.1-mini",
) -> Dict:
    """
    Use OpenAI GPT to evaluate the answer.
    Returns a dict with:
      - question
      - user_answer
      - relevance_score
      - confidence_score
      - final_score
      - feedback_text
      - strengths
      - improvements
    """
    user_prompt = (
        "Analyze the following interview answer and return a JSON object with fields: "
        "relevance_score (0-100), confidence_score (0-100), final_score (0-100), "
        "strengths (list of strings), improvements (list of strings).\n\n"
        f"Question: {question}\n\n"
        f"Ideal answer description: {ideal_answer[:800]}\n\n"
        f"Candidate answer: {user_answer[:800]}"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    data = json.loads(content)

    rel = float(data.get("relevance_score", 0.0))
    conf = float(data.get("confidence_score", 0.0))

    gpt_final = data.get("final_score")
    if gpt_final is not None:
        final_score = float(gpt_final)
    else:
        final_score = 0.7 * rel + 0.3 * conf

    strengths = data.get("strengths", [])
    improvements = data.get("improvements", [])

    strengths_text = ""
    if strengths:
        strengths_text = "Strengths: " + "; ".join(strengths)

    improvements_text = ""
    if improvements:
        improvements_text = "Improvements: " + "; ".join(improvements)

    feedback_parts = [part for part in [strengths_text, improvements_text] if part]
    feedback_text = " ".join(feedback_parts)

    return {
        "question": question,
        "user_answer": user_answer,
        "relevance_score": round(rel, 2),
        "confidence_score": round(conf, 2),
        "final_score": round(final_score, 2),
        "feedback_text": feedback_text,
        "strengths": strengths,
        "improvements": improvements,
    }


def evaluate_answer(question: str, ideal_answer: str, user_answer: str) -> Dict:
    """
    Backwards compatible wrapper that calls gpt_evaluate_answer.

    app.py imports this name, even if it does not call it right now.
    Keeping it avoids import errors without needing extra dependencies.
    """
    return gpt_evaluate_answer(
        question=question,
        ideal_answer=ideal_answer,
        user_answer=user_answer,
    )
