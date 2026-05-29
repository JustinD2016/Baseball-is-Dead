"""Baseball Analytics Suite — era-adjusted ranker + career explorer + league trends."""

import random
import unicodedata

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Baseball Analytics Suite",
    page_icon="⚾",
    layout="wide",
)

# ── Tech theme (augments dark config.toml) ───────────────────────────────────
st.markdown("""
<style>
/* Gradient headline */
.suite-title {
    background: linear-gradient(135deg, #00d4ff 0%, #7b68ee 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    background-clip: text;
    font-size: 2.2rem;
    font-weight: 800;
    letter-spacing: -0.5px;
    margin: 0;
    line-height: 1.2;
}
.suite-sub {
    color: #6a7590;
    font-size: 0.82rem;
    font-family: monospace;
    letter-spacing: 0.12em;
    text-transform: uppercase;
    margin-top: 4px;
}
.suite-header {
    text-align: center;
    padding: 0.9rem 0 1.1rem;
    border-bottom: 1px solid rgba(0,212,255,0.12);
    margin-bottom: 0.6rem;
}

/* Tabs */
.stTabs [data-baseweb="tab-list"] {
    gap: 2px;
    background: #0d1530;
    border-radius: 8px;
    padding: 4px;
    border: 1px solid rgba(0,212,255,0.14);
}
.stTabs [data-baseweb="tab"] {
    border-radius: 6px;
    border: none !important;
    color: #6a7590 !important;
    font-weight: 500;
    font-size: 0.88rem;
    padding: 6px 18px;
    background: transparent !important;
    transition: color 0.2s;
}
.stTabs [aria-selected="true"] {
    background: rgba(0,212,255,0.10) !important;
    color: #00d4ff !important;
}
.stTabs [data-baseweb="tab-highlight"] {
    background: #00d4ff !important;
    height: 2px !important;
    border-radius: 1px;
}

/* Buttons */
.stButton > button {
    background: rgba(0,212,255,0.07);
    border: 1px solid rgba(0,212,255,0.28);
    color: #00d4ff;
    border-radius: 6px;
    font-size: 0.85rem;
    transition: all 0.18s;
}
.stButton > button:hover {
    background: rgba(0,212,255,0.16);
    border-color: #00d4ff;
    box-shadow: 0 0 10px rgba(0,212,255,0.22);
    transform: translateY(-1px);
}

/* Section headers inside tabs */
h4 {
    color: #00d4ff !important;
    font-size: 0.78rem !important;
    text-transform: uppercase;
    letter-spacing: 0.12em;
    margin-bottom: 0.6rem !important;
}

/* Dividers */
hr { border-color: rgba(0,212,255,0.12) !important; }

/* Custom scrollbar */
::-webkit-scrollbar { width: 5px; height: 5px; }
::-webkit-scrollbar-track { background: #0a0f1e; }
::-webkit-scrollbar-thumb { background: rgba(0,212,255,0.25); border-radius: 3px; }
::-webkit-scrollbar-thumb:hover { background: rgba(0,212,255,0.55); }

/* Hide the sidebar toggle — we don't use the sidebar */
[data-testid="collapsedControl"] { display: none !important; }
</style>
""", unsafe_allow_html=True)

# ── DB / src imports ──────────────────────────────────────────────────────────
from src.db import (
    get_year_range, get_batting_stats, get_pitching_stats,
    get_batting_zscores, get_pitching_zscores, query_df,
)
from src.stats import (
    BATTING_STATS, PITCHING_STATS, BATTER_POSITIONS,
    DEFAULT_BATTING_STATS, DEFAULT_BATTING_WEIGHTS,
    DEFAULT_PITCHING_STATS, DEFAULT_PITCHING_WEIGHTS,
)
from src.ranking import rank_batters, rank_pitchers
from src.ui import render_results

# ── Chart palette & shared layout ────────────────────────────────────────────
PALETTE = [
    "#00d4ff", "#7b68ee", "#ff6b9d", "#ffa600", "#00ff88",
    "#ff4560", "#26e7a6", "#febc3b", "#775dd0", "#3f51b5",
    "#00b1f2", "#f48024", "#d7263d", "#02c39a", "#f7b731",
]

