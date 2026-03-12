"""
Analytics & Feedback Routes — Founder Insights Dashboard
═══════════════════════════════════════════════════════════════
Provides comprehensive analytics for website usage, user feedback,
and respondent experience tracking for the founder.

Features:
- Website traffic and user behavior analytics
- User feedback collection and management
- Respondent experience tracking (quick 30-second feedback)
- Daily/weekly/monthly metrics aggregation
- Real-time dashboard data
"""

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Optional, List, Dict, Any
from datetime import datetime, timedelta, date
from pydantic import BaseModel, Field
import sqlite3
import json
import uuid
try:
    import user_agents
except ImportError:
    user_agents = None

from ..auth import get_current_user_optional, get_current_user
from ..database import get_db, get_db_connection
from ..services.metrics_service import MetricsService

router = APIRouter()


def _parse_user_agent_info(user_agent_str: str) -> tuple[str, str]:
    """Parse user-agent safely with graceful fallback when dependency is unavailable."""
    if user_agents:
        ua = user_agents.parse(user_agent_str)
        device_type = "mobile" if ua.is_mobile else "tablet" if ua.is_tablet else "desktop"
        browser = f"{ua.browser.family} {ua.browser.version_string}".strip()
        return device_type, browser

    ua_lower = (user_agent_str or "").lower()
    if "mobile" in ua_lower or "android" in ua_lower or "iphone" in ua_lower:
        device_type = "mobile"
    elif "tablet" in ua_lower or "ipad" in ua_lower:
        device_type = "tablet"
    else:
        device_type = "desktop"

    if "edg/" in ua_lower:
        browser = "Edge"
    elif "chrome/" in ua_lower:
        browser = "Chrome"
    elif "firefox/" in ua_lower:
        browser = "Firefox"
    elif "safari/" in ua_lower:
        browser = "Safari"
    else:
        browser = "Unknown"

    return device_type, browser

# ═════════════════════════════════════════════════════════════
# MODELS — Request/Response validation
# ═════════════════════════════════════════════════════════════

class WebsiteAnalyticsRequest(BaseModel):
    page_url: str = Field(..., max_length=500)
    page_title: Optional[str] = Field(None, max_length=200)
    referrer: Optional[str] = Field(None, max_length=500)
    time_on_page: Optional[int] = Field(0, ge=0)
    exit_page: Optional[bool] = Field(False)
    conversion_event: Optional[str] = Field(None, max_length=100)

class UserFeedbackRequest(BaseModel):
    feedback_type: str = Field("general", max_length=50)
    rating: Optional[int] = Field(None, ge=1, le=5)
    title: Optional[str] = Field(None, max_length=200)
    description: str = Field(..., max_length=2000)
    feature_area: Optional[str] = Field(None, max_length=100)
    priority: str = Field("medium", max_length=20)
    browser_info: Optional[str] = Field(None, max_length=500)
    url_context: Optional[str] = Field(None, max_length=500)

class RespondentExperienceRequest(BaseModel):
    session_id: str = Field(..., max_length=100)
    survey_id: int = Field(..., gt=0)
    overall_rating: Optional[int] = Field(None, ge=1, le=5)
    easiness_rating: Optional[int] = Field(None, ge=1, le=5)
    clarity_rating: Optional[int] = Field(None, ge=1, le=5)
    time_rating: Optional[int] = Field(None, ge=1, le=5)
    technical_issues: Optional[bool] = Field(False)
    would_recommend: Optional[bool] = Field(None)
    quick_feedback: Optional[str] = Field(None, max_length=500)
    improvement_suggestion: Optional[str] = Field(None, max_length=500)
    completion_time: Optional[int] = Field(None, ge=0)
    device_type: Optional[str] = Field(None, max_length=50)
    channel_used: Optional[str] = Field(None, max_length=50)

class FeatureUsageRequest(BaseModel):
    feature_name: str = Field(..., max_length=100)
    action: str = Field(..., max_length=100)
    survey_id: Optional[int] = Field(None, gt=0)
    metadata: Optional[Dict[str, Any]] = Field(default_factory=dict)
    session_duration: Optional[int] = Field(None, ge=0)
    success: Optional[bool] = Field(True)

# ═════════════════════════════════════════════════════════════
# ANALYTICS COLLECTION ENDPOINTS
# ═════════════════════════════════════════════════════════════

