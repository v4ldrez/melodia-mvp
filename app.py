import os
import sys
import uuid

import streamlit as st
import pandas as pd
import plotly.express as px

# Garante que a raiz do app está no PYTHONPATH (Streamlit Cloud às vezes precisa)
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

            # pasta isolada por PDF (evita que um PDF contamine o outro)
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

    # Concatenar tudo
    df_cat = pd.concat(dfs_cat, ignore_index=True) if dfs_cat else pd.DataFrame()
    df_rub = pd.concat(dfs_rub, ignore_index=True) if dfs_rub else pd.DataFrame()
    df_obr = pd.concat(dfs_obr, ignore_index=True) if dfs_obr else pd.DataFrame()

    # Normalizações de data
    if "DATA REFERENTE" in df_cat.columns:
        df_cat["DATA REFERENTE"] = pd.to_datetime(df_cat["DATA REFERENTE"], errors="coerce")

    if "DATA REFERENTE" in df_rub.columns:
        df_rub["DATA REFERENTE"] = pd.to_datetime(df_rub["DATA REFERENTE"], errors="coerce")

    if "Data" in df_obr.columns:
        df_obr["Data"] = pd.to_datetime(df_obr["Data"], errors="coerce")

    st.divider()
    st.header("Dashboards")

    # Range global de datas
    dates = []
    for df, col in [(df_cat, "DATA REFERENTE"), (df_rub, "DATA REFERENTE"), (df_obr, "Data")]:
        if not df.empty and col in df.columns:
            dates += [df[col].min(), df[col].max()]
    dates = [d for d in dates if pd.notna(d)]

    if dates:
        start, end = st.date_input("Período", value=(min(dates).date(), max(dates).date()))
        start = pd.to_datetime(start)
        end = pd.to_datetime(end)
    else:
        st.info("Não foi possível detectar datas nos dados. Mostrando tudo sem filtro.")
        start = end = None

    def filtro(df: pd.DataFrame, col: str) -> pd.DataFrame:
        if start is None or end is None or df.empty or col not in df.columns:
            return df
        return df[(df[col] >= start) & (df[col] <= end)]

    df_cat_f = filtro(df_cat, "DATA REFERENTE")
    df_rub_f = filtro(df_rub, "DATA REFERENTE")
    df_obr_f = filtro(df_obr, "Data")

    # -------------------------
    # Totais base
    # -------------------------
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

    # -------------------------
    # Reconciliação: Obras bate com Rubricas
    # -------------------------
    if total_rub > 0 and total_obr > 0:
        fator = total_rub / total_obr
        # só aplica se diferença > 1%
        if abs(1 - fator) > 0.01:
            df_obr_f["Rateio"] = df_obr_f["Rateio"] * fator
            total_obr = df_obr_f["Rateio"].sum()
            st.caption(f"⚙️ Obras normalizado para bater com Rubricas (fator: {fator:.4f}).")

    # KPIs
    c1, c2, c3 = st.columns(3)
    c1.metric("Total (Categorias)", f"R$ {total_cat:,.2f}" if total_cat else "—")
    c2.metric("Total (Rubricas)",   f"R$ {total_rub:,.2f}" if total_rub else "—")
    c3.metric("Total (Obras)",      f"R$ {total_obr:,.2f}" if total_obr else "—")

    # -------------------------
    # Evolução mensal (Rubricas) - eixo limpo
    # -------------------------
    st.subheader("Evolução mensal (Rubricas)")

    if df_rub_f.empty or "DATA REFERENTE" not in df_rub_f.columns or "TOTAL GERAL" not in df_rub_f.columns:
        st.info("Sem dados suficientes para evolução mensal.")
    else:
        tmp = df_rub_f.copy()
        tmp["DATA REFERENTE"] = pd.to_datetime(tmp["DATA REFERENTE"], errors="coerce")
        tmp["TOTAL GERAL"] = pd.to_numeric(tmp["TOTAL GERAL"], errors="coerce").fillna(0)
        tmp = tmp.dropna(subset=["DATA REFERENTE"])

        if tmp.empty:
            st.info("Sem datas válidas para evolução mensal.")
        else:
            tmp["MES"] = tmp["DATA REFERENTE"].dt.to_period("M").astype(str)
            rub_month = (
                tmp.groupby("MES", as_index=False)["TOTAL GERAL"]
                   .sum()
                   .sort_values("MES")
            )
            # barra é melhor com poucos meses (e sem bug de horas)
            st.plotly_chart(px.bar(rub_month, x="MES", y="TOTAL GERAL"), use_container_width=True)

    # -------------------------
    # Top 10 Obras (já reconciliado se necessário)
    # -------------------------
    st.subheader("Top 10 Obras")

    if df_obr_f.empty or "Nome Obra" not in df_obr_f.columns or "Rateio" not in df_obr_f.columns:
        st.info("Sem dados suficientes para Top Obras.")
    else:
        top_obras = (
            df_obr_f.groupby("Nome Obra", as_index=False)["Rateio"]
                   .sum()
                   .sort_values("Rateio", ascending=False)
                   .head(10)
        )
        st.plotly_chart(px.bar(top_obras, x="Nome Obra", y="Rateio"), use_container_width=True)

    # -------------------------
    # Distribuição por Rubrica Modelo
    # -------------------------
    st.subheader("Distribuição por Rubrica Modelo")

    if df_rub_f.empty or "Rubrica_Modelo" not in df_rub_f.columns or "TOTAL GERAL" not in df_rub_f.columns:
        st.info("Sem dados suficientes para Rubrica Modelo.")
    else:
        tmprm = df_rub_f.copy()
        tmprm["TOTAL GERAL"] = pd.to_numeric(tmprm["TOTAL GERAL"], errors="coerce").fillna(0)
        tmprm["Rubrica_Modelo"] = tmprm["Rubrica_Modelo"].fillna("Sem mapeamento")

        rub_model = (
            tmprm.groupby("Rubrica_Modelo", as_index=False)["TOTAL GERAL"]
                 .sum()
                 .sort_values("TOTAL GERAL", ascending=False)
        )
        st.plotly_chart(px.bar(rub_model, x="Rubrica_Modelo", y="TOTAL GERAL"), use_container_width=True)

    # -------------------------
    # Tabelas
    # -------------------------
    st.divider()
    st.subheader("Categorias (filtrado)")
    st.dataframe(df_cat_f)

    st.subheader("Rubricas (filtrado)")
    st.dataframe(df_rub_f)

    st.subheader("Obras (filtrado e reconciliado)")
    st.dataframe(df_obr_f)

else:
    st.info("Envie um ou mais PDFs para começar.")
