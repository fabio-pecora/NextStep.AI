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

        system_prompt = """
You are NextStep.AI, an elite AI career strategist and interview coach.
Your job is to create a FULLY PERSONALIZED INTERVIEW PREPARATION REPORT
for a candidate based on the following inputs:
job title, company name (if available), job description, and resume text.

You speak directly to the candidate in a confident, supportive tone,
as if you are guiding them personally through each step.

OBJECTIVE
Generate a structured JSON object (response_format=json_object) with these main sections:

{
  "candidate_name": "<name extracted from resume if possible or null>",
  "mode": "role_only" or "role_and_company",
  "know_all_about_them": {
    "mission_values": ["...", "..."],
    "culture_snapshot": ["...", "..."],
    "recent_projects_news": ["...", "...", "..."],
    "competitors_industry_trends": ["...", "..."]
  },
  "perfect_fit_map": {
    "top_strengths": ["...", "...", "..."],
    "best_projects": [
      {"title": "...", "summary": "..."},
      {"title": "...", "summary": "..."}
    ]
  },
  "behavioral_practice": {
    "title": "They’ll Ask, You’ll Shine.",
    "questions": ["...", "..."],
    "example_answers": [
      {
        "question": "...",
        "answer": "🔴Situation ... 🔵Task ... 🟢Action ... 🟣Result ...",
        "legend": {
          "🔴": "Situation",
          "🔵": "Task",
          "🟢": "Action",
          "🟣": "Result"
        }
      }
    ]
  },
  "technical_prep": {
    "title": "Show Them You’re the Real Deal.",
    "questions": ["...", "..."],
    "example_answers": [
      {
        "question": "...",
        "answer": "🔴 ... 🔵 ... 🟢 ... 🟣 ..."
      }
    ],
    "key_concepts": ["...", "..."],
    "red_flags": ["...", "..."]
  },
  "improvement_zone": {
    "title": "Upgrade Yourself Before the Interview.",
    "skill_gaps": ["...", "..."],
    "soft_skills": ["...", "..."],
    "learning_focus": ["...", "..."]
  },
  "impress_them_back": {
    "title": "Ask Like an Insider.",
    "team_culture": ["...", "..."],
    "impact_growth": ["...", "..."],
    "technical_depth": ["...", "..."],
    "company_direction": ["...", "..."],
    "next_steps": ["...", "..."]
  }
}

STYLE AND RULES

1) Voice and perspective
   - Talk directly to the candidate.
   - Use their name if you can infer it from the resume.
   - Be warm, confident, and specific. Avoid generic career advice.

2) Know All About Them (Company Deep Dive)
   - Only if company_name is provided.
   - Mission and Values: 2 to 3 bullets in plain language.
   - Culture Snapshot: what they look for in people (based on typical public info, Glassdoor style feedback, and their industry).
   - Recent Projects and News: up to 3 high level initiatives, launches, or achievements.
   - Competitors and Industry Trends: 2 to 3 bullets about the market and how this company fits in.
   - If you lack real information, say: "Based on public information and typical practices for this industry..."

3) What to Be Proud Of (Perfect Fit Map)
   - Compare job description and resume.
   - List exactly 3 top strengths that align directly with the job.
   - Add 2 to 3 best projects to emphasize, each with a very short summary explaining why it proves fit.

4) Behavioral Interview Practice (They’ll Ask, You’ll Shine.)
   - Create 5 to 10 behavioral questions likely for this company and role.
   - For 2 of them, write full example answers based on the candidate’s background using STAR.
   - Use color coded emojis inside the answer:
       🔴 for Situation
       🔵 for Task
       🟢 for Action
       🟣 for Result
   - Include the legend object in at least one example as shown in the schema.

5) Technical or Role Specific Preparation (Show Them You’re the Real Deal.)
   - Create 5 to 10 technical or problem solving questions that are realistic for this role.
   - Provide 2 example answers tailored to the candidate’s experience.
   - Add:
       key_concepts: short bullet list of things to review.
       red_flags: common mistakes candidates make for this type of role.

6) How to Be an Even Better Candidate (Upgrade Yourself Before the Interview.)
   - Identify 2 to 4 concrete skill gaps or areas to polish based on the job vs resume.
   - Suggest 2 to 3 soft skills to focus on (storytelling, active listening, ownership, etc.).
   - Suggest what to learn or practice this week in a very actionable way.

7) Impress Them Back (Ask Like an Insider.)
   - Create 5 to 10 high quality questions for the candidate to ask the interviewer.
   - Split them into:
       team_culture
       impact_growth
       technical_depth
       company_direction
       next_steps
   - These questions must make the candidate sound prepared, thoughtful, and curious.

8) Output formatting
   - Always return valid JSON exactly as requested.
   - Do not use Markdown headings.
   - Only use emojis for the STAR color coding and keep everything else as plain text.
   - If company_name is missing, you can keep know_all_about_them fields shorter or more generic.
   - If resume or job description is missing, do your best with the data available.
   - If you cannot infer the candidate’s name, set candidate_name to null.
"""

        user_message = (
            "Create a full interview preparation report in the JSON format described above.\n\n"
            "Candidate info:\n"
            f"Job title: {job_title}\n"
            f"Company name: {company_name or ''}\n"
            f"Job description: {(job_description or '')[:2500]}\n"
            f"Resume: {(resume or '')[:2500]}\n"
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

        report = {
            "job_title": job_title,
            "company_name": company_name,
            "candidate_name": data.get("candidate_name"),
            "mode": data.get(
                "mode",
                "role_and_company" if company_name else "role_only",
            ),
            "know_all_about_them": data.get("know_all_about_them", {}),
            "perfect_fit_map": data.get("perfect_fit_map", {}),
            "behavioral_practice": data.get("behavioral_practice", {}),
            "technical_prep": data.get("technical_prep", {}),
            "improvement_zone": data.get("improvement_zone", {}),
            "impress_them_back": data.get("impress_them_back", {}),
        }
        return report

    except Exception as e:
        fallback = _local_fallback_report(job_title, company_name)
        fallback["error"] = f"GPT generation failed: {str(e)}"
        return fallback


def _local_fallback_report(job_title: str, company_name: Optional[str]) -> Dict:
    """
    Cheap local fallback if GPT is unavailable.
    """
    mission_values = []
    culture_snapshot = []
    recent_projects_news = []
    competitors_industry_trends = []

    if company_name:
        mission_values = [
            f"{company_name} likely values ownership, strong communication, and alignment with its mission."
        ]
        culture_snapshot = [
            "They probably look for people who take initiative, collaborate well, and care about impact."
        ]
        recent_projects_news = [
            "Review their recent announcements and product updates on their website and LinkedIn."
        ]
        competitors_industry_trends = [
            "Look at a few similar companies in the same space to understand the market landscape."
        ]

    perfect_fit_map = {
        "top_strengths": [
            f"You are motivated to grow as a {job_title}.",
            "You have relevant experience and stories you can shape into STAR answers.",
            "You are willing to prepare and practice deliberately.",
        ],
        "best_projects": [
            {
                "title": "Recent project or experience",
                "summary": "Pick a project where you had clear impact and be ready to explain it using STAR.",
            }
        ],
    }

    behavioral_practice = {
        "title": "They’ll Ask, You’ll Shine.",
        "questions": [
            "Tell me about a time you faced a difficult challenge at work or school.",
            "Describe a situation where you worked in a team with conflicting opinions.",
        ],
        "example_answers": [],
    }

    technical_prep = {
        "title": "Show Them You’re the Real Deal.",
        "questions": [
            f"What are the most important responsibilities of a {job_title}?",
            "Tell me about a time you solved a technical or analytical problem.",
        ],
        "example_answers": [],
        "key_concepts": [
            "Review the core tools and technologies commonly used in this role.",
            "Be ready to explain at least one or two projects in detail.",
        ],
        "red_flags": [
            "Very vague or generic answers with no concrete examples.",
            "Not understanding the basic responsibilities of the role.",
        ],
    }

    improvement_zone = {
        "title": "Upgrade Yourself Before the Interview.",
        "skill_gaps": [
            "Identify one or two technical or domain areas where you feel weaker and review them this week."
        ],
        "soft_skills": [
            "Practice telling your stories out loud using STAR.",
            "Focus on clear, concise communication.",
        ],
        "learning_focus": [
            "Write down three STAR stories and rehearse them.",
            "Review the job posting and highlight key skills you want to emphasize.",
        ],
    }

    impress_them_back = {
        "title": "Ask Like an Insider.",
        "team_culture": [
            "How does this team typically work together day to day?"
        ],
        "impact_growth": [
            "How will success in this role be measured in the first 3 to 6 months?"
        ],
        "technical_depth": [
            "What are the main tools, technologies, or processes the team uses?"
        ],
        "company_direction": [
            "What are the most important priorities or initiatives for the company this year?"
        ],
        "next_steps": [
            "Is there anything else I can share that would be helpful for your decision?"
        ],
    }

    return {
        "job_title": job_title,
        "company_name": company_name,
        "candidate_name": None,
        "mode": "role_and_company" if company_name else "role_only",
        "debug_note": "⚠️ LOCAL FALLBACK USED — GPT did not generate this report.",
        "know_all_about_them": {
            "mission_values": mission_values,
            "culture_snapshot": culture_snapshot,
            "recent_projects_news": recent_projects_news,
            "competitors_industry_trends": competitors_industry_trends,
        },
        "perfect_fit_map": perfect_fit_map,
        "behavioral_practice": behavioral_practice,
        "technical_prep": technical_prep,
        "improvement_zone": improvement_zone,
        "impress_them_back": impress_them_back,
    }
