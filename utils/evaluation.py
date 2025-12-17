import os
import json
from typing import Dict

from openai import OpenAI

# Single OpenAI client (uses OPENAI_API_KEY from env)
client = OpenAI()

# System prompt for GPT based evaluation
SYSTEM_PROMPT = """
You are a very strict interview coach.

Your job is to evaluate a candidate's answer to a behavioral interview question
and help them improve it to hiring-level quality.

You MUST:
- Use the STAR framework as the gold standard (Situation, Task, Action, Result).
- Be conservative with scores. A typical decent answer should be in the 55–70 range.
- Only give scores above 80 for truly excellent answers.

Scoring rules (0–100):

Relevance:
- 90–100: Perfect STAR, fully answers the question.
- 75–89: Mostly strong, minor gaps.
- 50–74: Partial answer, missing STAR elements.
- 0–49: Off-topic or ineffective.

Confidence:
- 90–100: Clear, structured, confident, professional.
- 75–89: Mostly clear but some hesitation or weakness.
- 50–74: Rambling, vague, or poorly structured.
- 0–49: Very unclear.

Final score:
- Rough average of relevance and confidence
- Penalize heavily if no clear Result or impact.

You must ALSO help the candidate improve.

Return a JSON object with EXACTLY these fields:

{
  "relevance_score": number,
  "confidence_score": number,
  "final_score": number,
  "strengths": [ "short bullet", ... ],
  "improvements": [ "short bullet", ... ],
  "rewritten_answer": {
    "star": "Improved STAR-based rewrite of the answer",
    "concise": "Short, high-impact version suitable for a real interview"
  }
}
"""


def transcribe_audio_whisper(file_path: str) -> str:
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file does not exist: {file_path}")

    with open(file_path, "rb") as f:
        resp = client.audio.transcriptions.create(
            model="gpt-4o-mini-transcribe",
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
    Evaluate an interview answer and generate improvements + rewrites.
    """

    user_prompt = f"""
Analyze the interview answer below.

1. Score it strictly using the STAR framework.
2. List up to 3 strengths.
3. List up to 3 concrete improvements.
4. Rewrite the answer in TWO ways:
   - A strong STAR-based version (preserve the candidate's experience).
   - A concise, high-impact version suitable for a real interview.

Question:
{question}

Ideal answer description (if any):
{ideal_answer[:800]}

Candidate answer:
{user_answer[:1200]}
"""

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.4,
    )

    data = json.loads(response.choices[0].message.content)

    rel = float(data.get("relevance_score", 0))
    conf = float(data.get("confidence_score", 0))
    final_score = float(data.get("final_score", 0))

    strengths = data.get("strengths", [])[:3]
    improvements = data.get("improvements", [])[:3]

    rewritten = data.get("rewritten_answer", {}) or {}
    star_rewrite = rewritten.get("star", "").strip()
    concise_rewrite = rewritten.get("concise", "").strip()

    return {
        "question": question,
        "user_answer": user_answer,
        "relevance_score": round(rel, 2),
        "confidence_score": round(conf, 2),
        "final_score": round(final_score, 2),
        "strengths": strengths,
        "improvements": improvements,
        "rewritten_answer": {
            "star": star_rewrite,
            "concise": concise_rewrite,
        },
    }


def evaluate_answer(question: str, ideal_answer: str, user_answer: str) -> Dict:
    """
    Backwards-compatible wrapper.
    """
    return gpt_evaluate_answer(
        question=question,
        ideal_answer=ideal_answer,
        user_answer=user_answer,
    )
