
# Unificador CSV/XLSX → Exporta a XLSX (hoja "Datos" con DD/MM/YYYY)

## Qué hace
- Acepta **1 a 3** archivos **CSV o XLSX** con el mismo formato de columnas.
- Si es **XLSX**, lee **todas las hojas**; si es **CSV**, autodetecta separador (coma, punto y coma, tab) y codificación (UTF‑8/LATIN‑1).
- Limpia encabezados; convierte **F VALE / F PROCESO / F ABONO** a fecha (primero `YYYYMMDD`; si no, `dayfirst=True`); normaliza **VLR ABONO** a numérico (si existe).
- Une todo y agrega `__source_file__` y `__sheet__`.
- Exporta **un solo** `unificado_fechas.xlsx` (hoja `Datos`) con fechas en **DD/MM/YYYY**.

## Cómo correr localmente
```bash
pip install streamlit pandas openpyxl
streamlit run app_streamlit.py
```

## Despliegue web
Usa Streamlit Cloud / Hugging Face Spaces / Render. Repositorio mínimo:
```
/
├─ app_streamlit.py
├─ processor.py
└─ requirements.txt
```

## Notas
- Si algún archivo **no tiene `VLR ABONO`**, el proceso continúa.
- Para CSV, se intenta `utf-8-sig` y luego `latin-1`. Para separador, `sep=None` (auto).
- Columnas buscadas de fecha: `F VALE`, `F PROCESO`, `F ABONO` (insensible a espacios/uppercase).
