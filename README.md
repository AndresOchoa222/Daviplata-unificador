
# Unificador XLSX con normalización de fechas y VLR ABONO

Esta app **Streamlit** permite cargar entre 1 y 3 archivos **.xlsx** con el mismo formato de columnas,
leer **todas** sus hojas, limpiar encabezados, convertir **F VALE / F PROCESO / F ABONO** a fechas reales (regla
de parseo *primero YYYYMMDD; luego genérico con `dayfirst=True`*), normalizar **VLR ABONO** a numérico (si existe),
y descargar un único Excel consolidado con trazabilidad de archivo y hoja.

## Requisitos
- Python 3.9+
- `streamlit`, `pandas`, `openpyxl`

Puedes instalar dependencias con:
```bash
pip install streamlit pandas openpyxl
```

## Ejecutar
En la carpeta del proyecto, corre:
```bash
streamlit run app_streamlit.py
```

## Uso
1. Sube **1 a 3** archivos `.xlsx` (se leerán **todas** las hojas).
2. Pulsa **"Procesar y Unificar"**.
3. Revisa la **vista previa** y descarga el archivo **`unificado_fechas.xlsx`** (hoja `Datos`).
   - Las columnas de fecha (si existen) se exportan con formato **DD/MM/YYYY**.
   - Si existe **VLR ABONO**, se convierte a numérico (tolera símbolos de moneda, separadores, paréntesis negativos).
   - Se incluyen columnas de trazabilidad: `__source_file__`, `__sheet__`.

## Notas técnicas
- Encabezados se limpian: se remueven comillas/saltos de línea, se colapsan espacios.
- Fechas: primero se intenta `%Y%m%d` (ej. `20251005`), luego `pd.to_datetime(..., dayfirst=True)`.
- La app tolera que **algún archivo no tenga VLR ABONO** sin fallar.
- Cualquier hoja que falle al leer se registra con una fila de error y se continúa con el resto.
