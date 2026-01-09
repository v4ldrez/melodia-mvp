import os
import sys
import uuid

import streamlit as st
import pandas as pd
import plotly.express as px


# -----------------------------
# Setup (PYTHONPATH / Config)
# -----------------------------
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from pipeline import process_uploaded_pdf

st.set_page_config(page_title="Melodia Finance", layout="wide")


# -----------------------------
# Styling (Dark + Hurst Yellow)
# -----------------------------
HURST_YELLOW = "#F2C94C"
BG = "#0E0E0E"
CARD = "#151515"
TEXT = "#FFFFFF"
MUTED = "#CFCFCF"
BORDER = "rgba(255,255,255,0.08)"

st.markdown(
    f"""
<style>
:root {{
  --bg: {BG};
  --card: {CARD};
  --text: {TEXT};
  --muted: {MUTED};
  --accent: {HURST_YELLOW};
  --border: {BORDER};
  --radius: 18px;
}}

html, body, [data-testid="stAppViewContainer"] {{
  background-color: var(--bg) !important;
  color: var(--text) !important;
}}

[data-testid="stSidebar"] {{
  background-color: var(--card) !important;
  border-right: 1px solid var(--border);
}}

h1, h2, h3, h4 {{
  color: var(--text) !important;
  letter-spacing: -0.02em;
}}

.small-muted {{
  color: var(--muted);
  font-size: 0.92rem;
}}

.hero {{
  padding: 18px 18px 10px 18px;
  border-radius: var(--radius);
  background: linear-gradient(180deg, rgba(255,255,255,0.04) 0%, rgba(255,255,255,0.02) 100%);
  border: 1px solid var(--border);
  margin-bottom: 14px;
}}

.hero-title {{
  font-size: 2.1rem;
  font-weight: 800;
  margin: 0;
  color: var(--text);
}}

.hero-sub {{
  margin-top: 8px;
  color: var(--muted);
  font-size: 1rem;
}}

.card {{
  background: var(--card);
  border: 1px solid var(--border);
  border-radius: var(--radius);
  padding: 14px 14px;
  margin-bottom: 12px;
}}

.divider-soft {{
  height: 1px;
  background: var(--border);
  margin: 16px 0;
}}

[data-testid="stMetricValue"] {{
  color: var(--text) !important;
}}

[data-testid="stMetricDelta"] {{
  color: var(--muted) !important;
}}
</style>
""",
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="hero">
  <div class="hero-title">Melodia Finance</div>
  <div class="hero-sub">Upload de PDFs do ECAD → dashboards interativos para entender seus rendimentos.</div>
</div>
""",
    unsafe_allow_html=True,
)


# -----------------------------
# Helpers
# -----------------------------
def ensure_datetime(df: pd.DataFrame, col: str) -> pd.DataFrame:
    if df is None or df.empty or col not in df.columns:
        return df
    df = df.copy()
    df[col] = pd.to_datetime(df[col], errors="coerce")
    return df


def add_period_cols(df: pd.DataFrame, date_col: str) -> pd.DataFrame:
    """Cria colunas PERIODO_DIA / MES / TRIM / ANO baseadas em date_col."""
    if df is None or df.empty or date_col not in df.columns:
        return df

    df = df.copy()
    df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
    df = df.dropna(subset=[date_col])

    if df.empty:
        return df

    df["PERIODO_DIA"] = df[date_col].dt.date.astype(str)           # YYYY-MM-DD
    df["PERIODO_MES"] = df[date_col].dt.to_period("M").astype(str) # YYYY-MM
    q = df[date_col].dt.to_period("Q").astype(str)                 # 2025Q3
    df["PERIODO_TRIM"] = q.str.replace("Q", "-Q", regex=False)     # 2025-Q3
    df["PERIODO_ANO"] = df[date_col].dt.year.astype(str)           # YYYY
    return df


def filter_by_mode(df: pd.DataFrame, mode: str, date_col: str, selection):
    """
    mode: "Dia"|"Mês"|"Trimestre"|"Ano"
    selection:
      - Dia: (start_ts, end_ts)
      - Mês/Trimestre/Ano: list[str]
    """
    if df is None or df.empty:
        return df

    if mode == "Dia":
        start_ts, end_ts = selection
        if date_col not in df.columns:
            return df
        df2 = df.copy()
        df2[date_col] = pd.to_datetime(df2[date_col], errors="coerce")
        return df2[(df2[date_col] >= start_ts) & (df2[date_col] <= end_ts)]

    col_map = {"Mês": "PERIODO_MES", "Trimestre": "PERIODO_TRIM", "Ano": "PERIODO_ANO"}
    pcol = col_map.get(mode)
    if not pcol or pcol not in df.columns:
        return df

    sel_list = selection or []
    if not sel_list:
        return df.iloc[0:0]  # nada selecionado => vazio
    return df[df[pcol].isin(sel_list)]


def unique_sorted(df: pd.DataFrame, col: str):
    if df is None or df.empty or col not in df.columns:
        return []
    vals = df[col].dropna().astype(str).unique().tolist()
    return sorted(vals)


def currency_fmt(v: float) -> str:
    if v is None:
        return "—"
    try:
        return f"R$ {float(v):,.2f}"
    except Exception:
        return "—"


def fig_bar(df, x, y, color=None):
    # barras amarelas por padrão
    if color:
        fig = px.bar(df, x=x, y=y, color=color)
        fig.update_layout(
            plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
            legend_title_text=""
        )
        return fig

    fig = px.bar(df, x=x, y=y, color_discrete_sequence=[HURST_YELLOW])
    fig.update_layout(
        plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
        legend_title_text=""
    )
    return fig


def fig_line(df, x, y, color=None, markers=True):
    # linha amarela quando é série única; multi-série usa paleta amarelo→branco
    if color:
        fig = px.line(df, x=x, y=y, color=color, markers=markers,
                      color_discrete_sequence=px.colors.sequential.YlOrBr)
    else:
        fig = px.line(df, x=x, y=y, markers=markers,
                      color_discrete_sequence=[HURST_YELLOW])

    fig.update_layout(
        plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT,
        legend_title_text=""
    )
    return fig


# -----------------------------
# Sidebar (Upload + Filtros)
# -----------------------------
with st.sidebar:
    st.markdown("### Upload")
    uploaded_files = st.file_uploader(
        "Envie um ou mais PDFs do ECAD",
        type=["pdf"],
        accept_multiple_files=True
    )

    st.markdown("---")
    st.markdown("### Filtro de período")
    filter_mode = st.radio("Filtrar por", ["Dia", "Mês", "Trimestre", "Ano"])

    st.markdown('<div class="small-muted">O filtro afeta categorias, rubricas e obras.</div>', unsafe_allow_html=True)


# -----------------------------
# Main
# -----------------------------
if not uploaded_files:
    st.info("Envie um ou mais PDFs para começar.")
    st.stop()

run_id = str(uuid.uuid4())[:8]
base_run_dir = os.path.join("workspace", run_id)
os.makedirs(base_run_dir, exist_ok=True)

base_rubricas_path = os.path.join("bases", "Base_Rubrica_Original.xlsx")

dfs_cat, dfs_rub, dfs_obr = [], [], []

with st.status("Processando PDFs...", expanded=True) as status:
    for i, uploaded in enumerate(uploaded_files, start=1):
        status.update(label=f"Processando {uploaded.name} ({i}/{len(uploaded_files)})")

        pdf_dir = os.path.join(base_run_dir, f"{i:03d}_{uploaded.name.replace('.pdf','')}")
        os.makedirs(pdf_dir, exist_ok=True)

        pdf_path = os.path.join(pdf_dir, uploaded.name)
        with open(pdf_path, "wb") as f:
            f.write(uploaded.getbuffer())

        try:
            df_cat, df_rub, df_obr = process_uploaded_pdf(
                pdf_path=pdf_path,
                base_dir=pdf_dir,
                base_rubricas_path=base_rubricas_path
            )

            if isinstance(df_cat, pd.DataFrame) and not df_cat.empty:
                dfs_cat.append(df_cat)
            if isinstance(df_rub, pd.DataFrame) and not df_rub.empty:
                dfs_rub.append(df_rub)
            if isinstance(df_obr, pd.DataFrame) and not df_obr.empty:
                dfs_obr.append(df_obr)

        except Exception as e:
            st.error(f"Erro ao processar {uploaded.name}")
            st.exception(e)

    status.update(label="Processamento concluído!", state="complete")

# Consolidar
df_cat = pd.concat(dfs_cat, ignore_index=True) if dfs_cat else pd.DataFrame()
df_rub = pd.concat(dfs_rub, ignore_index=True) if dfs_rub else pd.DataFrame()
df_obr = pd.concat(dfs_obr, ignore_index=True) if dfs_obr else pd.DataFrame()

# Normalizar datas e criar colunas de período
df_cat = ensure_datetime(df_cat, "DATA REFERENTE")
df_rub = ensure_datetime(df_rub, "DATA REFERENTE")
df_obr = ensure_datetime(df_obr, "Data")

df_cat = add_period_cols(df_cat, "DATA REFERENTE")
df_rub = add_period_cols(df_rub, "DATA REFERENTE")
df_obr = add_period_cols(df_obr, "Data")

# Range global (modo Dia) e listas (mês/trim/ano)
all_dates = []
for df, col in [(df_cat, "DATA REFERENTE"), (df_rub, "DATA REFERENTE"), (df_obr, "Data")]:
    if df is not None and not df.empty and col in df.columns:
        all_dates.extend([df[col].min(), df[col].max()])
all_dates = [d for d in all_dates if pd.notna(d)]
min_dt = min(all_dates) if all_dates else pd.to_datetime("2000-01-01")
max_dt = max(all_dates) if all_dates else pd.to_datetime("2000-01-01")

months = sorted(set(unique_sorted(df_cat, "PERIODO_MES") + unique_sorted(df_rub, "PERIODO_MES") + unique_sorted(df_obr, "PERIODO_MES")))
quarters = sorted(set(unique_sorted(df_cat, "PERIODO_TRIM") + unique_sorted(df_rub, "PERIODO_TRIM") + unique_sorted(df_obr, "PERIODO_TRIM")))
years = sorted(set(unique_sorted(df_cat, "PERIODO_ANO") + unique_sorted(df_rub, "PERIODO_ANO") + unique_sorted(df_obr, "PERIODO_ANO")))

# UI do filtro (na sidebar)
with st.sidebar:
    if filter_mode == "Dia":
        start_date, end_date = st.date_input(
            "Intervalo de datas",
            value=(min_dt.date(), max_dt.date())
        )
        # inclui o dia inteiro do end_date
        sel = (pd.to_datetime(start_date), pd.to_datetime(end_date) + pd.Timedelta(days=1) - pd.Timedelta(seconds=1))

    elif filter_mode == "Mês":
        default = months[-6:] if len(months) >= 6 else months
        sel = st.multiselect("Selecione mês(es)", months, default=default)

    elif filter_mode == "Trimestre":
        default = quarters[-4:] if len(quarters) >= 4 else quarters
        sel = st.multiselect("Selecione trimestre(s)", quarters, default=default)

    else:  # Ano
        default = years[-3:] if len(years) >= 3 else years
        sel = st.multiselect("Selecione ano(s)", years, default=default)

# Aplicar filtro
df_cat_f = filter_by_mode(df_cat, filter_mode, "DATA REFERENTE", sel)
df_rub_f = filter_by_mode(df_rub, filter_mode, "DATA REFERENTE", sel)
df_obr_f = filter_by_mode(df_obr, filter_mode, "Data", sel)

# Totais + Reconciliação
total_cat = 0.0
total_rub = 0.0
total_obr = 0.0

if not df_cat_f.empty and "TOTAL GERAL" in df_cat_f.columns:
    total_cat = pd.to_numeric(df_cat_f["TOTAL GERAL"], errors="coerce").fillna(0).sum()

if not df_rub_f.empty and "TOTAL GERAL" in df_rub_f.columns:
    total_rub = pd.to_numeric(df_rub_f["TOTAL GERAL"], errors="coerce").fillna(0).sum()

if not df_obr_f.empty and "Rateio" in df_obr_f.columns:
    df_obr_f = df_obr_f.copy()
    df_obr_f["Rateio"] = pd.to_numeric(df_obr_f["Rateio"], errors="coerce").fillna(0.0)
    total_obr = df_obr_f["Rateio"].sum()

# Reconciliação MVP: Obras bate com Rubricas
if total_rub > 0 and total_obr > 0:
    fator = total_rub / total_obr
    if abs(1 - fator) > 0.01:
        df_obr_f["Rateio"] = df_obr_f["Rateio"] * fator
        total_obr = df_obr_f["Rateio"].sum()
        st.caption(f"⚙️ Obras normalizado para bater com Rubricas (fator: {fator:.4f}).")

# KPIs (Cards)
k1, k2, k3 = st.columns(3)
with k1:
    st.markdown('<div class="card"><h3>Total (Categorias)</h3></div>', unsafe_allow_html=True)
    st.metric("", currency_fmt(total_cat))
with k2:
    st.markdown('<div class="card"><h3>Total (Rubricas)</h3></div>', unsafe_allow_html=True)
    st.metric("", currency_fmt(total_rub))
with k3:
    st.markdown('<div class="card"><h3>Total (Obras)</h3></div>', unsafe_allow_html=True)
    st.metric("", currency_fmt(total_obr))

st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)

# Evolução (Rubricas)
st.markdown('<div class="card"><h3>Evolução (Rubricas)</h3></div>', unsafe_allow_html=True)
if df_rub_f.empty or "TOTAL GERAL" not in df_rub_f.columns or "PERIODO_MES" not in df_rub_f.columns:
    st.info("Sem dados suficientes.")
else:
    tmp = df_rub_f.copy()
    tmp["TOTAL GERAL"] = pd.to_numeric(tmp["TOTAL GERAL"], errors="coerce").fillna(0)
    rub_month = (
        tmp.groupby("PERIODO_MES", as_index=False)["TOTAL GERAL"]
           .sum()
           .sort_values("PERIODO_MES")
    )
    st.plotly_chart(fig_bar(rub_month, x="PERIODO_MES", y="TOTAL GERAL"), use_container_width=True)

st.markdown('<div class="divider-soft"></div>', unsafe_allow_html=True)

# Abas detalhadas
st.markdown('<div class="card"><h3>Análises detalhadas</h3></div>', unsafe_allow_html=True)
tab1, tab2, tab3 = st.tabs(["Rubricas", "Categorias", "Obras"])

with tab1:
    st.subheader("Rubricas — Ranking e Drilldown")
    if df_rub_f.empty:
        st.info("Sem dados de rubricas no filtro.")
    else:
        tmp = df_rub_f.copy()
        tmp["TOTAL GERAL"] = pd.to_numeric(tmp.get("TOTAL GERAL", 0), errors="coerce").fillna(0)
        tmp["Rubrica_Modelo"] = tmp.get("Rubrica_Modelo", pd.Series(["Sem mapeamento"] * len(tmp))).fillna("Sem mapeamento")
        tmp["RUBRICA"] = tmp.get("RUBRICA", pd.Series(["(Sem nome)"] * len(tmp))).fillna("(Sem nome)")

        colA, colB = st.columns([1.2, 1])
        with colA:
            modelos = ["(Todos)"] + sorted(tmp["Rubrica_Modelo"].unique().tolist())
            sel_modelo = st.selectbox("Filtrar por Rubrica Modelo", modelos, key="rub_sel_modelo")
        with colB:
            topn = st.slider("Top N", 5, 50, 15, key="rub_topn")

        tmp_f = tmp if sel_modelo == "(Todos)" else tmp[tmp["Rubrica_Modelo"] == sel_modelo]

        by_modelo = (
            tmp_f.groupby("Rubrica_Modelo", as_index=False)["TOTAL GERAL"]
                 .sum()
                 .sort_values("TOTAL GERAL", ascending=False)
        )
        st.plotly_chart(fig_bar(by_modelo.head(topn), x="Rubrica_Modelo", y="TOTAL GERAL"), use_container_width=True)
        st.dataframe(by_modelo.head(topn), use_container_width=True)

        st.markdown("#### Drilldown: Rubricas dentro do Modelo")
        modelo_drill = st.selectbox(
            "Escolha um modelo para detalhar",
            options=sorted(tmp_f["Rubrica_Modelo"].unique().tolist()),
            key="rub_drill_modelo"
        )
        drill = tmp_f[tmp_f["Rubrica_Modelo"] == modelo_drill]
        by_rubrica = (
            drill.groupby("RUBRICA", as_index=False)["TOTAL GERAL"]
                 .sum()
                 .sort_values("TOTAL GERAL", ascending=False)
                 .head(topn)
        )
        st.plotly_chart(fig_bar(by_rubrica, x="RUBRICA", y="TOTAL GERAL"), use_container_width=True)
        st.dataframe(by_rubrica, use_container_width=True)

with tab2:
    st.subheader("Categorias — Distribuição e Evolução")
    if df_cat_f.empty:
        st.info("Sem dados de categorias no filtro.")
    else:
        tmp = df_cat_f.copy()
        tmp["TOTAL GERAL"] = pd.to_numeric(tmp.get("TOTAL GERAL", 0), errors="coerce").fillna(0)
        tmp["CATEGORIA"] = tmp.get("CATEGORIA", pd.Series(["(Sem nome)"] * len(tmp))).fillna("(Sem nome)")

        colA, colB = st.columns([1, 1])
        with colA:
            topn = st.slider("Top N categorias", 5, 30, 12, key="cat_topn")
        with colB:
            modo = st.radio("Visual", ["Barras", "Pizza (share)"], horizontal=True, key="cat_mode")

        by_cat = (
            tmp.groupby("CATEGORIA", as_index=False)["TOTAL GERAL"]
               .sum()
               .sort_values("TOTAL GERAL", ascending=False)
        )

        if modo == "Barras":
            st.plotly_chart(fig_bar(by_cat.head(topn), x="CATEGORIA", y="TOTAL GERAL"), use_container_width=True)
        else:
            pie = by_cat.head(min(topn, 12)).copy()
            fig = px.pie(pie, names="CATEGORIA", values="TOTAL GERAL",
                         color_discrete_sequence=[HURST_YELLOW, "#EDEDED", "#CFCFCF", "#AFAFAF"])
            fig.update_layout(plot_bgcolor=BG, paper_bgcolor=BG, font_color=TEXT)
            st.plotly_chart(fig, use_container_width=True)

        if "PERIODO_MES" in tmp.columns and tmp["PERIODO_MES"].nunique() >= 2:
            evol = (
                tmp.groupby(["PERIODO_MES", "CATEGORIA"], as_index=False)["TOTAL GERAL"]
                   .sum()
                   .sort_values("PERIODO_MES")
            )
            st.plotly_chart(fig_line(evol, x="PERIODO_MES", y="TOTAL GERAL", color="CATEGORIA"), use_container_width=True)
        else:
            st.caption("Evolução mensal aparece quando houver 2+ meses no filtro.")

with tab3:
    st.subheader("Obras — Evolução mês a mês (comparação)")
    if df_obr_f.empty or "Nome Obra" not in df_obr_f.columns or "Rateio" not in df_obr_f.columns:
        st.info("Sem dados suficientes de obras no filtro.")
    else:
        tmp = df_obr_f.copy()
        tmp["Rateio"] = pd.to_numeric(tmp["Rateio"], errors="coerce").fillna(0.0)
        tmp["Nome Obra"] = tmp["Nome Obra"].fillna("(Sem nome)")

        if "PERIODO_MES" not in tmp.columns:
            st.info("Sem informação de mês nas obras.")
        else:
            obras = sorted(tmp["Nome Obra"].unique().tolist())

            # sugestão automática (top 5 do filtro)
            sugestao = (
                tmp.groupby("Nome Obra", as_index=False)["Rateio"]
                   .sum()
                   .sort_values("Rateio", ascending=False)
                   .head(5)["Nome Obra"]
                   .tolist()
            )

            obras_sel = st.multiselect(
                "Selecione obras para comparar",
                options=obras,
                default=sugestao
            )

            st.markdown("#### Ranking geral (no filtro)")
            topn = st.slider("Top N (ranking)", 5, 50, 15, key="obr_topn")
            by_obra = (
                tmp.groupby("Nome Obra", as_index=False)["Rateio"]
                   .sum()
                   .sort_values("Rateio", ascending=False)
                   .head(topn)
            )
            st.plotly_chart(fig_bar(by_obra, x="Nome Obra", y="Rateio"), use_container_width=True)
            st.dataframe(by_obra, use_container_width=True)

            st.markdown("#### Evolução mensal (obras selecionadas)")
            if not obras_sel:
                st.info("Selecione pelo menos 1 obra.")
            else:
                serie = tmp[tmp["Nome Obra"].isin(obras_sel)].copy()
                obra_month = (
                    serie.groupby(["PERIODO_MES", "Nome Obra"], as_index=False)["Rateio"]
                         .sum()
                         .sort_values("PERIODO_MES")
                )
                st.plotly_chart(fig_line(obra_month, x="PERIODO_MES", y="Rateio", color="Nome Obra"), use_container_width=True)
                st.dataframe(obra_month, use_container_width=True)

# Tabelas (debug)
with st.expander("Ver tabelas (debug)", expanded=False):
    st.subheader("Categorias (filtrado)")
    st.dataframe(df_cat_f, use_container_width=True)

    st.subheader("Rubricas (filtrado)")
    st.dataframe(df_rub_f, use_container_width=True)

    st.subheader("Obras (filtrado e reconciliado)")
    st.dataframe(df_obr_f, use_container_width=True)
