import json
from typing import Dict, Optional

from openai import OpenAI


def generate_resume_report(
    resume_text: str,
    target_role: Optional[str] = None,
    model: str = "gpt-4.1-mini",
    use_gpt: bool = True,
) -> Dict:
    """
    Generate a structured resume review report.

    If use_gpt is True, this calls the OpenAI API.
    If it fails or use_gpt is False, it falls back to a simple local template.

    Returns a dict with the structure expected by the resume_check template.
    """
    if not use_gpt:
        return _local_fallback_resume_report(resume_text, target_role)

    try:
        client = OpenAI()

        system_prompt = """
          You are NextStep.AI, an elite AI resume coach.
          Your job is to review a candidate's resume and give specific, premium quality feedback.
          
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
          
          1) Voice and perspective
            - Talk directly to the candidate.
            - Be clear, actionable, and specific.
            - Avoid generic career advice. Focus on what is written in the resume text and what is missing.
          
          2) Experience bullets
            - Always give at least 3 bullet rewrites if there is enough content.
            - Use strong action verbs, clear outcomes, and metrics when possible.
          
          3) Keywords
            - If a target_role is provided, tune the feedback to that role.
            - If not, infer a likely role from the resume and say that in target_role.
            - Missing keywords should be realistic for that role and level.
          
          4) Spacing and readability
            - Scannability score is 1 to 10 where 10 is excellent.
            - Tips must be practical, not vague.
          
          5) Output formatting
            - Always return valid JSON only.
            - Do not include Markdown or extra commentary.
          """
          
        # Truncate resume_text to avoid very long inputs
        trimmed_resume = (resume_text or "")[:8000]

        user_message = (
            "Review the following resume and create a full resume feedback report in the JSON format described above.\n\n"
            f"Target role (may be empty): {target_role or ''}\n\n"
            f"Resume text:\n{trimmed_resume}"
        )

        response = client.chat.completions.create(
            model=model,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
        )

        content = response.choices[0].message.content
        data = json.loads(content)

        # Build a defensive report object so templates do not explode if some keys are missing
        report = {
            "target_role": data.get("keywords", {}).get("target_role") or target_role,
            "summary": data.get("summary"),
            "sections": data.get("sections", {}),
            "experience_bullets": data.get("experience_bullets", {}),
            "structure": data.get("structure", {}),
            "spacing_readability": data.get("spacing_readability", {}),
            "keywords": data.get("keywords", {}),
        }
        return report

    except Exception as e:
        fallback = _local_fallback_resume_report(resume_text, target_role)
        fallback["error"] = f"GPT generation failed: {str(e)}"
        return fallback


def _local_fallback_resume_report(
    resume_text: str,
    target_role: Optional[str],
) -> Dict:
    """
    Local fallback if GPT is not available.
    This is intentionally simple, but matches the expected JSON shape.
    """
    inferred_role = target_role or "your target role"

    return {
        "target_role": inferred_role,
        "summary": (
            f"This is a basic offline review of your resume for {inferred_role}. "
            "Focus on clear structure, strong action verbs, and measurable impact."
        ),
        "sections": {
            "overall_structure": {
                "strengths": [
                    "You have a resume that can be organized into clear sections.",
                ],
                "issues": [
                    "The ordering of sections might not highlight your strongest experience first.",
                ],
                "recommendations": [
                    "Start with Experience or Projects if they are strong, then Skills, then Education.",
                ],
            },
            "experience": {
                "strengths": [
                    "You likely have relevant experience that can be told with stronger bullets.",
                ],
                "issues": [
                    "Bullets may describe tasks instead of impact.",
                ],
                "recommendations": [
                    "Rewrite bullets to show what changed because of your work: use numbers, scope, and outcomes.",
                ],
            },
            "education": {
                "strengths": [
                    "Education can show technical foundation or domain knowledge.",
                ],
                "issues": [],
                "recommendations": [
                    "If you are early career, keep Education near the top. Otherwise, let Experience lead.",
                ],
            },
            "skills": {
                "strengths": [
                    "Listing tools, languages, and frameworks helps scanners quickly understand your fit.",
                ],
                "issues": [
                    "Skill lists can become too long or generic.",
                ],
                "recommendations": [
                    "Group skills by category and keep only the ones you would feel comfortable using in the role.",
                ],
            },
        },
        "experience_bullets": {
            "rewrites": [
                {
                    "original": "Worked on various tasks for the company.",
                    "improved": "Delivered features across 3 projects, collaborating with a cross functional team to ship on time.",
                    "why_it_is_better": "Uses a clear action verb, adds scope, and shows collaboration and delivery.",
                },
                {
                    "original": "Helped with data analysis.",
                    "improved": "Analyzed customer data to identify trends that informed 2 marketing campaigns.",
                    "why_it_is_better": "Shows what you did, what data you used, and the outcome.",
                },
            ],
            "title_suggestions": [
                {
                    "original_title": "Worker",
                    "suggested_title": "Operations Assistant",
                    "reason": "More specific and professional, and easier to map to job descriptions.",
                }
            ],
            "missing_information": [
                "Add metrics where possible (revenue, time saved, number of users, size of team).",
                "Mention tools and technologies you actually used.",
            ],
        },
        "structure": {
            "ordering": [
                "Recommended order for most candidates: Experience, Projects, Skills, Education.",
            ],
            "sections_to_add_or_remove": {
                "add": [
                    "Projects, if you have strong personal or academic work that is relevant.",
                ],
                "remove": [
                    "Generic objective statements that do not add value.",
                ],
            },
        },
        "spacing_readability": {
            "scannability_score": 6,
            "tips": [
                "Use consistent section headings and spacing.",
                "Align bullets and dates so the page looks clean.",
            ],
        },
        "keywords": {
            "target_role": inferred_role,
            "missing_keywords": [
                "Add 3 to 5 role specific keywords from the job descriptions you are targeting.",
            ],
            "present_keywords_to_keep": [
                "Keep any skills and tools that are used in multiple postings for your target role.",
            ],
            "how_to_add_them": [
                "Take 2 to 3 of your most relevant bullets and rewrite them so that the new keywords appear naturally.",
            ],
        },
    }
