"""Reusable Plotly chart builders (plotly_dark). Pure: no Streamlit imports."""

import pandas as pd
import plotly.graph_objects as go

from ui.styles import ACCENT, PLOTLY_TEMPLATE, STATUS_COLORS, TAG_SWATCHES


def _base(fig: go.Figure, title: str = "", height: int = 360) -> go.Figure:
    fig.update_layout(
        template=PLOTLY_TEMPLATE,
        title=title,
        height=height,
        margin={"l": 40, "r": 20, "t": 50, "b": 40},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
    )
    return fig


def activity_heatmap(daily: list[dict], height: int = 240) -> go.Figure | None:
    """GitHub-style calendar heatmap of items added per day."""
    if not daily:
        return None
    df = pd.DataFrame(daily)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date")
    # Continuous daily index so gaps render as empty cells.
    full = pd.date_range(df["date"].min(), df["date"].max(), freq="D")
    s = df.set_index("date")["count"].reindex(full, fill_value=0)
    grid = pd.DataFrame({"date": full, "count": s.values})
    grid["weekday"] = grid["date"].dt.weekday  # Mon=0
    grid["week"] = ((grid["date"] - grid["date"].min()).dt.days // 7)

    pivot = grid.pivot_table(
        index="weekday", columns="week", values="count", fill_value=0
    )
    weekdays = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    fig = go.Figure(
        go.Heatmap(
            z=pivot.values,
            y=[weekdays[i] for i in pivot.index],
            colorscale="Reds",
            showscale=True,
            xgap=2,
            ygap=2,
            hovertemplate="%{z} added<extra></extra>",
        )
    )
    fig.update_yaxes(autorange="reversed")
    fig.update_xaxes(showticklabels=False, title="weeks")
    return _base(fig, "", height)


def hbar(items: list[dict], color: str = ACCENT, height: int = 360) -> go.Figure | None:
    """Horizontal bar of [{name, count}], largest at top."""
    if not items:
        return None
    items = sorted(items, key=lambda d: d["count"])
    fig = go.Figure(
        go.Bar(
            x=[d["count"] for d in items],
            y=[d["name"] for d in items],
            orientation="h",
            marker_color=color,
        )
    )
    return _base(fig, "", height)


def monthly_bar(daily: list[dict], color: str = ACCENT, height: int = 320):
    """Bar of items per month derived from the daily timeline."""
    if not daily:
        return None
    df = pd.DataFrame(daily)
    df["date"] = pd.to_datetime(df["date"])
    monthly = (
        df.set_index("date")["count"].resample("MS").sum().reset_index()
    )
    monthly["label"] = monthly["date"].dt.strftime("%b %Y")
    fig = go.Figure(
        go.Bar(x=monthly["label"], y=monthly["count"], marker_color=color)
    )
    return _base(fig, "", height)


def status_donut(items: list[dict], height: int = 320) -> go.Figure | None:
    if not items:
        return None
    colors = [STATUS_COLORS.get(d["name"], TAG_SWATCHES[i % len(TAG_SWATCHES)])
              for i, d in enumerate(items)]
    fig = go.Figure(
        go.Pie(
            labels=[d["name"] for d in items],
            values=[d["count"] for d in items],
            hole=0.55,
            marker={"colors": colors},
        )
    )
    return _base(fig, "", height)
