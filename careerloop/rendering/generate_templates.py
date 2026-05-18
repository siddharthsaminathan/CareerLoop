import os
from pathlib import Path

TEMPLATES_DIR = Path("careerloop/rendering/templates")
TEMPLATES_DIR.mkdir(parents=True, exist_ok=True)

BASE_HTML = """<!DOCTYPE html>
<html lang="{{LANG}}">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{{NAME}} — CV</title>
<style>
  * {{ margin: 0; padding: 0; box-sizing: border-box; }}
  html {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
  body {{
    font-size: {font_size};
    line-height: {line_height};
    color: {text_color};
    background: #ffffff;
    padding: 0;
    margin: 0;
    font-family: {font_family};
  }}
  .page {{
    width: 100%;
    max-width: {{{{PAGE_WIDTH}}}};
    margin: 0 auto;
    padding: {page_padding};
    display: {page_display};
    grid-template-columns: {page_grid};
    gap: {page_gap};
  }}
  /* === HEADER === */
  .header {{ margin-bottom: {header_margin}; grid-column: {header_span}; }}
  .header h1 {{
    font-size: {h1_size};
    font-weight: 700;
    color: {h1_color};
    margin-bottom: 6px;
    line-height: 1.1;
    font-family: {h1_font};
    text-align: {header_align};
  }}
  .header-gradient {{
    height: {gradient_height};
    background: {gradient_bg};
    margin-bottom: 10px;
    display: {gradient_display};
  }}
  .contact-row {{
    display: flex;
    flex-wrap: wrap;
    gap: 8px 14px;
    font-size: 10.5px;
    color: {contact_color};
    justify-content: {header_align};
  }}
  .contact-row a {{ color: {contact_link_color}; text-decoration: none; }}
  .contact-row .separator {{ color: #ccc; }}

  /* === SECTIONS === */
  .main-column {{ display: block; }}
  .sidebar {{ display: {sidebar_display}; }}
  
  .section {{ margin-bottom: {section_margin}; }}
  .section-title {{
    font-size: {h2_size};
    font-weight: 700;
    text-transform: {h2_transform};
    color: {h2_color};
    border-bottom: {h2_border};
    padding-bottom: 4px;
    margin-bottom: 10px;
    font-family: {h2_font};
  }}
  .summary-text {{ font-size: 11px; line-height: 1.7; color: #2f2f2f; }}
  a {{ white-space: nowrap; }}

  /* === COMPETENCIES === */
  .competencies-grid {{ display: flex; flex-wrap: wrap; gap: 8px; }}
  .competency-tag {{
    font-size: 10px;
    font-weight: 500;
    color: {tag_color};
    background: {tag_bg};
    padding: 4px 10px;
    border-radius: {tag_radius};
    border: {tag_border};
  }}

  /* === WORK EXPERIENCE === */
  .job {{ margin-bottom: {job_margin}; }}
  .job-header {{
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    gap: 12px;
    margin-bottom: 4px;
  }}
  .job-company {{
    font-size: 12.5px;
    font-weight: 600;
    color: {company_color};
    font-family: {h2_font};
  }}
  .job-period {{ font-size: 10.5px; color: #777; white-space: nowrap; }}
  .job-role {{ font-size: 11px; font-weight: 600; color: #333; margin-bottom: 6px; }}
  .job-location {{ font-size: 10px; color: #888; }}
  .job ul {{ padding-left: 18px; margin-top: 6px; }}
  .job li {{ font-size: 10.5px; line-height: 1.6; color: #333; margin-bottom: 4px; }}
  .job li strong {{ font-weight: 600; }}

  /* === PROJECTS === */
  .project {{ margin-bottom: 12px; }}
  .project-title {{ font-size: 11.5px; font-weight: 600; color: {company_color}; }}
  .project-desc {{ font-size: 10.5px; color: #444; margin-top: 3px; line-height: 1.55; }}

  /* === EDUCATION === */
  .edu-item {{ margin-bottom: 8px; }}
  .edu-header {{ display: flex; justify-content: space-between; align-items: baseline; gap: 12px; }}
  .edu-title {{ font-weight: 600; font-size: 11px; color: #333; }}
  .edu-org {{ color: {company_color}; font-weight: 500; }}
  .edu-year {{ font-size: 10px; color: #777; white-space: nowrap; }}

  /* === SKILLS === */
  .skills-grid {{ display: flex; flex-wrap: wrap; gap: 6px 14px; }}
  .skill-item {{ font-size: 10.5px; color: #444; }}
  .skill-category {{ font-weight: 600; color: #333; font-size: 10.5px; }}

  @media print {{
    body {{ -webkit-print-color-adjust: exact; print-color-adjust: exact; }}
    .page {{ padding: 0; }}
  }}
  .avoid-break, .job, .project, .edu-item, .cert-item {{ break-inside: avoid; page-break-inside: avoid; }}
</style>
</head>
<body>
<div class="page">
  <div class="header avoid-break">
    <h1>{{{{NAME}}}}</h1>
    <div class="header-gradient"></div>
    <div class="contact-row">
      <span>{{{{PHONE}}}}</span><span class="separator">|</span>
      <span>{{{{EMAIL}}}}</span><span class="separator">|</span>
      <a href="{{{{LINKEDIN_URL}}}}">{{{{LINKEDIN_DISPLAY}}}}</a><span class="separator">|</span>
      <a href="{{{{PORTFOLIO_URL}}}}">{{{{PORTFOLIO_DISPLAY}}}}</a><span class="separator">|</span>
      <span>{{{{LOCATION}}}}</span>
    </div>
  </div>

  {layout_html}
</div>
</body>
</html>
"""

