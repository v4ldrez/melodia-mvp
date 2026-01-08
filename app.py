import os
import sys
import uuid

import streamlit as st
import pandas as pd
import plotly.express as px

# Garantir path
APP_DIR = os.path.dirname(os.path.abspath(__file__))
if APP_DIR not in sys.path:
    sys.path.insert(0, APP_DIR)

from pipeline import process_uploaded_pdf

st.set_page_config(page_title="Melodia Finance", layout="wide")

st.title("Melodia Finance")
st.write("Faça upload de **um ou mais PDFs do ECAD** para gerar dashboards.")

uploaded_files = st.file_uploader(
    "Upload dos PDFs do ECAD",
    type=["pdf"],
    accept_multiple_files=True
)

if uploaded_files:
    run_id = str(uuid.uuid4())[:8]
    base_run_dir = os.path.join("workspace", run_id)
    os.makedirs(base_run_dir, exist_ok=True)

    base_rubricas_path = os.path.join("bases", "Base_Rubrica_Original.xlsx")

    dfs_cat = []
    dfs_rub = []
    dfs_obr = []

    with st.status("Processando PDFs...", expanded=True) as status:
        for i, uploaded in enumerate(uploaded_files, start=1):
            status.update(label=f"Processando {uploaded.name} ({i}/{len(uploaded_files)})")

            pdf_dir = os.path.join(base_run_dir, uploaded.name.replace(".pdf", ""))
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

    # Concatenar tudo
    df_cat = pd.concat(dfs_cat, ignore_index=True) if dfs_cat else pd.DataFrame()
    df_rub = pd.concat(dfs_rub, ignore_index=True) if dfs_rub else pd.DataFrame()
    df_obr = pd.concat(dfs_obr, ignore_index=True) if dfs_obr else pd.DataFrame()

    # Normalizações
    if "DATA REFERENTE" in df_cat.columns:
        df_cat["DATA REFERENTE"] = pd.to_datetime(df_cat["DATA REFERENTE"], errors="coerce")

    if "DATA REFERENTE" in df_rub.columns:
        df_rub["DATA REFERENTE"] = pd.to_datetime(df_rub["DATA REFERENTE"], errors="coerce")

    if "Data" in df_obr.columns:
        df_obr["Data"] = pd.to_datetime(df_obr["Data"], errors="coerce")

    st.divider()
    st.header("Dashboards")

    # Datas globais
    dates = []
    for df, col in [
        (df_cat, "DATA REFERENTE"),
        (df_rub, "DATA REFERENTE"),
        (df_obr, "Data")
    ]:
        if not df.empty and col in df.columns:
            dates += [df[col].min(), df[col].max()]

    dates = [d for d in dates if pd.notna(d)]

    if dates:
        start, end = st.date_input(
            "Período",
            value=(min(dates).date(), max(dates).date())
        )
        start = pd.to_datetime(start)
        end = pd.to_datetime(end)
    else:
        start = end = None

    def filtro(df, col):
        if start is None or end is None or df.empty or col not in df.columns:
            return df
        return df[(df[col] >= start) & (df[col] <= end)]

    df_cat_f = filtro(df_cat, "DATA REFERENTE")
    df_rub_f = filtro(df_rub, "DATA REFERENTE")
    df_obr_f = filtro(df_obr, "Data")

    # KPIs
    c1, c2, c3 = st.columns(3)

    c1.metric(
        "Total (Categorias)",
        f"R$ {pd.to_numeric(df_cat_f.get('TOTAL GERAL', 0), errors='coerce').sum():,.2f}"
    )
    c2.metric(
        "Total (Rubricas)",
        f"R$ {pd.to_numeric(df_rub_f.get('TOTAL GERAL', 0), errors='coerce').sum():,.2f}"
    )
    c3.metric(
        "Total (Obras)",
        f"R$ {pd.to_numeric(df_obr_f.get('Rateio', 0), errors='coerce').sum():,.2f}"
    )

    # Evolução mensal
    st.subheader("Evolução mensal (Rubricas)")
    if not df_rub_f.empty:
        tmp = df_rub_f.copy()
        tmp["MES"] = tmp["DATA REFERENTE"].dt.to_period("M").astype(str)
        tmp["TOTAL GERAL"] = pd.to_numeric(tmp["TOTAL GERAL"], errors="coerce").fillna(0)

        rub_month = (
            tmp.groupby("MES", as_index=False)["TOTAL GERAL"]
               .sum()
               .sort_values("MES")
        )

        st.plotly_chart(px.bar(rub_month, x="MES", y="TOTAL GERAL"), use_container_width=True)

    # Top obras
    st.subheader("Top 10 Obras")
    if not df_obr_f.empty:
        tmpo = df_obr_f.copy()
        tmpo["Rateio"] = pd.to_numeric(tmpo["Rateio"], errors="coerce").fillna(0)

        top_obras = (
            tmpo.groupby("Nome Obra", as_index=False)["Rateio"]
                .sum()
                .sort_values("Rateio", ascending=False)
                .head(10)
        )

        st.plotly_chart(px.bar(top_obras, x="Nome Obra", y="Rateio"), use_container_width=True)

    # Tabelas
    st.divider()
    st.subheader("Categorias")
    st.dataframe(df_cat_f)

    st.subheader("Rubricas")
    st.dataframe(df_rub_f)

    st.subheader("Obras")
    st.dataframe(df_obr_f)

else:
    st.info("Envie um ou mais PDFs para começar.")