_LAYOUT_BASE = dict(
    template="plotly_dark",
    paper_bgcolor="rgba(10,15,30,0)",
    plot_bgcolor="rgba(13,21,48,0.55)",
    height=500,
    font=dict(family="system-ui, sans-serif", size=12, color="#8892a4"),
    legend=dict(
        orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1,
        font=dict(color="#c0c8d8"),
    ),
    xaxis=dict(
        gridcolor="rgba(0,212,255,0.07)",
        linecolor="rgba(0,212,255,0.18)",
        tickfont=dict(color="#8892a4"),
    ),
    yaxis=dict(
        gridcolor="rgba(0,212,255,0.07)",
        linecolor="rgba(0,212,255,0.18)",
        tickfont=dict(color="#8892a4"),
    ),
    margin=dict(l=10, r=10, t=58, b=10),
)


def line_chart(traces: list, title: str, x_lbl: str, y_lbl: str) -> go.Figure:
    fig = go.Figure()
    for t in traces:
        fig.add_trace(t)
    fig.update_layout(
        **_LAYOUT_BASE,
        title=dict(text=title, font=dict(color="#c0c8d8", size=13)),
        xaxis_title=x_lbl,
        yaxis_title=y_lbl,
    )
    return fig


def scatter_trace(x, y, name: str, color: str) -> go.Scatter:
    return go.Scatter(
        x=x, y=y, mode="lines+markers", name=name,
        line=dict(color=color, width=2),
        marker=dict(size=4, color=color),
    )


# ── Stat column mappings ──────────────────────────────────────────────────────
BATTER_STAT_COLS = {
    "Hits": "H", "Doubles": "2B", "Triples": "3B", "Home Runs": "HR",
    "Runs": "R", "RBI": "RBI", "Stolen Bases": "SB",
    "Walks": "BB", "Strikeouts": "SO", "GIDP": "GIDP",
    "Average": "BA", "On-Base %": "OBP", "Slugging": "SLG", "OPS": "OPS",
}
BATTER_RATE_STATS = {"Average", "On-Base %", "Slugging", "OPS"}

PITCHER_STAT_COLS = {
    "Strikeouts": "SO", "Walks": "BB", "Hits Allowed": "H", "HR Allowed": "HR",
    "Wins": "W", "Losses": "L", "Saves": "SV", "Innings Pitched": "IP",
    "ERA": "ERA", "WHIP": "WHIP", "K/9": "K9", "BB/9": "BB9",
}
PITCHER_RATE_STATS = {"ERA", "WHIP", "K/9", "BB/9"}

LEAGUE_BAT_COLS = {
    "Batting Average": "BA_mean",
    "On-Base %": "OBP_mean",
    "Slugging": "SLG_mean",
    "OPS": "OPS_mean",
    "HR per player": "HR_mean",
    "Runs per player": "R_mean",
    "Hits per player": "H_mean",
    "Walks per player": "BB_mean",
    "Strikeouts per player": "SO_mean",
}
LEAGUE_PIT_COLS = {
    "ERA": "ERA_mean",
    "WHIP": "WHIP_mean",
    "K/9": "K9_mean",
    "BB/9": "BB9_mean",
    "Wins per pitcher": "W_mean",
    "K per pitcher": "SO_mean",
    "Saves per pitcher": "SV_mean",
    "CG per pitcher": "CG_mean",
}


# ── Player lookup (DB-backed) ─────────────────────────────────────────────────
def _norm(s: str) -> str:
    return unicodedata.normalize("NFC", s).lower().strip() if isinstance(s, str) else ""


@st.cache_data(ttl=3600)
def _find_ids(first: str, last: str) -> list:
    df = query_df(
        "SELECT playerID FROM people WHERE LOWER(nameFirst)=? AND LOWER(nameLast)=?",
        (first, last),
    )
    return df["playerID"].tolist()


def resolve_player(name: str, table: str) -> str | None:
    parts = name.strip().split()
    if len(parts) < 2:
        return None
    ids = _find_ids(_norm(parts[0]), _norm(parts[1]))
    if not ids:
        return None
    if len(ids) == 1:
        return ids[0]
    counts = [
        query_df(f"SELECT COUNT(*) as n FROM {table} WHERE playerID=?", (pid,)).iloc[0]["n"]
        for pid in ids
    ]
    return ids[counts.index(max(counts))]


@st.cache_data(ttl=3600)
def get_player_batting(pid: str) -> pd.DataFrame:
    return query_df(
        "SELECT * FROM batting_consolidated WHERE playerID=? ORDER BY yearID", (pid,)
    )


