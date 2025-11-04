import math
from typing import Dict

import numpy as np

from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModelForSequenceClassification, pipeline

# Global singletons for models so they load only once
_sentence_model = None
_sentiment_pipeline = None


def get_sentence_model():
    """
    Load the sentence transformer model once and reuse.
    Uses a small CPU friendly model.
    """
    global _sentence_model
    if _sentence_model is None:
        # This will download the model the first time and cache it locally
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
    Returns a score between 0 and 100.
    """
    model = get_sentence_model()

    texts = [ideal_answer, user_answer, question]
    embeddings = model.encode(texts, convert_to_numpy=True)

    ideal_vec = embeddings[0]
    user_vec = embeddings[1]
    question_vec = embeddings[2]

    sim_ideal = cosine_similarity(ideal_vec, user_vec)
    sim_question = cosine_similarity(question_vec, user_vec)

    # Combine sims, weight ideal answer more heavily
    combined_sim = 0.7 * sim_ideal + 0.3 * sim_question

    # Map from [-1, 1] to [0, 100]
    relevance_score = (combined_sim + 1.0) / 2.0 * 100.0
    relevance_score = max(0.0, min(100.0, relevance_score))

    return relevance_score


def score_confidence(user_answer: str) -> float:
    """
    Approximate "confidence" or communication quality.
    We combine sentiment (more positive or neutral suggests confidence)
    and answer length (very short answers are usually low confidence).
    Returns a score between 0 and 100.
    """
    sentiment = get_sentiment_pipeline()(user_answer[:512])[0]
    label = sentiment["label"]
    score = float(sentiment["score"])

    # Map sentiment label to numeric base
    if label.upper() == "POSITIVE":
        base = 0.8 + 0.2 * score  # 0.8 to 1.0
    elif label.upper() == "NEUTRAL":
        base = 0.5 + 0.3 * score  # 0.5 to 0.8
    else:
        base = 0.2 + 0.3 * (1 - score)  # 0.2 to 0.5

    # Length factor: encourage at least 40 words
    words = user_answer.split()
    length = len(words)
    length_factor = min(length / 40.0, 1.0)  # 0 to 1

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
        parts.append("Your answer is mostly relevant, but you could align it more closely with what the question is asking.")
    else:
        parts.append("Your answer only partially addresses the question. Try to focus more on what is being asked.")

    if confidence_score > 80:
        parts.append("You sound confident and clear in your explanation.")
    elif confidence_score > 60:
        parts.append("Your communication is okay, but you could be more structured and assertive.")
    else:
        parts.append("Your answer comes across as hesitant or incomplete. Try speaking more clearly and giving concrete examples.")

    if len(user_answer.split()) < 30:
        parts.append("Consider expanding your answer with more detail or examples.")

    return " ".join(parts)


def evaluate_answer(question: str, ideal_answer: str, user_answer: str) -> Dict:
    """
    Main evaluation function used by both text and audio flows.
    Returns a dict with the fields:
        question
        user_answer
        relevance_score
        confidence_score
        final_score
        feedback_text
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


# Whisper transcription support
def transcribe_audio_whisper(audio_path: str) -> str:
    """
    Transcribe an audio file using the open source Whisper model.

    Uses the "base" model which is a good compromise between speed and accuracy
    on CPU. You can change to "small" or "medium" if you have a stronger machine.

    Make sure you have installed:
        pip install openai-whisper
        and that ffmpeg is installed on your system.
    """
    import whisper  # imported here so that text-only runs do not require it

    model = whisper.load_model("base")
    result = model.transcribe(audio_path, language="en")
    text = result.get("text", "").strip()
    return text


# Optional GPT based evaluation for richer feedback
def gpt_evaluate_answer(
    question: str,
    ideal_answer: str,
    user_answer: str,
    model: str = "gpt-4.1-mini",
) -> Dict:
    """
    Use OpenAI GPT to evaluate the answer.

    It returns a dict with the same fields as evaluate_answer, plus
    strengths and improvements from the model.

    This uses a small model (gpt-4.1-mini) and truncates long texts
    to keep token usage and cost low.
    """
    from openai import OpenAI
    import json

    client = OpenAI()

    system_prompt = (
        "You are an interview coach. "
        "Given an interview question, a short description of an ideal answer, "
        "and a candidate's answer, you must carefully judge:\n"
        "- relevance_score: how well the answer addresses the question (0 to 100)\n"
        "- confidence_score: how confident, clear, and structured the answer sounds (0 to 100)\n"
        "Then provide short bullet style strengths and improvements. Please act like a friend, be friendly and make the uder feel confortable with you, and willing to stay in the app to become a master of interviews"
    )

    response = client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {
                "role": "user",
                "content": (
                    "Analyze the following interview answer and return a JSON object with fields: "
                    "relevance_score (0-100), confidence_score (0-100), strengths (list of strings), "
                    "improvements (list of strings).\n\n"
                    f"Question: {question}\n\n"
                    f"Ideal answer description: {ideal_answer[:800]}\n\n"
                    f"Candidate answer: {user_answer[:800]}"
                ),
            },
        ],
        # Ask the API to respond with valid JSON
        response_format={"type": "json_object"},
    )

    content = response.choices[0].message.content
    data = json.loads(content)

    # Extract scores with safe defaults
    rel = float(data.get("relevance_score", 0.0))
    conf = float(data.get("confidence_score", 0.0))
    strengths = data.get("strengths", [])
    improvements = data.get("improvements", [])

    final_score = 0.7 * rel + 0.3 * conf

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
