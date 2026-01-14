# prep_generator.py
import json
from typing import Any, Dict, List, Optional

from openai import OpenAI


def generate_prep_report(
    job_title: str,
    company_name: Optional[str] = None,
    job_description: Optional[str] = None,
    candidate_name: Optional[str] = None,
    resume_text: Optional[str] = None,
    resume: Optional[str] = None,
    model: str = "gpt-4.1-mini",
    use_gpt: bool = True,
) -> Dict[str, Any]:
    """
    Behavioral:
      - Exactly 6 questions
      - Exactly 6 example answers (one per question)

    Technical:
      - Exactly 6 questions
      - Exactly 6 example answers (one per question)
      - Example answers are normal full sentences, but the legend shows the learning framing.
        The answer should NOT be "🔴Situation: ... 🔵Task: ...", instead it should be written as a coherent paragraph.
        Legend is still included for learning purposes.

    Backward compatibility:
      generate_prep_report(resume="...") or generate_prep_report(resume_text="...").
    """

    # Accept either resume_text or resume keyword
    if resume_text is None:
        resume_text = resume or ""
    else:
        resume_text = resume_text or ""

    job_title = (job_title or "").strip()
    if not job_title:
        return _error_report(
            "Missing required input: job_title",
            candidate_name=candidate_name,
            company_name=company_name,
            job_title=job_title,
        )

    if not use_gpt:
        return _local_fallback_prep_report(
            job_title=job_title,
            company_name=company_name,
            job_description=job_description,
            candidate_name=candidate_name,
        )

    try:
        client = OpenAI()

        mode_hint = "role_and_company" if (company_name and (job_description or "").strip()) else "role_focused"

        system_prompt = """
You are NextStep.AI, an elite AI career strategist and interview coach.

Goal:
Create a premium, structured interview preparation report for a candidate using:
- Resume text
- Job title
- Company name (optional)
- Job description (optional)

You MUST return a single JSON object with this exact shape:

{
  "mode": "role_and_company" or "role_focused",
  "candidate_name": "Optional string, if provided",
  "know_all_about_them": {
    "mission_values": ["...", "..."],
    "culture_snapshot": ["...", "..."],
    "recent_projects_news": ["...", "..."],
    "competitors_industry_trends": ["...", "..."]
  },
  "perfect_fit_map": {
    "top_strengths": ["...", "..."],
    "best_projects": [
      {"title": "...", "summary": "..."}
    ]
  },
  "behavioral_practice": {
    "questions": ["...", "..."],
    "example_answers": [
      {
        "experience_name": "Company or project name that appears in the resume text, or empty string if not available",
        "experience_source_quote": "Short exact phrase from resume proving it exists, or empty string",
        "confidence": "high" or "medium" or "low",
        "question": "...",
        "answer": "...",
        "legend": {"🔴Situation":"...","🔵Task":"...","🟢Action":"...","🟣Result":"..."}
      }
    ]
  },
  "technical_prep": {
    "questions": ["...", "..."],
    "example_answers": [
      {
        "experience_name": "Company or project name that appears in the resume text, or empty string if not available",
        "experience_source_quote": "Short exact phrase from resume proving it exists, or empty string",
        "confidence": "high" or "medium" or "low",
        "question": "...",
        "answer": "...",
        "legend": {"🔴Situation":"...","🔵Task":"...","🟢Action":"...","🟣Result":"..."}
      }
    ],
    "key_concepts": ["...", "..."],
    "red_flags": ["...", "..."]
  },
  "improvement_zone": {
    "skill_gaps": ["...", "..."],
    "soft_skills": ["...", "..."],
    "learning_focus": ["...", "..."]
  },
  "impress_them_back": {
    "team_culture": ["...", "..."],
    "impact_growth": ["...", "..."],
    "technical_depth": ["...", "..."],
    "company_direction": ["...", "..."],
    "next_steps": ["...", "..."]
  }
}

Hard rules:
- Return valid JSON only. No markdown. No extra commentary.
- Talk directly to the candidate.
- Use the job description as the source of truth when provided.
- Never suggest claiming skills the candidate does not have. Suggest honest reframes or learning actions.
- mode should be "role_and_company" when company_name and job_description exist, else "role_focused".
- Do not invent company names. If you cannot tie an answer to a real resume experience, leave experience_name empty,
  leave experience_source_quote empty, and set confidence to "low".

Behavioral requirements:
- Provide EXACTLY 6 behavioral questions.
- Provide EXACTLY 6 behavioral example_answers (one per question, in the same order).
- The answer should be a coherent paragraph (not labeled lines).
- Legend is for learning only and should summarize the S/T/A/R components.

Technical requirements:
- Provide EXACTLY 6 technical questions.
- Provide EXACTLY 6 technical example_answers (one per question, in the same order).
- The answer must be a coherent paragraph in full sentences.
  DO NOT write: "🔴Situation: ... 🔵Task: ..." in the answer text.
  Instead, write like: "To design X, I would ensure Y by doing Z..."
- Legend is for learning only and should summarize the S/T/A/R components, but not be copied verbatim into the answer.

Know their world requirements:
- Provide at least 4 items total across mission_values + culture_snapshot + recent_projects_news + competitors_industry_trends.

Questions to ask requirements:
- Provide at least 10 total questions across impress_them_back categories, spread across categories.

Keep list items short and scannable.
"""

        trimmed_resume = (resume_text or "")[:12000]
        trimmed_jd = (job_description or "")[:12000]

        user_message = (
            "Create an interview preparation report in the required JSON format.\n\n"
            f"Job title: {job_title}\n"
            f"Company name (may be empty): {company_name or ''}\n"
            f"Candidate name (may be empty): {candidate_name or ''}\n"
            f"Mode hint: {mode_hint}\n\n"
            "Job description (may be empty):\n"
            f"{trimmed_jd}\n\n"
            "Resume text:\n"
            f"{trimmed_resume}\n"
        )

        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt.strip()},
                {"role": "user", "content": user_message},
            ],
        )

        content = response.choices[0].message.content or "{}"
        data = json.loads(content)

        normalized = _normalize_prep_report(
            data=data,
            candidate_name=candidate_name,
            fallback_mode=mode_hint,
        )

        normalized = _enforce_exact_qna_counts(normalized)
        return normalized

    except Exception as e:
        fallback = _local_fallback_prep_report(
            job_title=job_title,
            company_name=company_name,
            job_description=job_description,
            candidate_name=candidate_name,
        )
        fallback["debug_note"] = f"GPT generation failed, fallback mode used. Error: {str(e)}"
        fallback = _enforce_exact_qna_counts(fallback)
        return fallback


