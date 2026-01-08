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
st.write("Faça upload do seu **PDF do ECAD** para gerar dashboards interativos.")

uploaded = st.file_uploader("Upload do PDF (ECAD)", type=["pdf"])

if uploaded:
    run_id = str(uuid.uuid4())[:8]
    base_dir = os.path.join("workspace", run_id)
    os.makedirs(base_dir, exist_ok=True)

    input_pdf_path = os.path.join(base_dir, uploaded.name)
    with open(input_pdf_path, "wb") as f:
        f.write(uploaded.getbuffer())

    base_rubricas_path = os.path.join("bases", "Base_Rubrica_Original.xlsx")

    with st.status("Processando PDF...", expanded=True) as status:
        try:
            df_cat, df_rub, df_obr = process_uploaded_pdf(
                pdf_path=input_pdf_path,
                base_dir=base_dir,
                base_rubricas_path=base_rubricas_path
            )
            status.update(label="Processamento concluído!", state="complete")
        except Exception as e:
            status.update(label="Erro no processamento", state="error")
            st.exception(e)
            st.stop()

    # Garantir DataFrames
    df_cat = df_cat if isinstance(df_cat, pd.DataFrame) else pd.DataFrame()
    df_rub = df_rub if isinstance(df_rub, pd.DataFrame) else pd.DataFrame()
    df_obr = df_obr if isinstance(df_obr, pd.DataFrame) else pd.DataFrame()

    # Normalizações seguras
    if not df_cat.empty and "DATA REFERENTE" in df_cat.columns:
        df_cat["DATA REFERENTE"] = pd.to_datetime(df_cat["DATA REFERENTE"], errors="coerce")

    if not df_rub.empty and "DATA REFERENTE" in df_rub.columns:
        df_rub["DATA REFERENTE"] = pd.to_datetime(df_rub["DATA REFERENTE"], errors="coerce")

    if not df_obr.empty and "Data" in df_obr.columns:
        df_obr["Data"] = pd.to_datetime(df_obr["Data"], errors="coerce")

    # Range global de datas
    dates = []
    if not df_cat.empty and "DATA REFERENTE" in df_cat.columns:
        dates += [df_cat["DATA REFERENTE"].min(), df_cat["DATA REFERENTE"].max()]
    if not df_rub.empty and "DATA REFERENTE" in df_rub.columns:
        dates += [df_rub["DATA REFERENTE"].min(), df_rub["DATA REFERENTE"].max()]
    if not df_obr.empty and "Data" in df_obr.columns:
        dates += [df_obr["Data"].min(), df_obr["Data"].max()]

    dates = [d for d in dates if pd.notna(d)]

    st.divider()
    st.header("Dashboards")

    if dates:
        min_date = min(dates).date()
        max_date = max(dates).date()
        start, end = st.date_input("Período", value=(min_date, max_date))
        start = pd.to_datetime(start)
        end = pd.to_datetime(end)
    else:
        st.info("Não foi possível detectar datas nos dados. Mostrando tudo sem filtro.")
        start = end = None

    def apply_date_filter(df: pd.DataFrame, col: str) -> pd.DataFrame:
        if start is None or end is None:
            return df
        if df.empty or col not in df.columns:
            return df
        return df[(df[col] >= start) & (df[col] <= end)]

    df_cat_f = apply_date_filter(df_cat, "DATA REFERENTE")
    df_rub_f = apply_date_filter(df_rub, "DATA REFERENTE")
    df_obr_f = apply_date_filter(df_obr, "Data")

    # KPIs
    c1, c2, c3 = st.columns(3)

    if not df_cat_f.empty and "TOTAL GERAL" in df_cat_f.columns:
        c1.metric("Total (Categorias)", f"R$ {pd.to_numeric(df_cat_f['TOTAL GERAL'], errors='coerce').fillna(0).sum():,.2f}")
    else:
        c1.metric("Total (Categorias)", "—")

    if not df_rub_f.empty and "TOTAL GERAL" in df_rub_f.columns:
        c2.metric("Total (Rubricas)", f"R$ {pd.to_numeric(df_rub_f['TOTAL GERAL'], errors='coerce').fillna(0).sum():,.2f}")
    else:
        c2.metric("Total (Rubricas)", "—")

    if not df_obr_f.empty and "Rateio" in df_obr_f.columns:
        c3.metric("Total (Obras)", f"R$ {pd.to_numeric(df_obr_f['Rateio'], errors='coerce').fillna(0).sum():,.2f}")
    else:
        c3.metric("Total (Obras)", "—")

    # -------------------------
    # Evolução mensal (Rubricas) - BLINDADO
    # -------------------------
    st.subheader("Evolução mensal (Rubricas)")

    if df_rub_f is None or df_rub_f.empty:
        st.info("Sem dados de rubricas para plotar.")
    else:
        if "DATA REFERENTE" not in df_rub_f.columns or "TOTAL GERAL" not in df_rub_f.columns:
            st.warning("Rubricas: colunas esperadas não encontradas (DATA REFERENTE / TOTAL GERAL).")
            st.dataframe(df_rub_f.head(30))
        else:
            tmp = df_rub_f.copy()
            tmp["DATA REFERENTE"] = pd.to_datetime(tmp["DATA REFERENTE"], errors="coerce")
            tmp["TOTAL GERAL"] = pd.to_numeric(tmp["TOTAL GERAL"], errors="coerce").fillna(0)
            tmp = tmp.dropna(subset=["DATA REFERENTE"])

            if tmp.empty:
                st.warning("Rubricas: DATA REFERENTE ficou vazia após conversão.")
                st.dataframe(df_rub_f.head(30))
            else:
                rub_month = (
                    tmp.set_index("DATA REFERENTE")
                       .resample("MS")["TOTAL GERAL"]
                       .sum()
                       .reset_index()
                )

                # ordena sem depender do nome
                rub_month = rub_month.sort_values(by=rub_month.columns[0])

                st.plotly_chart(
                    px.line(rub_month, x=rub_month.columns[0], y="TOTAL GERAL"),
                    use_container_width=True
                )

    # -------------------------
    # Top 10 Obras
    # -------------------------
    st.subheader("Top 10 Obras")

    if df_obr_f.empty or "Nome Obra" not in df_obr_f.columns or "Rateio" not in df_obr_f.columns:
        st.info("Sem dados suficientes para Top Obras.")
    else:
        tmpo = df_obr_f.copy()
        tmpo["Rateio"] = pd.to_numeric(tmpo["Rateio"], errors="coerce").fillna(0)

        top_obras = (
            tmpo.groupby("Nome Obra", as_index=False)["Rateio"]
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
    st.subheader("Tabela - Categorias (filtrada)")
    st.dataframe(df_cat_f if not df_cat_f.empty else df_cat)

    st.subheader("Tabela - Rubricas (filtrada)")
    st.dataframe(df_rub_f if not df_rub_f.empty else df_rub)

    st.subheader("Tabela - Obras (filtrada)")
    st.dataframe(df_obr_f if not df_obr_f.empty else df_obr)

else:
    st.info("Envie um PDF para começar.")
