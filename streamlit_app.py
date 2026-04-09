import os
import time
from typing import Any, Dict, List

import streamlit as st


# Load Streamlit secrets into environment before backend modules import config.
for _key in [
    "GEMINI_API_KEY",
    "ASSEMBLYAI_API_KEY",
    "JWT_SECRET",
    "DATA_DIR",
    "GOOGLE_CLIENT_ID",
    "GOOGLE_CLIENT_SECRET",
    "GOOGLE_REDIRECT_URI",
]:
    if _key in st.secrets and not os.getenv(_key):
        os.environ[_key] = str(st.secrets[_key])

from backend.database import DB_PATH, get_db, init_db
from backend.services.ai_service import AIService
from backend.services.survey_service import SurveyService


st.set_page_config(
    page_title="AI Survey Software - Streamlit",
    page_icon="AI",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_resource
def bootstrap() -> Dict[str, Any]:
    init_db()
    return {"db_path": DB_PATH, "started_at": time.time()}


def db_scalar(sql: str, params: tuple = ()) -> int:
    conn = get_db()
    try:
        row = conn.execute(sql, params).fetchone()
        if not row:
            return 0
        keys = row.keys()
        if not keys:
            return 0
        return int(row[keys[0]])
    finally:
        conn.close()


def load_surveys() -> List[Dict[str, Any]]:
    try:
        return SurveyService.list_surveys()
    except Exception:
        return []


def save_generated_survey(
    title: str,
    goal_text: str,
    research_type: str,
    generated_questions: List[Dict[str, Any]],
) -> int:
    goal = SurveyService.create_goal(
        title=title,
        description=goal_text,
        research_type=research_type,
    )
    survey = SurveyService.create_survey(
        research_goal_id=goal["id"],
        title=title,
        description=goal_text,
        channel_type="multi",
        estimated_duration=10,
        interview_style="balanced",
    )

    for idx, q in enumerate(generated_questions):
        follow_up_seeds = q.get("follow_ups")
        if follow_up_seeds is not None:
            follow_up_seeds = str(follow_up_seeds)

        SurveyService.create_question(
            survey_id=survey["id"],
            question_text=q.get("question_text", "Untitled question"),
            question_type=q.get("question_type", "open_ended"),
            order_index=idx,
            is_required=True,
            follow_up_seeds=follow_up_seeds,
            tone=q.get("tone", "neutral"),
            depth_level=int(q.get("depth", 1) or 1),
        )

    return int(survey["id"])


def app_sidebar(db_path: str) -> None:
    st.sidebar.title("Deployment")
    st.sidebar.caption("Streamlit-ready control panel")

    st.sidebar.markdown("### Environment")
    st.sidebar.write(f"DB: `{db_path}`")
    st.sidebar.write(
        "Gemini API key: "
        + ("Configured" if bool(os.getenv("GEMINI_API_KEY")) else "Missing")
    )
    st.sidebar.write(
        "AssemblyAI key: "
        + ("Configured" if bool(os.getenv("ASSEMBLYAI_API_KEY")) else "Missing")
    )

    st.sidebar.markdown("### Notes")
    st.sidebar.info(
        "This Streamlit app uses your existing backend service layer directly. "
        "Set secrets in Streamlit Cloud for AI features."
    )


def app_overview() -> None:
    st.subheader("Overview")

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Surveys", db_scalar("SELECT COUNT(*) AS c FROM surveys"))
    with col2:
        st.metric("Questions", db_scalar("SELECT COUNT(*) AS c FROM questions"))
    with col3:
        st.metric("Sessions", db_scalar("SELECT COUNT(*) AS c FROM interview_sessions"))
    with col4:
        st.metric("Responses", db_scalar("SELECT COUNT(*) AS c FROM responses"))

    st.markdown("---")
    st.write("Recent surveys")
    surveys = load_surveys()
    if not surveys:
        st.info("No surveys yet. Use the Create Survey tab to generate one.")
        return

    for s in surveys[:10]:
        with st.container(border=True):
            st.write(f"**#{s.get('id')} - {s.get('title', 'Untitled')}**")
            st.caption(
                f"Status: {s.get('status', 'draft')} | "
                f"Channel: {s.get('channel_type', 'web')} | "
                f"Created: {s.get('created_at', '-') }"
            )


def app_create_survey() -> None:
    st.subheader("Create Survey")
    st.caption("Generate AI questions and save them to the existing SQLite database.")

    with st.form("create_survey_form"):
        title = st.text_input("Survey title", placeholder="e.g. Customer Onboarding Feedback")
        goal_text = st.text_area(
            "Research goal",
            placeholder="Describe what you want to learn from respondents.",
            height=140,
        )
        c1, c2 = st.columns(2)
        with c1:
            research_type = st.selectbox(
                "Research type",
                options=[
                    "discovery",
                    "churn_analysis",
                    "satisfaction",
                    "usability",
                    "pricing",
                    "feature_feedback",
                ],
            )
        with c2:
            question_count = st.slider("Question count", min_value=5, max_value=12, value=8)

        submitted = st.form_submit_button("Generate with AI", type="primary")

    if submitted:
        if not title.strip() or not goal_text.strip():
            st.error("Please provide both title and research goal.")
            return

        with st.spinner("Generating survey structure and questions..."):
            try:
                parsed = SurveyService.ai_parse_goal(goal_text)
                deep = SurveyService.ai_generate_deep_questions(goal_text, research_type, question_count)

                st.session_state["generated"] = {
                    "title": title,
                    "goal_text": goal_text,
                    "research_type": research_type,
                    "parsed": parsed,
                    "deep": deep,
                }
                st.success("AI generation complete.")
            except Exception as e:
                st.error(f"Generation failed: {e}")
                return

    generated = st.session_state.get("generated")
    if not generated:
        return

    parsed = generated.get("parsed", {})
    deep = generated.get("deep", {})
    questions = deep.get("questions", [])

    st.markdown("### AI analysis")
    st.write(parsed if parsed else deep.get("analysis", {}))

    st.markdown("### Generated questions")
    if not questions:
        st.warning("No questions generated. Check your API key and try again.")
    else:
        for idx, q in enumerate(questions, start=1):
            with st.expander(f"Q{idx}: {q.get('question_text', 'Untitled')}", expanded=idx == 1):
                st.write(f"Type: {q.get('question_type', 'open_ended')}")
                st.write(f"Tone: {q.get('tone', 'neutral')} | Depth: {q.get('depth', 1)}")
                follow_ups = q.get("follow_ups", [])
                if follow_ups:
                    st.write("Follow-ups:")
                    for fu in follow_ups:
                        if isinstance(fu, dict):
                            st.write(f"- {fu.get('question_text', '')}")
                        else:
                            st.write(f"- {fu}")

        if st.button("Save survey to database", type="secondary"):
            try:
                survey_id = save_generated_survey(
                    title=generated["title"],
                    goal_text=generated["goal_text"],
                    research_type=generated["research_type"],
                    generated_questions=questions,
                )
                st.success(f"Survey saved successfully with ID: {survey_id}")
            except Exception as e:
                st.error(f"Save failed: {e}")


def app_survey_library() -> None:
    st.subheader("Survey Library")
    surveys = load_surveys()
    if not surveys:
        st.info("No surveys available yet.")
        return

    options = {f"#{s['id']} - {s.get('title', 'Untitled')}": s for s in surveys}
    selected_label = st.selectbox("Select survey", list(options.keys()))
    selected = options[selected_label]

    st.write(selected)

    st.markdown("### Optional consent form generation")
    consent_title = st.text_input("Consent form title", value=selected.get("title", "Research Survey"))
    consent_goal = st.text_area("Consent form goal", value=selected.get("description", ""), height=100)

    if st.button("Generate consent form"):
        try:
            form_text = AIService.generate_consent_form(consent_title, consent_goal)
            st.text_area("Generated consent form", form_text, height=300)
        except Exception as e:
            st.error(f"Could not generate consent form: {e}")


def main() -> None:
    bootstrap_info = bootstrap()
    app_sidebar(bootstrap_info["db_path"])

    st.title("AI Survey Software - Streamlit Deployment")
    st.caption("Operational Streamlit frontend for survey creation and monitoring")

    tab1, tab2, tab3 = st.tabs(["Overview", "Create Survey", "Survey Library"])

    with tab1:
        app_overview()
    with tab2:
        app_create_survey()
    with tab3:
        app_survey_library()


if __name__ == "__main__":
    main()
