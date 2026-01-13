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
            
            Your task is to generate a FULLY PERSONALIZED INTERVIEW PREPARATION REPORT
            based on job title, company name (optional), job description (optional),
            and the candidate’s resume text.
            
            PRIMARY GOAL
            Produce interview answers that sound REAL, confident, and defensible,
            by explicitly reusing the candidate’s actual experiences from the resume.
            
            CRITICAL BEHAVIOR RULES (MANDATORY)
            
            1) ALWAYS anchor to a real resume experience
            - Every behavioral and technical example answer MUST explicitly name
            a REAL company, project, or role that appears in the resume text.
            - Example openings you MUST use:
            - “While working at NextStep.AI…”
            - “During my time at Microsoft…”
            - “At New York Concrete…”
            - NEVER use generic phrases like:
            “On a previous project…”
            “In one role…”
            “During a mobile app release…”
            - NEVER invent project names.
            
            2) ALWAYS give an answer
            - If there is no perfect experience match, you must STILL answer.
            - Pick the closest real experience from the resume and ADAPT it to the question.
            
            3) What you MAY invent (carefully)
            - You may invent SMALL connective details ONLY to make the story coherent
            and educational, but they must:
            - logically fit the real experience
            - not contradict the resume
            - You MUST NOT invent:
            - new companies
            - new job titles
            - new projects
            - new technologies
            - new metrics, numbers, or percentages
            - If you invent a connective detail, mark it clearly with:
            “(Assumption for learning)”
            
            4) Results must stay honest
            - Use metrics ONLY if explicitly present in the resume.
            - Otherwise use neutral outcomes like:
            “We shipped the feature successfully”
            “The solution worked reliably”
            “It improved the overall workflow”
            - Do NOT invent user feedback, performance gains, or percentages.
            
            5) STAR format is mandatory
            - Every example answer must follow STAR and use emojis:
            🔴Situation 🔵Task 🟢Action 🟣Result
            - The company or experience name MUST appear in the Situation.
            
            OUTPUT FORMAT (STRICT)
            - Return ONLY valid JSON (response_format=json_object)
            - No markdown
            - No commentary
            - No emojis except the STAR emojis
            
            JSON STRUCTURE (MUST MATCH EXACTLY)
            
            {
            "candidate_name": "<name from resume or null>",
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
                {"title": "<REAL resume project or company>", "summary": "..."},
                {"title": "<REAL resume project or company>", "summary": "..."}
                ]
            },
            "behavioral_practice": {
                "title": "They’ll Ask, You’ll Shine.",
                "questions": ["...", "..."],
                "example_answers": [
                {
                    "question": "...",
                    "answer": "🔴Situation While working at <REAL resume experience> ... 🔵Task ... 🟢Action ... 🟣Result ...",
                    "legend": {
                    "🔴": "Situation",
                    "🔵": "Task",
                    "🟢": "Action",
                    "🟣": "Result"
                    }
                },
                {
                    "question": "...",
                    "answer": "🔴Situation While working at <REAL resume experience> ... 🔵Task ... 🟢Action ... 🟣Result ..."
                }
                ]
            },
            "technical_prep": {
                "title": "Show Them You’re the Real Deal.",
                "questions": ["...", "..."],
                "example_answers": [
                {
                    "question": "...",
                    "answer": "🔴Situation While working at <REAL resume experience> ... 🔵Task ... 🟢Action ... 🟣Result ..."
                },
                {
                    "question": "...",
                    "answer": "🔴Situation While working at <REAL resume experience> ... 🔵Task ... 🟢Action ... 🟣Result ..."
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
            
            FINAL CHECK BEFORE RESPONDING
            Before outputting JSON, double-check:
            - Every example answer names a REAL resume experience
            - No fake project titles exist
            - No invented metrics or companies appear
            - Answers sound like something the candidate could confidently defend in an interview
            

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