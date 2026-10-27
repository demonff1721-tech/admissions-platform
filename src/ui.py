"""Shared modern UI design system and components for Alliance Admissions Platform."""

import streamlit as st


def inject_custom_css():
    """Injects high-end modern enterprise CSS across Streamlit pages."""
    st.markdown("""
    <style>
        /* Import clean modern font */
        @import url('https://fonts.googleapis.com/css2?family=Plus+Jakarta+Sans:wght@400;500;600;700;800&family=JetBrains+Mono:wght@400;500;600&display=swap');

        html, body, [class*="css"] {
            font-family: 'Plus Jakarta Sans', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            color: #0F172A;
        }

        code, pre, .stCode {
            font-family: 'JetBrains Mono', monospace !important;
        }

        /* App Background */
        .stApp {
            background-color: #F8FAFC;
        }

        /* Modern Gradient Header */
        .enterprise-header {
            background: linear-gradient(135deg, #0A192F 0%, #0F284E 50%, #162F56 100%);
            border: 1px solid rgba(255, 255, 255, 0.12);
            border-left: 5px solid #C59B27; /* Alliance Gold */
            color: #FFFFFF;
            padding: 1.5rem 2rem;
            border-radius: 14px;
            margin-bottom: 1.75rem;
            box-shadow: 0 10px 25px -5px rgba(10, 25, 47, 0.18), 0 8px 10px -6px rgba(10, 25, 47, 0.1);
            position: relative;
            overflow: hidden;
        }

        .enterprise-header::after {
            content: "";
            position: absolute;
            top: -50%;
            right: -10%;
            width: 300px;
            height: 300px;
            background: radial-gradient(circle, rgba(13, 148, 136, 0.15) 0%, rgba(0,0,0,0) 70%);
            pointer-events: none;
        }

        .header-tag {
            display: inline-flex;
            align-items: center;
            gap: 0.35rem;
            background: rgba(197, 155, 39, 0.2);
            border: 1px solid rgba(197, 155, 39, 0.4);
            color: #F8E7A2;
            padding: 0.25rem 0.75rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.06em;
            text-transform: uppercase;
            margin-bottom: 0.5rem;
        }

        .header-title {
            margin: 0;
            font-size: 1.85rem;
            font-weight: 800;
            letter-spacing: -0.02em;
            color: #FFFFFF;
            display: flex;
            align-items: center;
            gap: 0.6rem;
        }

        .header-subtitle {
            margin: 0.5rem 0 0 0;
            font-size: 0.925rem;
            color: #CBD5E1;
            font-weight: 400;
            line-height: 1.45;
            max-width: 900px;
        }

        /* Metric Cards */
        .metric-card-container {
            background: #FFFFFF;
            border: 1px solid #E2E8F0;
            border-radius: 12px;
            padding: 1.25rem 1.5rem;
            box-shadow: 0 1px 3px rgba(0,0,0,0.04);
            transition: all 0.2s ease-in-out;
            position: relative;
            overflow: hidden;
            margin-bottom: 1rem;
        }

        .metric-card-container:hover {
            transform: translateY(-2px);
            box-shadow: 0 10px 15px -3px rgba(15, 23, 42, 0.08), 0 4px 6px -4px rgba(15, 23, 42, 0.03);
            border-color: #CBD5E1;
        }

        .metric-card-accent {
            position: absolute;
            top: 0;
            left: 0;
            width: 4px;
            height: 100%;
            background: #0D9488;
        }

        .metric-card-title {
            font-size: 0.8rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 0.05em;
            color: #64748B;
            margin-bottom: 0.35rem;
        }

        .metric-card-value {
            font-size: 1.85rem;
            font-weight: 800;
            color: #0F172A;
            line-height: 1.1;
        }

        .metric-card-subtitle {
            font-size: 0.8rem;
            color: #94A3B8;
            margin-top: 0.35rem;
            font-weight: 500;
        }

        /* Status Badges */
        .badge-pill {
            display: inline-flex;
            align-items: center;
            gap: 0.3rem;
            padding: 0.2rem 0.65rem;
            border-radius: 9999px;
            font-size: 0.75rem;
            font-weight: 700;
            letter-spacing: 0.02em;
        }

        .badge-high {
            background-color: #DCFCE7;
            color: #15803D;
            border: 1px solid #BBF7D0;
        }

        .badge-medium {
            background-color: #FEF3C7;
            color: #B45309;
            border: 1px solid #FDE68A;
        }

        .badge-low {
            background-color: #F1F5F9;
            color: #475569;
            border: 1px solid #E2E8F0;
        }

        .badge-uncertain {
            background-color: #FEE2E2;
            color: #B91C1C;
            border: 1px solid #FECACA;
        }

        .badge-approved {
            background-color: #EFF6FF;
            color: #1D4ED8;
            border: 1px solid #DBEAFE;
        }

        /* Sidebar Styling */
        section[data-testid="stSidebar"] {
            background: linear-gradient(180deg, #0A192F 0%, #0F2038 100%) !important;
            border-right: 1px solid rgba(255, 255, 255, 0.08);
        }

        section[data-testid="stSidebar"] .stMarkdown p, 
        section[data-testid="stSidebar"] span {
            color: #E2E8F0 !important;
        }

        section[data-testid="stSidebar"] h1,
        section[data-testid="stSidebar"] h2,
        section[data-testid="stSidebar"] h3 {
            color: #FFFFFF !important;
        }

        /* Modern Tabs */
        .stTabs [data-baseweb="tab-list"] {
            gap: 1.5rem;
            background-color: transparent;
            border-bottom: 2px solid #E2E8F0;
            padding-bottom: 0.25rem;
        }

        .stTabs [data-baseweb="tab"] {
            font-size: 0.925rem;
            font-weight: 600;
            color: #64748B;
            padding: 0.5rem 0.25rem;
            background-color: transparent;
            border: none;
        }

        .stTabs [aria-selected="true"] {
            color: #0D9488 !important;
            border-bottom: 2px solid #0D9488 !important;
        }

        /* Polished Buttons */
        .stButton > button {
            border-radius: 8px;
            font-weight: 600;
            font-size: 0.875rem;
            transition: all 0.15s ease-in-out;
            border: 1px solid #CBD5E1;
            padding: 0.5rem 1rem;
        }

        .stButton > button:hover {
            border-color: #0D9488;
            color: #0D9488;
            transform: translateY(-1px);
            box-shadow: 0 4px 6px -1px rgba(0, 0, 0, 0.05);
        }

        /* Form Controls */
        .stTextInput > div > div > input,
        .stTextArea > div > div > textarea,
        .stSelectbox > div > div {
            border-radius: 8px !important;
            border: 1px solid #CBD5E1 !important;
            font-size: 0.9rem !important;
        }

        .stTextInput > div > div > input:focus,
        .stTextArea > div > div > textarea:focus {
            border-color: #0D9488 !important;
            box-shadow: 0 0 0 2px rgba(13, 148, 136, 0.15) !important;
        }

        /* Pulse indicator */
        .pulse-indicator {
            display: inline-block;
            width: 8px;
            height: 8px;
            border-radius: 50%;
            background-color: #10B981;
            box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            animation: pulse-green 2s infinite;
        }

        @keyframes pulse-green {
            0% {
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(16, 185, 129, 0.7);
            }
            70% {
                transform: scale(1);
                box-shadow: 0 0 0 6px rgba(16, 185, 129, 0);
            }
            100% {
                transform: scale(0.95);
                box-shadow: 0 0 0 0 rgba(16, 185, 129, 0);
            }
        }

        /* Callout Banners */
        .callout-box {
            background-color: #FFFFFF;
            border-radius: 10px;
            border-left: 4px solid #0D9488;
            box-shadow: 0 1px 3px rgba(0,0,0,0.05);
            padding: 1rem 1.25rem;
            margin-bottom: 1.25rem;
        }
    </style>
    """, unsafe_allow_html=True)


