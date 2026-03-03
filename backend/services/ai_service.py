"""
AI Service — Powered by Google Gemini 2.0 Flash
Provides real AI capabilities for survey design, sentiment analysis,
follow-up generation, and executive summary production.
"""
import json
import re
import random
import time
from datetime import datetime
from google import genai
from ..config import GEMINI_API_KEY, GEMINI_MODEL

# ── Initialise Gemini client ──
client = genai.Client(api_key=GEMINI_API_KEY)

# Fallback models to try if primary is rate-limited (each has separate quota)
FALLBACK_MODELS = ["gemini-2.5-flash", "gemini-2.0-flash", "gemini-2.5-flash-lite", "gemini-2.0-flash-lite", "gemini-3-flash-preview"]


def _ask_gemini(prompt: str, max_tokens: int = 1024, retries: int = 3) -> str:
    """Send a prompt to Gemini with retry logic and model fallback for rate limits."""
    models_to_try = [GEMINI_MODEL] + [m for m in FALLBACK_MODELS if m != GEMINI_MODEL]

    for model in models_to_try:
        for attempt in range(retries):
            try:
                response = client.models.generate_content(
                    model=model,
                    contents=prompt,
                    config={
                        "max_output_tokens": max_tokens,
                        "temperature": 0.7,
                    },
                )
                # Try response.text first, fall back to extracting from candidates
                text = ""
                try:
                    text = response.text.strip()
                except Exception:
                    # response.text can raise if finish_reason is not STOP
                    # Try to extract text from candidates directly
                    if hasattr(response, 'candidates') and response.candidates:
                        for candidate in response.candidates:
                            if hasattr(candidate, 'content') and candidate.content:
                                for part in candidate.content.parts:
                                    if hasattr(part, 'text') and part.text:
                                        text += part.text
                        text = text.strip()
                if text:
                    return text
            except Exception as e:
                error_str = str(e)
                if "429" in error_str or "RESOURCE_EXHAUSTED" in error_str:
                    # Check if it's a daily quota (PerDay) — skip retries, try next model immediately
                    if "PerDay" in error_str:
                        print(f"[Gemini] Daily quota exhausted for {model}, trying next model...")
                        break  # Skip to next model
                    # Per-minute rate limit — wait and retry
                    wait_time = (attempt + 1) * 2  # 2s, 4s, 6s
                    print(f"[Gemini Rate Limit] Model {model}, attempt {attempt+1}/{retries}. Waiting {wait_time}s...")
                    time.sleep(wait_time)
                    continue
                else:
                    print(f"[Gemini Error] Model {model}: {e}")
                    break  # Non-rate-limit error, try next model

    print("[Gemini] All models and retries exhausted, returning empty")
    return ""


def _ask_gemini_json(prompt: str, max_tokens: int = 1024):
    """Send a prompt expecting JSON back; parse and return."""
    raw = _ask_gemini(prompt, max_tokens, retries=3)
    if not raw:
        return {}
    # Strip markdown fences if present
    raw = re.sub(r"^```(?:json)?\s*", "", raw, flags=re.MULTILINE)
    raw = re.sub(r"```\s*$", "", raw, flags=re.MULTILINE)
    raw = raw.strip()
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        # Try to extract JSON from the response
        json_match = re.search(r'[\[{].*[\]}]', raw, re.DOTALL)
        if json_match:
            try:
                return json.loads(json_match.group())
            except json.JSONDecodeError:
                pass
        # Try to fix truncated JSON by closing brackets
        truncated = raw.rstrip()
        for _ in range(20):
            try:
                return json.loads(truncated)
            except json.JSONDecodeError:
                # Try adding closing brackets/braces
                if truncated.count('{') > truncated.count('}'):
                    truncated += '}'
                elif truncated.count('[') > truncated.count(']'):
                    truncated += ']'
                elif truncated.endswith(','):
                    truncated = truncated[:-1]
                elif truncated.endswith('"'):
                    truncated += '}'
                else:
                    truncated += '}'
        print(f"[Gemini JSON parse error] Could not parse: {raw[:500]}")
        return {}