@st.cache_data(ttl=3600)
def get_player_pitching(pid: str) -> pd.DataFrame:
    return query_df(
        "SELECT * FROM pitching_consolidated WHERE playerID=? ORDER BY yearID", (pid,)
    )


@st.cache_data(ttl=3600)
def get_league_batting_trends() -> pd.DataFrame:
    return query_df("SELECT * FROM league_avg_batting ORDER BY yearID")


@st.cache_data(ttl=3600)
def get_league_pitching_trends() -> pd.DataFrame:
    return query_df("SELECT * FROM league_avg_pitching ORDER BY yearID")


# ── Helpers ───────────────────────────────────────────────────────────────────
def col_series(df: pd.DataFrame, col: str) -> pd.Series:
    return df[col].reset_index(drop=True) if col in df.columns else pd.Series([None] * len(df))


def fmt_val(v: float) -> str:
    return f"{v:,.0f}" if abs(v) >= 1_000 else f"{v:.1f}"


def build_suffix(name: str, s: pd.Series, cumulative: bool, is_rate: bool) -> str:
    if cumulative and not is_rate:
        return f"{name}: Total {fmt_val(s.iloc[-1])}"
    return f"{name}: Avg {s.mean():.3f}" if is_rate else f"{name}: Avg {fmt_val(s.mean())}"


# ── Session state ─────────────────────────────────────────────────────────────
for _k, _d in [("colors_b", [PALETTE[0], PALETTE[1]]), ("colors_p", [PALETTE[0], PALETTE[1]])]:
    if _k not in st.session_state:
        st.session_state[_k] = _d

# ── Header ────────────────────────────────────────────────────────────────────
st.markdown("""
<div class="suite-header">
  <div class="suite-title">⚾ Baseball Analytics Suite</div>
  <div class="suite-sub">Player Ranker · Career Explorer · League Trends</div>
</div>
""", unsafe_allow_html=True)

# ── DB availability check ─────────────────────────────────────────────────────
try:
    min_db_yr, max_db_yr = get_year_range()
except Exception:
    st.error("Cannot open `data/lahman.db`. Run `python scripts/build_db.py` to build it.")
    st.stop()

# ── Tab layout ────────────────────────────────────────────────────────────────
tab_rank, tab_bat, tab_pit, tab_lg, tab_about = st.tabs([
    "🏆 Player Ranker",
    "🏏 Batters",
    "⚾ Pitchers",
    "📈 League Trends",
    "ℹ️ About",
])


