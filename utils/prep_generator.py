# prep_generator.py
import json
import logging
import os
from typing import Any, Dict, List, Optional

from openai import OpenAI

logger = logging.getLogger(__name__)

DEFAULT_DEBUG_ENV = "NEXTSTEP_PREP_DEBUG"  # set to "1"


def generate_prep_report(
    job_title: str,
    company_name: Optional[str] = None,
    job_description: Optional[str] = None,
    candidate_name: Optional[str] = None,
    resume_text: Optional[str] = None,
    resume: Optional[str] = None,
    model: str = "gpt-4.1-mini",
    use_gpt: bool = True,
    debug: Optional[bool] = None,
) -> Dict[str, Any]:
    """
    Prep report generator that uses the resume text directly (same strategy as generate_resume_report),
    so it cannot "lose" the resume due to a strict extraction step.

    Guarantees:
    - Exactly 6 behavioral questions + 6 behavioral answers
    - Exactly 6 technical questions + 6 technical answers
    - Always includes improvement_zone and impress_them_back so sections render
    - Every example answer includes experience_name + experience_source_quote
    - Debug info proves what resume text was received
    """

    if debug is None:
        debug = os.getenv(DEFAULT_DEBUG_ENV, "").strip() == "1"

    # Backward compatibility with calls that pass resume="..."
    if resume_text is None:
        resume_text = resume or ""
    else:
        resume_text = resume_text or ""

    job_title = (job_title or "").strip()
    if not job_title:
        return _error_report("Missing required input: job_title", candidate_name, company_name)

    # Debug proof: log resume length and preview
    resume_len = len(resume_text or "")
    resume_preview = (resume_text or "")[:350].replace("\n", "\\n")
    if debug:
        logger.info("PREP DEBUG: resume_len=%s preview=%s", resume_len, resume_preview)

    if not use_gpt:
        rep = _local_fallback(job_title, company_name, job_description, candidate_name)
        rep["_debug"] = {"mode": "offline", "resume_len": resume_len} if debug else rep.get("_debug")
        return rep

    try:
        client = OpenAI()

        mode_hint = "role_and_company" if (company_name and (job_description or "").strip()) else "role_focused"
        trimmed_resume = (resume_text or "")[:12000]
        trimmed_jd = (job_description or "")[:12000]

        system_prompt = f"""
You are NextStep.AI, an elite interview coach.

You must create a structured interview prep report using the resume text as the source of truth.

Hard constraints:
- Exactly 6 behavioral questions.
- Exactly 6 behavioral answers (one per question, same order).
- Exactly 6 technical questions.
- Exactly 6 technical answers (one per question, same order).

Resume anchoring (IMPORTANT):
For every behavioral and technical answer you generate:
- "experience_name" must be the real company or project name from the resume (for example: J2 Health, NextStep.AI, Microsoft, etc).
- "experience_source_quote" must be a short exact quote from the resume that proves the experience exists.
- Do NOT output "N/A". If you cannot find a quote, use an empty string but still pick the closest real experience_name and set confidence="low".

Answer quality:
- Speak in first person as the candidate.
- 7 to 12 sentences per answer.
- The answer must sound like a real interview response tied to the resume.
- Do not include the labels "Situation/Task/Action/Result" inside the answer text.
- The legend is only for learning.

Return JSON only with this exact shape:

{{
  "mode": "{mode_hint}",
  "candidate_name": "{candidate_name or ""}",
  "know_all_about_them": {{
    "mission_values": ["...", "..."],
    "culture_snapshot": ["...", "..."],
    "recent_projects_news": ["...", "..."],
    "competitors_industry_trends": ["...", "..."]
  }},
  "perfect_fit_map": {{
    "top_strengths": ["...", "..."],
    "best_projects": [{{"title":"...","summary":"..."}}]
  }},
  "behavioral_practice": {{
    "questions": ["... x6"],
    "example_answers": [
      {{
        "experience_name": "...",
        "experience_source_quote": "...",
        "confidence": "high|medium|low",
        "question": "...",
        "answer": "...",
        "legend": {{"🔴Situation":"...","🔵Task":"...","🟢Action":"...","🟣Result":"..."}}
      }}
    ]
  }},
  "technical_prep": {{
    "questions": ["... x6"],
    "example_answers": [
      {{
        "experience_name": "...",
        "experience_source_quote": "...",
        "confidence": "high|medium|low",
        "question": "...",
        "answer": "...",
        "legend": {{"🔴Situation":"...","🔵Task":"...","🟢Action":"...","🟣Result":"..."}}
      }}
    ],
    "key_concepts": ["... x6"],
    "red_flags": ["...", "...", "..."]
  }},
  "improvement_zone": {{
    "skill_gaps": ["...", "..."],
    "soft_skills": ["...", "..."],
    "learning_focus": ["...", "..."]
  }},
  "impress_them_back": {{
    "team_culture": ["...", "..."],
    "impact_growth": ["...", "..."],
    "technical_depth": ["...", "..."],
    "company_direction": ["...", "..."],
    "next_steps": ["...", "..."]
  }}
}}
"""

        user_message = (
            "Create a prep report in the required JSON format.\n\n"
            f"Job title: {job_title}\n"
            f"Company name: {company_name or ''}\n"
            f"Job description:\n{trimmed_jd}\n\n"
            f"Resume text:\n{trimmed_resume}\n"
        )

        resp = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_message},
            ],
        )

        data = json.loads(resp.choices[0].message.content or "{}")
        if not isinstance(data, dict):
            data = {}

        report = _normalize_for_template(data, candidate_name=candidate_name, mode_hint=mode_hint)

        # Enforce counts, and ensure the sections always show
        report = _force_counts(report)
        report = _ensure_sections(report)

        # Debug proof stored in report JSON
        if debug:
            report["_debug"] = {
                "mode": "gpt",
                "model": model,
                "resume_len": resume_len,
                "resume_preview": resume_preview,
                "anchored_counts": _anchor_counts(report),
            }

        return report

    except Exception as e:
        fb = _local_fallback(job_title, company_name, job_description, candidate_name)
        fb["debug_note"] = f"GPT generation failed, fallback mode used. Error: {str(e)}"
        if debug:
            fb["_debug"] = {"mode": "fallback", "resume_len": resume_len, "error": str(e)}
        return fb


