# config/theme.py

TOKENS = {
    "text": "#1a1a1a",
    "muted": "#6e6e73",
    "border": "#e5e5e5",
    "soft": "#f5f5f7",
    "danger": "#d11a2a",
    "primary": "#2980b9",
}

CSS = f"""
<style>
  :root {{
    --text: {TOKENS["text"]};
    --muted: {TOKENS["muted"]};
    --border: {TOKENS["border"]};
    --soft: {TOKENS["soft"]};
    --danger: {TOKENS["danger"]};
    --primary: {TOKENS["primary"]};
  }}

  /* --- GLOBAL LAYOUT --- */
  .block-container {{
    max-width: 98% !important;
    padding-top: 2rem !important;
    padding-bottom: 3rem !important;
  }}

  .page-title {{
    font-size: 1.45rem;
    font-weight: 800;
    color: var(--text);
    letter-spacing: -0.02em;
    margin: 0;
    line-height: 1.15;
  }}

  .page-subtitle {{
    color: var(--muted);
    margin-top: .35rem;
    margin-bottom: 1.25rem;
    font-size: .95rem;
  }}

  .section-title {{
    font-size: 1.05rem;
    font-weight: 800;
    color: var(--text);
    letter-spacing: -0.02em;
    margin: 0 0 .75rem 0;
  }}

  .col-header {{
    font-size: 0.75rem;
    font-weight: 700;
    text-transform: uppercase;
    color: var(--muted);
    letter-spacing: 0.06em;
    padding-bottom: 0.5rem;
    border-bottom: 1px solid var(--border);
    margin-bottom: 0.5rem;
  }}

  /* --- INPUT FIELDS STYLING --- */
  div[data-testid="stTextInput"],
  div[data-testid="stNumberInput"],
  div[data-testid="stTextArea"] {{
    margin-bottom: 0px !important;
  }}

  div[data-baseweb="input"] {{
    background-color: #ffffff !important;
    border: 1px solid var(--border) !important;
    border-radius: 8px !important;
  }}

  div[data-baseweb="input"]:focus-within {{
    border-color: var(--primary) !important;
    box-shadow: 0 0 0 1px rgba(41,128,185,0.18) !important;
  }}

  /* --- BUTTONS & CONTAINERS --- */
  div[data-testid="stVerticalBlockBorderWrapper"] {{
    border-color: #f0f2f6 !important;
    border-radius: 12px !important;
    transition: all 0.2s ease;
  }}
  
  /* Efek Hover untuk Card POS */
  div[data-testid="stVerticalBlockBorderWrapper"]:hover {{
    border-color: var(--primary) !important;
    box-shadow: 0 4px 12px rgba(0,0,0,0.08);
    transform: translateY(-2px);
  }}

  .total-box {{
    background-color: var(--soft);
    border-radius: 8px;
    color: #1d1d1f;
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    font-weight: 700;
    font-size: 0.9rem;
    display: flex;
    align-items: center;
    justify-content: flex-end;
    padding: 0 0.75rem;
    height: 100%;
    min-height: 2.6rem;
    width: 100%;
  }}

  button[kind="secondary"] {{
    border: 1px solid var(--border) !important;
    color: #666 !important;
  }}

  /* Danger button style */
  div[data-testid="stVerticalBlock"][data-key^="danger"] button {{
    background-color: var(--danger) !important;
    color: white !important;
    border: 1px solid var(--danger) !important;
  }}

  button[aria-label="Close"] {{ display: none !important; }}

  /* --- DIALOGS --- */
  div[data-testid="stDialog"] div[role="dialog"] {{
    width: 420px !important;
    border-radius: 16px !important;
    padding-top: 0px !important;
    padding-bottom: 24px !important;
    box-shadow: 0 12px 30px rgba(0,0,0,0.15) !important;
  }}
  div[data-testid="stModalHeader"] {{ display: none !important; }}

  /* --- MINI CARDS (Catalog View Lama) --- */
  .mini-card {{
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 14px;
    background: #fff;
    transition: transform .12s ease, box-shadow .18s ease;
    will-change: transform;
    height: 100%;
    position: relative;
  }}
  .mini-card:hover {{
    transform: translateY(-1px);
    box-shadow: 0 10px 20px rgba(0,0,0,.06);
  }}
  .mini-title {{
    font-size: .95rem;
    font-weight: 800;
    color: var(--text);
    line-height: 1.2;
    margin: 10px 0 6px 0;
  }}
  .mini-price {{
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", monospace;
    font-weight: 800;
    color: #2c2c2c;
    font-size: .9rem;
  }}
  .mini-muted {{
    color: var(--muted);
    font-size: .84rem;
    line-height: 1.35;
    margin-top: 8px;
  }}
  .badge {{
    display: inline-flex;
    align-items: center;
    gap: 6px;
    padding: 4px 10px;
    border-radius: 999px;
    font-size: .72rem;
    font-weight: 800;
    letter-spacing: .06em;
    text-transform: uppercase;
  }}
  .badge-main {{ background: #e6f4ea; color: #137333; }}
  .badge-addon {{ background: #fff8e1; color: #f57f17; }}

  .card-topbar {{
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 10px;
  }}
  .mini-body {{ min-height: 98px; }}

  /* Preview (clamp) */
  .desc-clamp {{
    display: -webkit-box;
    -webkit-line-clamp: 3;
    -webkit-box-orient: vertical;
    overflow: hidden;
    color: #444;
    font-size: .90rem;
    font-family: inherit;
    line-height: 1.45;
    margin-top: 10px;
  }}
  .desc-more {{
    margin-top: 8px;
    color: var(--muted);
    font-size: .82rem;
  }}

  /* Hover tooltip full details */
  .desc-tooltip {{
    position: absolute;
    left: 12px;
    right: 12px;
    bottom: calc(100% + 10px);
    padding: 12px;
    border-radius: 12px;
    border: 1px solid var(--border);
    background: #fff;
    box-shadow: 0 14px 28px rgba(0,0,0,.08);
    display: none;
    z-index: 50;
  }}
  .mini-card:hover .desc-tooltip {{ display: block; }}
  .desc-tooltip-title {{
    font-weight: 900;
    margin-bottom: 6px;
    color: var(--text);
  }}
  .desc-tooltip-line {{
    font-size: .90rem;
    color: #444;
    line-height: 1.45;
    margin: 2px 0;
  }}
  .card-actions-gap {{ height: 14px; }}

  /* --- STICKY SUMMARY (Invoice Lama) --- */
  .sticky-wrap {{ position: sticky; top: 1.25rem; }}
  .summary-card {{
    border: 1px solid var(--border);
    border-radius: 14px;
    padding: 16px;
    background: #fff;
    box-shadow: 0 8px 18px rgba(0,0,0,.05);
  }}
  .summary-title {{
    font-weight: 900;
    color: var(--text);
    margin-bottom: 8px;
  }}
  .summary-row {{
    display: flex;
    justify-content: space-between;
    margin: 8px 0;
  }}
  .summary-label {{ color: var(--muted); font-size: .9rem; }}
  .summary-value {{ font-weight: 900; color: var(--text); }}
  .summary-divider {{
    height: 1px;
    background: #f0f0f0;
    margin: 12px 0;
  }}

  /* --- NEW: POS RECEIPT STYLING --- */
  .ticket-header {{
    text-align: center;
    border-bottom: 2px dashed #ddd;
    padding-bottom: 15px;
    margin-bottom: 15px;
  }}
  
  .ticket-total-box {{
    background: #2c3e50; 
    color: white; 
    padding: 15px; 
    border-radius: 8px; 
    text-align: right;
    margin-top: 20px;
    box-shadow: 0 4px 10px rgba(44, 62, 80, 0.3);
  }}

  /* Center number input di struk */
  div[data-testid="stNumberInput"] input {{
    text-align: center;
  }}
  
  /* --- HIDE STREAMLIT BRANDING --- */
  #MainMenu {{visibility: hidden;}}
  footer {{visibility: hidden;}}
  header {{visibility: hidden;}}
  
  /* Hide Element Specifics */
  [data-testid="stToolbar"] {{visibility: hidden !important;}}
  [data-testid="stDecoration"] {{visibility: hidden !important;}}
  [data-testid="stFooter"] {{visibility: hidden !important;}}
  .viewerBadge_container__1QSob {{display: none !important;}}
</style>
"""