@router.post("/track/page-view")
async def track_page_view(
    analytics_data: WebsiteAnalyticsRequest,
    request: Request,
    current_user = Depends(get_current_user_optional)
):
    """Track page views and user navigation for website analytics."""
    
    # Extract request metadata
    user_agent = request.headers.get("user-agent", "")
    ip_address = request.client.host
    
    # Parse user agent for device info
    device_type, browser = _parse_user_agent_info(user_agent)
    
    # Generate session ID if not present in cookies
    session_id = request.cookies.get("session_id", str(uuid.uuid4()))
    
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO website_analytics (
                user_id, session_id, page_url, page_title, referrer,
                user_agent, ip_address, device_type, browser,
                time_on_page, exit_page, conversion_event
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            current_user["id"] if current_user else None,
            session_id,
            analytics_data.page_url,
            analytics_data.page_title,
            analytics_data.referrer,
            user_agent,
            ip_address,
            device_type,
            browser,
            analytics_data.time_on_page,
            1 if analytics_data.exit_page else 0,
            analytics_data.conversion_event
        ))
    
    # Return session_id for frontend tracking
    response = JSONResponse({"success": True, "session_id": session_id})
    response.set_cookie("session_id", session_id, max_age=86400)  # 24 hours
    return response

@router.post("/feedback/user")
async def submit_user_feedback(
    feedback_data: UserFeedbackRequest,
    request: Request,
    current_user = Depends(get_current_user_optional)
):
    """Submit feedback about the software from users."""
    
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO user_feedback (
                user_id, feedback_type, rating, title, description,
                feature_area, priority, browser_info, url_context
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            current_user["id"] if current_user else None,
            feedback_data.feedback_type,
            feedback_data.rating,
            feedback_data.title,
            feedback_data.description,
            feedback_data.feature_area,
            feedback_data.priority,
            feedback_data.browser_info,
            feedback_data.url_context
        ))
    
    return {"success": True, "message": "Thank you for your feedback!"}

@router.post("/feedback/respondent")
async def submit_respondent_experience(
    experience_data: RespondentExperienceRequest,
    request: Request,
    current_user = Depends(get_current_user_optional)
):
    """Submit quick experience feedback from survey respondents (max 30 seconds)."""
    
    # Extract device info from request
    user_agent = request.headers.get("user-agent", "")
    device_type, _ = _parse_user_agent_info(user_agent)
    
    # Get respondent ID if available
    respondent_id = None
    if current_user:
        with get_db_connection() as conn:
            result = conn.execute("""
                SELECT id FROM respondents WHERE email = ?
            """, (current_user["email"],)).fetchone()
            if result:
                respondent_id = result[0]
    
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO respondent_experience (
                session_id, survey_id, respondent_id, overall_rating,
                easiness_rating, clarity_rating, time_rating, technical_issues,
                would_recommend, quick_feedback, improvement_suggestion,
                completion_time, device_type, channel_used
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            experience_data.session_id,
            experience_data.survey_id,
            respondent_id,
            experience_data.overall_rating,
            experience_data.easiness_rating,
            experience_data.clarity_rating,
            experience_data.time_rating,
            1 if experience_data.technical_issues else 0,
            1 if experience_data.would_recommend else (0 if experience_data.would_recommend is False else None),
            experience_data.quick_feedback,
            experience_data.improvement_suggestion,
            experience_data.completion_time,
            device_type,
            experience_data.channel_used
        ))
    
    return {"success": True, "message": "Thank you for sharing your experience!"}