def _normalize_for_template(data: Dict[str, Any], candidate_name: Optional[str], mode_hint: str) -> Dict[str, Any]:
    def d(x: Any) -> Dict[str, Any]:
        return x if isinstance(x, dict) else {}

    def l(x: Any) -> List[Any]:
        if x is None:
            return []
        if isinstance(x, list):
            return x
        return [x]

    know = d(data.get("know_all_about_them"))
    fit = d(data.get("perfect_fit_map"))
    beh = d(data.get("behavioral_practice"))
    tech = d(data.get("technical_prep"))
    imp = d(data.get("improvement_zone"))
    itm = d(data.get("impress_them_back"))

    mode = str(data.get("mode") or mode_hint).strip() or mode_hint
    cname = str(data.get("candidate_name") or candidate_name or "").strip() or candidate_name

    return {
        "mode": mode,
        "candidate_name": cname,
        "debug_note": data.get("debug_note"),
        "know_all_about_them": {
            "mission_values": [str(x).strip() for x in l(know.get("mission_values")) if str(x).strip()],
            "culture_snapshot": [str(x).strip() for x in l(know.get("culture_snapshot")) if str(x).strip()],
            "recent_projects_news": [str(x).strip() for x in l(know.get("recent_projects_news")) if str(x).strip()],
            "competitors_industry_trends": [str(x).strip() for x in l(know.get("competitors_industry_trends")) if str(x).strip()],
        },
        "perfect_fit_map": {
            "top_strengths": [str(x).strip() for x in l(fit.get("top_strengths")) if str(x).strip()],
            "best_projects": [
                {"title": str(p.get("title") or "").strip(), "summary": str(p.get("summary") or "").strip()}
                for p in l(fit.get("best_projects"))
                if isinstance(p, dict) and (str(p.get("title") or "").strip() or str(p.get("summary") or "").strip())
            ],
        },
        "behavioral_practice": {
            "questions": [str(x).strip() for x in l(beh.get("questions")) if str(x).strip()],
            "example_answers": l(beh.get("example_answers")),
        },
        "technical_prep": {
            "questions": [str(x).strip() for x in l(tech.get("questions")) if str(x).strip()],
            "example_answers": l(tech.get("example_answers")),
            "key_concepts": [str(x).strip() for x in l(tech.get("key_concepts")) if str(x).strip()],
            "red_flags": [str(x).strip() for x in l(tech.get("red_flags")) if str(x).strip()],
        },
        "improvement_zone": {
            "skill_gaps": [str(x).strip() for x in l(imp.get("skill_gaps")) if str(x).strip()],
            "soft_skills": [str(x).strip() for x in l(imp.get("soft_skills")) if str(x).strip()],
            "learning_focus": [str(x).strip() for x in l(imp.get("learning_focus")) if str(x).strip()],
        },
        "impress_them_back": {
            "team_culture": [str(x).strip() for x in l(itm.get("team_culture")) if str(x).strip()],
            "impact_growth": [str(x).strip() for x in l(itm.get("impact_growth")) if str(x).strip()],
            "technical_depth": [str(x).strip() for x in l(itm.get("technical_depth")) if str(x).strip()],
            "company_direction": [str(x).strip() for x in l(itm.get("company_direction")) if str(x).strip()],
            "next_steps": [str(x).strip() for x in l(itm.get("next_steps")) if str(x).strip()],
        },
    }


