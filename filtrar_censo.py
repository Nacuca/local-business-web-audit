"""
Filtro del censo de locales del Ayuntamiento de Madrid
======================================================

Lee el CSV del censo de locales y saca los negocios de un sector y un distrito,
quedandose solo con los que estan abiertos.

Fuente: datos.madrid.es > "Censo de locales, sus actividades y terrazas".
Se actualiza a diario y es el registro oficial de licencias, asi que contiene
practicamente todos los locales de la ciudad.

Uso:
    python filtrar_censo.py                          # mira el fichero y avisa
    python filtrar_censo.py talleres carabanchel
    python filtrar_censo.py --columnas                # ver como se llaman las columnas
    python filtrar_censo.py --sectores
"""

import sys
import glob
import re

import pandas as pd

# =========================== CONFIGURACION ================================

# Patrones que se buscan dentro de la descripcion de la actividad (epigrafe).
# Son expresiones regulares y se comparan sin distinguir mayusculas ni acentos.
SECTORES = {
    "talleres":     r"reparaci\w*n.*veh\w*culo|taller.*(?:mec\w*nico|autom)|neum\w*tico|chapa y pintura",
    "peluquerias":  r"peluquer\w*a|barber\w*a|est\w*tica capilar",
    "restaurantes": r"restaurante|bar |cafeter\w*a|taberna",
    "clinicas":     r"cl\w*nica|consulta.*m\w*dic|odontol|fisioterap|dentista",
    "gimnasios":    r"gimnasio|deportiv\w*.*instalaci|fitness",
    "inmobiliarias": r"inmobiliari|agencia.*inmueble",
    "academias":    r"academia|ense\w*anza|centro.*formaci\w*n",
    "veterinarios": r"veterinari",
}

# Cuantos candidatos sacar. Para empezar no necesitas mas.
CUANTOS = 20


# ===================== 1. LOCALIZAR Y LEER EL FICHERO ======================

def buscar_csv():
    """Busca el CSV del censo en la carpeta actual."""
    candidatos = glob.glob("*ocales*.csv") + glob.glob("*enso*.csv")
    return candidatos[0] if candidatos else None


def leer(ruta):
    """
    El censo viene separado por ';' y en codificacion latin-1, que es lo
    habitual en los ficheros de la administracion espanola. Probamos varias
    combinaciones por si cambian el formato.
    """
    # IMPORTANTE: utf-8 va primero. latin-1 nunca falla al leer (acepta
    # cualquier byte), asi que si se prueba antes se "traga" un fichero utf-8
    # y lo deja lleno de simbolos raros: Ñ se convierte en Ã, Ó en Ã, etc.
    # Con utf-8 delante, un fichero que de verdad sea latin-1 revienta con
    # UnicodeDecodeError y cae al siguiente intento, que es lo que queremos.
    for sep, cod in [(";", "utf-8"), (";", "utf-8-sig"), (",", "utf-8"),
                     (";", "latin-1"), (";", "cp1252")]:
        try:
            df = pd.read_csv(ruta, sep=sep, encoding=cod, low_memory=False)
            if df.shape[1] > 3:          # si solo sale 1 columna, el separador era otro
                print(f"Leido con separador '{sep}' y codificacion {cod}: "
                      f"{len(df)} filas, {df.shape[1]} columnas\n")
                return df
        except (UnicodeDecodeError, pd.errors.ParserError):
            continue
    raise SystemExit("No he podido leer el CSV. Abrelo y mira como esta separado.")


# ===================== 2. ENCONTRAR LAS COLUMNAS ==========================
# Los nombres de columna del censo han cambiado alguna vez, asi que en lugar
# de escribirlos fijos los buscamos por lo que contienen.

def columna_que_contenga(df, *trozos):
    """Devuelve la primera columna cuyo nombre contenga todos los trozos."""
    for col in df.columns:
        n = col.lower()
        if all(t in n for t in trozos):
            return col
    return None


def sin_acentos(serie):
    """Quita acentos para que 'mecánico' y 'mecanico' se comparen igual."""
    return (serie.astype(str)
                 .str.normalize("NFKD")
                 .str.encode("ascii", "ignore")
                 .str.decode("ascii")
                 .str.lower())


# ============================ 3. PROGRAMA =================================