@router.post("/track/feature-usage")
async def track_feature_usage(
    usage_data: FeatureUsageRequest,
    request: Request,
    current_user = Depends(get_current_user_optional)
):
    """Track specific feature usage for product analytics."""
    
    with get_db_connection() as conn:
        conn.execute("""
            INSERT INTO feature_usage (
                user_id, survey_id, feature_name, action,
                metadata_json, session_duration, success
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            current_user["id"] if current_user else None,
            usage_data.survey_id,
            usage_data.feature_name,
            usage_data.action,
            json.dumps(usage_data.metadata),
            usage_data.session_duration,
            1 if usage_data.success else 0
        ))
    
    return {"success": True}

# ═════════════════════════════════════════════════════════════
# ANALYTICS DASHBOARD ENDPOINTS (Founder Only)
# ═════════════════════════════════════════════════════════════

@router.get("/dashboard/overview")
async def get_dashboard_overview(
    days: int = 30,
    current_user = Depends(get_current_user)
):
    """Get comprehensive analytics overview for the founder dashboard."""
    
    # Ensure only founder/admin can access
    if current_user["role"] != "founder" and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    with get_db_connection() as conn:
        # Website traffic metrics
        traffic_stats = conn.execute("""
            SELECT 
                COUNT(*) as page_views,
                COUNT(DISTINCT session_id) as unique_sessions,
                COUNT(DISTINCT user_id) as logged_in_users,
                AVG(time_on_page) as avg_time_on_page,
                COUNT(DISTINCT ip_address) as unique_visitors
            FROM website_analytics 
            WHERE created_at >= ?
        """, (start_date.isoformat(),)).fetchone()
        
        # User engagement metrics
        user_stats = conn.execute("""
            SELECT 
                COUNT(DISTINCT id) as total_users,
                COUNT(DISTINCT CASE WHEN last_login >= ? THEN id END) as active_users,
                COUNT(DISTINCT CASE WHEN created_at >= ? THEN id END) as new_signups
            FROM users
        """, (start_date.isoformat(), start_date.isoformat())).fetchone()
        
        # Survey metrics
        survey_stats = conn.execute("""
            SELECT 
                COUNT(DISTINCT s.id) as surveys_created,
                COUNT(DISTINCT sp.id) as surveys_published,
                COUNT(DISTINCT r.id) as responses_collected,
                AVG(re.overall_rating) as avg_respondent_rating
            FROM surveys s
            LEFT JOIN survey_publications sp ON s.id = sp.survey_id
            LEFT JOIN responses r ON s.id = r.survey_id AND r.created_at >= ?
            LEFT JOIN respondent_experience re ON s.id = re.survey_id AND re.created_at >= ?
            WHERE s.created_at >= ?
        """, (start_date.isoformat(), start_date.isoformat(), start_date.isoformat())).fetchone()
        
        # Feedback metrics
        feedback_stats = conn.execute("""
            SELECT 
                COUNT(*) as total_feedback,
                AVG(rating) as avg_user_rating,
                COUNT(DISTINCT CASE WHEN feedback_type = 'bug' THEN id END) as bug_reports,
                COUNT(DISTINCT CASE WHEN feedback_type = 'feature_request' THEN id END) as feature_requests
            FROM user_feedback 
            WHERE created_at >= ?
        """, (start_date.isoformat(),)).fetchone()
        
        # Top pages and conversion events
        top_pages = conn.execute("""
            SELECT page_url, COUNT(*) as views
            FROM website_analytics 
            WHERE created_at >= ?
            GROUP BY page_url
            ORDER BY views DESC
            LIMIT 10
        """, (start_date.isoformat(),)).fetchall()
        
        # Daily traffic trend
        daily_trend = conn.execute("""
            SELECT 
                DATE(created_at) as date,
                COUNT(*) as page_views,
                COUNT(DISTINCT session_id) as unique_sessions
            FROM website_analytics 
            WHERE created_at >= ?
            GROUP BY DATE(created_at)
            ORDER BY date DESC
        """, (start_date.isoformat(),)).fetchall()
    
    return {
        "period_days": days,
        "traffic": dict(traffic_stats) if traffic_stats else {},
        "users": dict(user_stats) if user_stats else {},
        "surveys": dict(survey_stats) if survey_stats else {},
        "feedback": dict(feedback_stats) if feedback_stats else {},
        "top_pages": [dict(page) for page in top_pages],
        "daily_trend": [dict(day) for day in daily_trend],
        "system_metrics": MetricsService.get_system_metrics(),
        "generated_at": datetime.now().isoformat()
    }

@router.get("/dashboard/user-feedback")
async def get_user_feedback_dashboard(
    status: Optional[str] = None,
    feedback_type: Optional[str] = None,
    limit: int = 50,
    current_user = Depends(get_current_user)
):
    """Get detailed user feedback for founder review."""
    
    if current_user["role"] != "founder" and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    conditions = []
    params = []
    
    if status:
        conditions.append("uf.status = ?")
        params.append(status)
    
    if feedback_type:
        conditions.append("uf.feedback_type = ?")
        params.append(feedback_type)
    
    where_clause = "WHERE " + " AND ".join(conditions) if conditions else ""
    params.append(limit)
    
    with get_db_connection() as conn:
        feedback_items = conn.execute(f"""
            SELECT 
                uf.*, 
                u.name as user_name, 
                u.email as user_email
            FROM user_feedback uf
            LEFT JOIN users u ON uf.user_id = u.id
            {where_clause}
            ORDER BY uf.created_at DESC
            LIMIT ?
        """, params).fetchall()
        
        # Summary stats
        summary = conn.execute("""
            SELECT 
                COUNT(*) as total_feedback,
                COUNT(DISTINCT CASE WHEN status = 'open' THEN id END) as open_items,
                COUNT(DISTINCT CASE WHEN status = 'in_progress' THEN id END) as in_progress,
                COUNT(DISTINCT CASE WHEN status = 'resolved' THEN id END) as resolved,
                AVG(rating) as avg_rating
            FROM user_feedback
        """).fetchone()
    
    return {
        "feedback_items": [dict(item) for item in feedback_items],
        "summary": dict(summary) if summary else {},
        "total_count": len(feedback_items)
    }

@router.get("/dashboard/respondent-experience")
async def get_respondent_experience_dashboard(
    survey_id: Optional[int] = None,
    days: int = 30,
    current_user = Depends(get_current_user)
):
    """Get respondent experience analytics for founder insights."""
    
    if current_user["role"] != "founder" and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)
    
    with get_db_connection() as conn:
        conditions = ["re.created_at >= ?"]
        params = [start_date.isoformat()]
        
        if survey_id:
            conditions.append("re.survey_id = ?")
            params.append(survey_id)
        
        where_clause = "WHERE " + " AND ".join(conditions)
        
        # Experience metrics
        experience_stats = conn.execute(f"""
            SELECT 
                COUNT(*) as total_responses,
                AVG(overall_rating) as avg_overall_rating,
                AVG(easiness_rating) as avg_easiness_rating,
                AVG(clarity_rating) as avg_clarity_rating,
                AVG(time_rating) as avg_time_rating,
                COUNT(CASE WHEN technical_issues = 1 THEN 1 END) as technical_issues_count,
                COUNT(CASE WHEN would_recommend = 1 THEN 1 END) as would_recommend_count,
                AVG(completion_time) as avg_completion_time
            FROM respondent_experience re
            {where_clause}
        """, params).fetchone()
        
        # Experience by survey
        survey_breakdown = conn.execute(f"""
            SELECT 
                s.title as survey_title,
                s.id as survey_id,
                COUNT(re.id) as response_count,
                AVG(re.overall_rating) as avg_rating,
                COUNT(CASE WHEN re.would_recommend = 1 THEN 1 END) as recommend_count
            FROM respondent_experience re
            JOIN surveys s ON re.survey_id = s.id
            {where_clause}
            GROUP BY s.id, s.title
            ORDER BY response_count DESC
        """, params).fetchall()
        
        # Recent feedback comments
        recent_feedback = conn.execute(f"""
            SELECT 
                re.quick_feedback,
                re.improvement_suggestion,
                re.overall_rating,
                s.title as survey_title,
                re.created_at
            FROM respondent_experience re
            JOIN surveys s ON re.survey_id = s.id
            {where_clause}
            AND (re.quick_feedback IS NOT NULL OR re.improvement_suggestion IS NOT NULL)
            ORDER BY re.created_at DESC
            LIMIT 20
        """, params).fetchall()
    
    return {
        "period_days": days,
        "survey_filter": survey_id,
        "experience_stats": dict(experience_stats) if experience_stats else {},
        "survey_breakdown": [dict(survey) for survey in survey_breakdown],
        "recent_feedback": [dict(feedback) for feedback in recent_feedback],
        "generated_at": datetime.now().isoformat()
    }

# ═════════════════════════════════════════════════════════════
# UTILITY ENDPOINTS
# ═════════════════════════════════════════════════════════════

@router.post("/update-daily-metrics")
async def update_daily_metrics(current_user = Depends(get_current_user)):
    """Update daily metrics summary (can be called by cron job)."""
    
    if current_user["role"] != "founder" and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    today = date.today()
    yesterday = today - timedelta(days=1)
    
    with get_db_connection() as conn:
        # Calculate metrics for yesterday
        metrics = conn.execute("""
            SELECT 
                COUNT(DISTINCT u.id) as total_users,
                COUNT(DISTINCT CASE WHEN DATE(u.last_login) = ? THEN u.id END) as active_users,
                COUNT(DISTINCT CASE WHEN DATE(u.created_at) = ? THEN u.id END) as new_signups,
                COUNT(DISTINCT CASE WHEN DATE(s.created_at) = ? THEN s.id END) as surveys_created,
                COUNT(DISTINCT CASE WHEN DATE(sp.published_at) = ? THEN sp.id END) as surveys_published,
                COUNT(DISTINCT CASE WHEN DATE(r.created_at) = ? THEN r.id END) as responses_collected
            FROM users u
            LEFT JOIN surveys s ON s.created_at >= ?
            LEFT JOIN survey_publications sp ON sp.published_at >= ?
            LEFT JOIN responses r ON r.created_at >= ?
        """, (
            yesterday.isoformat(), yesterday.isoformat(), yesterday.isoformat(),
            yesterday.isoformat(), yesterday.isoformat(), yesterday.isoformat(),
            yesterday.isoformat(), yesterday.isoformat()
        )).fetchone()
        
        # Website analytics for yesterday
        web_metrics = conn.execute("""
            SELECT 
                COUNT(*) as page_views,
                COUNT(DISTINCT session_id) as unique_visitors,
                AVG(time_on_page) as avg_session_duration
            FROM website_analytics
            WHERE DATE(created_at) = ?
        """, (yesterday.isoformat(),)).fetchone()
        
        # Feedback metrics
        feedback_metrics = conn.execute("""
            SELECT 
                COUNT(*) as user_feedback_count,
                AVG(rating) as avg_user_satisfaction
            FROM user_feedback
            WHERE DATE(created_at) = ?
        """, (yesterday.isoformat(),)).fetchone()
        
        # Insert or update daily metrics
        conn.execute("""
            INSERT OR REPLACE INTO daily_metrics (
                date_recorded, total_users, active_users, new_signups,
                surveys_created, surveys_published, responses_collected,
                page_views, unique_visitors, avg_session_duration,
                user_feedback_count, avg_user_satisfaction, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            yesterday.isoformat(),
            dict(metrics).get("total_users", 0) if metrics else 0,
            dict(metrics).get("active_users", 0) if metrics else 0,
            dict(metrics).get("new_signups", 0) if metrics else 0,
            dict(metrics).get("surveys_created", 0) if metrics else 0,
            dict(metrics).get("surveys_published", 0) if metrics else 0,
            dict(metrics).get("responses_collected", 0) if metrics else 0,
            dict(web_metrics).get("page_views", 0) if web_metrics else 0,
            dict(web_metrics).get("unique_visitors", 0) if web_metrics else 0,
            dict(web_metrics).get("avg_session_duration", 0) if web_metrics else 0,
            dict(feedback_metrics).get("user_feedback_count", 0) if feedback_metrics else 0,
            dict(feedback_metrics).get("avg_user_satisfaction", 0) if feedback_metrics else 0,
            datetime.now().isoformat()
        ))
    
    return {"success": True, "date_processed": yesterday.isoformat()}

@router.patch("/feedback/user/{feedback_id}")
async def update_feedback_status(
    feedback_id: int,
    status: str,
    current_user = Depends(get_current_user)
):
    """Update user feedback status (founder/admin only)."""
    
    if current_user["role"] != "founder" and current_user["role"] != "admin":
        raise HTTPException(status_code=403, detail="Access denied")
    
    valid_statuses = ["open", "in_progress", "resolved", "closed"]
    if status not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")
    
    with get_db_connection() as conn:
        result = conn.execute("""
            UPDATE user_feedback 
            SET status = ?, updated_at = ?
            WHERE id = ?
        """, (status, datetime.now().isoformat(), feedback_id))
        
        if result.rowcount == 0:
            raise HTTPException(status_code=404, detail="Feedback not found")
    
    return {"success": True, "message": f"Feedback status updated to {status}"}