import os
import sys
import uuid

import streamlit as st
import pandas as pd
import plotly.express as px

# Garantir que a raiz do app está no PYTHONPATH (Streamlit Cloud às vezes precisa)
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

            # Pasta isolada por PDF (evita mistura)
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

    # Normalizar datas
    if "DATA REFERENTE" in df_cat.columns:
        df_cat["DATA REFERENTE"] = pd.to_datetime(df_cat["DATA REFERENTE"], errors="coerce")
    if "DATA REFERENTE" in df_rub.columns:
        df_rub["DATA REFERENTE"] = pd.to_datetime(df_rub["DATA REFERENTE"], errors="coerce")
    if "Data" in df_obr.columns:
        df_obr["Data"] = pd.to_datetime(df_obr["Data"], errors="coerce")

    st.divider()
    st.header("Dashboards")

    # Range global para filtro
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

    # Totais
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

    # Reconciliação: Obras bate com Rubricas (MVP)
    if total_rub > 0 and total_obr > 0:
        fator = total_rub / total_obr
        if abs(1 - fator) > 0.01:
            df_obr_f["Rateio"] = df_obr_f["Rateio"] * fator
            total_obr = df_obr_f["Rateio"].sum()
            st.caption(f"⚙️ Obras normalizado para bater com Rubricas (fator: {fator:.4f}).")

    # KPIs
    c1, c2, c3 = st.columns(3)
    c1.metric("Total (Categorias)", f"R$ {total_cat:,.2f}" if total_cat else "—")
    c2.metric("Total (Rubricas)",   f"R$ {total_rub:,.2f}" if total_rub else "—")
    c3.metric("Total (Obras)",      f"R$ {total_obr:,.2f}" if total_obr else "—")

    # Evolução mensal (Rubricas)
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
            st.plotly_chart(px.bar(rub_month, x="MES", y="TOTAL GERAL"), use_container_width=True)

    # =========================================================
    # ABAS DETALHADAS
    # =========================================================
    st.divider()
    st.header("Análises detalhadas")
    tab1, tab2, tab3 = st.tabs(["Rubricas", "Categorias", "Obras"])

    # -------------------------
    # TAB 1 — RUBRICAS
    # -------------------------
    with tab1:
        st.subheader("Rubricas — Ranking e drilldown")

        if df_rub_f.empty:
            st.info("Sem dados de rubricas.")
        else:
            tmp = df_rub_f.copy()
            tmp["TOTAL GERAL"] = pd.to_numeric(tmp.get("TOTAL GERAL", 0), errors="coerce").fillna(0)

            if "DATA REFERENTE" in tmp.columns:
                tmp["DATA REFERENTE"] = pd.to_datetime(tmp["DATA REFERENTE"], errors="coerce")
                tmp["MES"] = tmp["DATA REFERENTE"].dt.to_period("M").astype(str)

            tmp["Rubrica_Modelo"] = tmp.get("Rubrica_Modelo", pd.Series(["Sem mapeamento"] * len(tmp))).fillna("Sem mapeamento")
            tmp["RUBRICA"] = tmp.get("RUBRICA", pd.Series(["(Sem nome)"] * len(tmp))).fillna("(Sem nome)")

            colA, colB, colC = st.columns([1.2, 1.2, 1])
            with colA:
                modelos = ["(Todos)"] + sorted(tmp["Rubrica_Modelo"].unique().tolist())
                sel_modelo = st.selectbox("Filtrar por Rubrica Modelo", modelos, key="rub_sel_modelo")
            with colB:
                topn = st.slider("Top N", 5, 50, 15, key="rub_topn")
            with colC:
                mostrar_percent = st.checkbox("Mostrar %", value=True, key="rub_percent")

            tmp_f = tmp if sel_modelo == "(Todos)" else tmp[tmp["Rubrica_Modelo"] == sel_modelo]

            st.markdown("### Ranking por Rubrica Modelo")
            by_modelo = (
                tmp_f.groupby("Rubrica_Modelo", as_index=False)["TOTAL GERAL"]
                     .sum()
                     .sort_values("TOTAL GERAL", ascending=False)
            )
            if mostrar_percent and total_rub > 0:
                by_modelo["%"] = (by_modelo["TOTAL GERAL"] / total_rub) * 100

            st.plotly_chart(px.bar(by_modelo.head(topn), x="Rubrica_Modelo", y="TOTAL GERAL"), use_container_width=True)
            st.dataframe(by_modelo.head(topn), use_container_width=True)

            st.markdown("### Drilldown: Rubricas dentro do Modelo")
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
            st.plotly_chart(px.bar(by_rubrica, x="RUBRICA", y="TOTAL GERAL"), use_container_width=True)
            st.dataframe(by_rubrica, use_container_width=True)

            if "MES" in tmp_f.columns and tmp_f["MES"].nunique() >= 2:
                st.markdown("### Evolução mensal por Rubrica Modelo")
                evol = (
                    tmp_f.groupby(["MES", "Rubrica_Modelo"], as_index=False)["TOTAL GERAL"]
                         .sum()
                         .sort_values("MES")
                )
                st.plotly_chart(px.line(evol, x="MES", y="TOTAL GERAL", color="Rubrica_Modelo"), use_container_width=True)
            else:
                st.caption("Evolução mensal por modelo aparece quando houver 2+ meses.")

    # -------------------------
    # TAB 2 — CATEGORIAS
    # -------------------------
    with tab2:
        st.subheader("Categorias — Distribuição e evolução")

        if df_cat_f.empty:
            st.info("Sem dados de categorias.")
        else:
            tmp = df_cat_f.copy()
            tmp["TOTAL GERAL"] = pd.to_numeric(tmp.get("TOTAL GERAL", 0), errors="coerce").fillna(0)
            tmp["CATEGORIA"] = tmp.get("CATEGORIA", pd.Series(["(Sem nome)"] * len(tmp))).fillna("(Sem nome)")

            if "DATA REFERENTE" in tmp.columns:
                tmp["DATA REFERENTE"] = pd.to_datetime(tmp["DATA REFERENTE"], errors="coerce")
                tmp["MES"] = tmp["DATA REFERENTE"].dt.to_period("M").astype(str)

            colA, colB = st.columns([1, 1])
            with colA:
                topn = st.slider("Top N categorias", 5, 30, 10, key="cat_topn")
            with colB:
                modo = st.radio("Visual", ["Barras", "Pizza (share)"], horizontal=True, key="cat_mode")

            by_cat = (
                tmp.groupby("CATEGORIA", as_index=False)["TOTAL GERAL"]
                   .sum()
                   .sort_values("TOTAL GERAL", ascending=False)
            )

            if modo == "Barras":
                st.plotly_chart(px.bar(by_cat.head(topn), x="CATEGORIA", y="TOTAL GERAL"), use_container_width=True)
            else:
                pie = by_cat.head(min(topn, 12)).copy()
                st.plotly_chart(px.pie(pie, names="CATEGORIA", values="TOTAL GERAL"), use_container_width=True)

            st.dataframe(by_cat.head(topn), use_container_width=True)

            if "MES" in tmp.columns and tmp["MES"].nunique() >= 2:
                st.markdown("### Evolução mensal por categoria")
                evol = (
                    tmp.groupby(["MES", "CATEGORIA"], as_index=False)["TOTAL GERAL"]
                       .sum()
                       .sort_values("MES")
                )
                st.plotly_chart(px.line(evol, x="MES", y="TOTAL GERAL", color="CATEGORIA"), use_container_width=True)
            else:
                st.caption("Evolução mensal por categoria aparece quando houver 2+ meses.")

    # -------------------------
    # TAB 3 — OBRAS
    # -------------------------
    with tab3:
        st.subheader("Obras — Ranking e evolução mês a mês por obra")

        if df_obr_f.empty or "Nome Obra" not in df_obr_f.columns or "Rateio" not in df_obr_f.columns:
            st.info("Sem dados suficientes de obras.")
        else:
            tmp = df_obr_f.copy()
            tmp["Rateio"] = pd.to_numeric(tmp["Rateio"], errors="coerce").fillna(0.0)
            tmp["Nome Obra"] = tmp["Nome Obra"].fillna("(Sem nome)")

            # Eixo mensal (precisa de Data)
            if "Data" in tmp.columns:
                tmp["Data"] = pd.to_datetime(tmp["Data"], errors="coerce")
                tmp = tmp.dropna(subset=["Data"])
                tmp["MES"] = tmp["Data"].dt.to_period("M").astype(str)
            else:
                tmp["MES"] = "(Sem mês)"

            colA, colB = st.columns([1.2, 1])
            with colA:
                # filtro por obra
                obras = sorted(tmp["Nome Obra"].unique().tolist())
                obra_sel = st.selectbox("Selecione uma obra", obras, key="obra_sel")
            with colB:
                topn = st.slider("Top N (ranking)", 5, 50, 15, key="obr_topn")

            # 1) Ranking geral de obras
            st.markdown("### Ranking geral de obras")
            by_obra = (
                tmp.groupby("Nome Obra", as_index=False)["Rateio"]
                   .sum()
                   .sort_values("Rateio", ascending=False)
                   .head(topn)
            )
            st.plotly_chart(px.bar(by_obra, x="Nome Obra", y="Rateio"), use_container_width=True)
            st.dataframe(by_obra, use_container_width=True)

            # 2) Evolução mensal da obra selecionada
            st.markdown("### Evolução mensal da obra selecionada")
            serie = tmp[tmp["Nome Obra"] == obra_sel].copy()

            if serie.empty:
                st.info("Sem dados para essa obra no período filtrado.")
            else:
                obra_month = (
                    serie.groupby("MES", as_index=False)["Rateio"]
                         .sum()
                         .sort_values("MES")
                )

                st.plotly_chart(
                    px.line(obra_month, x="MES", y="Rateio", markers=True),
                    use_container_width=True
                )
                st.dataframe(obra_month, use_container_width=True)

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