def main():
    argumentos = [a for a in sys.argv[1:]]

    if "--sectores" in argumentos:
        print("Sectores disponibles:")
        for nombre in SECTORES:
            print("  -", nombre)
        return

    ruta = buscar_csv()
    if not ruta:
        print("No encuentro el CSV del censo en esta carpeta.")
        print("Descargalo de datos.madrid.es (Censo de locales) y dejalo aqui.")
        return
    print(f"Fichero: {ruta}")
    df = leer(ruta)

    if "--columnas" in argumentos:
        for col in df.columns:
            print("  -", col)
        return

    sector = argumentos[0] if len(argumentos) > 0 else "talleres"
    distrito = argumentos[1] if len(argumentos) > 1 else "carabanchel"

    if sector not in SECTORES:
        print(f"Sector '{sector}' no reconocido. Usa --sectores.")
        return

    col_rotulo   = columna_que_contenga(df, "rotulo") or columna_que_contenga(df, "nombre")
    col_distrito = columna_que_contenga(df, "distrito", "desc") or columna_que_contenga(df, "distrito")
    col_epigrafe = columna_que_contenga(df, "epigrafe", "desc") or columna_que_contenga(df, "epigrafe")
    # OJO: el censo trae varias columnas con "situacion" en el nombre, y una de
    # ellas es un id numerico. Hay que pedir expresamente la descriptiva.
    col_situacion = (columna_que_contenga(df, "desc", "situacion")
                     or columna_que_contenga(df, "situacion"))
    # Mismo cuidado que con la situacion: hay una columna de codigo numerico
    # de la via y otra con su nombre. Queremos la descriptiva.
    col_clase    = columna_que_contenga(df, "clase", "vial")
    col_vial     = (columna_que_contenga(df, "desc", "vial")
                    or columna_que_contenga(df, "nombre", "vial"))
    col_numero   = columna_que_contenga(df, "num", "acceso")
    col_barrio   = columna_que_contenga(df, "barrio", "desc")

    faltan = [n for n, c in [("rotulo", col_rotulo), ("distrito", col_distrito),
                             ("epigrafe", col_epigrafe)] if c is None]
    if faltan:
        print("No encuentro estas columnas:", faltan)
        print("Lanza 'python filtrar_censo.py --columnas' y me dices como se llaman.")
        return

    # --- filtrado ---
    m_distrito = sin_acentos(df[col_distrito]).str.contains(distrito, na=False)
    m_sector   = sin_acentos(df[col_epigrafe]).str.contains(SECTORES[sector], na=False, regex=True)
    # En vez de exigir que ponga "abierto", descartamos los que dicen estar
    # cerrados o de baja. Es mas robusto: si manana cambian el texto a "Activo"
    # o "En funcionamiento", el filtro sigue valiendo.
    if col_situacion:
        estados = sin_acentos(df.loc[m_distrito & m_sector, col_situacion])
        print(f"Valores de '{col_situacion}' en este sector y distrito:")
        for valor, n in estados.value_counts().head(8).items():
            print(f"   {n:>5}  {valor}")
        print()
        m_abierto = ~sin_acentos(df[col_situacion]).str.contains(
            r"cerrad|baja|cese|anulad", na=False, regex=True)
    else:
        m_abierto = True

    sel = df[m_distrito & m_sector & m_abierto].copy()
    print(f"En {distrito}: {m_distrito.sum()} locales en total, "
          f"{(m_distrito & m_sector).sum()} del sector '{sector}', "
          f"{len(sel)} de ellos abiertos.\n")

    if sel.empty:
        print("Sin resultados. Prueba otro distrito o revisa el patron del sector.")
        return

    # --- tabla de salida ---
    salida = pd.DataFrame({
        "negocio":  sel[col_rotulo],
        "actividad": sel[col_epigrafe],
    })
    if col_vial is not None:
        direccion = sel[col_vial].astype(str).str.strip()
        if col_clase is not None:                      # CALLE, AVENIDA, PLAZA...
            direccion = sel[col_clase].astype(str).str.strip() + " " + direccion
        if col_numero is not None:
            # El numero llega como decimal (9.0) por culpa de las celdas vacias.
            numero = (pd.to_numeric(sel[col_numero], errors="coerce")
                        .astype("Int64").astype(str).replace("<NA>", ""))
            direccion = direccion + ", " + numero
        salida["direccion"] = direccion.str.replace(r",\s*$", "", regex=True).str.title()
    if col_barrio is not None:
        salida["barrio"] = sel[col_barrio]

    # Locales sin rotulo no sirven: no sabes a quien escribes.
    salida = salida[salida["negocio"].notna() & (salida["negocio"].astype(str).str.strip() != "")]
    salida = salida.drop_duplicates(subset=["negocio"]).head(CUANTOS).reset_index(drop=True)

    # Columnas para rellenar a mano al revisarlos en Google.
    salida["buscar_en_google"] = salida["negocio"].astype(str).str.replace(" ", "+", regex=False)
    salida["buscar_en_google"] = ("https://www.google.com/search?q=" +
                                  salida["buscar_en_google"] + "+" + distrito + "+madrid")
    salida["sigue_abierto"] = ""
    salida["tiene_web"] = ""
    salida["resenas"] = ""
    salida["notas"] = ""

    fichero = f"candidatos_{sector}_{distrito}.xlsx"
    salida.to_excel(fichero, index=False)
    print(salida[["negocio", "direccion"]].to_string() if "direccion" in salida
          else salida[["negocio"]].to_string())
    print(f"\nGuardado en {fichero} — {len(salida)} candidatos para revisar a mano.")


if __name__ == "__main__":
    main()
