"""Streamlit UI components for the baseball player comparison tool."""

import altair as alt
import pandas as pd
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
    Render the sidebar controls (filters only, no stat selection).

    Returns:
        Dict with keys: mode, start_year, end_year, position, top_n, min_pa, min_ip
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

    return {
        "mode": mode,
        "start_year": start_year,
        "end_year": end_year,
        "position": position,
        "top_n": top_n,
        "min_pa": min_pa,
        "min_ip": min_ip,
    }


def _init_selected_stats(mode: str):
    """Initialize session state for selected stats if needed."""
    key = f"selected_stats_{mode}"
    if key not in st.session_state:
        if mode == "Batters":
            st.session_state[key] = list(DEFAULT_BATTING_STATS)
        else:
            st.session_state[key] = list(DEFAULT_PITCHING_STATS)


def render_stat_controls(mode: str) -> tuple[list[str], dict[str, float]]:
    """
    Render stat selection (dropdown + chips) and weight sliders on the main page.

    Returns:
        (selected_stats, weights) tuple
    """
    if mode == "Batters":
        stat_defs = BATTING_STATS
        default_weights = DEFAULT_BATTING_WEIGHTS
    else:
        stat_defs = PITCHING_STATS
        default_weights = DEFAULT_PITCHING_WEIGHTS

    _init_selected_stats(mode)
    state_key = f"selected_stats_{mode}"
    selected = st.session_state[state_key]

    st.subheader("Stats & Weights")

    # Dropdown to add stats
    available = [s for s in stat_defs.keys() if s not in selected]
    if available:
        col_add, col_spacer = st.columns([2, 3])
        with col_add:
            choice = st.selectbox(
                "Add a stat",
                options=[""] + available,
                format_func=lambda x: "Select a stat to add..." if x == "" else f"{stat_defs[x].short_name} - {stat_defs[x].display_name}",
                key=f"add_stat_{mode}",
            )
            if choice and choice not in selected:
                selected.append(choice)
                st.session_state[state_key] = selected
                st.rerun()

    # Chips for selected stats (removable)
    if selected:
        chip_cols = st.columns(min(len(selected), 5))
        to_remove = None
        for i, stat_key in enumerate(selected):
            col_idx = i % min(len(selected), 5)
            with chip_cols[col_idx]:
                if st.button(f"\u2715 {stat_defs[stat_key].short_name}", key=f"remove_{mode}_{stat_key}"):
                    to_remove = stat_key
        if to_remove:
            selected.remove(to_remove)
            st.session_state[state_key] = selected
            st.rerun()
    else:
        st.warning("Please add at least one stat.")
        # Fall back to first default stat
        if mode == "Batters":
            selected = [DEFAULT_BATTING_STATS[0]]
        else:
            selected = [DEFAULT_PITCHING_STATS[0]]
        st.session_state[state_key] = selected

    # Weight sliders in columns
    weights = {}
    n_stats = len(selected)
    if n_stats > 0:
        n_cols = min(n_stats, 3)
        slider_cols = st.columns(n_cols)
        for i, stat_key in enumerate(selected):
            col_idx = i % n_cols
            with slider_cols[col_idx]:
                default_w = default_weights.get(stat_key, 100 // n_stats)
                weights[stat_key] = st.slider(
                    f"{stat_defs[stat_key].short_name} weight",
                    0, 100, default_w,
                    key=f"weight_{mode}_{stat_key}",
                )

        # Show normalized percentages
        total = sum(weights.values())
        if total > 0:
            pct_str = " | ".join(
                f"{stat_defs[s].short_name}: {weights[s]*100/total:.0f}%"
                for s in selected if weights[s] > 0
            )
            st.caption(f"Normalized weights: {pct_str}")

    return selected, weights


def render_results(results_df, selected_stats, stat_defs, mode):
    """Render the results table and visualization."""
    if results_df.empty:
        st.warning("No players found matching your criteria. Try adjusting filters.")
        return

    # Handle duplicate 'name' columns from merge
    if results_df.columns.duplicated().any():
        results_df = results_df.loc[:, ~results_df.columns.duplicated()]

    # Build display DataFrame
    display_cols = []

    if "name" in results_df.columns:
        display_cols.append("name")

    if "first_year" in results_df.columns and "last_year" in results_df.columns:
        results_df = results_df.copy()
        results_df["Years"] = (
            results_df["first_year"].astype(int).astype(str) + "-" +
            results_df["last_year"].astype(int).astype(str)
        )
        display_cols.append("Years")

    if "seasons" in results_df.columns:
        display_cols.append("seasons")

    # Add raw stat values for selected stats
    for stat_key in selected_stats:
        raw_col = stat_defs[stat_key].raw_column
        if raw_col in results_df.columns:
            display_cols.append(raw_col)

    display_cols.append("rating")

    display_df = results_df[[c for c in display_cols if c in results_df.columns]].copy()

    # Add 1-based rank column
    display_df.insert(0, "Rank", range(1, len(display_df) + 1))

    # Rename columns for display
    rename_map = {"name": "Player", "seasons": "Seasons", "rating": "Rating"}
    for stat_key in selected_stats:
        raw_col = stat_defs[stat_key].raw_column
        rename_map[raw_col] = stat_defs[stat_key].short_name
    display_df = display_df.rename(columns=rename_map)

    # Format numeric columns
    format_dict = {"Rating": "{:.0f}", "Rank": "{:.0f}"}
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
        hide_index=True,
    )

    # Bar chart with stat selector
    if len(display_df) > 0 and "Player" in display_df.columns:
        chart_n = min(15, len(display_df))
        chart_source = display_df.head(chart_n).copy()

        # Build chart stat options
        chart_options = ["Rating"]
        for stat_key in selected_stats:
            short = stat_defs[stat_key].short_name
            if short in chart_source.columns:
                chart_options.append(short)

        chart_stat = st.selectbox("Chart stat", chart_options, index=0, key=f"chart_stat_{mode}")

        if chart_stat in chart_source.columns:
            # Use altair to preserve ranking order
            chart_data = chart_source[["Player", chart_stat]].copy()
            chart_data["Player"] = pd.Categorical(
                chart_data["Player"],
                categories=chart_data["Player"].tolist(),
                ordered=True,
            )

            chart = (
                alt.Chart(chart_data)
                .mark_bar()
                .encode(
                    x=alt.X("Player:N", sort=chart_data["Player"].tolist(), title=None),
                    y=alt.Y(f"{chart_stat}:Q", title=chart_stat),
                    tooltip=["Player", chart_stat],
                )
                .properties(height=400)
            )
            st.altair_chart(chart, use_container_width=True)
