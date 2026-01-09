import os
import sys
import uuid

import streamlit as st
import pandas as pd
import plotly.express as px

# ======================================================
# Setup
# ======================================================
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from pipeline import process_uploaded_pdf

st.set_page_config(page_title="Melodia Finance", layout="wide")

# ======================================================
# Cores / Tema
# ======================================================
HURST_YELLOW = "#F2C94C"
BG = "#0E0E0E"
CARD = "#151515"
TEXT = "#FFFFFF"
MUTED = "#CFCFCF"
BORDER = "rgba(255,255,255,0.08)"

# ======================================================
# CSS
# ======================================================
st.markdown(
    f"""
<style>
html, body, [data-testid="stAppViewContainer"] {{
  background-color: {BG} !important;
  color: {TEXT} !important;
}}

[data-testid="stSidebar"] {{
  background-color: {CARD} !important;
  border-right: 1px solid {BORDER};
}}

h1, h2, h3 {{
  color: {TEXT} !important;
  letter-spacing: -0.02em;
}}

.hero {{
  padding: 18px;
  border-radius: 18px;
  background: linear-gradient(180deg, rgba(255,255,255,0.05), rgba(255,255,255,0.02));
  border: 1px solid {BORDER};
  margin-bottom: 16px;
}}

.hero-title {{
  font-size: 2.2rem;
  font-weight: 800;
}}

.hero-sub {{
  color: {MUTED};
  margin-top: 6px;
}}

.card {{
  background: {CARD};
  border: 1px solid {BORDER};
  border-radius: 18px;
  padding: 14px;
  margin-bottom: 14px;
}}

.divider {{
  height: 1px;
  background: {BORDER};
  margin: 18px 0;
}}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
  <div class="hero-title">Melodia Finance</div>
  <div class="hero-sub">Rendimentos do ECAD em dashboards claros e comparáveis</div>
</div>
""",
    unsafe_allow_html=True,
)

# ======================================================
# Helpers
# ======================================================
def ensure_datetime(df, col):
    if col in df.columns:
        df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def add_period_cols(df, col):
    if col not in df.columns:
        return df
    df = df.dropna(subset=[col]).copy()
    df["MES"] = df[col].dt.to_period("M").astype(str)
    df["TRIM"] = df[col].dt.to_period("Q").astype(str).str.replace("Q", "-Q")
    df["ANO"] = df[col].dt.year.astype(str)
    return df


def fig_bar(df, x, y):
    fig = px.bar(
        df,
        x=x,
        y=y,
        color_discrete_sequence=[HURST_YELLOW]
    )

    fig.update_traces(
        texttemplate="R$ %{y:,.2f}",
        textposition="outside",
        textfont=dict(color="black", size=12),
        cliponaxis=False
    )

    fig.update_layout(
        plot_bgcolor=BG,
        paper_bgcolor=BG,
        font_color=TEXT,
        margin=dict(t=30, r=10, b=10, l=10)
    )
    return fig


def fig_line(df, x, y, color):
    fig = px.line(
        df,
        x=x,
        y=y,
        color=color,
        markers=True,
        color_discrete_sequence=px.colors.sequential.YlOrBr
    )
    fig.update_layout(
        plot_bgcolor=BG,
        paper_bgcolor=BG,
        font_color=TEXT
    )
    return fig


# ======================================================
# Sidebar
# ======================================================
with st.sidebar:
    uploaded_files = st.file_uploader(
        "Upload PDFs do ECAD",
        type=["pdf"],
        accept_multiple_files=True
    )

    filter_mode = st.radio("Filtro de período", ["Dia", "Mês", "Trimestre", "Ano"])


# ======================================================
# Main
# ======================================================
if not uploaded_files:
    st.info("Envie pelo menos um PDF para começar.")
    st.stop()

run_id = str(uuid.uuid4())[:8]
base_dir = os.path.join("workspace", run_id)
os.makedirs(base_dir, exist_ok=True)

dfs_cat, dfs_rub, dfs_obr = [], [], []

