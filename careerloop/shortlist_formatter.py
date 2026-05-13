"""
CareerLoop Shortlist Formatter — WhatsApp-style text output.

Produces human-readable daily shortlist summaries.
Designed to feel like a sharp career friend texting you.
"""

from datetime import datetime, timezone


def format_daily_shortlist(scored_jobs: list, follow_ups: list, user_name: str = "") -> str:
    """
    Format the daily shortlist for WhatsApp/CLI output.

    Args:
        scored_jobs: List of {job, score, breakdown} sorted by score desc
        follow_ups: List of ledger entries with follow-ups due
        user_name: User's first name for greeting
    """
    greeting = f"🌅 Morning{', ' + user_name if user_name else ''}."

    # Count new vs total
    new_count = sum(1 for j in scored_jobs if j.get("job", {}).get("status") == "DISCOVERED")
    worth_count = sum(1 for j in scored_jobs if j["score"] >= 60)

    if worth_count == 0:
        return f"{greeting} No strong matches today. {len(scored_jobs)} jobs scanned, none above 60/100. I'll scan again tomorrow."

    lines = [
        greeting,
        f" {new_count} new jobs today. {worth_count} worth your time.",
        "",
    ]

    # Top jobs
    top = [j for j in scored_jobs if j["score"] >= 60][:5]
    medals = ["🥇", "🥈", "🥉", "4️⃣", "5️⃣"]

    for i, item in enumerate(top):
        job = item["job"]
        score = item["score"]
        breakdown = item.get("breakdown", {})

        title = job.get("title", "Unknown Role")
        company = job.get("company", "Unknown Company")
        location = job.get("location", "")

        lines.append(f"{medals[i]} {company} — {title}")
        if location:
            lines.append(f"   {location} | Fit: {score}/100")
        else:
            lines.append(f"   Fit: {score}/100")

        # Why + Risk from breakdown
        why, risk = _extract_why_risk(breakdown)
        if why:
            lines.append(f"   ✅ {why}")
        if risk:
            lines.append(f"   ⚠️ {risk}")
        lines.append("")

    # Follow-ups
    if follow_ups:
        lines.append("📬 Follow-ups due today:")
        lines.append("")
        for fu in follow_ups[:3]:
            company = fu.get("company", "Unknown")
            title = fu.get("title", "Unknown")
            lines.append(f"   • {company} — {title}")
            recruiter = fu.get("recruiter_name")
            if recruiter:
                lines.append(f"     Recruiter: {recruiter}")
        lines.append("")

    # Actions
    lines.append("Reply:")
    lines.append("1 = review best job")
    if len(top) > 1:
        lines.append("2 = show all jobs")
    if follow_ups:
        lines.append("3 = follow-ups")
    lines.append("4 = skip today")

    return "\n".join(lines)


def format_job_detail(job_item: dict) -> str:
    """Format a single job in detail."""
    job = job_item.get("job", job_item)
    score = job_item.get("score", job_item.get("fit_score", "N/A"))
    breakdown = job_item.get("breakdown", job_item.get("fit_breakdown", {}))

    lines = [
        f"📋 {job.get('title', 'Unknown')}",
        f"🏢 {job.get('company', 'Unknown')}",
        f"📍 {job.get('location', 'Not specified')}",
        f"📊 Fit Score: {score}/100",
        "",
        "Dimension Breakdown:",
    ]

    if breakdown:
        for dim, values in breakdown.items():
            raw = values.get("raw", 0)
            weight = values.get("weight", 0)
            weighted = values.get("weighted", 0)
            bar = "█" * int(raw) + "░" * (10 - int(raw))
            dim_name = dim.replace("_", " ").title()
            lines.append(f"  {dim_name:<22} {bar} {raw:.0f}/10 (w{weight})")

    lines.append("")
    lines.append(f"🔗 {job.get('source_url', 'No URL')}")
    lines.append("")
    lines.append("Approve? y/n/maybe/skip")

    return "\n".join(lines)


def format_follow_up_message(job: dict) -> str:
    """Format a suggested follow-up message."""
    company = job.get("company", "Unknown")
    title = job.get("title", "the role")
    recruiter = job.get("recruiter_name", "Hiring Team")

    return f"""Hi {recruiter},

I applied for the {title} role at {company} about a week ago and wanted to follow up. I'm very interested in the opportunity and would love to discuss how my experience in production AI systems could contribute to the team.

Would you have time for a brief conversation this week?

Best,
Siddharth"""


def format_weekly_report(stats: dict, user_name: str = "") -> str:
    """Format a weekly progress report."""
    by_status = stats.get("by_status", {})

    lines = [
        f"📊 Weekly CareerLoop Report{f' — {user_name}' if user_name else ''}",
        f"   {datetime.now(timezone.utc).strftime('%B %d, %Y')}",
        "",
        "This Week:",
        f"   Jobs discovered:  {by_status.get('DISCOVERED', 0)}",
        f"   Jobs shortlisted: {by_status.get('SHORTLISTED', 0)}",
        f"   Applied:          {by_status.get('APPLIED', 0)}",
        f"   Follow-ups sent:  {by_status.get('FOLLOW_UP_DUE', 0)}",
        f"   Interviews:       {by_status.get('INTERVIEW', 0)}",
        f"   Rejections:       {by_status.get('REJECTED', 0)}",
        f"   Offers:           {by_status.get('OFFER', 0)}",
        "",
        f"Pipeline: {stats.get('active_count', 0)} active | {stats.get('total_jobs', 0)} total",
        f"Avg fit score: {stats.get('avg_fit_score', 0)}/100",
    ]

    return "\n".join(lines)


# ── Internal helpers ────────────────────────────────────────────────

def _extract_why_risk(breakdown: dict) -> tuple[str, str]:
    """Extract 'why this is good' and 'what's the risk' from breakdown."""
    if not breakdown:
        return "", ""

    # Find strongest and weakest dimensions
    sorted_dims = sorted(breakdown.items(), key=lambda x: x[1].get("weighted", 0), reverse=True)
    strongest = sorted_dims[0] if sorted_dims else None
    weakest = sorted_dims[-1] if sorted_dims else None

    why = ""
    risk = ""

    if strongest:
        name = strongest[0].replace("_", " ").title()
        raw = strongest[1].get("raw", 0)
        if raw >= 8:
            why = f"Strong {name.lower()}"

    # Find actual risks (dimensions below 4)
    risks = [(k, v) for k, v in breakdown.items() if v.get("raw", 10) <= 3]
    if risks:
        worst = risks[0]
        name = worst[0].replace("_", " ").title()
        raw = worst[1].get("raw", 0)
        if raw <= 2:
            risk = f"Low {name.lower()} ({raw}/10)"
        elif raw <= 3:
            risk = f"Watch: {name.lower()} ({raw}/10)"

    # If no strong risk, check if weakest is below 5
    if not risk and weakest and weakest[1].get("raw", 10) <= 4:
        name = weakest[0].replace("_", " ").title()
        raw = weakest[1].get("raw", 0)
        risk = f"{name.lower()} ({raw}/10)"

    return why, risk