class AIService:
    """Gemini-backed AI service for all AI-powered features."""

    # ───────────────────────────────────────────────────────────
    # Feature 1: Research Goal Understanding
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def parse_research_goal(user_input: str) -> dict:
        """Convert natural-language research goal into a structured objective using Gemini."""
        prompt = f"""You are an expert UX researcher.  The user described their research goal below.
Analyse it and return a JSON object with these exact keys (no extra keys):
- "title": concise research title (max 10 words)
- "research_type": one of [discovery, churn_analysis, satisfaction, usability, pricing, feature_feedback]
- "problem_space": one-sentence description of the problem
- "target_outcome": what the research should achieve
- "objectives": list of 3-5 specific research objectives (strings)
- "suggested_audience": description of ideal respondents
- "themes": list of 3-6 keyword themes to explore
- "suggested_question_count": integer 5-12
- "estimated_duration": integer minutes (4-10)
- "success_criteria": one sentence
- "quality_score": number 75-95
- "target_audience": description of ideal respondents

User goal: \"{user_input}\"

Return ONLY valid JSON, no markdown."""

        result = _ask_gemini_json(prompt)

        if not result or "title" not in result:
            return {
                "title": user_input[:60],
                "research_type": "discovery",
                "problem_space": f"Understanding: {user_input[:100]}",
                "target_outcome": f"Identify key factors related to: {user_input[:80]}",
                "objectives": [
                    "Understand user pain points",
                    "Identify recurring themes",
                    "Discover improvement opportunities",
                ],
                "suggested_audience": "Active users in the last 30 days",
                "target_audience": "Active users in the last 30 days",
                "themes": ["experience", "usability", "satisfaction"],
                "suggested_question_count": 8,
                "estimated_duration": 5,
                "success_criteria": "Identify 3+ recurring patterns with 85%+ confidence",
                "quality_score": 80.0,
            }
        return result

    # ───────────────────────────────────────────────────────────
    # Feature 1: Question Generation
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def generate_questions(research_type: str, count: int = 8, goal_text: str = "") -> list:
        """Generate contextual interview questions using Gemini."""
        prompt = f"""You are an expert UX researcher designing an interview.
Research type: {research_type}
{f'Research goal context: {goal_text}' if goal_text else ''}
Generate exactly {count} high-quality interview questions.

Return a JSON array where each element has:
- "question_text": the question string
- "question_type": one of [open_ended, rating, multiple_choice, yes_no, scale]
- "tone": one of [friendly, neutral, empathetic, curious, encouraging]
- "depth": integer 1-3 (1=icebreaker, 2=core, 3=deep dive)

Start with a warm icebreaker, move to core questions, end with a reflective question.
Mix question types — at least 60% open_ended.
Return ONLY the JSON array, no markdown."""

        result = _ask_gemini_json(prompt, max_tokens=2048)

        if isinstance(result, list) and len(result) > 0:
            return result[:count]

        return _fallback_questions(research_type, count)

    # ───────────────────────────────────────────────────────────
    # Feature 1b: Deep Question Generation with Follow-ups
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def generate_deep_questions(goal_text: str, research_type: str = "discovery", count: int = 8) -> dict:
        """Generate in-depth survey questions with follow-up questions using AI analysis."""
        prompt = f"""You are a world-class UX research expert. A user wants to create a survey.
They described their research goal:
\"{goal_text}\"
Research type: {research_type}

Do the following:
1. Deeply analyze this research goal
2. Generate exactly {count} high-quality main interview questions with 2 follow-up questions each
3. For each question, think about what the respondent might answer and craft follow-ups that dig deeper

Return a JSON object with:
- "analysis": {{
    "goal_summary": "1-2 sentence summary of what the survey aims to discover",
    "key_areas": ["list of 4-6 key research areas to explore"],
    "respondent_guidance": "Brief description of ideal respondents",
    "estimated_duration": integer minutes (5-15),
    "interview_approach": "Brief description of the interview strategy"
  }}
- "questions": [
    {{
      "question_text": "Main question text",
      "question_type": "open_ended|rating|multiple_choice|yes_no|scale",
      "purpose": "Why this question is being asked (1 sentence)",
      "tone": "friendly|neutral|empathetic|curious|encouraging",
      "depth": 1|2|3,
      "follow_ups": [
        {{
          "trigger": "Description of when to ask this follow-up",
          "question_text": "Follow-up question text"
        }},
        {{
          "trigger": "Description of when to ask this follow-up",
          "question_text": "Follow-up question text"
        }}
      ]
    }}
  ]
- "respondent_briefing": "A friendly message to tell the user (survey creator) what questions will be asked and how the interview will flow"
- "interview_flow_summary": "A brief description of how the interview progresses from warm-up to deep dive"

Start with warm icebreaker questions, progress to core deep questions, end with reflective/forward-looking questions.
At least 60% should be open_ended. Mix question types.
Return ONLY valid JSON, no markdown."""

        result = _ask_gemini_json(prompt, max_tokens=8192)

        if result and "questions" in result and isinstance(result["questions"], list):
            return result

        # Fallback
        fallback_qs = _fallback_questions(research_type, count)
        return {
            "analysis": {
                "goal_summary": f"Understanding: {goal_text[:100]}",
                "key_areas": ["User experience", "Pain points", "Feature satisfaction", "Improvement suggestions"],
                "respondent_guidance": "Active users who have used the product in the last 30 days",
                "estimated_duration": 7,
                "interview_approach": "Start with rapport building, explore key areas, then gather forward-looking suggestions"
            },
            "questions": [
                {
                    **q,
                    "purpose": "Explore user perspective",
                    "follow_ups": [
                        {"trigger": "If respondent mentions a positive experience", "question_text": "What specifically made that experience good?"},
                        {"trigger": "If respondent mentions a negative experience", "question_text": "How did that make you feel? What would you have preferred?"}
                    ]
                }
                for q in fallback_qs
            ],
            "respondent_briefing": f"We'll be asking {count} questions about your experience. The interview covers your overall impressions, specific features, and suggestions for improvement. We'll also ask follow-up questions to better understand your perspective.",
            "interview_flow_summary": "The interview starts with a warm icebreaker, moves into core experience questions, and ends with forward-looking suggestions."
        }

    # ───────────────────────────────────────────────────────────
    # Feature: Audience-Targeted Question Generation
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def generate_audience_targeted_questions(goal_text: str, target_audiences: list, research_type: str = "discovery", count_per_audience: int = 6) -> dict:
        """Generate audience-specific questions for each target audience plus a generic set.

        Returns:
            {
                "analysis": { ... },
                "audience_sets": [
                    { "audience": "Audience Name", "questions": [...], "briefing": "..." },
                    ...
                ],
                "generic_set": { "audience": "General / All Audiences", "questions": [...], "briefing": "..." },
                "respondent_briefing": "...",
                "interview_flow_summary": "..."
            }
        """
        audiences_str = ", ".join(target_audiences)

        prompt = f"""You are a world-class UX research expert. A user wants to create a survey for MULTIPLE target audiences.

Research goal: \"{goal_text}\"
Research type: {research_type}
Target audiences: {audiences_str}

Your task:
1. Analyze the research goal
2. For EACH target audience, generate {count_per_audience} audience-specific questions with 2 follow-ups each. These questions should be TAILORED to the specific audience's perspective, language, and context.
3. Also generate {count_per_audience} GENERIC questions that work for ALL audiences (a universal survey form).

Return a JSON object with:
- "analysis": {{
    "goal_summary": "1-2 sentence summary",
    "key_areas": ["list of 4-6 key research areas"],
    "respondent_guidance": "Brief description of ideal respondents",
    "estimated_duration": integer minutes,
    "interview_approach": "Brief description of strategy",
    "audience_rationale": "Why these audiences were chosen and how questions differ"
  }}
- "audience_sets": [
    {{
      "audience": "Name of target audience",
      "description": "Brief description of this audience segment",
      "questions": [
        {{
          "question_text": "Main question tailored for this audience",
          "question_type": "open_ended|rating|multiple_choice|yes_no|scale",
          "purpose": "Why this question is asked for THIS audience",
          "tone": "friendly|neutral|empathetic|curious|encouraging",
          "depth": 1|2|3,
          "follow_ups": [
            {{ "trigger": "When to ask this", "question_text": "Follow-up text" }},
            {{ "trigger": "When to ask this", "question_text": "Follow-up text" }}
          ]
        }}
      ],
      "briefing": "Brief message about what this audience-specific interview covers"
    }}
  ]
- "generic_set": {{
    "audience": "General / All Audiences",
    "description": "Universal survey suitable for any respondent regardless of segment",
    "questions": [same structure as above],
    "briefing": "Brief message about the generic survey"
  }}
- "respondent_briefing": "Overall friendly message about the survey"
- "interview_flow_summary": "How the interview progresses"

IMPORTANT:
- Audience-specific questions should use language and examples relevant to that audience
- Start each set with icebreakers, move to core, end with reflective questions
- At least 60% open_ended questions in each set
- Make follow-ups genuinely different based on expected audience responses
Return ONLY valid JSON, no markdown."""

        result = _ask_gemini_json(prompt, max_tokens=16384)

        if result and "audience_sets" in result and isinstance(result["audience_sets"], list):
            return result

        # Fallback: generate basic structure
        fallback_qs = _fallback_questions(research_type, count_per_audience)
        audience_sets = []
        for aud in target_audiences:
            audience_sets.append({
                "audience": aud,
                "description": f"Questions tailored for {aud}",
                "questions": [
                    {
                        **q,
                        "purpose": f"Explore {aud}'s perspective",
                        "follow_ups": [
                            {"trigger": "If respondent mentions a positive experience", "question_text": "What specifically made that experience good?"},
                            {"trigger": "If respondent mentions a challenge", "question_text": "How did that affect you? What would you have preferred?"}
                        ]
                    }
                    for q in fallback_qs
                ],
                "briefing": f"This interview is tailored for {aud}. We'll explore your specific experiences and perspectives."
            })

        return {
            "analysis": {
                "goal_summary": f"Understanding: {goal_text[:100]}",
                "key_areas": ["User experience", "Pain points", "Feature satisfaction", "Improvement suggestions"],
                "respondent_guidance": f"Target audiences: {audiences_str}",
                "estimated_duration": 7,
                "interview_approach": "Audience-specific interviews with tailored questions for each segment",
                "audience_rationale": f"Questions are customized for {len(target_audiences)} distinct audience segments to capture unique perspectives."
            },
            "audience_sets": audience_sets,
            "generic_set": {
                "audience": "General / All Audiences",
                "description": "Universal survey suitable for any respondent",
                "questions": [
                    {
                        **q,
                        "purpose": "General exploration",
                        "follow_ups": [
                            {"trigger": "If positive", "question_text": "What made it good?"},
                            {"trigger": "If negative", "question_text": "What would you improve?"}
                        ]
                    }
                    for q in fallback_qs
                ],
                "briefing": "This is a general survey covering your overall experience."
            },
            "respondent_briefing": f"We'll be asking questions about your experience. The interview is tailored to your specific context.",
            "interview_flow_summary": "Warm-up, core exploration, and reflective close."
        }

    # ───────────────────────────────────────────────────────────
    # Feature: Interview Transcript & Report Generation
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def generate_interview_transcript_report(session_data: dict) -> dict:
        """Generate a complete transcript summary and report from interview data."""
        history = session_data.get("history", [])
        responses = session_data.get("responses", [])

        conversation_text = ""
        for h in history:
            role = "Interviewer" if h.get("role") == "ai" else "Respondent"
            conversation_text += f"{role}: {h.get('message', '')}\n"

        prompt = f"""You are an expert UX research analyst. Below is a complete interview transcript.
Analyze it thoroughly and generate a comprehensive report.

IMPORTANT: The transcript may contain responses in multiple languages (English, Urdu, Roman Urdu, Hindi, etc.).
You MUST translate ALL non-English content to English in your report. The entire output (summaries, quotes, analysis, recommendations) must be in ENGLISH only.
When quoting the respondent, provide the English translation. If the original quote adds value, include it in parentheses like: "I really liked this feature" (original: "Mujhe yeh feature bohat acha laga").

INTERVIEW TRANSCRIPT:
{conversation_text[:6000]}

Return a JSON object with:
- "transcript_summary": {{
    "total_questions_asked": integer,
    "total_responses": integer,
    "duration_estimate": "string like '5 minutes'",
    "completion_status": "complete|incomplete|partial",
    "key_topics_discussed": ["list of main topics covered"]
  }}
- "question_summaries": [
    {{
      "question": "The question asked",
      "response_summary": "Brief summary of respondent's answer",
      "sentiment": "positive|negative|neutral|mixed",
      "key_insight": "Main takeaway from this response",
      "notable_quotes": ["Direct quotes from respondent, if any"]
    }}
  ]
- "overall_analysis": {{
    "respondent_sentiment": "Overall sentiment description",
    "sentiment_score": float -1.0 to 1.0,
    "main_pain_points": ["List of pain points identified"],
    "positive_highlights": ["List of positive aspects mentioned"],
    "suggestions_made": ["List of suggestions from respondent"],
    "emotional_journey": "Description of how respondent's emotions evolved during the interview"
  }}
- "executive_summary": "2-3 paragraph professional summary of the entire interview findings"
- "recommendations": [
    {{
      "title": "Recommendation title",
      "description": "What should be done",
      "priority": "high|medium|low",
      "based_on": "Which response(s) this is based on"
    }}
  ]

Return ONLY valid JSON, no markdown."""

        result = _ask_gemini_json(prompt, max_tokens=4096)

        if result and ("executive_summary" in result or "transcript_summary" in result):
            return result

        # Fallback
        q_count = len([h for h in history if h.get("role") == "ai"])
        r_count = len([h for h in history if h.get("role") != "ai"])
        return {
            "transcript_summary": {
                "total_questions_asked": q_count,
                "total_responses": r_count,
                "duration_estimate": f"{max(1, len(history) // 3)} minutes",
                "completion_status": "complete" if r_count >= 3 else "incomplete",
                "key_topics_discussed": ["User experience", "Feedback"]
            },
            "question_summaries": [
                {
                    "question": h.get("message", ""),
                    "response_summary": history[i+1].get("message", "") if i+1 < len(history) else "",
                    "sentiment": "neutral",
                    "key_insight": "Response recorded",
                    "notable_quotes": []
                }
                for i, h in enumerate(history) if h.get("role") == "ai" and i+1 < len(history)
            ][:10],
            "overall_analysis": {
                "respondent_sentiment": "Neutral overall",
                "sentiment_score": 0.0,
                "main_pain_points": [],
                "positive_highlights": [],
                "suggestions_made": [],
                "emotional_journey": "The respondent maintained a consistent tone throughout."
            },
            "executive_summary": f"Interview with {r_count} responses collected across {q_count} questions. Further analysis is needed for detailed insights.",
            "recommendations": [
                {"title": "Continue data collection", "description": "Gather more responses for statistically significant insights", "priority": "medium", "based_on": "Limited sample size"}
            ]
        }

    # ───────────────────────────────────────────────────────────
    # Group-Level Survey Analysis (across ALL respondents)
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def generate_survey_group_analysis(survey_data: dict) -> dict:
        """Generate comprehensive group-level analysis across all respondents for a survey."""
        title = survey_data.get("title", "Survey")
        description = survey_data.get("description", "")
        questions = survey_data.get("questions", [])
        transcripts = survey_data.get("transcripts", [])
        respondent_count = survey_data.get("respondent_count", 0)
        completed_count = survey_data.get("completed_count", 0)

        # Build combined transcript text
        all_conversations = ""
        for i, t in enumerate(transcripts[:15]):  # Limit to 15 transcripts
            all_conversations += f"\n--- Respondent {i+1} ({t.get('channel', 'unknown')} channel) ---\n"
            entries = t.get("entries", [])
            for e in entries[:30]:
                role = "Interviewer" if e.get("role") == "ai" else "Respondent"
                all_conversations += f"{role}: {e.get('message', '')}\n"

        questions_text = "\n".join([f"Q{i+1}. {q}" for i, q in enumerate(questions)])

        prompt = f"""You are a senior UX research analyst. Analyze ALL the interview data below from a survey and produce a comprehensive group-level analysis report.

SURVEY: "{title}"
CONTEXT: {description[:500]}
QUESTIONS ASKED:
{questions_text}

TOTAL RESPONDENTS: {respondent_count}
COMPLETED INTERVIEWS: {completed_count}

ALL INTERVIEW TRANSCRIPTS:
{all_conversations[:12000]}

IMPORTANT: Translate ALL non-English content to English. Output must be entirely in English.

Return a JSON object with exactly these fields:
- "executive_summary": "3-4 paragraph professional executive summary of ALL findings across all respondents. Include key numbers, patterns, and actionable insights."
- "key_findings": [
    {{"finding": "Clear finding statement", "evidence": "Supporting data/quotes from respondents", "impact": "high|medium|low", "respondent_count": number_who_mentioned_this}}
  ] (list 5-8 key findings)
- "sentiment_overview": {{
    "overall": "positive|negative|neutral|mixed",
    "score": float -1.0 to 1.0,
    "summary": "2-3 sentence summary of overall sentiment across all respondents"
  }}
- "pain_points": [
    {{"issue": "Description of the pain point", "severity": "critical|major|minor", "frequency": "how many respondents mentioned this", "example_quotes": ["1-2 relevant quotes"]}}
  ] (list top 5 pain points)
- "positive_aspects": [
    {{"aspect": "What respondents liked", "frequency": "how many mentioned it", "example_quotes": ["1-2 quotes"]}}
  ] (list top 5 positives)
- "per_question_analysis": [
    {{"question": "The question text", "response_pattern": "Summary of how respondents answered this", "common_themes": ["theme1", "theme2"], "sentiment": "positive|negative|neutral|mixed", "notable_quotes": ["1-2 best quotes"]}}
  ]
- "recommendations": [
    {{"title": "Action item title", "description": "Detailed recommendation", "priority": "high|medium|low", "category": "product|process|research|strategy", "expected_impact": "What improvement to expect"}}
  ] (list 5-8 actionable recommendations sorted by priority)
- "themes_discovered": [
    {{"theme": "Theme name", "description": "What this theme is about", "frequency": number_of_respondents, "sentiment": "positive|negative|neutral|mixed"}}
  ]
- "respondent_segments": [
    {{"segment": "Segment name (e.g. 'Satisfied users', 'Frustrated users')", "description": "Who falls in this segment", "size": "approximate count or percentage", "key_characteristics": ["trait1", "trait2"]}}
  ]

Return ONLY valid JSON, no markdown."""

        result = _ask_gemini_json(prompt, max_tokens=8192)

        if result and ("executive_summary" in result or "key_findings" in result):
            return result

        # Fallback
        return {
            "executive_summary": f"Analysis of {respondent_count} respondents for '{title}'. {completed_count} completed their interviews. Further data collection is recommended for more comprehensive insights.",
            "key_findings": [{"finding": "Insufficient data for detailed analysis", "evidence": "Limited completed interviews", "impact": "medium", "respondent_count": completed_count}],
            "sentiment_overview": {"overall": "neutral", "score": 0.0, "summary": "Not enough data to determine overall sentiment."},
            "pain_points": [],
            "positive_aspects": [],
            "per_question_analysis": [],
            "recommendations": [{"title": "Collect more responses", "description": "Share the survey link more widely to get statistically meaningful results.", "priority": "high", "category": "research", "expected_impact": "Better insights with more data"}],
            "themes_discovered": [],
            "respondent_segments": []
        }

    # ───────────────────────────────────────────────────────────
    # Consent Form Generation
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def generate_consent_form(title: str, goal: str) -> str:
        """Generate a professional research consent form using AI."""
        prompt = f"""You are a research ethics specialist. Generate a professional participant consent form for the following research study.

Study Title: "{title}"
Research Purpose: "{goal}"

The consent form should include these sections:
1. PURPOSE OF THE STUDY — What the research is about and why it matters
2. WHAT YOU WILL BE ASKED TO DO — Description of the interview process (conversational AI interview, ~5-10 minutes)
3. CONFIDENTIALITY — How data will be stored, anonymized, and protected
4. VOLUNTARY PARTICIPATION — That participation is voluntary and respondents can stop at any time
5. USE OF DATA — How the collected data will be used (research analysis, reports, product improvement)
6. CONTACT INFORMATION — A placeholder for the researcher's contact

IMPORTANT:
- Write in clear, simple language (8th grade reading level)
- Be concise — each section should be 2-3 sentences max
- Use plain text paragraphs with section headings in ALL CAPS
- Do NOT use HTML, markdown, or special formatting
- Keep the total form under 300 words
- End with: "By clicking 'I Agree' below, you confirm that you have read and understood this consent form and agree to participate."

Return ONLY the consent form text, nothing else."""

        result = _ask_gemini(prompt, max_tokens=800)
        if result and len(result.strip()) > 50:
            return result.strip()

        # Fallback: generic consent form
        return f"""PURPOSE OF THE STUDY
You are invited to participate in a research study titled \"{title}\". The purpose is to gather your experiences, opinions, and feedback to help improve our products and services.

WHAT YOU WILL BE ASKED TO DO
You will participate in a brief AI-powered interview lasting approximately 5-10 minutes. You will be asked questions about your experiences and opinions. You may answer via text, chat, or voice.

CONFIDENTIALITY
Your responses will be kept confidential. All data will be stored securely and will be anonymized in any reports or publications. Your personal information will not be shared with third parties.

VOLUNTARY PARTICIPATION
Your participation is entirely voluntary. You may stop the interview at any time without any consequences. You may skip any question you do not wish to answer.

USE OF DATA
The data collected will be used for research analysis, generating insights, and creating reports. Your feedback will help inform product decisions and improvements.

CONTACT INFORMATION
If you have questions about this study, please contact the research team at the organization that shared this survey link with you.

By clicking 'I Agree' below, you confirm that you have read and understood this consent form and agree to participate."""

    # ───────────────────────────────────────────────────────────
    # Feature 2: Dynamic Follow-Up Generation
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def generate_follow_up(response_text: str, context: dict = None) -> dict:
        """Generate a contextual follow-up question based on the respondent's answer."""
        ctx_str = ""
        if context:
            ctx_str = f"\nPrior conversation context: {json.dumps(context)[:400]}"

        prompt = f"""You are a warm, empathetic UX research interviewer conducting a live interview.
The respondent just said:
\"{response_text}\"
{ctx_str}

MULTILINGUAL SUPPORT:
- The respondent may reply in ANY language (Roman Urdu, Urdu, Hindi, English, or a mix).
- You MUST reply in the SAME language or mix the respondent is using.
- If they write in Roman Urdu, reply in Roman Urdu. If English, reply in English. If mixed, use the same mix.

Generate a JSON object with:
- "follow_up": your next conversational follow-up question or empathetic response + question (1-2 sentences, in the respondent's language)
- "intent": one of [complaint, praise, confusion, suggestion, neutral, emotional]
- "emotion": detected emotion (e.g. frustration, satisfaction, confusion, excitement, neutral)
- "sentiment_score": float -1.0 to 1.0
- "should_probe_deeper": boolean — true if the response needs more depth

Return ONLY valid JSON."""

        result = _ask_gemini_json(prompt)

        if result and "follow_up" in result:
            return result

        return _fallback_follow_up(response_text)

    # ───────────────────────────────────────────────────────────
    # Feature 3: Sentiment Analysis
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def analyze_sentiment(text: str) -> dict:
        """Analyse sentiment and emotion of text using Gemini."""
        prompt = f"""Analyse the following user response and return a JSON object with:
- "sentiment_label": "positive", "negative", or "neutral"
- "sentiment_score": float from -1.0 (very negative) to 1.0 (very positive)
- "emotion": the primary emotion (e.g. frustration, satisfaction, confusion, excitement, disappointment, trust, anger, neutral)
- "emotion_intensity": float 0-100
- "confidence": float 0.0-1.0

Text: \"{text}\"
Return ONLY valid JSON."""

        result = _ask_gemini_json(prompt)

        if result and "sentiment_label" in result:
            return result

        return _fallback_sentiment(text)

    # ───────────────────────────────────────────────────────────
    # Feature 4: Executive Summary Generation
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def generate_executive_summary(insights: list, tone: str = "professional", length: str = "detailed") -> dict:
        """Generate an executive summary narrative from insights using Gemini."""
        if not insights:
            return {
                "summary": "No insights available yet.",
                "narrative": "",
                "key_findings": [],
                "insight_count": 0,
                "total_responses": 0,
                "generated_at": datetime.now().isoformat(),
            }

        insight_summaries = []
        for ins in insights[:15]:
            insight_summaries.append({
                "title": ins.get("title", ""),
                "text": ins.get("insight_text", "")[:150],
                "category": ins.get("category", ""),
                "severity": ins.get("severity", ""),
                "confidence": ins.get("confidence", 0),
                "frequency": ins.get("frequency", 0),
                "impact": ins.get("impact_score", 0),
            })

        total_responses = sum(i.get("frequency", 0) for i in insights)

        prompt = f"""You are a senior UX research analyst writing an executive report.
Tone: {tone}  |  Length: {length}

Below are the top insights from user feedback analysis:
{json.dumps(insight_summaries, indent=2)}

Total user responses analysed: {total_responses}

Return a JSON object with:
- "executive_summary": a polished two-paragraph executive summary
- "narrative": a detailed narrative (3-5 paragraphs for 'detailed', 1-2 for 'brief')
- "key_findings": list of 4-6 bullet-point finding strings
- "overall_sentiment": float 0-1 representing positive sentiment ratio
- "positive_pct": integer percent
- "neutral_pct": integer percent
- "negative_pct": integer percent
- "response_rate": integer (estimate 70-95)
- "avg_completion_time": string like "4.2"

Return ONLY valid JSON."""

        result = _ask_gemini_json(prompt, max_tokens=3000)

        if result and ("executive_summary" in result or "summary" in result):
            result["insight_count"] = len(insights)
            result["total_responses"] = total_responses
            result["generated_at"] = datetime.now().isoformat()
            if "summary" not in result:
                result["summary"] = result.get("executive_summary", "")
            return result

        top = sorted(insights, key=lambda x: x.get("impact_score", 0), reverse=True)[:5]
        summary_parts = [
            f"{ins['title']} — {int(ins.get('confidence', 0) * 100)}% confidence ({ins.get('frequency', 0)} responses)"
            for ins in top
        ]
        return {
            "summary": "Key findings from user feedback analysis:\n\n" + "\n".join(f"• {s}" for s in summary_parts),
            "executive_summary": "Key findings from user feedback analysis.",
            "narrative": f"Analysis of {total_responses} user responses reveals {len(top)} critical areas.",
            "key_findings": summary_parts,
            "overall_sentiment": 0.65,
            "positive_pct": 65, "neutral_pct": 25, "negative_pct": 10,
            "response_rate": 85, "avg_completion_time": "4.5",
            "insight_count": len(insights),
            "total_responses": total_responses,
            "generated_at": datetime.now().isoformat(),
        }

    # ───────────────────────────────────────────────────────────
    # Feature 5: Response Quality Scoring
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def score_response_quality(response_text: str) -> dict:
        """Score the quality of a user response using Gemini."""
        prompt = f"""Rate the quality of this interview response on 4 dimensions (each 0.0-1.0):
Response: \"{response_text}\"

Return JSON with:
- "quality_score": overall quality 0.0-1.0
- "clarity": how clear the response is
- "depth": how much detail/insight it contains
- "relevance": estimated relevance (assume relevant topic)
- "word_count": integer count of words
- "needs_follow_up": boolean — true if the response is too shallow

Return ONLY valid JSON."""

        result = _ask_gemini_json(prompt)

        if result and "quality_score" in result:
            result.setdefault("word_count", len(response_text.split()))
            return result

        words = response_text.split()
        wc = len(words)
        clarity = min(1.0, wc / 20) if wc > 3 else 0.3
        depth = min(1.0, wc / 40) if wc > 5 else 0.2
        relevance = 0.8
        quality = round(clarity * 0.3 + depth * 0.4 + relevance * 0.3, 2)
        return {
            "quality_score": quality,
            "clarity": round(clarity, 2),
            "depth": round(depth, 2),
            "relevance": round(relevance, 2),
            "word_count": wc,
            "needs_follow_up": quality < 0.5,
        }

    # ───────────────────────────────────────────────────────────
    # Chat — full conversational AI response
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def generate_chat_response(message: str, history: list = None, survey_context: dict = None) -> str:
        """Generate a natural chat response for the AI interviewer."""
        history_text = ""
        if history:
            for h in history[-8:]:
                role = "Interviewer" if h.get("role") == "ai" else "User"
                history_text += f"{role}: {h.get('message', '')}\n"

        context_block = ""
        if survey_context:
            goal = survey_context.get("research_goal", "")
            questions = survey_context.get("questions", [])
            q_texts = [q.get("question_text", "") for q in questions[:10]]
            context_block = f"""
RESEARCH CONTEXT:
- Research Goal: {goal}
- Key questions to explore: {json.dumps(q_texts)}
- Stay focused on these topics. Ask questions that dig deeper into these areas.
"""

        prompt = f"""You are a friendly, empathetic AI research interviewer conducting a live interview.
{context_block}
Your job is to:
1. Ask insightful questions related to the research goal
2. Follow up on the user's answers to extract deeper insights
3. Be warm, conversational, and encouraging
4. Keep responses concise (1-3 sentences)
5. Always end with a relevant follow-up question
6. Reference specific things the user mentioned to show you're listening

Conversation so far:
{history_text}
User: {message}

Reply as the Interviewer (1-3 sentences, warm and professional, always ask a follow-up question):"""

        result = _ask_gemini(prompt, max_tokens=300)
        if result:
            return result
        # Dynamic fallback based on context
        return _dynamic_fallback_response(message, history, survey_context)

    # ───────────────────────────────────────────────────────────
    # Semantic Memory — extract entities & context from responses
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def extract_semantic_memory(response_text: str, existing_memory: list = None) -> list:
        """Extract semantic entities and relationships from a response for memory graph."""
        mem_context = ""
        if existing_memory:
            mem_context = f"\nExisting knowledge from this session:\n{json.dumps(existing_memory[:10])}\n"

        prompt = f"""You are a knowledge-graph extraction engine.
Extract key entities and relationships from the user's response below.
{mem_context}
User response: "{response_text}"

Return a JSON array of objects, each with:
- "entity": the subject (e.g. "checkout", "mobile app", "user")
- "relation": the relationship (e.g. "has_issue", "likes", "uses", "expects", "dislikes")
- "value": the object/detail (e.g. "freezing bug", "dark mode", "daily")
- "confidence": float 0.0-1.0

Return 2-6 entries. Return ONLY valid JSON array."""

        result = _ask_gemini_json(prompt)
        if isinstance(result, list) and len(result) > 0:
            return result
        # Fallback: simple entity extraction
        words = response_text.split()
        return [{"entity": "response", "relation": "contains", "value": " ".join(words[:5]), "confidence": 0.5}]

    # ───────────────────────────────────────────────────────────
    # Chat with Semantic Memory — enhanced context-aware response
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def generate_chat_response_with_memory(message: str, history: list = None, memory: list = None, survey_context: dict = None) -> str:
        """Generate a chat response enhanced with semantic memory and survey context."""
        history_text = ""
        if history:
            for h in history[-8:]:
                role = "Interviewer" if h.get("role") == "ai" else "User"
                history_text += f"{role}: {h.get('message', '')}\n"

        memory_text = ""
        if memory:
            memory_text = "\nKnown facts about this respondent:\n"
            for m in memory[:8]:
                memory_text += f"- {m.get('entity', '')} {m.get('relation', '')} {m.get('value', '')}\n"

        context_block = ""
        if survey_context:
            goal = survey_context.get("research_goal", "")
            questions = survey_context.get("questions", [])
            asked_count = len([h for h in (history or []) if h.get("role") == "ai"])
            q_texts = [q.get("question_text", "") for q in questions[:12]]
            context_block = f"""
RESEARCH CONTEXT:
- Research Goal: {goal}
- Survey questions to explore: {json.dumps(q_texts)}
- Questions already asked: approximately {asked_count}
- Total questions planned: {len(q_texts)}

IMPORTANT: Your task is to explore the research topics thoroughly. Use the survey questions as a guide but adapt based on the respondent's answers. If they mention something interesting, dig deeper before moving to the next topic.
"""

        prompt = f"""You are a world-class AI research interviewer conducting a live conversational interview.
{context_block}
{memory_text}
Your interviewing style:
1. Be warm, empathetic, and genuinely curious
2. Acknowledge what the user said before asking your next question
3. Ask ONE clear follow-up question at the end of each response
4. Use the known facts to make your questions more targeted and relevant
5. If the user gives a short answer, gently probe deeper with "Could you tell me more about that?" or "What specifically..."
6. If the user gives a detailed answer, validate their experience and explore a related angle
7. Keep responses to 1-3 sentences plus your question
8. NEVER repeat a question that was already asked

MULTILINGUAL SUPPORT — CRITICAL:
- The respondent may reply in ANY language: English, Urdu, Roman Urdu (Urdu written in English script), Hindi, Arabic, or any other language.
- ALWAYS respond in the SAME language the respondent is currently using. If they write in Roman Urdu, reply in Roman Urdu. If they switch to English, switch to English.
- If the respondent mixes languages (e.g., English + Roman Urdu), you may also mix naturally.
- Regardless of language, keep exploring the research topics thoroughly.
- Example: If user says "Mujhe yeh feature bohat acha laga" reply in Roman Urdu like "Yeh sun kar acha laga! Kya aap bata sakte hain ke kaunsa feature sabse zyada helpful tha?"

Conversation so far:
{history_text}
User: {message}

Reply as the Interviewer (acknowledge their response warmly in their language, then ask a relevant follow-up question):"""

        result = _ask_gemini(prompt, max_tokens=350)
        if result:
            return result
        # Dynamic fallback
        return _dynamic_fallback_response(message, history, survey_context)

    # ───────────────────────────────────────────────────────────
    # Theme Clustering — real-time LLM-powered clustering
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def cluster_themes_from_responses(responses: list, existing_themes: list = None) -> list:
        """Cluster responses into themes using AI. Returns new/updated themes."""
        resp_texts = [r.get("response_text", "")[:200] for r in responses[:20]]
        existing_str = ""
        if existing_themes:
            existing_str = f"\nExisting themes: {json.dumps([{'name': t.get('name',''), 'description': t.get('description','')} for t in existing_themes[:10]])}"

        prompt = f"""You are a UX research analyst. Analyze these user responses and identify key themes.
{existing_str}

User responses:
{json.dumps(resp_texts)}

Return a JSON array of themes. Each theme has:
- "name": short theme name (2-4 words)
- "description": one sentence description
- "sentiment_avg": float -1.0 to 1.0
- "priority": "high", "medium", or "low"
- "business_risk": "high", "medium", or "low"
- "is_emerging": boolean (true if this is a new pattern)
- "matched_responses": list of indices (0-based) from the responses array

If an existing theme matches, use the same name. Add new themes as needed.
Return 3-8 themes. Return ONLY valid JSON array."""

        result = _ask_gemini_json(prompt, max_tokens=2048)
        if isinstance(result, list) and len(result) > 0:
            return result
        return [{"name": "General Feedback", "description": "Uncategorized user feedback", "sentiment_avg": 0.0, "priority": "medium", "business_risk": "low", "is_emerging": False, "matched_responses": list(range(len(resp_texts)))}]

    # ───────────────────────────────────────────────────────────
    # Response Segmentation — split multi-topic responses
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def segment_response(response_text: str) -> list:
        """Segment a multi-topic response into individual topic segments."""
        if len(response_text.split()) < 15:
            return [{
                "segment_text": response_text,
                "topic": "single_topic",
                "sentiment_label": "neutral",
                "sentiment_score": 0.0,
                "emotion": "neutral",
                "confidence": 0.9
            }]

        prompt = f"""You are a response analysis engine. The user's interview response below may touch on multiple topics.
Split it into distinct topic segments.

Response: "{response_text}"

Return a JSON array of segments. Each segment has:
- "segment_text": the exact portion of text (or close paraphrase) for this topic
- "topic": short topic label (2-4 words)
- "sentiment_label": "positive", "negative", or "neutral"
- "sentiment_score": float -1.0 to 1.0
- "emotion": primary emotion
- "confidence": float 0.0-1.0

If the response is single-topic, return one segment.
Return ONLY valid JSON array."""

        result = _ask_gemini_json(prompt)
        if isinstance(result, list) and len(result) > 0:
            return result
        return [{
            "segment_text": response_text,
            "topic": "general",
            "sentiment_label": "neutral",
            "sentiment_score": 0.0,
            "emotion": "neutral",
            "confidence": 0.7
        }]

    # ───────────────────────────────────────────────────────────
    # Intake Clarification — Multi-step conversational intake
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def generate_intake_clarification(user_input: str, conversation: list = None) -> dict:
        """Analyze user's research description and either ask clarifying questions or confirm readiness.
        Specifically ensures target audiences are identified before proceeding."""
        conv_text = ""
        if conversation:
            for msg in conversation:
                role = "User" if msg.get("role") == "user" else "AI Assistant"
                conv_text += f"{role}: {msg.get('message', '')}\n"

        prompt = f"""You are an expert UX research consultant helping a user design their survey.
The user is describing what they want to research. Your job is to understand their needs deeply.

Conversation so far:
{conv_text}
User's latest input: "{user_input}"

Analyze what the user has told you so far. Determine if you have enough information to create excellent, targeted survey questions. You MUST know:
1. The specific problem or topic they want to research
2. Their TARGET AUDIENCES (this is CRITICAL) — you need to know the specific groups/segments of people they want to survey (e.g., "college students, working professionals, retirees" or "free users, premium users, churned users")
3. What they hope to learn or achieve
4. Any specific areas or hypotheses they want to explore

IMPORTANT: If the user has NOT yet specified their target audiences, you MUST ask about them. This is non-negotiable because we will generate audience-specific questions for each target audience plus a generic survey.

If you DON'T have enough information (especially target audiences), ask 1-2 specific clarifying questions. Make sure to ask about target audiences if not provided.
If you DO have enough information (including clear target audiences), indicate you're ready to generate questions.

Return a JSON object with:
- "has_enough_info": boolean (true ONLY if you have enough info INCLUDING target audiences)
- "ai_message": your response message (either clarifying questions or a confirmation that you're ready)
- "extracted_context": {{
    "topic": "the main research topic",
    "audience": "target audience if mentioned",
    "target_audiences": ["list", "of", "specific", "target", "audience", "segments"],
    "objectives": ["list of research objectives identified so far"],
    "specific_areas": ["specific areas or hypotheses to explore"]
  }}

Keep your message conversational, warm, and brief (2-4 sentences).
Return ONLY valid JSON, no markdown."""

        result = _ask_gemini_json(prompt, max_tokens=1024)
        if result and "ai_message" in result:
            return result

        # Fallback: if we have a decent amount of text, proceed
        word_count = len(user_input.split())
        has_enough = word_count >= 20 or (conversation and len(conversation) >= 3)
        if has_enough:
            return {
                "has_enough_info": True,
                "ai_message": "Great, I have a good understanding of what you're looking for! Let me generate targeted questions for your research.",
                "extracted_context": {
                    "topic": user_input[:100],
                    "audience": "Target users",
                    "target_audiences": ["General Users"],
                    "objectives": ["Understand user experience", "Identify pain points"],
                    "specific_areas": []
                }
            }
        return {
            "has_enough_info": False,
            "ai_message": "That's a great start! To create the most targeted questions, I need to know: **Who are your target audiences?** Please list the specific groups or segments you want to survey (e.g., 'new users, power users, churned users'). I'll generate tailored questions for each audience plus a generic survey for everyone.",
            "extracted_context": {
                "topic": user_input[:100],
                "audience": "",
                "target_audiences": [],
                "objectives": [],
                "specific_areas": []
            }
        }

    # ───────────────────────────────────────────────────────────
    # AI Simulated Interview — AI acts as respondent
    # ───────────────────────────────────────────────────────────
    @staticmethod
    def simulate_interview(questions: list, persona: str = None) -> dict:
        """Run a simulated interview where AI plays the respondent."""
        if not persona:
            persona = "A tech-savvy millennial user who has been using the app for 3 months and has mixed feelings about it"

        questions_formatted = "\n".join([f"{i+1}. {q.get('question_text', q) if isinstance(q, dict) else q}" for i, q in enumerate(questions[:12])])

        prompt = f"""You are a simulated user being interviewed for UX research.
Your persona: {persona}

You are being asked the following interview questions. Answer each one naturally, as this persona would.
Be authentic — include both positive and negative feedback, emotions, specific examples, and realistic detail.
Vary your response length (some short, some detailed).

Questions:
{questions_formatted}

Return a JSON object with:
- "persona_summary": 1-sentence description of who you're roleplaying
- "responses": [
    {{
      "question": "the question text",
      "response": "your natural answer (1-4 sentences)",
      "sentiment": "positive|negative|neutral|mixed",
      "emotion": "primary emotion",
      "confidence": float 0.5-1.0 (how confident this persona would be)
    }}
  ]
- "overall_sentiment": "positive|negative|neutral|mixed"
- "key_themes": ["list of 3-5 themes from the simulated responses"]

Return ONLY valid JSON."""

        result = _ask_gemini_json(prompt, max_tokens=4096)
        if result and "responses" in result:
            return result

        # Fallback
        return {
            "persona_summary": persona,
            "responses": [
                {
                    "question": q.get("question_text", str(q)) if isinstance(q, dict) else str(q),
                    "response": "I have mixed feelings about this aspect of the product.",
                    "sentiment": "mixed",
                    "emotion": "neutral",
                    "confidence": 0.6
                }
                for q in questions[:12]
            ],
            "overall_sentiment": "mixed",
            "key_themes": ["usability", "feature requests", "general feedback"]
        }


