
import streamlit as st
import pandas as pd
from io import BytesIO
from processor import unify_and_transform, export_excel_bytes

st.set_page_config(page_title="Unificador CSV/XLSX con Fechas", layout="wide")
st.title("Unificador (CSV o Excel) con normalización de fechas y VLR ABONO")

st.markdown("""
**Objetivo:** Cargar entre 1 y 3 archivos **.csv** o **.xlsx** con el mismo esquema de columnas, leer **todas** las hojas (si es Excel) o el CSV completo,
limpiar encabezados, convertir **F VALE**, **F PROCESO** y **F ABONO** a fecha real (primero `YYYYMMDD`, luego genérico con `dayfirst=True`); y normalizar **VLR ABONO** a numérico (si existe).
Unificar todo en un único DataFrame con trazabilidad y permitir la descarga de un Excel consolidado.
""")

uploaded_files = st.file_uploader(
    "Sube de 1 a 3 archivos .csv o .xlsx (mismo formato de columnas)",
    type=["csv", "xlsx"],
    accept_multiple_files=True,
    help="Para XLSX se leerán todas las hojas; para CSV, se detecta automáticamente el separador."
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
                df = unify_and_transform(file_objs)
                st.success(f"Listo: {len(df):,} filas unificadas.".replace(",", "."))
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
        except Exception as e:
            st.error(f"Ocurrió un error durante el procesamiento: {e}")
else:
    st.info("Aún no has subido archivos. Carga entre 1 y 3 .csv/.xlsx para comenzar.")