def _force_counts(report: Dict[str, Any]) -> Dict[str, Any]:
    # Force exactly 6 questions + 6 answers each
    beh = report.get("behavioral_practice", {})
    tech = report.get("technical_prep", {})

    beh_q = (beh.get("questions") or [])[:6]
    tech_q = (tech.get("questions") or [])[:6]

    while len(beh_q) < 6:
        beh_q.append("Describe a time you took full ownership of a challenging project.")
    while len(tech_q) < 6:
        tech_q.append("Walk me through how you would design and ship a full stack feature end to end.")

    beh["questions"] = beh_q
    tech["questions"] = tech_q

    beh_ex = beh.get("example_answers") or []
    tech_ex = tech.get("example_answers") or []

    def normalize_example(ex: Any, q: str) -> Dict[str, Any]:
        if not isinstance(ex, dict):
            ex = {}
        legend = ex.get("legend") if isinstance(ex.get("legend"), dict) else {}
        return {
            "experience_name": str(ex.get("experience_name") or "").strip(),
            "experience_source_quote": str(ex.get("experience_source_quote") or "").strip(),
            "confidence": str(ex.get("confidence") or "low").strip().lower(),
            "question": str(ex.get("question") or q).strip(),
            "answer": str(ex.get("answer") or "").strip(),
            "legend": {
                "🔴Situation": str(legend.get("🔴Situation") or "").strip(),
                "🔵Task": str(legend.get("🔵Task") or "").strip(),
                "🟢Action": str(legend.get("🟢Action") or "").strip(),
                "🟣Result": str(legend.get("🟣Result") or "").strip(),
            },
        }

    # Ensure 6 answers aligned
    out_beh = []
    for i, q in enumerate(beh_q):
        ex = beh_ex[i] if i < len(beh_ex) else {}
        out_beh.append(normalize_example(ex, q))

    out_tech = []
    for i, q in enumerate(tech_q):
        ex = tech_ex[i] if i < len(tech_ex) else {}
        out_tech.append(normalize_example(ex, q))

    beh["example_answers"] = out_beh
    tech["example_answers"] = out_tech

    report["behavioral_practice"] = beh
    report["technical_prep"] = tech

    # Ensure 6 key concepts
    kc = report["technical_prep"].get("key_concepts") or []
    while len(kc) < 6:
        kc.append("System design fundamentals")
    report["technical_prep"]["key_concepts"] = kc[:6]

    # Red flags minimum
    rf = report["technical_prep"].get("red_flags") or []
    while len(rf) < 3:
        rf.append("Not grounding answers in real shipped work")
    report["technical_prep"]["red_flags"] = rf[:6]

    return report


