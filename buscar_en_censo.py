"""
Buscador de locales por direccion en el censo del Ayuntamiento
==============================================================

Dada una calle (y opcionalmente un numero), lista todos los locales dados de
alta en esa direccion, con su rotulo, su actividad y si estan abiertos.

Sirve para dos cosas:
  - Averiguar el nombre real de un negocio cuya ficha de Google esta rellenada
    con palabras clave en vez de con su rotulo.
  - Ver que mas hay en el mismo portal (naves con varios talleres, etc).

Uso:
    python buscar_en_censo.py "carlos daban"
    python buscar_en_censo.py "carlos daban" 24
"""

import sys
import glob

import pandas as pd


def buscar_csv():
    candidatos = glob.glob("*ocales*.csv") + glob.glob("*enso*.csv")
    return candidatos[0] if candidatos else None


def leer(ruta):
    # utf-8 primero: latin-1 nunca falla y se traga un utf-8 dejandolo con
    # simbolos raros, asi que va de ultimo recurso.
    for sep, cod in [(";", "utf-8"), (";", "utf-8-sig"), (",", "utf-8"),
                     (";", "latin-1"), (";", "cp1252")]:
        try:
            df = pd.read_csv(ruta, sep=sep, encoding=cod, low_memory=False)
            if df.shape[1] > 3:
                return df
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise SystemExit("No he podido leer el CSV.")


def columna(df, *trozos):
    for col in df.columns:
        n = col.lower()
        if all(t in n for t in trozos):
            return col
    return None


def sin_acentos(serie):
    return (serie.astype(str)
                 .str.normalize("NFKD")
                 .str.encode("ascii", "ignore")
                 .str.decode("ascii")
                 .str.lower())


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        return

    calle = sys.argv[1]
    numero = sys.argv[2] if len(sys.argv) > 2 else None

    ruta = buscar_csv()
    if not ruta:
        print("No encuentro el CSV del censo en esta carpeta.")
        return

    print(f"Leyendo {ruta} (tarda un minuto)...")
    df = leer(ruta)

    col_rotulo    = columna(df, "rotulo") or columna(df, "nombre")
    col_vial      = columna(df, "desc", "vial") or columna(df, "nombre", "vial")
    col_clase     = columna(df, "clase", "vial")
    col_numero    = columna(df, "num", "acceso")
    col_epigrafe  = columna(df, "epigrafe", "desc") or columna(df, "epigrafe")
    col_situacion = columna(df, "desc", "situacion")
    col_distrito  = columna(df, "distrito", "desc")

    if col_vial is None:
        print("No encuentro la columna de la calle.")
        return

    sel = df[sin_acentos(df[col_vial]).str.contains(
        sin_acentos(pd.Series([calle]))[0], na=False, regex=False)]

    if numero is not None and col_numero is not None:
        n = pd.to_numeric(sel[col_numero], errors="coerce")
        sel = sel[n == float(numero)]

    if sel.empty:
        print(f"Sin resultados para '{calle}'"
              + (f" numero {numero}" if numero else "")
              + ". Prueba solo con la calle, o con menos palabras.")
        return

    salida = pd.DataFrame({"rotulo": sel[col_rotulo]})
    if col_numero is not None:
        salida["num"] = pd.to_numeric(sel[col_numero], errors="coerce").map(
            lambda v: "" if pd.isna(v) else str(int(v)))
    for nombre, col in [("actividad", col_epigrafe),
                        ("situacion", col_situacion),
                        ("distrito", col_distrito)]:
        if col is not None:
            salida[nombre] = sel[col]

    pd.set_option("display.width", 220)
    pd.set_option("display.max_colwidth", 55)
    print(f"\n{len(salida)} locales encontrados:\n")
    print(salida.to_string(index=False))


if __name__ == "__main__":
    main()
