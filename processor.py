
import re
from io import BytesIO
from typing import List, Tuple, Optional, Dict
import pandas as pd
from pandas import ExcelWriter
import numpy as np
import os

# ==============================
# (a) Limpieza de encabezados
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

# ======================================
# (b) Parseo de fechas primero YYYYMMDD
# ======================================
def _try_parse_yyyymmdd(series: pd.Series) -> pd.Series:
    s = series.astype(str).str.extract(r"(?P<raw>^\s*(\d{8})\s*$)")[0]
    mask = s.notna()
    out = pd.to_datetime(pd.Series(np.where(mask, s, None)), format="%Y%m%d", errors="coerce")
    return out

def parse_dates_with_rule(df: pd.DataFrame, date_cols: List[str]) -> pd.DataFrame:
    for col in date_cols:
        if col in df.columns:
            ymd = _try_parse_yyyymmdd(df[col])
            generic = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
            df[col] = ymd.fillna(generic)
    return df

# =================================================
# (c) Normalización numérica para "VLR ABONO"
# =================================================
_CURRENCY_SYMS = ["$", "€", "£", "S/", "COP", "USD"]

def _normalize_numeric_str(x: str) -> Optional[str]:
    if pd.isna(x):
        return None
    s = str(x).strip()
    if s == "":
        return None

    # Negativos en paréntesis: (123,45) -> -123,45
    if re.match(r"^\(.*\)$", s):
        s = "-" + s[1:-1].strip()

    # Quitar símbolos de moneda y espacios
    for sym in _CURRENCY_SYMS:
        s = s.replace(sym, "")
    s = s.replace(" ", "")

    # Heurística separadores
    if "." in s and "," in s:
        s = s.replace(".", "")
        s = s.replace(",", ".")
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

# =================================================
# (d) Lector robusto: CSV y Excel
# =================================================
def _read_csv_robust(file_like, source_name: str, sep_override: Optional[str]=None, encoding_override: Optional[str]=None) -> Tuple[pd.DataFrame, Dict[str,str]]:
    """
    Intenta leer un CSV de forma robusta.
    - sep_override: 'auto' | ';' | ',' | '\t' | '|' | None
    - encoding_override: 'auto' | 'utf-8-sig' | 'latin-1' | 'cp1252' | None
    Retorna (df, meta) con meta={'sep':..., 'encoding':...}
    """
    candidates_sep = [';', ',', '\t', '|'] if not sep_override or sep_override=='auto' else [sep_override]
    candidates_enc = ['utf-8-sig', 'latin-1', 'cp1252'] if not encoding_override or encoding_override=='auto' else [encoding_override]

    last_err = None
    for enc in candidates_enc:
        for sep in candidates_sep:
            try:
                file_like.seek(0)
                df = pd.read_csv(
                    file_like,
                    sep=None if sep=='auto' else sep,
                    engine='python',
                    dtype=str,
                    encoding=enc,
                    skip_blank_lines=True
                )
                # Si sep es '	', pandas espera el literal '\t'
                if sep == '\t' and df.shape[1] == 1:
                    file_like.seek(0)
                    df = pd.read_csv(file_like, sep='\t', engine='python', dtype=str, encoding=enc, skip_blank_lines=True)
                # Validación básica: al menos 2 columnas
                if df.shape[1] < 2:
                    raise ValueError(f"Archivo leído con 1 columna usando sep={sep} enc={enc}")
                return clean_headers(df), {'sep': sep, 'encoding': enc}
            except Exception as e:
                last_err = e
                continue
    raise RuntimeError(f"No se pudo leer CSV '{source_name}'. Último error: {last_err}")

def read_all_sheets(file_like, source_name: str, sep_override: Optional[str]=None, encoding_override: Optional[str]=None) -> pd.DataFrame:
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
        # Excel
        try:
            xls = pd.ExcelFile(file_like)
        except Exception as e:
            raise RuntimeError(f"No se pudo abrir '{source_name}': {e}")

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
        if not frames:
            return pd.DataFrame(columns=["__source_file__", "__sheet__"])
        return pd.concat(frames, ignore_index=True)

# =================================================
# (e) Unificación, conversión y exportación a Excel
# =================================================
TARGET_DATES = ["F VALE", "F PROCESO", "F ABONO"]
VLR_COL = "VLR ABONO"

def _find_actual_col(df: pd.DataFrame, target: str) -> Optional[str]:
    t_norm = re.sub(r"\s+", " ", target.strip()).lower()
    for c in df.columns:
        c_norm = re.sub(r"\s+", " ", c.strip()).lower()
        if c_norm == t_norm:
            return c
    return None

def unify_and_transform(file_objs: List[Tuple[BytesIO, str]], sep_override: Optional[str]=None, encoding_override: Optional[str]=None) -> pd.DataFrame:
    all_frames = []
    for fobj, fname in file_objs:
        all_frames.append(read_all_sheets(fobj, fname, sep_override=sep_override, encoding_override=encoding_override))
    # Mantener filas de error para reportar, pero permitir continuar si hay válidas
    valid_frames = [f for f in all_frames if isinstance(f, pd.DataFrame) and not f.empty and "__error__" not in f.columns]
    error_frames = [f for f in all_frames if isinstance(f, pd.DataFrame) and "__error__" in f.columns]

    if not valid_frames and error_frames:
        # Si todo falló, devolver los errores combinados
        return pd.concat(error_frames, ignore_index=True)

    df = pd.concat(valid_frames + error_frames, ignore_index=True)

    # Parseo de fechas
    actual_date_cols = []
    for t in TARGET_DATES:
        found = _find_actual_col(df, t)
        if found:
            actual_date_cols.append(found)
    if actual_date_cols:
        df = parse_dates_with_rule(df, actual_date_cols)

    # VLR ABONO
    vlr_actual = _find_actual_col(df, VLR_COL)
    if vlr_actual:
        df[vlr_actual] = normalize_vlr_abono(df[vlr_actual])

    return df

def export_excel_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> bytes:
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
