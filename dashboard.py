#!/usr/bin/env python3
"""Streamlit dashboard for Iran conflict news."""

import sqlite3
from datetime import datetime, timedelta

import pandas as pd
import streamlit as st

DB_PATH = "iran_news.db"


@st.cache_data(ttl=300)
def load_data() -> pd.DataFrame:
    try:
        conn = sqlite3.connect(DB_PATH)
        df = pd.read_sql_query(
            "SELECT id, title, description, source, pub_date, link, scraped_at FROM articles ORDER BY pub_date DESC",
            conn,
        )
        conn.close()
    except Exception:
        return pd.DataFrame(columns=["id", "title", "description", "source", "pub_date", "link", "scraped_at"])

    if not df.empty:
        df["pub_date"] = pd.to_datetime(df["pub_date"], errors="coerce")
        df["scraped_at"] = pd.to_datetime(df["scraped_at"], errors="coerce")
    return df


def run_scraper_inline():
    """Run the scraper and clear cache."""
    from scraper import run_scraper
    run_scraper()
    st.cache_data.clear()


# --- Auto-scrape on first load (needed for Streamlit Cloud) ---
if "scraped" not in st.session_state:
    with st.spinner("Fetching latest news..."):
        run_scraper_inline()
    st.session_state.scraped = True

# --- Page config ---
st.set_page_config(page_title="Iran Conflict News", page_icon="📰", layout="wide")
st.title("Iran Conflict News Dashboard")

# --- Sidebar ---
st.sidebar.header("Filters")

df = load_data()

# Source filter
sources = sorted(df["source"].unique().tolist()) if not df.empty else []
selected_sources = st.sidebar.multiselect("Sources", sources, default=sources)

# Date range filter
if not df.empty and df["pub_date"].notna().any():
    min_date = df["pub_date"].min().date()
    max_date = df["pub_date"].max().date()
else:
    min_date = datetime.now().date() - timedelta(days=7)
    max_date = datetime.now().date()

date_range = st.sidebar.date_input(
    "Date range",
    value=(min_date, max_date),
    min_value=min_date,
    max_value=max_date,
)

# Keyword search
keyword = st.sidebar.text_input("Search articles", "")

# Refresh
if st.sidebar.button("Refresh (re-scrape)"):
    with st.spinner("Scraping..."):
        run_scraper_inline()
    st.rerun()

auto_refresh = st.sidebar.toggle("Auto-refresh (5 min)")
if auto_refresh:
    st.markdown('<meta http-equiv="refresh" content="300">', unsafe_allow_html=True)

# --- Apply filters ---
filtered = df.copy()
if selected_sources:
    filtered = filtered[filtered["source"].isin(selected_sources)]

if isinstance(date_range, tuple) and len(date_range) == 2:
    start, end = pd.Timestamp(date_range[0]), pd.Timestamp(date_range[1]) + pd.Timedelta(days=1)
    filtered = filtered[filtered["pub_date"].between(start, end, inclusive="left") | filtered["pub_date"].isna()]

if keyword:
    mask = (
        filtered["title"].str.contains(keyword, case=False, na=False)
        | filtered["description"].str.contains(keyword, case=False, na=False)
    )
    filtered = filtered[mask]

# --- Metrics ---
col1, col2, col3 = st.columns(3)
col1.metric("Total Articles", len(filtered))
col2.metric("Sources", filtered["source"].nunique() if not filtered.empty else 0)
latest = filtered["pub_date"].max() if not filtered.empty and filtered["pub_date"].notna().any() else None
col3.metric("Latest Article", latest.strftime("%Y-%m-%d %H:%M") if pd.notna(latest) else "N/A")

# --- Chart ---
if not filtered.empty:
    st.subheader("Articles per Source")
    chart_data = filtered["source"].value_counts().reset_index()
    chart_data.columns = ["source", "count"]
    st.bar_chart(chart_data, x="source", y="count")

# --- Tabs ---
tab_cards, tab_table = st.tabs(["Article Cards", "Data Table"])

with tab_cards:
    if filtered.empty:
        st.info("No articles found. Try adjusting filters or run the scraper first.")
    else:
        for _, row in filtered.iterrows():
            with st.container():
                pub = row["pub_date"].strftime("%Y-%m-%d %H:%M") if pd.notna(row["pub_date"]) else "Unknown date"
                link = row["link"] if row["link"] else "#"
                st.markdown(f"#### [{row['title']}]({link})")
                st.caption(f"**{row['source']}** — {pub}")
                if row["description"]:
                    st.markdown(row["description"][:300] + ("..." if len(str(row["description"])) > 300 else ""))
                st.divider()

with tab_table:
    if filtered.empty:
        st.info("No articles to display.")
    else:
        display_df = filtered[["title", "source", "pub_date", "link"]].copy()
        display_df["pub_date"] = display_df["pub_date"].dt.strftime("%Y-%m-%d %H:%M")
        st.dataframe(
            display_df,
            column_config={
                "link": st.column_config.LinkColumn("Link"),
                "title": st.column_config.TextColumn("Title", width="large"),
                "source": st.column_config.TextColumn("Source"),
                "pub_date": st.column_config.TextColumn("Published"),
            },
            hide_index=True,
            use_container_width=True,
        )