# ═══════════════════════════════════════════════════════════════
# Fallback helpers (used when Gemini call fails)
# ═══════════════════════════════════════════════════════════════

def _fallback_questions(research_type: str, count: int) -> list:
    bank = {
        "discovery": [
            {"question_text": "Tell me about your overall experience with the product.", "question_type": "open_ended", "tone": "friendly", "depth": 1},
            {"question_text": "What was the first thing you noticed when you started using it?", "question_type": "open_ended", "tone": "curious", "depth": 1},
            {"question_text": "Walk me through a typical session — what do you usually do?", "question_type": "open_ended", "tone": "conversational", "depth": 2},
            {"question_text": "Was there a moment where you felt frustrated or confused?", "question_type": "open_ended", "tone": "empathetic", "depth": 2},
            {"question_text": "If you could change one thing, what would it be?", "question_type": "open_ended", "tone": "encouraging", "depth": 2},
            {"question_text": "How does this compare to other tools you've used?", "question_type": "open_ended", "tone": "neutral", "depth": 3},
            {"question_text": "How likely are you to recommend this product? (1-5)", "question_type": "rating", "tone": "neutral", "depth": 1},
            {"question_text": "What would make you recommend this to a friend?", "question_type": "open_ended", "tone": "warm", "depth": 2},
        ],
        "churn_analysis": [
            {"question_text": "What initially brought you to our product?", "question_type": "open_ended", "tone": "friendly", "depth": 1},
            {"question_text": "What made you stop using it or use it less?", "question_type": "open_ended", "tone": "empathetic", "depth": 2},
            {"question_text": "Were there specific features that didn't meet expectations?", "question_type": "open_ended", "tone": "curious", "depth": 2},
            {"question_text": "Did you switch to another solution? If so, why?", "question_type": "open_ended", "tone": "neutral", "depth": 3},
            {"question_text": "What would need to change for you to come back?", "question_type": "open_ended", "tone": "encouraging", "depth": 2},
            {"question_text": "Rate your overall experience from 1-5.", "question_type": "rating", "tone": "neutral", "depth": 1},
        ],
    }
    questions = bank.get(research_type, bank["discovery"])
    return questions[:count]