def _normalize_prep_report(
    data: Dict[str, Any],
    candidate_name: Optional[str],
    fallback_mode: str,
) -> Dict[str, Any]:
    def as_dict(x: Any) -> Dict[str, Any]:
        return x if isinstance(x, dict) else {}

    def as_list(x: Any) -> List[Any]:
        if x is None:
            return []
        if isinstance(x, list):
            return x
        return [x]

    know = as_dict(data.get("know_all_about_them"))
    fit = as_dict(data.get("perfect_fit_map"))
    beh = as_dict(data.get("behavioral_practice"))
    tech = as_dict(data.get("technical_prep"))
    imp = as_dict(data.get("improvement_zone"))
    itm = as_dict(data.get("impress_them_back"))

    # Projects
    best_projects_raw = as_list(fit.get("best_projects"))
    best_projects: List[Dict[str, str]] = []
    for p in best_projects_raw:
        pd = as_dict(p)
        title = str(pd.get("title") or "").strip()
        summary = str(pd.get("summary") or "").strip()
        if title or summary:
            best_projects.append({"title": title or "Project highlight", "summary": summary})

    # Behavioral and Technical examples share same structure
    beh_examples = _normalize_examples_with_legend(as_list(beh.get("example_answers")))
    tech_examples = _normalize_examples_with_legend(as_list(tech.get("example_answers")))

    mode = str(data.get("mode") or fallback_mode).strip() or fallback_mode
    cname = data.get("candidate_name") or candidate_name

    return {
        "mode": mode,
        "candidate_name": cname,
        "know_all_about_them": {
            "mission_values": _coerce_str_list(as_list(know.get("mission_values"))),
            "culture_snapshot": _coerce_str_list(as_list(know.get("culture_snapshot"))),
            "recent_projects_news": _coerce_str_list(as_list(know.get("recent_projects_news"))),
            "competitors_industry_trends": _coerce_str_list(as_list(know.get("competitors_industry_trends"))),
        },
        "perfect_fit_map": {
            "top_strengths": _coerce_str_list(as_list(fit.get("top_strengths"))),
            "best_projects": best_projects,
        },
        "behavioral_practice": {
            "questions": _coerce_str_list(as_list(beh.get("questions"))),
            "example_answers": beh_examples,
        },
        "technical_prep": {
            "questions": _coerce_str_list(as_list(tech.get("questions"))),
            "example_answers": tech_examples,
            "key_concepts": _coerce_str_list(as_list(tech.get("key_concepts"))),
            "red_flags": _coerce_str_list(as_list(tech.get("red_flags"))),
        },
        "improvement_zone": {
            "skill_gaps": _coerce_str_list(as_list(imp.get("skill_gaps"))),
            "soft_skills": _coerce_str_list(as_list(imp.get("soft_skills"))),
            "learning_focus": _coerce_str_list(as_list(imp.get("learning_focus"))),
        },
        "impress_them_back": {
            "team_culture": _coerce_str_list(as_list(itm.get("team_culture"))),
            "impact_growth": _coerce_str_list(as_list(itm.get("impact_growth"))),
            "technical_depth": _coerce_str_list(as_list(itm.get("technical_depth"))),
            "company_direction": _coerce_str_list(as_list(itm.get("company_direction"))),
            "next_steps": _coerce_str_list(as_list(itm.get("next_steps"))),
        },
        "debug_note": str(data.get("debug_note") or "").strip() or None,
    }


