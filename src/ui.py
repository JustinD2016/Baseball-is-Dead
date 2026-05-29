"""Streamlit UI components for the baseball player comparison tool."""

import streamlit as st

from src.stats import (
    BATTING_STATS,
    PITCHING_STATS,
    BATTER_POSITIONS,
    DEFAULT_BATTING_STATS,
    DEFAULT_BATTING_WEIGHTS,
    DEFAULT_PITCHING_STATS,
    DEFAULT_PITCHING_WEIGHTS,
)


def render_sidebar(min_year: int, max_year: int) -> dict:
    """
    Render the sidebar controls and return the user's selections.

    Returns:
        Dict with keys: mode, start_year, end_year, position, top_n,
                        selected_stats, weights, min_pa, min_ip
    """
    st.sidebar.header("Settings")

    # Mode toggle
    mode = st.sidebar.radio("Player Type", ["Batters", "Pitchers"], horizontal=True)

    st.sidebar.divider()

    # Year range
    st.sidebar.subheader("Year Range")
    start_year, end_year = st.sidebar.slider(
        "Select years",
        min_value=min_year,
        max_value=max_year,
        value=(min_year, max_year),
        step=1,
    )

    # Position (batters only)
    position = "All"
    if mode == "Batters":
        position = st.sidebar.selectbox("Position", BATTER_POSITIONS, index=0)

    st.sidebar.divider()

    # Number of players
    top_n = st.sidebar.slider("Number of players to show", 5, 50, 25)

    # Minimum qualification
    st.sidebar.subheader("Minimum Qualification")
    if mode == "Batters":
        min_pa = st.sidebar.number_input("Min plate appearances", 50, 5000, 500, step=50)
        min_ip = 30
    else:
        min_ip = st.sidebar.number_input("Min innings pitched", 10, 3000, 100, step=10)
        min_pa = 100

    st.sidebar.divider()

    # Stat selection and weights
    st.sidebar.subheader("Stats & Weights")

    if mode == "Batters":
        stat_defs = BATTING_STATS
        default_stats = DEFAULT_BATTING_STATS
        default_weights = DEFAULT_BATTING_WEIGHTS
    else:
        stat_defs = PITCHING_STATS
        default_stats = DEFAULT_PITCHING_STATS
        default_weights = DEFAULT_PITCHING_WEIGHTS

    stat_options = list(stat_defs.keys())
    selected_stats = st.sidebar.multiselect(
        "Select stats to rank by",
        options=stat_options,
        default=default_stats,
        format_func=lambda x: f"{stat_defs[x].short_name} - {stat_defs[x].display_name}",
    )

    if not selected_stats:
        st.sidebar.warning("Please select at least one stat.")
        selected_stats = default_stats[:1]

    # Weight sliders
    weights = {}
    st.sidebar.markdown("**Adjust weights** (will be normalized to 100%)")
    for stat_key in selected_stats:
        stat_def = stat_defs[stat_key]
        default_w = default_weights.get(stat_key, 100 // len(selected_stats))
        weights[stat_key] = st.sidebar.slider(
            f"{stat_def.short_name} weight",
            0, 100, default_w,
            key=f"weight_{stat_key}",
        )

    total = sum(weights.values())
    if total > 0:
        pct_str = ", ".join(f"{stat_defs[s].short_name}: {weights[s]*100//total:.0f}%"
                            for s in selected_stats if weights[s] > 0)
        st.sidebar.caption(f"Normalized: {pct_str}")
    else:
        st.sidebar.warning("All weights are zero!")

    return {
        "mode": mode,
        "start_year": start_year,
        "end_year": end_year,
        "position": position,
        "top_n": top_n,
        "selected_stats": selected_stats,
        "weights": weights,
        "min_pa": min_pa,
        "min_ip": min_ip,
    }


def render_results(results_df, selected_stats, stat_defs, mode):
    """Render the results table and visualization."""
    if results_df.empty:
        st.warning("No players found matching your criteria. Try adjusting filters.")
        return

    # Build display columns
    display_cols = []
    if "name" in results_df.columns:
        # Handle duplicate 'name' columns from merge
        name_cols = [c for c in results_df.columns if c == "name"]
        if len(name_cols) > 1:
            results_df = results_df.loc[:, ~results_df.columns.duplicated()]
        display_cols.append("name")

    if "first_year" in results_df.columns and "last_year" in results_df.columns:
        results_df["Years"] = results_df["first_year"].astype(int).astype(str) + "-" + results_df["last_year"].astype(int).astype(str)
        display_cols.append("Years")

    if "seasons" in results_df.columns:
        display_cols.append("seasons")

    # Add raw stat values for selected stats
    for stat_key in selected_stats:
        raw_col = stat_defs[stat_key].raw_column
        if raw_col in results_df.columns:
            display_cols.append(raw_col)

    display_cols.append("composite_score")

    # Format the display DataFrame
    display_df = results_df[[c for c in display_cols if c in results_df.columns]].copy()

    # Rename columns for display
    rename_map = {"name": "Player", "seasons": "Seasons", "composite_score": "Score"}
    for stat_key in selected_stats:
        raw_col = stat_defs[stat_key].raw_column
        rename_map[raw_col] = stat_defs[stat_key].short_name
    display_df = display_df.rename(columns=rename_map)

    # Format numeric columns
    format_dict = {"Score": "{:.3f}"}
    for stat_key in selected_stats:
        short = stat_defs[stat_key].short_name
        if stat_defs[stat_key].is_rate:
            format_dict[short] = "{:.3f}"
        else:
            format_dict[short] = "{:.0f}"

    st.dataframe(
        display_df.style.format(format_dict, na_rep="-"),
        use_container_width=True,
        height=min(len(display_df) * 35 + 38, 900),
    )

    # Bar chart of top players
    if len(display_df) > 0 and "Player" in display_df.columns and "Score" in display_df.columns:
        import plotly.graph_objects as go
        top = display_df.head(min(15, len(display_df)))
        colors = [f"rgba(0,{int(180 + 75 * i / max(len(top)-1,1))},255,0.85)" for i in range(len(top))]
        fig = go.Figure(go.Bar(
            x=top["Score"], y=top["Player"],
            orientation="h",
            marker=dict(color=colors[::-1]),
            text=top["Score"].map("{:.3f}".format),
            textposition="outside",
            textfont=dict(color="#8892a4", size=11),
        ))
        fig.update_layout(
            template="plotly_dark",
            paper_bgcolor="rgba(10,15,30,0)",
            plot_bgcolor="rgba(13,21,48,0.55)",
            height=max(300, len(top) * 28 + 60),
            margin=dict(l=10, r=60, t=10, b=10),
            xaxis=dict(gridcolor="rgba(0,212,255,0.07)", title="Composite Score",
                       tickfont=dict(color="#8892a4")),
            yaxis=dict(gridcolor="rgba(0,212,255,0.07)", autorange="reversed",
                       tickfont=dict(color="#c0c8d8")),
            showlegend=False,
        )
        st.plotly_chart(fig, use_container_width=True)