def _fallback_follow_up(response_text: str) -> dict:
    rl = response_text.lower()
    if any(w in rl for w in ["frustrat", "annoying", "hate", "terrible"]):
        return {"follow_up": "I can sense that was frustrating. Could you walk me through what happened?",
                "intent": "complaint", "emotion": "frustration", "sentiment_score": -0.8, "should_probe_deeper": True}
    if any(w in rl for w in ["love", "great", "amazing", "excellent"]):
        return {"follow_up": "That's great to hear! What specifically made it great?",
                "intent": "praise", "emotion": "satisfaction", "sentiment_score": 0.8, "should_probe_deeper": False}
    if any(w in rl for w in ["confus", "unclear", "lost"]):
        return {"follow_up": "That sounds confusing. Which part was unclear?",
                "intent": "confusion", "emotion": "confusion", "sentiment_score": -0.5, "should_probe_deeper": True}
    return {"follow_up": "Thank you for sharing. Could you give me a specific example?",
            "intent": "neutral", "emotion": "neutral", "sentiment_score": 0.0, "should_probe_deeper": True}


def _fallback_sentiment(text: str) -> dict:
    tl = text.lower()
    neg = ["bad", "terrible", "hate", "frustrat", "annoying", "slow", "crash", "confus", "broken"]
    pos = ["love", "great", "amazing", "perfect", "excellent", "fast", "easy", "helpful"]
    nc = sum(1 for w in neg if w in tl)
    pc = sum(1 for w in pos if w in tl)
    if nc > pc:
        return {"sentiment_label": "negative", "sentiment_score": round(-0.3 - nc * 0.15, 2),
                "emotion": "frustration", "emotion_intensity": 65.0, "confidence": 0.80}
    if pc > nc:
        return {"sentiment_label": "positive", "sentiment_score": round(0.3 + pc * 0.15, 2),
                "emotion": "satisfaction", "emotion_intensity": 60.0, "confidence": 0.80}
    return {"sentiment_label": "neutral", "sentiment_score": 0.0,
            "emotion": "neutral", "emotion_intensity": 30.0, "confidence": 0.75}


