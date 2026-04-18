# Blood Bank Dashboard Visualizations using Plotly + Streamlit
# ------------------------------------------------------------
# Install:
# pip install streamlit plotly pandas

import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Blood Bank Dashboard", layout="wide")

st.title("🩸 Blood Bank Analytics Dashboard")

# ============================================================
# Sample Data
# ============================================================

# Blood Inventory Data
inventory_data = pd.DataFrame({
    "Blood Type": ["A+", "A-", "B+", "B-", "AB+", "AB-", "O+", "O-"],
    "Units Available": [45, 12, 38, 9, 20, 6, 60, 15]
})

# Requests Over Time
request_data = pd.DataFrame({
    "Date": pd.date_range(start="2025-01-01", periods=12, freq="ME"),
    "Requests": [120, 135, 150, 142, 165, 180, 170, 160, 175, 190, 200, 210]
})

# Donor Engagement Data
engagement_data = pd.DataFrame({
    "Status": ["Active", "Inactive", "New Donors"],
    "Count": [320, 140, 90]
})

# ============================================================
# Layout
# ============================================================

col1, col2 = st.columns(2)

# ============================================================
# 1. Blood Inventory Bar Chart
# ============================================================

with col1:
    st.subheader("📦 Blood Inventory Levels")

    fig_bar = px.bar(
        inventory_data,
        x="Blood Type",
        y="Units Available",
        color="Blood Type",
        text="Units Available",
        title="Available Blood Units by Type"
    )

    fig_bar.update_layout(
        xaxis_title="Blood Group",
        yaxis_title="Units",
        hovermode="x unified"
    )

    st.plotly_chart(fig_bar, use_container_width=True)

# ============================================================
# 2. Requests Over Time Line Chart
# ============================================================

with col2:
    st.subheader("📈 Blood Requests Trend")

    fig_line = px.line(
        request_data,
        x="Date",
        y="Requests",
        markers=True,
        title="Monthly Blood Requests"
    )

    fig_line.update_layout(
        xaxis_title="Month",
        yaxis_title="Requests",
        hovermode="x unified"
    )

    st.plotly_chart(fig_line, use_container_width=True)

# ============================================================
# 3. Donor Engagement Pie Chart
# ============================================================

st.subheader("👥 Donor Engagement Rate")

fig_pie = px.pie(
    engagement_data,
    names="Status",
    values="Count",
    hole=0.45,
    title="Donor Participation"
)

fig_pie.update_traces(textinfo="percent+label")

st.plotly_chart(fig_pie, use_container_width=True)
