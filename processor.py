
import re
from io import BytesIO
from typing import List, Tuple, Optional
import pandas as pd
from pandas import ExcelWriter
import numpy as np
import os

# -----------------------------
# (a) Limpieza de encabezados
# -----------------------------
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

# --------------------------------------
# (b) Parseo de fechas primero YYYYMMDD
# --------------------------------------
def _try_parse_yyyymmdd(series: pd.Series) -> pd.Series:
    # Detecta estrictamente 8 dígitos tipo 20251005
    s = series.astype(str).str.extract(r"(?P<raw>^\s*(\d{8})\s*$)")[0]
    mask = s.notna()
    out = pd.to_datetime(pd.Series(np.where(mask, s, None)), format="%Y%m%d", errors="coerce")
    return out

def parse_dates_with_rule(df: pd.DataFrame, date_cols: List[str]) -> pd.DataFrame:
    # Regla: primero intenta YYYYMMDD; si no, to_datetime dayfirst=True
    for col in date_cols:
        if col in df.columns:
            ymd = _try_parse_yyyymmdd(df[col])
            generic = pd.to_datetime(df[col], dayfirst=True, errors="coerce")
            df[col] = ymd.fillna(generic)
    return df

# ----------------------------------------------
# (c) Normalización numérica para "VLR ABONO"
# ----------------------------------------------
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

# ----------------------------------------------
# (d) Lectura de todas las hojas de 1..3 archivos
#     Ahora soporta CSV además de XLSX
# ----------------------------------------------
def _read_csv_auto(file_like, source_name: str) -> pd.DataFrame:
    # intenta UTF-8 (con BOM) y auto-separador; si falla, prueba latin-1
    for enc in ("utf-8-sig", "latin-1"):
        try:
            df = pd.read_csv(file_like, sep=None, engine="python", dtype=str, encoding=enc)
            return df
        except Exception:
            try:
                file_like.seek(0)
            except Exception:
                pass
            continue
    raise RuntimeError(f"No se pudo leer CSV '{source_name}' con UTF-8 ni latin-1.")

def read_all_sheets(file_like, source_name: str) -> pd.DataFrame:
    ext = os.path.splitext(source_name)[1].lower()
    if ext == ".csv":
        try:
            # Clonar el buffer para múltiples lecturas
            raw = file_like.read()
            bio = BytesIO(raw)
            df = _read_csv_auto(bio, source_name)
            df = clean_headers(df)
            df["__source_file__"] = source_name
            df["__sheet__"] = "csv"
            return df
        except Exception as e:
            return pd.DataFrame({"__source_file__": [source_name],
                                 "__sheet__": ["csv"],
                                 "__error__": [str(e)]})
    else:
        # Excel (xlsx)
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

# -------------------------------------------------
# (e) Unificación, conversión y exportación a Excel
# -------------------------------------------------
TARGET_DATES = ["F VALE", "F PROCESO", "F ABONO"]
VLR_COL = "VLR ABONO"

def _find_actual_col(df: pd.DataFrame, target: str) -> Optional[str]:
    t_norm = re.sub(r"\s+", " ", target.strip()).lower()
    for c in df.columns:
        c_norm = re.sub(r"\s+", " ", c.strip()).lower()
        if c_norm == t_norm:
            return c
    return None

def unify_and_transform(file_objs: List[Tuple[BytesIO, str]]) -> pd.DataFrame:
    all_frames = []
    for fobj, fname in file_objs:
        all_frames.append(read_all_sheets(fobj, fname))
    if not all_frames:
        raise RuntimeError("No se recibieron archivos para procesar.")
    df = pd.concat(all_frames, ignore_index=True)

    # Mapear nombres reales de columnas objetivo
    actual_date_cols = []
    for t in TARGET_DATES:
        found = _find_actual_col(df, t)
        if found:
            actual_date_cols.append(found)

    if actual_date_cols:
        df = parse_dates_with_rule(df, actual_date_cols)

    vlr_actual = _find_actual_col(df, VLR_COL)
    if vlr_actual:
        df[vlr_actual] = normalize_vlr_abono(df[vlr_actual])

    return df

def export_excel_bytes(df: pd.DataFrame, sheet_name: str = "Datos") -> bytes:
    output = BytesIO()
    with ExcelWriter(output, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name=sheet_name)
        wb = writer.book
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
