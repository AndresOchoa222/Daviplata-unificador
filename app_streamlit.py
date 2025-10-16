
import streamlit as st
import pandas as pd
from io import BytesIO
from processor import unify_and_transform, export_excel_bytes

st.set_page_config(page_title="Unificador CSV/XLSX (robusto)", layout="wide")
st.title("Unificador de CSV o Excel • robusto a separadores/encodings • fechas y VLR ABONO")

with st.sidebar:
    st.header("⚙️ Opciones avanzadas")
    sep_choice = st.selectbox("Separador CSV", options=["auto", ";", ",", "\t", "|"], index=0, help="Usa 'auto' para probar ; , tab y |")
    enc_choice = st.selectbox("Codificación CSV", options=["auto", "utf-8-sig", "latin-1", "cp1252"], index=0)
    st.caption("Si sabes el separador/codificación exacta, puedes fijarlos aquí para evitar ambigüedades.")

st.markdown("""
**Flujo:** Sube **1 a 3** archivos `.csv` o `.xlsx`. La app detecta separador/encoding (o usa tus preferencias), limpia encabezados,
convierte **F VALE / F PROCESO / F ABONO** a fecha (YYYYMMDD → si falla, `dayfirst=True`), normaliza **VLR ABONO** a numérico (si existe),
agrega trazabilidad y permite descargar un único Excel con **DD/MM/YYYY**.
""")

uploaded_files = st.file_uploader(
    "Sube de 1 a 3 archivos .csv / .xlsx (mismo formato de columnas)",
    type=["csv", "xlsx"],
    accept_multiple_files=True,
    help="Para XLSX se leen todas las hojas; para CSV se prueba separador/encoding automáticamente o según tus opciones."
)

if uploaded_files:
    if len(uploaded_files) > 3:
        st.warning("Has subido más de 3 archivos. Solo se procesarán los primeros 3.")
        uploaded_files = uploaded_files[:3]

    if st.button("Procesar y Unificar", type="primary"):
        try:
            file_objs = []
            for uf in uploaded_files:
                data = uf.read()
                if not data:
                    st.warning(f"El archivo '{uf.name}' está vacío o no se pudo leer.")
                    continue
                file_objs.append((BytesIO(data), uf.name))

            if not file_objs:
                st.error("No se cargaron archivos válidos.")
            else:
                df = unify_and_transform(file_objs, sep_override=sep_choice, encoding_override=enc_choice)

                # Si solo hay errores, mostrar y abortar exportación
                if "__error__" in df.columns and df.dropna(subset=["__error__"]).shape[0] == len(df):
                    st.error("No se pudieron leer datos de los archivos. Revisa el detalle de errores abajo.")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.success(f"Listo: {len(df):,} filas procesadas (incluye trazabilidad y posibles filas de error).".replace(",", "."))
                    st.subheader("Vista previa")
                    st.dataframe(df.head(100), use_container_width=True)

                    excel_bytes = export_excel_bytes(df, sheet_name="Datos")
                    st.download_button(
                        label="⬇️ Descargar Excel unificado (unificado_fechas.xlsx)",
                        data=excel_bytes,
                        file_name="unificado_fechas.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                    )

                    with st.expander("Ver esquema y tipos de datos (inferidos)"):
                        info = pd.DataFrame({
                            "columna": df.columns,
                            "dtype": [str(dt) for dt in df.dtypes]
                        })
                        st.dataframe(info, use_container_width=True)

                    if "__error__" in df.columns:
                        with st.expander("⚠️ Detalle de errores por archivo/hoja"):
                            st.dataframe(
                                df.loc[df["__error__"].notna(), ["__source_file__", "__sheet__", "__error__"]],
                                use_container_width=True
                            )
        except Exception as e:
            st.error(f"Ocurrió un error durante el procesamiento: {e}")
else:
    st.info("Aún no has subido archivos. Carga entre 1 y 3 .csv/.xlsx para comenzar.")
