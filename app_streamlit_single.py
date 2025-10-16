
import streamlit as st
import pandas as pd
from io import BytesIO
import re
import numpy as np

# ==============================
# Procesador embebido (single-file)
# ==============================

def clean_headers(df: pd.DataFrame) -> pd.DataFrame:
    def _clean(col: str) -> str:
        if col is None:
            return ""
        c = str(col)
        c = c.replace("\n", " ").replace("\r", " ").replace("\t", " ")
        c = c.replace('"', "").replace("'", "")
        c = re.sub(r"\s+", " ", c).strip()
        return c
    new_cols = []
    seen = {}
    for c in df.columns:
        base = _clean(c)
        if base in seen:
            seen[base] += 1
            base = f"{base}__{seen[base]}"
        else:
            seen[base] = 0
        new_cols.append(base)
    df = df.rename(columns={old: new for old, new in zip(df.columns, new_cols)})
    return df

def _try_parse_yyyymmdd(series: pd.Series) -> pd.Series:
    # Versión segura para pandas>=2.2: retorna Serie directamente
    s = series.astype(str).str.extract(r"^\s*(\d{8})\s*$", expand=False)
    mask = s.notna()
    out = pd.to_datetime(pd.Series(np.where(mask, s, None)), format="%Y%m%d", errors="coerce")
    return out

def parse_dates_with_rule(df: pd.DataFrame, date_cols):
    for col in date_cols:
        if col in df.columns:
            ymd = _try_parse_yyyymmdd(df[col])
            generic = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
            df[col] = ymd.fillna(generic)
    return df

_CURRENCY_SYMS = ["$", "€", "£", "S/", "COP", "USD"]

def _normalize_numeric_str(x: str):
    if pd.isna(x):
        return None
    s = str(x).strip()
    if s == "":
        return None
    # Negativos en paréntesis
    if re.match(r"^\(.*\)$", s):
        s = "-" + s[1:-1].strip()
    # Quitar símbolos de moneda y espacios
    for sym in _CURRENCY_SYMS:
        s = s.replace(sym, "")
    s = s.replace(" ", "")
    # Heurística separadores
    if "." in s and "," in s:
        s = s.replace(".", "").replace(",", ".")
    elif "," in s and "." not in s:
        parts = s.split(",")
        if len(parts) == 2 and 1 <= len(parts[1]) <= 2:
            s = s.replace(",", ".")
        else:
            s = s.replace(",", "")
    s = re.sub(r"[^0-9\.-]", "", s)
    if s in ("", "-", ".", "-."):
        return None
    return s

def normalize_vlr_abono(series: pd.Series) -> pd.Series:
    cleaned = series.map(_normalize_numeric_str)
    return pd.to_numeric(cleaned, errors="coerce")

def _read_csv_robust(file_like, source_name: str, sep_override=None, encoding_override=None):
    cand_sep = [';', ',', '\t', '|'] if not sep_override or sep_override=='auto' else [sep_override]
    cand_enc = ['utf-8-sig', 'latin-1', 'cp1252'] if not encoding_override or encoding_override=='auto' else [encoding_override]

    last_err = None
    for enc in cand_enc:
        for sep in cand_sep:
            try:
                file_like.seek(0)
                df = pd.read_csv(
                    file_like,
                    sep=sep,
                    engine='python',
                    dtype=str,
                    encoding=enc,
                    skip_blank_lines=True,
                    on_bad_lines='skip'   # ignora filas malformadas
                )
                # Si 1 sola columna, separador incorrecto
                if df.shape[1] == 1:
                    raise ValueError(f"CSV leído con 1 columna usando sep={repr(sep)} enc={enc}")
                # Si headers parecen inválidos, promover primera fila a encabezado
                if all([(c is None) or bool(re.fullmatch(r'Unnamed:.*|\d+', str(c))) for c in df.columns]):
                    tmp = df.iloc[0].fillna("").astype(str).tolist()
                    df = df.iloc[1:].copy()
                    df.columns = [re.sub(r"\s+", " ", str(x)).strip().strip('"').strip("'") for x in tmp]
                df = clean_headers(df)
                return df, {'sep': sep, 'encoding': enc}
            except Exception as e:
                last_err = e
                continue
    raise RuntimeError(f"No se pudo leer CSV '{source_name}'. Último error: {last_err}")

