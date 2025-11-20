import os
import math
import json
from typing import Dict

import numpy as np
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline
from openai import OpenAI

# Global singletons for models and OpenAI client
_sentence_model = None
_sentiment_pipeline = None
client = OpenAI()  # uses OPENAI_API_KEY from your environment

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


def get_sentence_model():
    """
    Load the sentence transformer model once and reuse.
    Uses a small CPU friendly model.
    """
    global _sentence_model
    if _sentence_model is None:
        _sentence_model = SentenceTransformer("sentence-transformers/all-MiniLM-L6-v2")
    return _sentence_model


def get_sentiment_pipeline():
    """
    Load a sentiment analysis pipeline.
    We use a small RoBERTa sentiment model from Hugging Face.
    """
    global _sentiment_pipeline
    if _sentiment_pipeline is None:
        model_name = "cardiffnlp/twitter-roberta-base-sentiment"
        tokenizer = AutoTokenizer.from_pretrained(model_name)
        model = AutoModelForSequenceClassification.from_pretrained(model_name)
        _sentiment_pipeline = pipeline(
            "sentiment-analysis",
            model=model,
            tokenizer=tokenizer,
        )
    return _sentiment_pipeline


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """
    Compute cosine similarity between two 1D numpy arrays.
    Returns a value between -1 and 1.
    """
    dot = float(np.dot(vec1, vec2))
    norm1 = float(np.linalg.norm(vec1))
    norm2 = float(np.linalg.norm(vec2))
    if norm1 == 0.0 or norm2 == 0.0:
        return 0.0
    return dot / (norm1 * norm2)


def score_relevance(question: str, ideal_answer: str, user_answer: str) -> float:
    """
    Use sentence embeddings to measure relevance between the user answer
    and the ideal answer, with a small contribution from the question text itself.
    """
    model = get_sentence_model()

    texts = [ideal_answer, user_answer, question]
    embeddings = model.encode(texts, convert_to_numpy=True)

    ideal_vec = embeddings[0]
    user_vec = embeddings[1]
    question_vec = embeddings[2]

    sim_ideal = cosine_similarity(ideal_vec, user_vec)
    sim_question = cosine_similarity(question_vec, user_vec)

    combined_sim = 0.7 * sim_ideal + 0.3 * sim_question

    relevance_score = (combined_sim + 1.0) / 2.0 * 100.0
    relevance_score = max(0.0, min(100.0, relevance_score))

    return relevance_score


def score_confidence(user_answer: str) -> float:
    """
    Approximate "confidence" or communication quality.
    """
    sentiment = get_sentiment_pipeline()(user_answer[:512])[0]
    label = sentiment["label"]
    score = float(sentiment["score"])

    if label.upper() == "POSITIVE":
        base = 0.8 + 0.2 * score
    elif label.upper() == "NEUTRAL":
        base = 0.5 + 0.3 * score
    else:
        base = 0.2 + 0.3 * (1 - score)

    words = user_answer.split()
    length = len(words)
    length_factor = min(length / 40.0, 1.0)

    confidence_score = base * 0.6 + length_factor * 0.4
    confidence_score = confidence_score * 100.0
    confidence_score = max(0.0, min(100.0, confidence_score))

    return confidence_score


def build_feedback_text(
    question: str,
    user_answer: str,
    relevance_score: float,
    confidence_score: float,
) -> str:
    """
    Build a simple textual feedback string based on the scores.
    """
    parts = []

    if relevance_score > 80:
        parts.append("Your answer is highly relevant to the question.")
    elif relevance_score > 60:
        parts.append(
            "Your answer is mostly relevant, but you could align it more closely with what the question is asking."
        )
    else:
        parts.append(
            "Your answer only partially addresses the question. Try to focus more on what is being asked."
        )

    if confidence_score > 80:
        parts.append("You sound confident and clear in your explanation.")
    elif confidence_score > 60:
        parts.append(
            "Your communication is okay, but you could be more structured and assertive."
        )
    else:
        parts.append(
            "Your answer comes across as hesitant or incomplete. Try speaking more clearly and giving concrete examples."
        )

    if len(user_answer.split()) < 30:
        parts.append("Consider expanding your answer with more detail or examples.")

    return " ".join(parts)


def evaluate_answer(question: str, ideal_answer: str, user_answer: str) -> Dict:
    """
    Classical local evaluation function (no GPT).
    """
    relevance_score = score_relevance(question, ideal_answer, user_answer)
    confidence_score = score_confidence(user_answer)

    final_score = 0.6 * relevance_score + 0.4 * confidence_score

    feedback_text = build_feedback_text(
        question=question,
        user_answer=user_answer,
        relevance_score=relevance_score,
        confidence_score=confidence_score,
    )

    return {
        "question": question,
        "user_answer": user_answer,
        "relevance_score": round(relevance_score, 2),
        "confidence_score": round(confidence_score, 2),
        "final_score": round(final_score, 2),
        "feedback_text": feedback_text,
    }


def transcribe_audio_whisper(file_path: str) -> str:
    """
    Transcribe an audio file using OpenAI's transcription API.

    file_path - absolute or relative path to an audio file on disk.
    Returns the raw transcript text.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"Audio file does not exist: {file_path}")

    with open(file_path, "rb") as f:
        # gpt-4o-mini-transcribe or whisper-1 both work
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
    Use OpenAI GPT to evaluate the answer.
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
