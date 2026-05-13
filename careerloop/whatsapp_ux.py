"""
CareerLoop WhatsApp UX — Low cognitive load message contract.

One job at a time. No dumping. No huge tables.
"""

from datetime import datetime, timezone
from typing import Optional


def daily_brief(new_count: int, good_count: int, top_job: Optional[dict],
                follow_ups_count: int, user_name: str = "") -> str:
    """Morning brief — under 12 lines, WhatsApp-optimized."""

    greeting = f"Morning{', ' + user_name if user_name else ''}."

    lines = [greeting]

    if good_count == 0:
        lines.append(f"Scanned {new_count} jobs. None above your bar today.")
        if follow_ups_count:
            lines.append(f"{follow_ups_count} follow-ups due. Reply 3 to see them.")
        return "\n".join(lines)

    lines.append(f"{good_count}/{new_count} jobs worth your time.")

    if top_job:
        company = top_job.get("company", top_job.get("_company", "Unknown"))
        title = top_job.get("role_title", top_job.get("_role", "Unknown"))
        score = top_job.get("overall_score", top_job.get("fit_score", "?"))
        reason = top_job.get("why_user_might_like_it", top_job.get("reason", ""))
        risks = top_job.get("risks", [])

        lines.append(f"🥇 {company} — {title} ({score}/100)")
        if reason:
            lines.append(f"   {reason}")
        if risks:
            lines.append(f"   ⚠️ {risks[0]}")

    if follow_ups_count:
        lines.append(f"📬 {follow_ups_count} follow-ups due.")

    lines.append("Reply: 1=best 2=all" + (" 3=followups" if follow_ups_count else "") + " 4=skip")

    return "\n".join(lines)


def job_review_card(job: dict, index: int, total: int) -> str:
    """Single job review card — one at a time."""

    company = job.get("company", job.get("_company", "Unknown"))
    title = job.get("role_title", job.get("_role", "Unknown"))
    location = job.get("location", job.get("_location", "?"))
    score = job.get("overall_score", job.get("fit_score", "?"))
    rec = job.get("recommendation", "MAYBE")
    reason = job.get("why_user_might_like_it", job.get("reason", ""))
    risks = job.get("risks", [])
    concerns = job.get("why_user_might_hate_it", "")
    confidence = job.get("confidence", 0)

    emoji = {"APPLY": "🟢", "MAYBE": "🟡", "SKIP": "🔴"}.get(rec, "⚪")

    lines = [
        f"*Job {index}/{total}* {emoji}",
        f"{company} — {title}",
        f"📍 {location} | Fit: {score}/100",
    ]

    if reason:
        lines.append(f"✅ {reason}")
    if risks:
        lines.append(f"⚠️ {risks[0]}")
    if concerns and concerns != reason:
        lines.append(f"🤔 {concerns}")

    if confidence < 0.5:
        lines.append("📋 Low confidence — review manually")

    lines.append("")
    lines.append("Reply: apply | skip | maybe | next | details")

    return "\n".join(lines)


def job_detail_card(job: dict) -> str:
    """Detailed job view with all dimensions."""

    company = job.get("company", job.get("_company", "Unknown"))
    title = job.get("role_title", job.get("_role", "Unknown"))
    location = job.get("location", job.get("_location", "?"))
    score = job.get("overall_score", job.get("fit_score", "?"))
    url = job.get("source_url", job.get("application_url", ""))

    lines = [
        f"📋 *{company} — {title}*",
        f"📍 {location}",
        f"📊 Fit: {score}/100",
        f"🔗 {url}" if url else "",
        "",
        "Why: " + job.get("why_user_might_like_it", job.get("reason", "N/A")),
        "Risk: " + ", ".join(job.get("risks", ["None identified"])),
        "Concern: " + job.get("why_user_might_hate_it", "None"),
        "",
        f"Confidence: {job.get('confidence', 0):.0%}",
    ]

    # Dimension breakdown if available
    dims = job.get("dimensions", {})
    if dims:
        lines.append("")
        for dim, score_val in dims.items():
            name = dim.replace("_", " ").title()
            bar = "█" * score_val + "░" * (10 - score_val)
            lines.append(f"  {name:<20} {bar} {score_val}/10")

    lines.append("")
    lines.append("Reply: apply | skip | maybe | back")

    return "\n".join(lines)


def follow_up_card(follow_up: dict, index: int, total: int) -> str:
    """Follow-up reminder card."""

    company = follow_up.get("company", "Unknown")
    title = follow_up.get("role_title", follow_up.get("_role", "the role"))
    days_ago = follow_up.get("days_since_applied", "?")
    recruiter = follow_up.get("recruiter_name", "the hiring team")
    message = follow_up.get("suggested_message", "")

    lines = [
        f"*Follow-up {index}/{total}*",
        f"{company} — {title}",
        f"Applied {days_ago} days ago.",
    ]

    if recruiter and recruiter != "unknown":
        lines.append(f"Recruiter: {recruiter}")

    if message:
        lines.append("")
        lines.append("Suggested message:")
        lines.append(message[:300])

    lines.append("")
    lines.append("Reply: send | edit | skip | remind tomorrow")
    return "\n".join(lines)


def skip_reason_prompt(job) -> str:
    """Ask user why they skipped."""
    company = job.get("company", job.get("_company", "Unknown"))
    title = job.get("role_title", job.get("_role", "the role"))

    return f"""Skipping {company} — {title}.

Why? (helps me learn)
Reply:
salary | location | role | startup | not interested | other reason"""


def no_jobs_message(user_name: str = "") -> str:
    return f"🌅 Morning{', ' + user_name if user_name else ''}. No new jobs matched your profile today. I'll scan again tomorrow."


def apply_confirmation(job) -> str:
    """Confirmation after user applies."""
    company = job.get("company", job.get("_company", "Unknown"))
    title = job.get("role_title", job.get("_role", "the role"))
    return f"✅ Marked {company} — {title} as APPROVED. Resume needed. I'll remind you to follow up in 5 days."