with st.status("Processando PDFs...", expanded=True):
    for file in uploaded_files:
        pdf_path = os.path.join(base_dir, file.name)
        with open(pdf_path, "wb") as f:
            f.write(file.getbuffer())

        df_cat, df_rub, df_obr = process_uploaded_pdf(
            pdf_path=pdf_path,
            base_dir=base_dir,
            base_rubricas_path="bases/Base_Rubrica_Original.xlsx"
        )

        dfs_cat.append(df_cat)
        dfs_rub.append(df_rub)
        dfs_obr.append(df_obr)

df_cat = ensure_datetime(pd.concat(dfs_cat), "DATA REFERENTE")
df_rub = ensure_datetime(pd.concat(dfs_rub), "DATA REFERENTE")
df_obr = ensure_datetime(pd.concat(dfs_obr), "Data")

df_cat = add_period_cols(df_cat, "DATA REFERENTE")
df_rub = add_period_cols(df_rub, "DATA REFERENTE")
df_obr = add_period_cols(df_obr, "Data")

# ======================================================
# Filtro de período
# ======================================================
if filter_mode == "Ano":
    anos = sorted(df_rub["ANO"].unique())
    sel = st.sidebar.multiselect("Ano(s)", anos, default=anos[-1:])
    df_cat = df_cat[df_cat["ANO"].isin(sel)]
    df_rub = df_rub[df_rub["ANO"].isin(sel)]
    df_obr = df_obr[df_obr["ANO"].isin(sel)]

elif filter_mode == "Mês":
    meses = sorted(df_rub["MES"].unique())
    sel = st.sidebar.multiselect("Mês(es)", meses, default=meses[-3:])
    df_cat = df_cat[df_cat["MES"].isin(sel)]
    df_rub = df_rub[df_rub["MES"].isin(sel)]
    df_obr = df_obr[df_obr["MES"].isin(sel)]

elif filter_mode == "Trimestre":
    trims = sorted(df_rub["TRIM"].unique())
    sel = st.sidebar.multiselect("Trimestre(s)", trims, default=trims[-1:])
    df_cat = df_cat[df_cat["TRIM"].isin(sel)]
    df_rub = df_rub[df_rub["TRIM"].isin(sel)]
    df_obr = df_obr[df_obr["TRIM"].isin(sel)]

# ======================================================
# Totais
# ======================================================
total_cat = df_cat["TOTAL GERAL"].sum()
total_rub = df_rub["TOTAL GERAL"].sum()
total_obr = df_obr["Rateio"].sum()

# Reconciliação
if total_rub > 0 and total_obr > 0:
    fator = total_rub / total_obr
    if abs(1 - fator) > 0.01:
        df_obr["Rateio"] *= fator
        total_obr = df_obr["Rateio"].sum()

# ======================================================
# KPIs
# ======================================================
c1, c2, c3 = st.columns(3)
c1.metric("Categorias", f"R$ {total_cat:,.2f}")
c2.metric("Rubricas", f"R$ {total_rub:,.2f}")
c3.metric("Obras", f"R$ {total_obr:,.2f}")

st.markdown('<div class="divider"></div>', unsafe_allow_html=True)

# ======================================================
# Evolução Rubricas
# ======================================================
st.markdown("### Evolução mensal – Rubricas")
rub_month = df_rub.groupby("MES", as_index=False)["TOTAL GERAL"].sum()
st.plotly_chart(fig_bar(rub_month, "MES", "TOTAL GERAL"), use_container_width=True)

# ======================================================
# Obras – comparação
# ======================================================
st.markdown("### Obras – rendimento mês a mês")
obras = sorted(df_obr["Nome Obra"].unique())
sel_obras = st.multiselect("Selecione obras", obras, default=obras[:3])

if sel_obras:
    obra_month = (
        df_obr[df_obr["Nome Obra"].isin(sel_obras)]
        .groupby(["MES", "Nome Obra"], as_index=False)["Rateio"]
        .sum()
    )
    st.plotly_chart(
        fig_line(obra_month, "MES", "Rateio", "Nome Obra"),
        use_container_width=True
    )

# ======================================================
# Tabelas
# ======================================================
with st.expander("Ver dados detalhados"):
    st.dataframe(df_cat)
    st.dataframe(df_rub)
    st.dataframe(df_obr)
