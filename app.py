import os
import uuid
import streamlit as st
import pandas as pd
import plotly.express as px

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

    # Se vier vazio, avisa
    if df_cat is None or df_cat.empty:
        st.warning("Categorias: não foi possível gerar dados.")
    if df_rub is None or df_rub.empty:
        st.warning("Rubricas: não foi possível gerar dados.")
    if df_obr is None or df_obr.empty:
        st.warning("Obras: não foi possível gerar dados.")

    st.divider()
    st.header("Dashboards")

    # ---- Normalizações de datas
    if "DATA REFERENTE" in df_cat.columns and not df_cat.empty:
        df_cat["DATA REFERENTE"] = pd.to_datetime(df_cat["DATA REFERENTE"], errors="coerce")
    if "DATA REFERENTE" in df_rub.columns and not df_rub.empty:
        df_rub["DATA REFERENTE"] = pd.to_datetime(df_rub["DATA REFERENTE"], errors="coerce")
    if "Data" in df_obr.columns and not df_obr.empty:
        df_obr["Data"] = pd.to_datetime(df_obr["Data"], errors="coerce")

    # ---- Define range global de datas (se houver)
    dates = []
    if not df_cat.empty and "DATA REFERENTE" in df_cat.columns:
        dates += [df_cat["DATA REFERENTE"].min(), df_cat["DATA REFERENTE"].max()]
    if not df_rub.empty and "DATA REFERENTE" in df_rub.columns:
        dates += [df_rub["DATA REFERENTE"].min(), df_rub["DATA REFERENTE"].max()]
    if not df_obr.empty and "Data" in df_obr.columns:
        dates += [df_obr["Data"].min(), df_obr["Data"].max()]

    dates = [d for d in dates if pd.notna(d)]
    if dates:
        min_date = min(dates).date()
        max_date = max(dates).date()
        start, end = st.date_input("Período", value=(min_date, max_date))
        start = pd.to_datetime(start)
        end = pd.to_datetime(end)
    else:
        start = end = None

    def apply_date_filter(df, col):
        if start is None or end is None or df.empty or col not in df.columns:
            return df
        return df[(df[col] >= start) & (df[col] <= end)]

    df_cat_f = apply_date_filter(df_cat, "DATA REFERENTE")
    df_rub_f = apply_date_filter(df_rub, "DATA REFERENTE")
    df_obr_f = apply_date_filter(df_obr, "Data")

    # ---- KPIs
    c1, c2, c3 = st.columns(3)
    if not df_cat_f.empty and "TOTAL GERAL" in df_cat_f.columns:
        c1.metric("Total (Categorias)", f"R$ {df_cat_f['TOTAL GERAL'].sum():,.2f}")
    else:
        c1.metric("Total (Categorias)", "—")

    if not df_rub_f.empty and "TOTAL GERAL" in df_rub_f.columns:
        c2.metric("Total (Rubricas)", f"R$ {df_rub_f['TOTAL GERAL'].sum():,.2f}")
    else:
        c2.metric("Total (Rubricas)", "—")

    if not df_obr_f.empty and "Rateio" in df_obr_f.columns:
        c3.metric("Total (Obras)", f"R$ {df_obr_f['Rateio'].sum():,.2f}")
    else:
        c3.metric("Total (Obras)", "—")

    st.subheader("Evolução mensal (Rubricas)")
    if not df_rub_f.empty and {"DATA REFERENTE", "TOTAL GERAL"}.issubset(df_rub_f.columns):
        rub_month = df_rub_f.groupby(pd.Grouper(key="DATA REFERENTE", freq="MS"), as_index=False)["TOTAL GERAL"].sum()
        st.plotly_chart(px.line(rub_month, x="DATA REFERENTE", y="TOTAL GERAL"), use_container_width=True)
    else:
        st.info("Sem dados suficientes para evolução de rubricas.")

    st.subheader("Top 10 Obras")
    if not df_obr_f.empty and {"Nome Obra", "Rateio"}.issubset(df_obr_f.columns):
        top_obras = (
            df_obr_f.groupby("Nome Obra", as_index=False)["Rateio"]
            .sum()
            .sort_values("Rateio", ascending=False)
            .head(10)
        )
        st.plotly_chart(px.bar(top_obras, x="Nome Obra", y="Rateio"), use_container_width=True)
    else:
        st.info("Sem dados suficientes para Top Obras.")

    st.subheader("Distribuição por Rubrica Modelo")
    if not df_rub_f.empty and {"Rubrica_Modelo", "TOTAL GERAL"}.issubset(df_rub_f.columns):
        rub_model = (
            df_rub_f.groupby("Rubrica_Modelo", as_index=False)["TOTAL GERAL"]
            .sum()
            .sort_values("TOTAL GERAL", ascending=False)
        )
        st.plotly_chart(px.bar(rub_model, x="Rubrica_Modelo", y="TOTAL GERAL"), use_container_width=True)
    else:
        st.info("Sem dados suficientes para Rubrica Modelo.")

    st.divider()
    st.subheader("Tabela - Categorias (filtrada)")
    st.dataframe(df_cat_f)

    st.subheader("Tabela - Rubricas (filtrada)")
    st.dataframe(df_rub_f)

    st.subheader("Tabela - Obras (filtrada)")
    st.dataframe(df_obr_f)