SINGLE_COLUMN_HTML = """
  <div class="main-column">
    <div class="section avoid-break">
      <div class="section-title">{{{{SECTION_SUMMARY}}}}</div>
      <div class="summary-text">{{{{SUMMARY_TEXT}}}}</div>
    </div>
    <div class="section">
      <div class="section-title">{{{{SECTION_COMPETENCIES}}}}</div>
      <div class="competencies-grid">{{{{COMPETENCIES}}}}</div>
    </div>
    <div class="section">
      <div class="section-title">{{{{SECTION_EXPERIENCE}}}}</div>
      {{{{EXPERIENCE}}}}
    </div>
    <div class="section avoid-break">
      <div class="section-title">{{{{SECTION_PROJECTS}}}}</div>
      {{{{PROJECTS}}}}
    </div>
    <div class="section avoid-break">
      <div class="section-title">{{{{SECTION_EDUCATION}}}}</div>
      {{{{EDUCATION}}}}
    </div>
    <div class="section avoid-break">
      <div class="section-title">{{{{SECTION_SKILLS}}}}</div>
      {{{{SKILLS}}}}
    </div>
  </div>
"""

TWO_COLUMN_HTML = """
  <div class="sidebar">
    <div class="section avoid-break">
      <div class="section-title">{{{{SECTION_SKILLS}}}}</div>
      {{{{SKILLS}}}}
    </div>
    <div class="section avoid-break">
      <div class="section-title">{{{{SECTION_EDUCATION}}}}</div>
      {{{{EDUCATION}}}}
    </div>
    <div class="section">
      <div class="section-title">{{{{SECTION_COMPETENCIES}}}}</div>
      <div class="competencies-grid">{{{{COMPETENCIES}}}}</div>
    </div>
  </div>
  <div class="main-column">
    <div class="section avoid-break">
      <div class="section-title">{{{{SECTION_SUMMARY}}}}</div>
      <div class="summary-text">{{{{SUMMARY_TEXT}}}}</div>
    </div>
    <div class="section">
      <div class="section-title">{{{{SECTION_EXPERIENCE}}}}</div>
      {{{{EXPERIENCE}}}}
    </div>
    <div class="section avoid-break">
      <div class="section-title">{{{{SECTION_PROJECTS}}}}</div>
      {{{{PROJECTS}}}}
    </div>
  </div>
"""