def read_all_sheets(file_like, source_name: str, sep_override=None, encoding_override=None) -> pd.DataFrame:
    import os
    ext = os.path.splitext(source_name)[1].lower()
    if ext == ".csv":
        try:
            raw = file_like.read()
            bio = BytesIO(raw)
            df, meta = _read_csv_robust(bio, source_name, sep_override, encoding_override)
            df["__source_file__"] = source_name
            df["__sheet__"] = f"csv({meta['sep']},{meta['encoding']})"
            return df
        except Exception as e:
            return pd.DataFrame({"__source_file__": [source_name],
                                 "__sheet__": ["csv"],
                                 "__error__": [str(e)]})
    else:
        try:
            xls = pd.ExcelFile(file_like)
        except Exception as e:
            return pd.DataFrame({"__source_file__": [source_name],
                                 "__sheet__": ["workbook"],
                                 "__error__": [f"No se pudo abrir: {e}"]})
        frames = []
        for sheet in xls.sheet_names:
            try:
                df = xls.parse(sheet_name=sheet, dtype=str)
                df = clean_headers(df)
                df["__source_file__"] = source_name
                df["__sheet__"] = sheet
                frames.append(df)
            except Exception as e:
                frames.append(pd.DataFrame({"__source_file__": [source_name],
                                            "__sheet__": [sheet],
                                            "__error__": [str(e)]}))
        return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame()

def unify_and_transform(file_objs, sep_override=None, encoding_override=None) -> pd.DataFrame:
    TARGET_DATES = ["F VALE", "F PROCESO", "F ABONO"]
    VLR_COL = "VLR ABONO"

    frames = []
    for fobj, fname in file_objs:
        frames.append(read_all_sheets(fobj, fname, sep_override, encoding_override))

    valid = [f for f in frames if isinstance(f, pd.DataFrame) and not f.empty and "__error__" not in f.columns]
    errs = [f for f in frames if isinstance(f, pd.DataFrame) and "__error__" in f.columns]

    if not valid and errs:
        return pd.concat(errs, ignore_index=True)

    df = pd.concat(valid + errs, ignore_index=True)

    # Fechas
    actual_date_cols = []
    for t in TARGET_DATES:
        for c in df.columns:
            if re.sub(r"\s+"," ",c.strip()).lower() == re.sub(r"\s+"," ",t.strip()).lower():
                actual_date_cols.append(c)
                break
    if actual_date_cols:
        df = parse_dates_with_rule(df, actual_date_cols)

    # VLR ABONO
    vlr_col = next((c for c in df.columns if re.sub(r"\s+"," ",c.strip()).lower()=="vlr abono"), None)
    if vlr_col:
        df[vlr_col] = normalize_vlr_abono(df[vlr_col])

    return df

def export_excel_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> bytes:
    from pandas import ExcelWriter
    output = BytesIO()
    with ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        ws = writer.sheets[sheet_name]
        col_idx = {col: idx+1 for idx, col in enumerate(df.columns)}
        for col in df.columns:
            if pd.api.types.is_datetime64_any_dtype(df[col]):
                idx = col_idx[col]
                for r in range(2, len(df) + 2):
                    cell = ws.cell(row=r, column=idx)
                    if str(cell.value).strip() not in ("", "NaT", "None"):
                        cell.number_format = "DD/MM/YYYY"
    output.seek(0)
    return output.getvalue()

# ==============================
# UI Streamlit (single-file)
# ==============================

st.set_page_config(page_title="Unificador CSV/XLSX (single-file) • robusto", layout="wide")
st.title("Unificador Archivos Daviplata Deposit")

with st.sidebar:
    st.header("⚙️ Opciones CSV")
    sep_choice = st.selectbox("Separador", ["auto", ";", ",", "\t", "|"], index=0)
    enc_choice = st.selectbox("Codificación", ["auto", "utf-8-sig", "latin-1", "cp1252"], index=0)
    st.caption("Deja 'auto' si no estás seguro.")

st.markdown("Sube **1 a 3** archivos `.csv` o `.xlsx` y descarga un Excel consolidado.")

uploaded_files = st.file_uploader(
    "Cargar archivo(s)",
    type=["csv","xlsx"],
    accept_multiple_files=True
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

                if "__error__" in df.columns and df.dropna(subset=["__error__"]).shape[0] == len(df):
                    st.error("No se pudieron leer datos de los archivos. Revisa el detalle debajo.")
                    st.dataframe(df, use_container_width=True)
                else:
                    st.success(f"Procesadas {len(df):,} filas.".replace(",", "."))
                    st.subheader("Vista previa")
                    st.dataframe(df.head(100), use_container_width=True)

                    excel_bytes = export_excel_bytes(df, sheet_name="Datos")
                    st.download_button(
                        "⬇️ Descargar Excel unificado (unificado_fechas.xlsx)",
                        data=excel_bytes,
                        file_name="unificado_fechas.xlsx",
                        mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
                    )

                    if "__error__" in df.columns:
                        with st.expander("⚠️ Detalle de errores"):
                            st.dataframe(df.loc[df["__error__"].notna(), ["__source_file__","__sheet__","__error__"]])

        except Exception as e:
            import traceback
            st.error(f"Error al procesar: {repr(e)}")
            with st.expander("Ver detalle técnico"):
                st.code(traceback.format_exc())
else:
    st.info("Aún no has subido archivos.")