def _normalize_examples_with_legend(raw_examples: List[Any]) -> List[Dict[str, Any]]:
    def as_dict(x: Any) -> Dict[str, Any]:
        return x if isinstance(x, dict) else {}

    examples: List[Dict[str, Any]] = []
    for ex in raw_examples:
        exd = as_dict(ex)

        exp_name = str(exd.get("experience_name") or "").strip()
        exp_quote = str(exd.get("experience_source_quote") or "").strip()
        conf = str(exd.get("confidence") or "").strip().lower()
        if conf not in {"high", "medium", "low"}:
            conf = "low"

        q = str(exd.get("question") or "").strip()
        a = str(exd.get("answer") or "").strip()

        legend_in = as_dict(exd.get("legend"))
        legend = {
            "🔴Situation": str(legend_in.get("🔴Situation") or "").strip(),
            "🔵Task": str(legend_in.get("🔵Task") or "").strip(),
            "🟢Action": str(legend_in.get("🟢Action") or "").strip(),
            "🟣Result": str(legend_in.get("🟣Result") or "").strip(),
        }

        if q or a:
            examples.append(
                {
                    "experience_name": exp_name,
                    "experience_source_quote": exp_quote,
                    "confidence": conf,
                    "question": q,
                    "answer": a,
                    "legend": legend,
                }
            )

    return examples


def _coerce_str_list(items: List[Any]) -> List[str]:
    out: List[str] = []
    for x in items:
        if x is None:
            continue
        s = str(x).strip()
        if s:
            out.append(s)
    return out