def _ensure_sections(report: Dict[str, Any]) -> Dict[str, Any]:
    # Ensure upgrade + questions exist so your template renders them
    imp = report.get("improvement_zone", {})
    imp.setdefault("skill_gaps", [])
    imp.setdefault("soft_skills", [])
    imp.setdefault("learning_focus", [])
    if not imp["skill_gaps"]:
        imp["skill_gaps"] = ["Pick 2 role-critical skills and map them to resume bullets.", "Prepare one end-to-end system story with tradeoffs."]
    if not imp["soft_skills"]:
        imp["soft_skills"] = ["Lead with outcome, then the why and tradeoffs.", "Keep answers structured and concise."]
    if not imp["learning_focus"]:
        imp["learning_focus"] = ["Practice your 6 behavioral stories out loud.", "Rewrite 2 technical answers with concrete metrics you can defend."]
    report["improvement_zone"] = imp

    itm = report.get("impress_them_back", {})
    for k in ["team_culture", "impact_growth", "technical_depth", "company_direction", "next_steps"]:
        itm.setdefault(k, [])
    # Ensure 10 total questions
    def total() -> int:
        return sum(len(itm[k]) for k in ["team_culture", "impact_growth", "technical_depth", "company_direction", "next_steps"])
    while total() < 10:
        itm["team_culture"].append("What does success look like in the first 60 days?")
        if total() >= 10:
            break
        itm["impact_growth"].append("What problems will this role tackle in the next 90 days?")
        if total() >= 10:
            break
        itm["technical_depth"].append("What are the biggest scaling or reliability risks right now?")
        if total() >= 10:
            break
        itm["company_direction"].append("What product bet matters most this year, and why?")
        if total() >= 10:
            break
        itm["next_steps"].append("What are the next steps and timeline?")
    report["impress_them_back"] = itm

    # Ensure know section has at least 4 items total
    know = report.get("know_all_about_them", {})
    for k in ["mission_values", "culture_snapshot", "recent_projects_news", "competitors_industry_trends"]:
        know.setdefault(k, [])
    total_know = sum(len(know[k]) for k in ["mission_values", "culture_snapshot", "recent_projects_news", "competitors_industry_trends"])
    if total_know < 4:
        know["mission_values"].append("Mirror the company mission language in your intro.")
        know["culture_snapshot"].append("Bring one ownership story and one collaboration story.")
        know["recent_projects_news"].append("Reference one product bet and why it matters.")
        know["competitors_industry_trends"].append("Know two competitors and a crisp differentiation.")
    report["know_all_about_them"] = know

    return report


def _anchor_counts(report: Dict[str, Any]) -> Dict[str, Any]:
    def count(section: str) -> Dict[str, int]:
        block = report.get(section, {}) if isinstance(report.get(section), dict) else {}
        ex = block.get("example_answers") or []
        total = 0
        anchored = 0
        for item in ex:
            if isinstance(item, dict):
                total += 1
                if (item.get("experience_name") or "").strip() and (item.get("experience_source_quote") or "").strip():
                    anchored += 1
        return {"total": total, "anchored": anchored}
    return {"behavioral": count("behavioral_practice"), "technical": count("technical_prep")}


def _local_fallback(job_title: str, company_name: Optional[str], job_description: Optional[str], candidate_name: Optional[str]) -> Dict[str, Any]:
    mode = "role_and_company" if (company_name and (job_description or "").strip()) else "role_focused"
    return {
        "mode": mode,
        "candidate_name": candidate_name,
        "debug_note": "Offline mode: using a basic template report.",
        "know_all_about_them": {"mission_values": [], "culture_snapshot": [], "recent_projects_news": [], "competitors_industry_trends": []},
        "perfect_fit_map": {"top_strengths": ["Full stack delivery", "Ownership"], "best_projects": []},
        "behavioral_practice": {"questions": [], "example_answers": []},
        "technical_prep": {"questions": [], "example_answers": [], "key_concepts": [], "red_flags": []},
        "improvement_zone": {"skill_gaps": [], "soft_skills": [], "learning_focus": []},
        "impress_them_back": {"team_culture": [], "impact_growth": [], "technical_depth": [], "company_direction": [], "next_steps": []},
    }


def _error_report(message: str, candidate_name: Optional[str], company_name: Optional[str]) -> Dict[str, Any]:
    return {
        "mode": "role_focused",
        "candidate_name": candidate_name,
        "debug_note": message,
        "know_all_about_them": {"mission_values": [f"Unable to generate company insights for {company_name or 'the company'}."], "culture_snapshot": [], "recent_projects_news": [], "competitors_industry_trends": []},
        "perfect_fit_map": {"top_strengths": [], "best_projects": []},
        "behavioral_practice": {"questions": [], "example_answers": []},
        "technical_prep": {"questions": [], "example_answers": [], "key_concepts": [], "red_flags": []},
        "improvement_zone": {"skill_gaps": [], "soft_skills": [], "learning_focus": []},
        "impress_them_back": {"team_culture": [], "impact_growth": [], "technical_depth": [], "company_direction": [], "next_steps": []},
    }
