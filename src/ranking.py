"""Weighted ranking engine for comparing baseball players."""

import pandas as pd

from src.stats import BATTING_STATS, PITCHING_STATS, StatDef


def compute_composite_score(
    zscores_df: pd.DataFrame,
    selected_stats: list[str],
    weights: dict[str, float],
    stat_defs: dict[str, StatDef],
) -> pd.DataFrame:
    """
    Compute a weighted composite score for each player.

    Args:
        zscores_df: DataFrame with z-score columns (e.g., BA_z, HR_z)
        selected_stats: List of stat keys to include (e.g., ["BA", "HR", "RBI"])
        weights: Dict mapping stat key -> weight percentage (should sum to 100)
        stat_defs: The stat definitions dict (BATTING_STATS or PITCHING_STATS)

    Returns:
        DataFrame with added 'composite_score' column, sorted descending.
    """
    df = zscores_df.copy()

    # Normalize weights to sum to 1.0
    total_weight = sum(weights[s] for s in selected_stats)
    if total_weight == 0:
        df["composite_score"] = 0.0
        return df

    norm_weights = {s: weights[s] / total_weight for s in selected_stats}

    # Compute weighted sum of z-scores
    df["composite_zscore"] = 0.0
    for stat_key in selected_stats:
        stat_def = stat_defs[stat_key]
        z_col = stat_def.key  # e.g., "BA_z"
        if z_col in df.columns:
            df["composite_zscore"] += df[z_col].fillna(0) * norm_weights[stat_key]

    # Convert to 100-based rating (like OPS+/ERA+): 100 = average, each z-score unit = 100 points
    df["rating"] = (100 + df["composite_zscore"] * 100).round().astype(int)

    df = df.sort_values("composite_zscore", ascending=False).reset_index(drop=True)

    return df


def rank_batters(
    zscores_df: pd.DataFrame,
    raw_stats_df: pd.DataFrame,
    selected_stats: list[str],
    weights: dict[str, float],
    top_n: int = 25,
) -> pd.DataFrame:
    """
    Rank batters by composite score and return a display-ready DataFrame.

    Args:
        zscores_df: DataFrame from get_batting_zscores()
        raw_stats_df: DataFrame from get_batting_stats()
        selected_stats: List of stat keys
        weights: Dict of stat weights
        top_n: Number of players to return

    Returns:
        DataFrame ready for display with player info, raw stats, z-scores, and composite score.
    """
    scored = compute_composite_score(zscores_df, selected_stats, weights, BATTING_STATS)
    scored = scored.head(top_n)

    # Merge with raw stats for display
    if not raw_stats_df.empty and not scored.empty:
        raw_cols = ["playerID", "name", "first_year", "last_year", "seasons",
                    "G", "PA", "AB"]
        # Add raw stat columns that are selected
        for stat_key in selected_stats:
            stat_def = BATTING_STATS[stat_key]
            if stat_def.raw_column in raw_stats_df.columns:
                raw_cols.append(stat_def.raw_column)

        raw_subset = raw_stats_df[
            [c for c in raw_cols if c in raw_stats_df.columns]
        ].copy()

        scored = scored.merge(raw_subset, on="playerID", how="left", suffixes=("", "_raw"))

    return scored


def rank_pitchers(
    zscores_df: pd.DataFrame,
    raw_stats_df: pd.DataFrame,
    selected_stats: list[str],
    weights: dict[str, float],
    top_n: int = 25,
) -> pd.DataFrame:
    """Rank pitchers by composite score."""
    scored = compute_composite_score(zscores_df, selected_stats, weights, PITCHING_STATS)
    scored = scored.head(top_n)

    if not raw_stats_df.empty and not scored.empty:
        raw_cols = ["playerID", "name", "first_year", "last_year", "seasons",
                    "G", "GS", "IP"]
        for stat_key in selected_stats:
            stat_def = PITCHING_STATS[stat_key]
            if stat_def.raw_column in raw_stats_df.columns:
                raw_cols.append(stat_def.raw_column)

        raw_subset = raw_stats_df[
            [c for c in raw_cols if c in raw_stats_df.columns]
        ].copy()

        scored = scored.merge(raw_subset, on="playerID", how="left", suffixes=("", "_raw"))

    return scored