def render_page_header(title: str, subtitle: str, icon: str = "🎓", badge: str = "Alliance University, Bengaluru"):
    """Renders a consistent, enterprise-grade header at the top of pages."""
    inject_custom_css()
    st.markdown(f"""
    <div class="enterprise-header">
        <div class="header-tag">
            <span>🏛️</span> {badge}
        </div>
        <h1 class="header-title">
            <span>{icon}</span> {title}
        </h1>
        <p class="header-subtitle">
            {subtitle}
        </p>
    </div>
    """, unsafe_allow_html=True)


def render_sidebar_info():
    """Renders persistent enterprise university branding and system pulse in sidebar."""
    st.sidebar.markdown("""
    <div style="text-align: center; padding: 1.25rem 0.5rem 0.75rem 0.5rem; border-bottom: 1px solid rgba(255,255,255,0.08);">
        <div style="font-size: 2.2rem; filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));">🎓</div>
        <div style="font-weight: 800; font-size: 1.15rem; color: #FFFFFF; letter-spacing: 0.05em; margin-top: 0.35rem;">ALLIANCE UNIVERSITY</div>
        <div style="font-size: 0.725rem; color: #94A3B8; text-transform: uppercase; letter-spacing: 0.08em; font-weight: 600;">Admissions AI Operations</div>
        <div style="margin-top: 0.6rem; display: inline-flex; align-items: center; gap: 0.4rem; background: rgba(13,148,136,0.18); border: 1px solid rgba(13,148,136,0.4); padding: 0.2rem 0.6rem; border-radius: 9999px; font-size: 0.7rem; color: #5EEAD4; font-weight: 600;">
            <span class="pulse-indicator"></span> System Active & Governed
        </div>
    </div>
    """, unsafe_allow_html=True)

    st.sidebar.markdown("""
    <div style="padding: 0.75rem 0.25rem; font-size: 0.75rem; color: #94A3B8;">
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
            <span>Governance Rules:</span> <strong style="color: #FFFFFF;">R1 – R15</strong>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
            <span>Workflow Stages:</span> <strong style="color: #FFFFFF;">S1 – S9</strong>
        </div>
        <div style="display: flex; justify-content: space-between; margin-bottom: 0.3rem;">
            <span>Capacity Limit:</span> <strong style="color: #FFFFFF;">≤ 8 / Counsellor</strong>
        </div>
        <div style="display: flex; justify-content: space-between;">
            <span>Mode:</span> <strong style="color: #5EEAD4;">Deterministic Demo</strong>
        </div>
    </div>
    """, unsafe_allow_html=True)
    st.sidebar.markdown("---")


def render_kpi_card(title: str, value: str, subtitle: str, delta: str = None, color_accent: str = "#0D9488"):
    """Renders a high-finish KPI metric card."""
    delta_html = f"<div style='font-size: 0.75rem; color: #10B981; margin-top: 0.25rem; font-weight: 600;'>{delta}</div>" if delta else ""
    st.markdown(f"""
    <div class="metric-card-container">
        <div class="metric-card-accent" style="background: {color_accent};"></div>
        <div class="metric-card-title">{title}</div>
        <div class="metric-card-value">{value}</div>
        <div class="metric-card-subtitle">{subtitle}</div>
        {delta_html}
    </div>
    """, unsafe_allow_html=True)