# ════════════════════════════════════════════════════════════════════════════
# TAB 1 — PLAYER RANKER
# ════════════════════════════════════════════════════════════════════════════
with tab_rank:
    ctrl, main = st.columns([1, 3], gap="large")

    with ctrl:
        st.markdown("#### Settings")
        mode = st.radio("Player type", ["Batters", "Pitchers"], horizontal=True)
        st.divider()

        st.markdown("**Year range**")
        start_yr, end_yr = st.slider(
            "years", min_value=min_db_yr, max_value=max_db_yr,
            value=(min_db_yr, max_db_yr), label_visibility="collapsed",
        )

        position = "All"
        if mode == "Batters":
            position = st.selectbox("Position", BATTER_POSITIONS)
        top_n = st.slider("Players to show", 5, 50, 25)
        st.divider()

        st.markdown("**Qualification**")
        if mode == "Batters":
            min_pa = st.number_input("Min plate appearances", 50, 5_000, 500, step=50)
            min_ip = 30
        else:
            min_ip = st.number_input("Min innings pitched", 10, 3_000, 100, step=10)
            min_pa = 100
        st.divider()

        st.markdown("**Stats & weights**")
        if mode == "Batters":
            stat_defs = BATTING_STATS
            def_stats = DEFAULT_BATTING_STATS
            def_wts = DEFAULT_BATTING_WEIGHTS
        else:
            stat_defs = PITCHING_STATS
            def_stats = DEFAULT_PITCHING_STATS
            def_wts = DEFAULT_PITCHING_WEIGHTS

        sel = st.multiselect(
            "Stats",
            list(stat_defs.keys()),
            default=def_stats,
            format_func=lambda x: f"{stat_defs[x].short_name} – {stat_defs[x].display_name}",
        )
        if not sel:
            st.warning("Select at least one stat.")
            sel = def_stats[:1]

        wts = {}
        st.markdown("*Weights — normalized to 100%*")
        for sk in sel:
            wts[sk] = st.slider(
                stat_defs[sk].short_name, 0, 100,
                def_wts.get(sk, 100 // len(sel)),
                key=f"rw_{sk}",
            )
        total_w = sum(wts.values())
        if total_w > 0:
            st.caption(", ".join(
                f"{stat_defs[s].short_name} {wts[s]*100//total_w}%"
                for s in sel if wts[s] > 0
            ))
        else:
            st.warning("All weights are zero.")

    with main:
        pos_tag = f" · {position}" if mode == "Batters" and position != "All" else ""
        st.markdown(f"**Top {top_n} {mode.lower()}** · {start_yr}–{end_yr}{pos_tag}")

        if mode == "Batters":
            with st.spinner("Loading…"):
                raw = get_batting_stats(start_yr, end_yr, position, min_pa)
                zsc = get_batting_zscores(start_yr, end_yr, position, min_pa)
            if zsc.empty:
                st.warning("No qualifying batters. Lower min PA or expand the year range.")
            else:
                render_results(rank_batters(zsc, raw, sel, wts, top_n), sel, stat_defs, mode)
        else:
            with st.spinner("Loading…"):
                raw = get_pitching_stats(start_yr, end_yr, min_ip)
                zsc = get_pitching_zscores(start_yr, end_yr, min_ip)
            if zsc.empty:
                st.warning("No qualifying pitchers. Lower min IP or expand the year range.")
            else:
                render_results(rank_pitchers(zsc, raw, sel, wts, top_n), sel, stat_defs, mode)

        with st.expander("How does the ranking work?"):
            st.markdown("""
**Z-Score Normalization** — `z = (value − era_mean) / era_std` per season. Every stat is
expressed as standard deviations above the league average *for that year*, making a 1927
slugger directly comparable to a 2015 hitter.

**PA / IP Weighting** — z-scores are averaged across seasons weighted by plate appearances
(batters) or innings pitched (pitchers), so a full 162-game season counts more than a brief
stint.

**Composite Score** — your sliders set relative importance. Weights are normalized to 100%
and blended into one number. Higher is always better (ERA, WHIP, BB/9 are inverted).

*Data: Lahman Baseball Database · Chadwick Bureau · 1871–{max_db_yr}.*
""".format(max_db_yr=max_db_yr))


# ════════════════════════════════════════════════════════════════════════════
# TAB 2 — BATTERS
# ════════════════════════════════════════════════════════════════════════════
with tab_bat:
    ctrl, main = st.columns([1, 3], gap="large")

    with ctrl:
        st.markdown("#### Batting Controls")
        b_p1 = st.text_input("Player 1", value="Ted Williams", key="b_p1")
        b_p2 = st.text_input("Player 2 (optional)", value="", key="b_p2")
        b_career = st.checkbox("Align by career year", key="b_career")
        b_cumul = st.checkbox("Cumulative totals", key="b_cumul")
        b_stat = st.selectbox("Stat", list(BATTER_STAT_COLS.keys()), key="b_stat")
        if st.button("🎲 Randomize colors", key="b_colors"):
            st.session_state.colors_b = random.sample(PALETTE, 2)

    with main:
        pid1 = resolve_player(b_p1, "batting_consolidated") if b_p1.strip() else None

        if b_p1.strip() and pid1 is None:
            st.error(f'"{b_p1}" not found. Check spelling — First Last format required.')
        elif pid1:
            df1 = get_player_batting(pid1)
            pid2 = resolve_player(b_p2, "batting_consolidated") if b_p2.strip() else None
            if b_p2.strip() and pid2 is None:
                st.warning(f'"{b_p2}" not found — showing {b_p1} only.')
            df2 = get_player_batting(pid2) if pid2 else None

            col = BATTER_STAT_COLS[b_stat]
            is_rate = b_stat in BATTER_RATE_STATS

            x1 = list(range(1, len(df1) + 1)) if b_career else df1["yearID"].tolist()
            x_lbl = "Career Year" if b_career else "Season"
            s1 = col_series(df1, col)
            if b_cumul and not is_rate:
                s1 = s1.cumsum()
                y_lbl = f"Cumulative {b_stat}"
            else:
                y_lbl = b_stat

            traces = [scatter_trace(x1, s1, b_p1, st.session_state.colors_b[0])]
            suf1 = build_suffix(b_p1, s1, b_cumul, is_rate)
            title_parts = [suf1]

            if df2 is not None:
                x2 = list(range(1, len(df2) + 1)) if b_career else df2["yearID"].tolist()
                s2 = col_series(df2, col)
                if b_cumul and not is_rate:
                    s2 = s2.cumsum()
                traces.append(scatter_trace(x2, s2, b_p2, st.session_state.colors_b[1]))
                title_parts.append(build_suffix(b_p2, s2, b_cumul, is_rate))
                vs = f" vs {b_p2}"
            else:
                vs = ""

            career_tag = " (by career year)" if b_career else ""
            title = f"{b_p1}{vs} — {b_stat}{career_tag}<br><sup>{'  |  '.join(title_parts)}</sup>"
            st.plotly_chart(line_chart(traces, title, x_lbl, y_lbl), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 3 — PITCHERS
# ════════════════════════════════════════════════════════════════════════════
with tab_pit:
    ctrl, main = st.columns([1, 3], gap="large")

    with ctrl:
        st.markdown("#### Pitching Controls")
        p_p1 = st.text_input("Player 1", value="Randy Johnson", key="p_p1")
        p_p2 = st.text_input("Player 2 (optional)", value="", key="p_p2")
        p_career = st.checkbox("Align by career year", key="p_career")
        p_cumul = st.checkbox("Cumulative totals", key="p_cumul")
        p_stat = st.selectbox("Stat", list(PITCHER_STAT_COLS.keys()), key="p_stat")
        if st.button("🎲 Randomize colors", key="p_colors"):
            st.session_state.colors_p = random.sample(PALETTE, 2)

    with main:
        pid1 = resolve_player(p_p1, "pitching_consolidated") if p_p1.strip() else None

        if p_p1.strip() and pid1 is None:
            st.error(f'"{p_p1}" not found. Check spelling — First Last format required.')
        elif pid1:
            df1 = get_player_pitching(pid1)
            pid2 = resolve_player(p_p2, "pitching_consolidated") if p_p2.strip() else None
            if p_p2.strip() and pid2 is None:
                st.warning(f'"{p_p2}" not found — showing {p_p1} only.')
            df2 = get_player_pitching(pid2) if pid2 else None

            col = PITCHER_STAT_COLS[p_stat]
            is_rate = p_stat in PITCHER_RATE_STATS

            x1 = list(range(1, len(df1) + 1)) if p_career else df1["yearID"].tolist()
            x_lbl = "Career Year" if p_career else "Season"
            s1 = col_series(df1, col)
            if p_cumul and not is_rate:
                s1 = s1.cumsum()
                y_lbl = f"Cumulative {p_stat}"
            else:
                y_lbl = p_stat

            traces = [scatter_trace(x1, s1, p_p1, st.session_state.colors_p[0])]
            suf1 = build_suffix(p_p1, s1, p_cumul, is_rate)
            title_parts = [suf1]

            if df2 is not None:
                x2 = list(range(1, len(df2) + 1)) if p_career else df2["yearID"].tolist()
                s2 = col_series(df2, col)
                if p_cumul and not is_rate:
                    s2 = s2.cumsum()
                traces.append(scatter_trace(x2, s2, p_p2, st.session_state.colors_p[1]))
                title_parts.append(build_suffix(p_p2, s2, p_cumul, is_rate))
                vs = f" vs {p_p2}"
            else:
                vs = ""

            career_tag = " (by career year)" if p_career else ""
            title = f"{p_p1}{vs} — {p_stat}{career_tag}<br><sup>{'  |  '.join(title_parts)}</sup>"
            st.plotly_chart(line_chart(traces, title, x_lbl, y_lbl), use_container_width=True)


# ════════════════════════════════════════════════════════════════════════════
# TAB 4 — LEAGUE TRENDS
# ════════════════════════════════════════════════════════════════════════════
with tab_lg:
    ctrl, main = st.columns([1, 3], gap="large")

    with ctrl:
        st.markdown("#### League Trends")
        lg_mode = st.radio("Category", ["Batting", "Pitching"], horizontal=True, key="lg_mode")
        if lg_mode == "Batting":
            lg_stat = st.selectbox("Stat", list(LEAGUE_BAT_COLS.keys()), key="lg_bstat")
        else:
            lg_stat = st.selectbox("Stat", list(LEAGUE_PIT_COLS.keys()), key="lg_pstat")
        show_band = st.checkbox("Show ±1 std deviation band", value=True, key="lg_band")
        lg_yr_range = st.slider(
            "Year range", min_value=min_db_yr, max_value=max_db_yr,
            value=(min_db_yr, max_db_yr), key="lg_yr",
        )

    with main:
        if lg_mode == "Batting":
            df_lg = get_league_batting_trends()
            col_mean = LEAGUE_BAT_COLS[lg_stat]
        else:
            df_lg = get_league_pitching_trends()
            col_mean = LEAGUE_PIT_COLS[lg_stat]

        col_std = col_mean.replace("_mean", "_std")
        df_lg = df_lg[
            (df_lg["yearID"] >= lg_yr_range[0]) & (df_lg["yearID"] <= lg_yr_range[1])
        ]

        if col_mean not in df_lg.columns or df_lg.empty:
            st.warning("No data for this selection.")
        else:
            yy = df_lg["yearID"]
            mu = df_lg[col_mean]
            traces = [
                go.Scatter(x=yy, y=mu, mode="lines", name=lg_stat,
                           line=dict(color=PALETTE[0], width=2.5)),
            ]
            if show_band and col_std in df_lg.columns:
                sd = df_lg[col_std]
                traces.insert(0, go.Scatter(
                    x=list(yy) + list(yy)[::-1],
                    y=list(mu + sd) + list((mu - sd).clip(lower=0))[::-1],
                    fill="toself",
                    fillcolor="rgba(0,212,255,0.07)",
                    line=dict(color="rgba(0,0,0,0)"),
                    name="±1 std dev",
                    showlegend=True,
                ))

            title = (
                f"League Average {lg_stat} · {lg_yr_range[0]}–{lg_yr_range[1]}"
                f"<br><sup>Qualified {lg_mode.lower()} only"
                f" ({'≥100 PA' if lg_mode == 'Batting' else '≥30 IP'} per season)</sup>"
            )
            st.plotly_chart(
                line_chart(traces, title, "Season", lg_stat),
                use_container_width=True,
            )

            with st.expander("About this view"):
                st.markdown("""
League averages are computed from **qualified players only** (batters ≥100 PA per season;
pitchers ≥30 IP per season), so they reflect the typical *good* player rather than
roster-filler. The shaded band spans ±1 standard deviation — a wider band means
greater spread in performance that year (often a sign of rule changes or an era in flux).
""")


# ════════════════════════════════════════════════════════════════════════════
# TAB 5 — ABOUT
# ════════════════════════════════════════════════════════════════════════════
with tab_about:
    c1, c2 = st.columns(2, gap="large")

    with c1:
        st.markdown("### 🏆 Player Ranker")
        st.markdown("""
Era-adjusted ranking using z-score normalization. Every stat is converted to
"standard deviations above the league mean for that season," so a 1920s slugger
and a modern DH compete on the same scale.

- Configurable stat selection and per-stat weighting
- Supports all fielding positions and custom year windows
- PA / IP weighting rewards full-season performance
- Results update instantly as you adjust controls
""")
        st.markdown("### 🏏 / ⚾  Career Explorer")
        st.markdown("""
Year-by-year career arc charting for any player in the Lahman database.

- Compare two players side by side on one chart
- Align by **calendar year** or **career year** (rookie year = Year 1)
- Toggle cumulative totals for counting stats
- 15-color palette with one-click randomization
""")

    with c2:
        st.markdown("### 📈 League Trends")
        st.markdown("""
Track how the game has evolved over 150+ years. Batting averages, strikeout rates,
ERA, WHIP — plotted with an optional standard-deviation band to show how spread out
performance was in each era.
""")
        st.markdown("### 🗄️ Data")
        st.markdown(f"""
**[Lahman Baseball Database](https://sabr.org/lahman-database/)** (1871–{max_db_yr})

Copyright 1996–2024 Sean Lahman
Licensed under [CC BY-SA 3.0](http://creativecommons.org/licenses/by-sa/3.0/)
Distributed by the [Chadwick Bureau](https://github.com/chadwickbureau/baseballdatabank)

All data is served from a local SQLite database (`data/lahman.db`).
To rebuild it from the latest upstream CSVs, run:
```
python scripts/build_db.py
```
""")
        st.markdown("### How to Use")
        st.markdown("""
1. **Player Ranker** — Adjust stat weights and filters in the left panel.
2. **Batters / Pitchers** — Type a player name (*First Last*), pick a stat, and
   optionally add a second player to compare.
3. **League Trends** — Choose a stat category and drag the year slider.
""")