def _enforce_exact_qna_counts(report: Dict[str, Any]) -> Dict[str, Any]:
    """
    Guarantees:
      - 6 behavioral questions + 6 behavioral answers (1:1, same order)
      - 6 technical questions + 6 technical answers (1:1, same order)
    Also makes sure answers are coherent paragraphs (not "🔴Situation:" etc).
    """
    report.setdefault("behavioral_practice", {})
    report.setdefault("technical_prep", {})

    beh = report["behavioral_practice"]
    tech = report["technical_prep"]

    beh_q = beh.get("questions") or []
    beh_a = beh.get("example_answers") or []
    tech_q = tech.get("questions") or []
    tech_a = tech.get("example_answers") or []

    # Default question banks if missing
    default_beh_q = [
        "Describe a time you took full ownership of a challenging project.",
        "Tell me about a time you dealt with ambiguity.",
        "Describe a time you had to learn a new technology quickly.",
        "Tell me about a time you received critical feedback and how you handled it.",
        "Give an example of a time you collaborated with cross-functional teams.",
        "How have you contributed to improving team processes or code quality?",
    ]

    default_tech_q = [
        "Explain how you would build a scalable backend service for processing healthcare data.",
        "How would you design an API to support high traffic while staying reliable?",
        "How do you approach database schema design and query performance optimization?",
        "How would you add observability (logs, metrics, tracing) to a production service?",
        "How do you ensure code is maintainable and testable as the system grows?",
        "How would you debug a production incident with limited information?",
    ]

    # Force exactly 6 questions
    beh_q = (beh_q + default_beh_q)[:6]
    tech_q = (tech_q + default_tech_q)[:6]

    # Build a map from existing answers by question
    def index_by_question(items: List[Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
        out = {}
        for it in items:
            if isinstance(it, dict):
                qq = str(it.get("question") or "").strip()
                if qq:
                    out[qq] = it
        return out

    beh_map = index_by_question(beh_a)
    tech_map = index_by_question(tech_a)

    # Helper to ensure paragraph style (no "🔴Situation:" tokens)
    def scrub_answer(text: str) -> str:
        if not text:
            return text
        # Remove the common "🔴Situation:" style if the model produced it
        for token in ["🔴Situation:", "🔵Task:", "🟢Action:", "🟣Result:"]:
            text = text.replace(token, "").strip()
        # Collapse extra spaces
        return " ".join(text.split())

    # Create answers exactly aligned to questions
    def make_fallback_answer(q: str, is_tech: bool) -> Dict[str, Any]:
        if is_tech:
            answer = (
                "To handle this, I would start by clarifying requirements and constraints, then design a modular service "
                "with clear API boundaries, efficient data access patterns, and a safe processing pipeline. I would add "
                "validation, batching where appropriate, and caching for hot reads, then layer in observability and tests "
                "to make it reliable under load. Finally, I would roll it out gradually and track metrics like latency, "
                "error rate, throughput, and cost so the system can scale predictably."
            )
            legend = {
                "🔴Situation": "A production service must process growing volumes of sensitive data with strict reliability needs.",
                "🔵Task": "Design for scalability, correctness, and maintainability.",
                "🟢Action": "Use modular APIs, efficient queries, batching/queues where needed, caching, and strong observability/testing.",
                "🟣Result": "A service that scales with predictable performance and measurable reliability.",
            }
        else:
            answer = (
                "In a challenging project, I take ownership by clarifying the goal, breaking the work into milestones, "
                "communicating early with stakeholders, and delivering in small increments with tests. If something is unclear, "
                "I propose a direction, validate it quickly, and adjust based on feedback so progress never stalls. The outcome "
                "is usually faster delivery with fewer surprises and stronger trust from the team."
            )
            legend = {
                "🔴Situation": "A high impact project with constraints like time, complexity, and changing requirements.",
                "🔵Task": "Own the work end to end and keep delivery on track.",
                "🟢Action": "Plan milestones, communicate proactively, ship iteratively with quality checks.",
                "🟣Result": "Delivered outcomes with fewer issues and clearer stakeholder alignment.",
            }

        return {
            "experience_name": "",
            "experience_source_quote": "",
            "confidence": "low",
            "question": q,
            "answer": answer,
            "legend": legend,
        }

    new_beh_answers: List[Dict[str, Any]] = []
    for q in beh_q:
        ex = beh_map.get(q)
        if not ex:
            ex = make_fallback_answer(q, is_tech=False)
        else:
            ex = dict(ex)
            ex["question"] = q
            ex["answer"] = scrub_answer(str(ex.get("answer") or ""))
            ex.setdefault("experience_name", "")
            ex.setdefault("experience_source_quote", "")
            conf = str(ex.get("confidence") or "").lower().strip()
            ex["confidence"] = conf if conf in {"high", "medium", "low"} else "low"
            ex.setdefault("legend", {})
            # Guarantee keys
            ex["legend"] = {
                "🔴Situation": str(ex["legend"].get("🔴Situation") or "").strip(),
                "🔵Task": str(ex["legend"].get("🔵Task") or "").strip(),
                "🟢Action": str(ex["legend"].get("🟢Action") or "").strip(),
                "🟣Result": str(ex["legend"].get("🟣Result") or "").strip(),
            }
        new_beh_answers.append(ex)

    new_tech_answers: List[Dict[str, Any]] = []
    for q in tech_q:
        ex = tech_map.get(q)
        if not ex:
            ex = make_fallback_answer(q, is_tech=True)
        else:
            ex = dict(ex)
            ex["question"] = q
            ex["answer"] = scrub_answer(str(ex.get("answer") or ""))
            ex.setdefault("experience_name", "")
            ex.setdefault("experience_source_quote", "")
            conf = str(ex.get("confidence") or "").lower().strip()
            ex["confidence"] = conf if conf in {"high", "medium", "low"} else "low"
            ex.setdefault("legend", {})
            ex["legend"] = {
                "🔴Situation": str(ex["legend"].get("🔴Situation") or "").strip(),
                "🔵Task": str(ex["legend"].get("🔵Task") or "").strip(),
                "🟢Action": str(ex["legend"].get("🟢Action") or "").strip(),
                "🟣Result": str(ex["legend"].get("🟣Result") or "").strip(),
            }
        new_tech_answers.append(ex)

    beh["questions"] = beh_q
    beh["example_answers"] = new_beh_answers

    tech["questions"] = tech_q
    tech["example_answers"] = new_tech_answers

    report["behavioral_practice"] = beh
    report["technical_prep"] = tech
    return report


def _local_fallback_prep_report(
    job_title: str,
    company_name: Optional[str],
    job_description: Optional[str],
    candidate_name: Optional[str],
) -> Dict[str, Any]:
    mode = "role_and_company" if (company_name and (job_description or "").strip()) else "role_focused"
    return {
        "mode": mode,
        "candidate_name": candidate_name,
        "debug_note": "Offline mode: using a basic template report.",
        "know_all_about_them": {
            "mission_values": ["Mirror the company mission language in your intro and closing."],
            "culture_snapshot": ["Bring one story that shows ownership and one that shows collaboration."],
            "recent_projects_news": ["Reference 1 or 2 recent product updates and explain why they matter."],
            "competitors_industry_trends": ["Know 2 competitors and a clear differentiation for each."],
        },
        "perfect_fit_map": {"top_strengths": ["Ownership", "Full stack delivery"], "best_projects": []},
        "behavioral_practice": {"questions": [], "example_answers": []},
        "technical_prep": {"questions": [], "example_answers": [], "key_concepts": [], "red_flags": []},
        "improvement_zone": {"skill_gaps": [], "soft_skills": [], "learning_focus": []},
        "impress_them_back": {
            "team_culture": [],
            "impact_growth": [],
            "technical_depth": [],
            "company_direction": [],
            "next_steps": [],
        },
    }


def _error_report(
    message: str,
    candidate_name: Optional[str],
    company_name: Optional[str],
    job_title: str,
) -> Dict[str, Any]:
    company_label = company_name or "the company"
    return {
        "mode": "role_focused",
        "candidate_name": candidate_name,
        "debug_note": message,
        "know_all_about_them": {
            "mission_values": [f"Unable to generate company insights for {company_label}."],
            "culture_snapshot": [],
            "recent_projects_news": [],
            "competitors_industry_trends": [],
        },
        "perfect_fit_map": {"top_strengths": [], "best_projects": []},
        "behavioral_practice": {"questions": [], "example_answers": []},
        "technical_prep": {"questions": [], "example_answers": [], "key_concepts": [], "red_flags": []},
        "improvement_zone": {"skill_gaps": [], "soft_skills": [], "learning_focus": []},
        "impress_them_back": {
            "team_culture": [],
            "impact_growth": [],
            "technical_depth": [],
            "company_direction": [],
            "next_steps": [],
        },
    }