TEMPLATES = {
    "classic_ats": {
        "font_family": '"Times New Roman", Times, serif',
        "font_size": "11px",
        "line_height": "1.5",
        "text_color": "#000000",
        "page_padding": "0",
        "page_display": "block",
        "page_grid": "none",
        "page_gap": "0",
        "header_margin": "16px",
        "header_span": "1",
        "h1_size": "24px",
        "h1_color": "#000000",
        "h1_font": '"Times New Roman", Times, serif',
        "header_align": "center",
        "gradient_height": "0",
        "gradient_bg": "none",
        "gradient_display": "none",
        "contact_color": "#000000",
        "contact_link_color": "#000000",
        "sidebar_display": "none",
        "section_margin": "16px",
        "h2_size": "12px",
        "h2_transform": "uppercase",
        "h2_color": "#000000",
        "h2_border": "1px solid #000000",
        "h2_font": '"Times New Roman", Times, serif',
        "tag_color": "#000000",
        "tag_bg": "transparent",
        "tag_radius": "0",
        "tag_border": "1px solid #000000",
        "job_margin": "14px",
        "company_color": "#000000",
        "layout_html": SINGLE_COLUMN_HTML
    },
    "modern_accent": {
        "font_family": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "font_size": "11px",
        "line_height": "1.5",
        "text_color": "#1a1a2e",
        "page_padding": "0",
        "page_display": "block",
        "page_grid": "none",
        "page_gap": "0",
        "header_margin": "20px",
        "header_span": "1",
        "h1_size": "28px",
        "h1_color": "#1a1a2e",
        "h1_font": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "header_align": "left",
        "gradient_height": "2px",
        "gradient_bg": "linear-gradient(to right, #0077b6, #e63946)",
        "gradient_display": "block",
        "contact_color": "#555555",
        "contact_link_color": "#0077b6",
        "sidebar_display": "none",
        "section_margin": "18px",
        "h2_size": "12px",
        "h2_transform": "uppercase",
        "h2_color": "#0077b6",
        "h2_border": "1.5px solid #e2e2e2",
        "h2_font": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "tag_color": "#0077b6",
        "tag_bg": "#f0f8ff",
        "tag_radius": "3px",
        "tag_border": "1px solid #caf0f8",
        "job_margin": "14px",
        "company_color": "#0077b6",
        "layout_html": SINGLE_COLUMN_HTML
    },
    "executive_clean": {
        "font_family": 'Georgia, serif',
        "font_size": "10.5px",
        "line_height": "1.6",
        "text_color": "#2c3e50",
        "page_padding": "0",
        "page_display": "block",
        "page_grid": "none",
        "page_gap": "0",
        "header_margin": "24px",
        "header_span": "1",
        "h1_size": "26px",
        "h1_color": "#2c3e50",
        "h1_font": 'Georgia, serif',
        "header_align": "center",
        "gradient_height": "1px",
        "gradient_bg": "#34495e",
        "gradient_display": "block",
        "contact_color": "#7f8c8d",
        "contact_link_color": "#2c3e50",
        "sidebar_display": "none",
        "section_margin": "20px",
        "h2_size": "13px",
        "h2_transform": "uppercase",
        "h2_color": "#34495e",
        "h2_border": "none",
        "h2_font": 'Georgia, serif',
        "tag_color": "#34495e",
        "tag_bg": "transparent",
        "tag_radius": "0",
        "tag_border": "1px solid #bdc3c7",
        "job_margin": "16px",
        "company_color": "#2c3e50",
        "layout_html": SINGLE_COLUMN_HTML
    },
    "compact_one_page": {
        "font_family": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "font_size": "9.5px",
        "line_height": "1.3",
        "text_color": "#111111",
        "page_padding": "0",
        "page_display": "block",
        "page_grid": "none",
        "page_gap": "0",
        "header_margin": "10px",
        "header_span": "1",
        "h1_size": "20px",
        "h1_color": "#111111",
        "h1_font": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "header_align": "left",
        "gradient_height": "0",
        "gradient_bg": "none",
        "gradient_display": "none",
        "contact_color": "#444444",
        "contact_link_color": "#111111",
        "sidebar_display": "none",
        "section_margin": "10px",
        "h2_size": "11px",
        "h2_transform": "uppercase",
        "h2_color": "#111111",
        "h2_border": "1px solid #cccccc",
        "h2_font": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "tag_color": "#111111",
        "tag_bg": "#eeeeee",
        "tag_radius": "2px",
        "tag_border": "none",
        "job_margin": "8px",
        "company_color": "#111111",
        "layout_html": SINGLE_COLUMN_HTML
    },
    "technical_two_column": {
        "font_family": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "font_size": "10.5px",
        "line_height": "1.4",
        "text_color": "#333333",
        "page_padding": "0",
        "page_display": "grid",
        "page_grid": "1fr 2.5fr",
        "page_gap": "20px",
        "header_margin": "20px",
        "header_span": "1 / -1",
        "h1_size": "26px",
        "h1_color": "#222222",
        "h1_font": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "header_align": "left",
        "gradient_height": "2px",
        "gradient_bg": "#2b6cb0",
        "gradient_display": "block",
        "contact_color": "#555555",
        "contact_link_color": "#2b6cb0",
        "sidebar_display": "block",
        "section_margin": "16px",
        "h2_size": "12px",
        "h2_transform": "uppercase",
        "h2_color": "#2b6cb0",
        "h2_border": "1px solid #e2e8f0",
        "h2_font": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "tag_color": "#2b6cb0",
        "tag_bg": "#ebf8ff",
        "tag_radius": "3px",
        "tag_border": "none",
        "job_margin": "14px",
        "company_color": "#2b6cb0",
        "layout_html": TWO_COLUMN_HTML
    },
    "product_engineer": {
        "font_family": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "font_size": "11px",
        "line_height": "1.55",
        "text_color": "#1f2937",
        "page_padding": "0",
        "page_display": "block",
        "page_grid": "none",
        "page_gap": "0",
        "header_margin": "24px",
        "header_span": "1",
        "h1_size": "30px",
        "h1_color": "#111827",
        "h1_font": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "header_align": "left",
        "gradient_height": "3px",
        "gradient_bg": "linear-gradient(to right, #10b981, #3b82f6)",
        "gradient_display": "block",
        "contact_color": "#4b5563",
        "contact_link_color": "#2563eb",
        "sidebar_display": "none",
        "section_margin": "20px",
        "h2_size": "13px",
        "h2_transform": "none",
        "h2_color": "#111827",
        "h2_border": "2px solid #e5e7eb",
        "h2_font": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "tag_color": "#047857",
        "tag_bg": "#d1fae5",
        "tag_radius": "4px",
        "tag_border": "none",
        "job_margin": "16px",
        "company_color": "#3b82f6",
        "layout_html": SINGLE_COLUMN_HTML
    },
    "founder_operator": {
        "font_family": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "font_size": "11px",
        "line_height": "1.6",
        "text_color": "#000000",
        "page_padding": "0",
        "page_display": "block",
        "page_grid": "none",
        "page_gap": "0",
        "header_margin": "20px",
        "header_span": "1",
        "h1_size": "28px",
        "h1_color": "#000000",
        "h1_font": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "header_align": "center",
        "gradient_height": "1px",
        "gradient_bg": "#000000",
        "gradient_display": "block",
        "contact_color": "#333333",
        "contact_link_color": "#000000",
        "sidebar_display": "none",
        "section_margin": "18px",
        "h2_size": "12px",
        "h2_transform": "uppercase",
        "h2_color": "#000000",
        "h2_border": "1px solid #000000",
        "h2_font": 'system-ui, -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif',
        "tag_color": "#000000",
        "tag_bg": "transparent",
        "tag_radius": "0",
        "tag_border": "1px solid #000000",
        "job_margin": "16px",
        "company_color": "#000000",
        "layout_html": SINGLE_COLUMN_HTML
    }
}

for name, params in TEMPLATES.items():
    content = BASE_HTML.format(**params)
    with open(TEMPLATES_DIR / f"{name}.html", "w") as f:
        f.write(content)

print("Templates generated successfully.")
