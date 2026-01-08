import streamlit as st
import pandas as pd
import plotly.express as px

st.set_page_config(page_title="Melodia Finance (MVP)", layout="wide")

st.title("Melodia Finance (MVP)")
st.write("Faça upload do seu arquivo ECAD e veja um dashboard básico.")

uploaded = st.file_uploader("Envie seu arquivo (CSV ou Excel)", type=["csv", "xlsx"])

if uploaded:
    if uploaded.name.endswith(".csv"):
        df = pd.read_csv(uploaded)
    else:
        df = pd.read_excel(uploaded)

    st.success(f"Arquivo carregado: {uploaded.name}")
    st.subheader("Prévia dos dados")
    st.dataframe(df.head(20))

    st.subheader("Gráfico simples (exemplo)")
    cols = df.columns.tolist()

    date_col = st.selectbox("Escolha a coluna de data/mês", cols)
    value_col = st.selectbox("Escolha a coluna de valor", cols)

    try:
        df[date_col] = pd.to_datetime(df[date_col])
        grouped = df.groupby(date_col, as_index=False)[value_col].sum()
        fig = px.line(grouped, x=date_col, y=value_col)
        st.plotly_chart(fig, use_container_width=True)
    except Exception:
        st.warning("Não consegui gerar o gráfico automaticamente. Tente escolher outras colunas.")
