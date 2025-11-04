import json
from typing import Dict, Optional

from openai import OpenAI


def generate_prep_report(
    job_title: str,
    company_name: Optional[str] = None,
    job_description: Optional[str] = None,
    resume: Optional[str] = None,
    model: str = "gpt-4.1-mini",
    use_gpt: bool = True,
) -> Dict:
    """
    Generate a tailored preparation report.

    If use_gpt is True, this calls the OpenAI API.
    If it fails or use_gpt is False, it falls back to a simple local template.

    Returns a dict with fields that the template can render.
    """
    if not use_gpt:
        return _local_fallback_report(job_title, company_name)

    try:
        client = OpenAI()

        system_prompt = (
            "You are NextStep.AI, an expert interview coach. "
            "Given information about a target job (and optionally a company, job description, and resume), "
            "you must create a realistic, tailored interview preparation report. "
            "Always follow these rules:\n"
            "- If only a job title is provided, generate 30 questions (mix of behavioral and technical or role specific), "
            "short guidance for each, plus 5 general tips for that role.\n"
            "- If a company name is also provided, simulate a deep AI search based on typical public information about the company and its industry. "
            "Include a company summary, 15 to 20 tailored questions, a 'How to impress them' section, 5 talking points, and a 'Next Steps to prepare' section.\n"
            "- Write in a confident, friendly, professional tone. Use clear formatting and avoid generic fluff.\n"
            "- If you lack real company information, say: 'Based on public information and typical practices for this industry...' in the summary.\n"
        )

        user_content = {
            "job_title": job_title,
            "company_name": company_name,
            "job_description": (job_description or "")[:2500],
            "resume": (resume or "")[:2500],
        }

        # Ask the model for structured JSON so parsing is easy
        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {
                    "role": "user",
                    "content": (
                        "Create a preparation report for the following candidate.\n\n"
                        "Return a JSON object with at least these fields:\n"
                        "- mode: 'role_only' or 'role_and_company'\n"
                        "- role_questions: list of objects {question, guidance}\n"
                        "- role_tips: list of strings\n"
                        "If company_name is provided, also include:\n"
                        "- company_summary: string\n"
                        "- company_questions: list of objects {question, guidance}\n"
                        "- how_to_impress: list of strings\n"
                        "- talking_points: list of strings\n"
                        "- next_steps: list of strings\n\n"
                        "Candidate info:\n"
                        f"Job title: {job_title}\n"
                        f"Company name: {company_name or ''}\n"
                        f"Job description: {job_description or ''}\n"
                        f"Resume: {resume or ''}\n"
                    ),
                },
            ],
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        # Ensure minimal structure for templates
        report = {
            "job_title": job_title,
            "company_name": company_name,
            "mode": data.get("mode", "role_only"),
            "role_questions": data.get("role_questions", []),
            "role_tips": data.get("role_tips", []),
            "company_summary": data.get("company_summary"),
            "company_questions": data.get("company_questions", []),
            "how_to_impress": data.get("how_to_impress", []),
            "talking_points": data.get("talking_points", []),
            "next_steps": data.get("next_steps", []),
        }
        return report

    except Exception as e:
        # If the API fails (quota, network etc.), fall back to a simple template
        fallback = _local_fallback_report(job_title, company_name)
        fallback["error"] = f"GPT generation failed: {str(e)}"
        return fallback


def _local_fallback_report(job_title: str, company_name: Optional[str]) -> Dict:
    """
    Cheap local fallback if GPT is unavailable.
    This is simple and generic but keeps the feature usable for free.
    """
    base_questions = [
        {
            "question": f"Why are you interested in working as a {job_title}?",
            "guidance": "Connect your past experiences, skills, and long term goals to this type of role.",
        },
        {
            "question": "Tell me about a challenging situation you faced and how you handled it.",
            "guidance": "Use the STAR method: Situation, Task, Action, Result.",
        },
        {
            "question": "What do you consider your biggest strength in this role?",
            "guidance": "Pick a strength that matters for the job and back it up with a concrete example.",
        },
        {
            "question": "What is an area you are currently working to improve?",
            "guidance": "Be honest but show that you have a plan and are already taking action.",
        },
    ]

    role_tips = [
        "Prepare 3 to 4 strong stories using the STAR method.",
        "Research common responsibilities and tools for this role on several job postings.",
        "Practice answering aloud. Focus on speaking clearly and at a steady pace.",
        "Have at least 2 thoughtful questions ready to ask the interviewer.",
        "Review your resume and be ready to discuss any point in detail.",
    ]

    company_summary = None
    if company_name:
        company_summary = (
            f"Based on public information and typical practices for this industry, "
            f"{company_name} is likely to value ownership, strong communication, and alignment with their mission."
        )

    return {
        "job_title": job_title,
        "company_name": company_name,
        "mode": "role_and_company" if company_name else "role_only",
        "role_questions": base_questions,
        "role_tips": role_tips,
        "company_summary": company_summary,
        "company_questions": [],
        "how_to_impress": [],
        "talking_points": [],
        "next_steps": [],
    }
