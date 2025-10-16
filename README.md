# 📊 Unificador CSV/XLSX

## 🧰 Qué hace
- Permite subir **1 a 3 archivos** `.csv` o `.xlsx` con el mismo formato.  
- Si es `.xlsx`, lee **todas las hojas**.  
- Si es `.csv`, detecta automáticamente **separador** (`;`, `,`, `\t`) y **codificación** (`utf-8`, `latin-1`).  
- Limpia los encabezados.  
- Convierte las columnas **F VALE**, **F PROCESO** y **F ABONO** a formato de fecha.  
- Convierte **VLR ABONO** a número (si existe).  
- Une todos los datos en un solo archivo e incluye columnas con el nombre del archivo y hoja de origen.  
- Exporta un único archivo **`unificado_fechas.xlsx`** con fechas en formato **DD/MM/YYYY**.

## ▶️ Cómo ejecutar localmente
```bash
pip install -r requirements.txt
streamlit run app_streamlit_single.py
```

## 🌐 Cómo desplegar la app
Puedes publicarla fácilmente en **Streamlit Cloud**, **Hugging Face Spaces** o **Render**.  
Tu repositorio debe tener al menos estos archivos:

```
/
├─ app_streamlit_single.py
├─ requirements.txt
├─ runtime.txt
└─ .streamlit/config.toml
```

## ℹ️ Notas importantes
- Si un archivo no tiene **VLR ABONO**, el proceso no se detiene.  
- Para CSV se intentan varias codificaciones y separadores automáticamente.  
- Las columnas de fecha deben llamarse: `F VALE`, `F PROCESO`, `F ABONO`.