def _dynamic_fallback_response(message: str, history: list = None, survey_context: dict = None) -> str:
    """Generate a contextual fallback response when Gemini is unavailable."""
    ml = message.lower()
    msg_count = len(history) if history else 0

    # Try to use survey context for topic-aware fallbacks
    topic = ""
    if survey_context:
        topic = survey_context.get("research_goal", "")[:80]

    # Detect message sentiment/intent for varied responses
    if any(w in ml for w in ["frustrat", "annoying", "hate", "terrible", "bad", "awful"]):
        return "I can really hear your frustration there. That sounds like a difficult experience. Could you walk me through exactly what happened? The specific details really help us understand the issue better."
    if any(w in ml for w in ["love", "great", "amazing", "excellent", "awesome", "best"]):
        return "That's wonderful to hear! It's great when things work well. What specifically made that experience stand out for you? I'd love to understand what we're doing right."
    if any(w in ml for w in ["confus", "unclear", "don't understand", "lost"]):
        return "I appreciate you sharing that — clarity is so important. Could you point me to the specific part that felt confusing? Understanding exactly where the confusion starts helps us fix it."

    # Varied follow-up responses based on conversation progress
    follow_ups = [
        f"That's really insightful, thank you for sharing. {'In the context of ' + topic + ', ' if topic else ''}could you give me a specific example of what you mean?",
        f"I appreciate that perspective! {'Thinking about ' + topic + ', ' if topic else ''}what impact has this had on your experience overall?",
        f"That's a great point. Can you think of a time when this was particularly noticeable? I'd love to hear the details.",
        f"Interesting! {'Regarding ' + topic + ', ' if topic else ''}how does this compare to what you expected or experienced elsewhere?",
        f"Thank you for that! If you could change one thing about this, what would it be and why?",
        f"That really helps me understand your perspective. {'On the topic of ' + topic + ', ' if topic else ''}what would make this experience better for you?",
    ]

    idx = msg_count % len(follow_ups)
    return follow_ups[idx]
