
import streamlit as st
import pandas as pd
from io import BytesIO
from processor import unify_and_transform, export_excel_bytes

st.set_page_config(page_title="Unificador XLSX con Fechas", layout="wide")
st.title("Unificador de Excel (1–3 archivos) con normalización de fechas y VLR ABONO")

st.markdown("""
**Objetivo:** Cargar entre 1 y 3 archivos **.xlsx** con el mismo esquema de columnas, leer **todas** las hojas,
limpiar encabezados, convertir las columnas **F VALE**, **F PROCESO** y **F ABONO** a fecha real; y normalizar **VLR ABONO** a numérico (si existe).
Luego unificar todo en un único DataFrame con trazabilidad y permitir la descarga de un Excel consolidado.
\""":)

uploaded_files = st.file_uploader(
    "Sube de 1 a 3 archivos .xlsx (mismo formato de columnas)",
    type=["xlsx"],
    accept_multiple_files=True,
    help="Se leerán todas las hojas de cada archivo y se añadirán columnas de trazabilidad: __source_file__ y __sheet__"
)

if uploaded_files:
    if len(uploaded_files) > 3:
        st.warning("Has subido más de 3 archivos. Solo se procesarán los primeros 3.")
        uploaded_files = uploaded_files[:3]

    if st.button("Procesar y Unificar", type="primary"):
        try:
            # Prepara tuplas (BytesIO, nombre) para el procesador
            file_objs = []
            for uf in uploaded_files:
                # Convertimos a BytesIO para asegurar múltiples lecturas
                data = uf.read()
                file_objs.append((BytesIO(data), uf.name))

            df = unify_and_transform(file_objs)

            st.success(f"Listo: {len(df):,} filas unificadas.".replace(",", "."))
            st.subheader("Vista previa")
            st.dataframe(df.head(100), use_container_width=True)

            # Exportar a Excel con formato de fecha DD/MM/YYYY
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
    st.info("Aún no has subido archivos. Carga entre 1 y 3 .xlsx para comenzar.")
