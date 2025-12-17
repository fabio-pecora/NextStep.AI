import json
from typing import Dict, Optional

from openai import OpenAI


def generate_resume_report(
    resume_text: str,
    target_role: Optional[str] = None,
    job_description: Optional[str] = None,
    model: str = "gpt-4.1-mini",
    use_gpt: bool = True,
) -> Dict:
    """
    Generate a structured resume review report.

    If job_description is provided, the report must align to the JD:
      - extract ATS style keywords and skills
      - compare JD vs resume
      - propose missing keywords and concrete ways to add them

    Returns a dict with the structure expected by the resume_check template.
    """
    if not use_gpt:
        report = _local_fallback_resume_report(resume_text, target_role, job_description)
        return report

    try:
        client = OpenAI()

        system_prompt = """
You are NextStep.AI, an elite AI resume coach and ATS optimization expert.

Your job:
1) Read the resume text.
2) If a job description is provided, treat it as the source of truth for alignment:
   - infer what the company is screening for
   - extract keywords, tools, responsibilities, and must-have skills
   - compare them against the resume text
   - propose missing keywords and the safest, most honest ways to add them (no lying)
3) Produce premium, specific, actionable feedback.

You MUST return a single JSON object with this exact shape:

{
  "summary": "High level review of how strong this resume is for the target role.",
  "sections": {
    "overall_structure": {
      "strengths": ["...", "..."],
      "issues": ["...", "..."],
      "recommendations": ["...", "..."]
    },
    "experience": {
      "strengths": ["...", "..."],
      "issues": ["...", "..."],
      "recommendations": ["...", "..."]
    },
    "education": {
      "strengths": ["...", "..."],
      "issues": ["...", "..."],
      "recommendations": ["...", "..."]
    },
    "skills": {
      "strengths": ["...", "..."],
      "issues": ["...", "..."],
      "recommendations": ["...", "..."]
    }
  },
  "experience_bullets": {
    "rewrites": [
      {
        "original": "Original bullet from the resume",
        "improved": "Stronger, impact focused version",
        "why_it_is_better": "Short explanation of the changes"
      }
    ],
    "title_suggestions": [
      {
        "original_title": "Old job title",
        "suggested_title": "Better aligned job title",
        "reason": "Why this is a better wording"
      }
    ],
    "missing_information": [
      "Concrete, specific things that should be added to bullets (metrics, scope, tools, outcomes)."
    ]
  },
  "structure": {
    "ordering": [
      "Clear guidance on which sections should come first for this candidate.",
      "For example: Experience, Projects, Skills, Education."
    ],
    "sections_to_add_or_remove": {
      "add": [
        "Sections or subsections that would help (Projects, Summary, Skills, Certifications)."
      ],
      "remove": [
        "Sections or items that do not add value or feel redundant."
      ]
    }
  },
  "spacing_readability": {
    "scannability_score": 1 to 10 integer,
    "tips": [
      "Short, specific tips to make it easier to skim.",
      "For example: more white space, strong section headings, consistent bullet structure."
    ]
  },
  "keywords": {
    "target_role": "Target role string (echo the one provided or infer a likely one).",
    "missing_keywords": [
      "Important domain or technical keywords that are not present but should be."
    ],
    "present_keywords_to_keep": [
      "Keywords already present that are very relevant to the target role."
    ],
    "how_to_add_them": [
      "Concrete rewrite suggestions showing how to naturally inject missing keywords."
    ]
  }
}

RULES:
- Always return valid JSON only. No markdown. No extra commentary.
- Talk directly to the candidate.
- Be specific. Reference the resume text and the job description (if provided).
- Never suggest adding skills the candidate does not have. Phrase additions as honest reframes.
- Always produce at least 3 bullet rewrites if there is enough resume content.
- Missing keywords should be drawn from the job description when it exists.
"""

        trimmed_resume = (resume_text or "")[:9000]
        trimmed_jd = (job_description or "")[:9000]

        user_message = (
            "Create a resume feedback report in the required JSON format.\n\n"
            f"Target role (may be empty): {target_role or ''}\n\n"
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

        content = response.choices[0].message.content
        data = json.loads(content)

        report = {
            "target_role": data.get("keywords", {}).get("target_role") or target_role,
            "summary": data.get("summary"),
            "sections": data.get("sections", {}),
            "experience_bullets": data.get("experience_bullets", {}),
            "structure": data.get("structure", {}),
            "spacing_readability": data.get("spacing_readability", {}),
            "keywords": data.get("keywords", {}),
            "used_job_description": bool((job_description or "").strip()),
        }
        return report

    except Exception as e:
        fallback = _local_fallback_resume_report(resume_text, target_role, job_description)
        fallback["error"] = f"GPT generation failed: {str(e)}"
        return fallback


def _local_fallback_resume_report(
    resume_text: str,
    target_role: Optional[str],
    job_description: Optional[str],
) -> Dict:
    inferred_role = target_role or "your target role"
    used_jd = bool((job_description or "").strip())

    return {
        "target_role": inferred_role,
        "used_job_description": used_jd,
        "summary": (
            f"This is a basic offline review of your resume for {inferred_role}. "
            + ("A job description was provided, but offline mode cannot extract ATS keywords from it." if used_jd else
               "For best keyword results, paste a job description and enable GPT mode.")
        ),
        "sections": {
            "overall_structure": {
                "strengths": ["Your resume can be organized into clear sections."],
                "issues": ["The ordering might not highlight your strongest experience first."],
                "recommendations": ["Lead with Experience or Projects, then Skills, then Education."],
            },
            "experience": {
                "strengths": ["You likely have relevant experience that can be told with stronger bullets."],
                "issues": ["Bullets may describe tasks instead of outcomes."],
                "recommendations": ["Rewrite bullets with scope, tools, and measurable impact."],
            },
            "education": {
                "strengths": ["Education can show technical foundation or domain knowledge."],
                "issues": [],
                "recommendations": ["If early career, keep Education near the top. Otherwise, let Experience lead."],
            },
            "skills": {
                "strengths": ["A skills section helps scanners quickly assess fit."],
                "issues": ["Skill lists can become too long or generic."],
                "recommendations": ["Group skills by category and keep only role relevant items."],
            },
        },
        "experience_bullets": {
            "rewrites": [
                {
                    "original": "Worked on various tasks for the company.",
                    "improved": "Delivered features across multiple projects, collaborating with a cross functional team to ship on time.",
                    "why_it_is_better": "Adds scope and shows delivery and collaboration.",
                },
                {
                    "original": "Helped with data analysis.",
                    "improved": "Analyzed customer data to identify trends that informed campaign and product decisions.",
                    "why_it_is_better": "Clarifies the action and the impact path.",
                },
                {
                    "original": "Assisted with software development.",
                    "improved": "Implemented and tested application features, improving reliability and reducing manual work for the team.",
                    "why_it_is_better": "Uses stronger verbs and highlights outcomes.",
                },
            ],
            "title_suggestions": [
                {
                    "original_title": "Worker",
                    "suggested_title": "Operations Assistant",
                    "reason": "More specific and easier to map to job descriptions.",
                }
            ],
            "missing_information": [
                "Add metrics: time saved, scale, number of users, dollars, latency, accuracy, throughput.",
                "Name tools and technologies used in each bullet where relevant.",
            ],
        },
        "structure": {
            "ordering": ["Recommended order: Experience, Projects, Skills, Education."],
            "sections_to_add_or_remove": {
                "add": ["Projects, if you have strong relevant work.", "A short Summary if you are switching roles."],
                "remove": ["Generic objective statements that do not add value."],
            },
        },
        "spacing_readability": {
            "scannability_score": 6,
            "tips": ["Keep bullets to 1 to 2 lines.", "Use consistent spacing and date alignment."],
        },
        "keywords": {
            "target_role": inferred_role,
            "missing_keywords": [
                "Paste a job description and enable GPT mode to get exact ATS keywords.",
            ],
            "present_keywords_to_keep": [
                "Keep the tools and skills that appear most in your target role postings.",
            ],
            "how_to_add_them": [
                "Add missing keywords by rewriting existing bullets to describe the same work with the JD vocabulary.",
            ],
        },
    }
