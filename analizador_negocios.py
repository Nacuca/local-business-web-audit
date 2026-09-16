"""
Analizador de presencia digital de negocios locales
===================================================

Descarga los negocios de un sector y una zona desde OpenStreetMap, comprueba
el estado real de su web y genera un Excel priorizado.

Uso:
    python analizador_negocios.py                        # sector y ciudad por defecto
    python analizador_negocios.py peluquerias            # otro sector
    python analizador_negocios.py peluquerias valencia   # otro sector y otra ciudad
    python analizador_negocios.py --sectores             # ver sectores disponibles
    python analizador_negocios.py --ciudades             # ver ciudades disponibles

Fuente: OpenStreetMap via Overpass API (datos abiertos, licencia ODbL).
"""

import sys
import time
from urllib.parse import quote_plus

import requests
import pandas as pd

# =========================== CONFIGURACION ================================

SECTORES = {
    "dentistas":    [("amenity", "dentist"), ("healthcare", "dentist")],
    "peluquerias":  [("shop", "hairdresser")],
    "talleres":     [("shop", "car_repair")],
    "veterinarios": [("amenity", "veterinary")],
    "gimnasios":    [("leisure", "fitness_centre")],
    "restaurantes": [("amenity", "restaurant")],
    "inmobiliarias":[("office", "estate_agent")],
    "fisios":       [("healthcare", "physiotherapist")],
    "abogados":     [("office", "lawyer")],
    "academias":    [("amenity", "language_school"), ("office", "educational_institution")],
}

SECTOR_POR_DEFECTO = "dentistas"

# Zonas a analizar: (sur, oeste, norte, este).
# Son rectangulos aproximados sobre el centro de cada ciudad, no el termino
# municipal entero. Para añadir una ciudad nueva: openstreetmap.org, pestaña
# "Exportar", y copiar los cuatro valores del recuadro.
CIUDADES = {
    "madrid":     (40.418, -3.720, 40.455, -3.675),
    "barcelona":  (41.372, 2.142, 41.410, 2.198),
    "valencia":   (39.457, -0.393, 39.487, -0.355),
    "sevilla":    (37.372, -6.008, 37.404, -5.975),
    "zaragoza":   (41.640, -0.898, 41.668, -0.865),
    "malaga":     (36.710, -4.438, 36.732, -4.405),
    "bilbao":     (43.252, -2.945, 43.275, -2.912),
    "murcia":     (37.975, -1.145, 37.998, -1.115),
    "alicante":   (38.332, -0.500, 38.356, -0.470),
    "valladolid": (41.640, -4.740, 41.665, -4.708),
    "granada":    (37.165, -3.615, 37.190, -3.585),
}

CIUDAD_POR_DEFECTO = "madrid"
PASO = 0.012        # tamaño del cuadradito en grados (~1,3 km)
PAUSA_OSM = 2.0     # segundos entre peticiones a Overpass (menos da error 429)
PAUSA_WEB = 0.5     # segundos entre visitas a webs

# Cadenas y franquicias: la decision no se toma en el local, no son clientes.
CADENAS = [
    "vitaldent", "dentix", "sanitas", "adeslas", "asisa", "milenium",
    "cleardent", "unidental", "impress", "dkv", "caser", "mapfre", "donte",
    "mcdonald", "burger king", "telepizza", "domino", "starbucks", "rodilla",
    "midas", "norauto", "feuvert", "aurgi", "carglass",
    "basic fit", "mcfit", "anytime fitness", "vivagym", "altafit",
    "tecnocasa", "look and find", "engel", "remax", "century 21",
]

UA_SCRIPT = {"User-Agent": "analizador-negocios-locales/1.0"}
UA_NAVEGADOR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                  "(KHTML, like Gecko) Chrome/122.0 Safari/537.36"
}

SERVIDORES_OSM = [
    "https://overpass-api.de/api/interpreter",
    "https://overpass.private.coffee/api/interpreter",
    "https://overpass.kumi.systems/api/interpreter",
]


# ======================= 1. DESCARGA DESDE OSM ============================

def cuadricula(zona, paso):
    """Parte la zona en cuadraditos pequeños: Overpass rechaza los grandes."""
    sur, oeste, norte, este = zona
    trozos, lat = [], sur
    while lat < norte:
        lon = oeste
        while lon < este:
            trozos.append((lat, lon, min(lat + paso, norte), min(lon + paso, este)))
            lon += paso
        lat += paso
    return trozos


def pedir_trozo(trozo, etiquetas):
    """Descarga un cuadradito. Devuelve (elementos, ok)."""
    s, o, n, e = trozo
    lineas = "\n  ".join(f'node["{k}"="{v}"]({s},{o},{n},{e});' for k, v in etiquetas)
    consulta = f"[out:json][timeout:15];\n(\n  {lineas}\n);\nout tags;"

    for url in SERVIDORES_OSM:
        try:
            r = requests.post(url, data={"data": consulta},
                              headers=UA_SCRIPT, timeout=40)
            if r.status_code == 200:
                return r.json()["elements"], True
        except requests.exceptions.RequestException:
            pass
        time.sleep(1)
    return [], False


def descargar_sector(etiquetas, zona):
    """Recorre la cuadricula. Devuelve (elementos, cuadraditos_fallidos)."""
    trozos = cuadricula(zona, PASO)
    minutos = round(len(trozos) * 3 / 60, 1)      # ~3 s por cuadradito
    print(f"Zona partida en {len(trozos)} cuadraditos (~{minutos} min)\n")

    todos, fallidos = [], 0
    for i, trozo in enumerate(trozos, start=1):
        elementos, ok = pedir_trozo(trozo, etiquetas)
        if not ok:
            fallidos += 1
        marca = " " if ok else "!"
        print(f"[{i:>2}/{len(trozos)}]{marca} {len(elementos):>3} encontrados "
              f"(acumulado: {len(todos) + len(elementos)})")
        todos.extend(elementos)
        time.sleep(PAUSA_OSM)

    return todos, fallidos


def a_tabla(elementos):
    filas = []
    for el in elementos:
        t = el.get("tags", {})
        filas.append({
            "nombre":   t.get("name"),
            "web":      t.get("website") or t.get("contact:website"),
            "telefono": t.get("phone") or t.get("contact:phone"),
            "calle":    t.get("addr:street"),
            "numero":   t.get("addr:housenumber"),
            "osm_id":   el.get("id"),
        })
    return pd.DataFrame(filas)


# ======================= 2. ANALISIS DE LA WEB ============================

def variantes(url):
    """Formas alternativas de escribir la misma direccion."""
    url = str(url).strip()
    if not url.startswith("http"):
        url = "https://" + url
    dominio = url.split("://", 1)[1].split("/", 1)[0]
    opciones = [url]
    opciones.append("https://" + dominio[4:] if dominio.startswith("www.")
                    else "https://www." + dominio)
    opciones.append("http://" + dominio)
    return opciones


def revisar_web(url):
    """Comprueba el estado real de una web probando varias URLs."""
    if not isinstance(url, str) or not url.strip():
        return {"estado": "sin web en OSM (verificar)", "codigo": None,
                "segundos": None, "https": None, "movil": None}

    for intento in variantes(url):
        inicio = time.time()
        try:
            r = requests.get(intento, headers=UA_NAVEGADOR, timeout=12,
                             allow_redirects=True)
        except requests.exceptions.RequestException:
            time.sleep(0.3)
            continue

        if r.status_code < 400:
            html = r.text[:200_000].lower()
            return {
                "estado":   "ok",
                "codigo":   r.status_code,
                "segundos": round(time.time() - inicio, 2),
                "https":    r.url.startswith("https"),
                "movil":    'name="viewport"' in html or "name='viewport'" in html,
            }

    return {"estado": "no responde", "codigo": None, "segundos": None,
            "https": None, "movil": None}


# ======================= 3. PRIORIZACION ==================================

def es_cadena(nombre):
    n = str(nombre).lower()
    return any(marca in n for marca in CADENAS)


def clasificar(fila):
    """Devuelve (accion, argumento). Solo afirma lo que esta comprobado."""
    if fila["cadena"]:
        return "DESCARTAR", "Cadena o franquicia: no deciden en el local."
    if fila["estado"] == "no responde":
        return "1 - web caida", "Su web no carga por ninguna via. Comprobado."
    if fila["estado"].startswith("sin web"):
        return "2 - verificar", "Posible sin web. Comprobar antes de contactar."

    motivos = []
    if fila["movil"] is False:
        motivos.append("no esta adaptada a movil")
    if fila["https"] is False:
        motivos.append("sin HTTPS, el navegador la marca como no segura")
    if fila["segundos"] and fila["segundos"] > 4:
        motivos.append(f"tarda {fila['segundos']}s en cargar")

    if motivos:
        return "3 - web mejorable", "Su web " + ", ".join(motivos) + "."
    return "4 - web correcta", "Su web funciona correctamente."


# ======================= 4. PROGRAMA PRINCIPAL ============================

def main():
    argumentos = sys.argv[1:]

    if "--sectores" in argumentos:
        print("Sectores disponibles:")
        for nombre in SECTORES:
            print("  -", nombre)
        return

    if "--ciudades" in argumentos:
        print("Ciudades disponibles:")
        for nombre in CIUDADES:
            print("  -", nombre)
        print("\nPara añadir otra: openstreetmap.org > Exportar > copiar el recuadro.")
        return

    sector = argumentos[0] if len(argumentos) > 0 else SECTOR_POR_DEFECTO
    ciudad = argumentos[1] if len(argumentos) > 1 else CIUDAD_POR_DEFECTO

    if sector not in SECTORES:
        print(f"Sector '{sector}' no reconocido. Usa --sectores para ver la lista.")
        return
    if ciudad not in CIUDADES:
        print(f"Ciudad '{ciudad}' no reconocida. Usa --ciudades para ver la lista.")
        return

    zona = CIUDADES[ciudad]
    print(f"=== Analizando: {sector} en {ciudad} ===\n")

    elementos, fallidos = descargar_sector(SECTORES[sector], zona)
    if not elementos:
        print("\nNo se ha descargado nada. Reintenta en unos minutos.")
        return

    df = a_tabla(elementos)
    df = df.dropna(subset=["nombre"]).drop_duplicates(subset=["osm_id"])
    df = df.reset_index(drop=True)
    print(f"\n{len(df)} negocios con nombre. Comprobando sus webs...\n")

    resultados = []
    for i, fila in df.iterrows():
        info = revisar_web(fila["web"])
        print(f"[{i+1:>2}/{len(df)}] {str(fila['nombre'])[:34]:<36} {info['estado']}")
        resultados.append(info)
        time.sleep(PAUSA_WEB)

    df = pd.concat([df, pd.DataFrame(resultados)], axis=1)
    df["cadena"] = df["nombre"].apply(es_cadena)
    df[["accion", "argumento"]] = df.apply(clasificar, axis=1, result_type="expand")
    df["comprobar_en"] = df["nombre"].apply(
        lambda n: "https://www.google.com/search?q=" + quote_plus(f'"{n}" {sector} {ciudad}'))
    df = df.sort_values("accion").reset_index(drop=True)

    print("\n--- Reparto ---")
    print(df["accion"].value_counts().sort_index().to_string())

    if fallidos:
        print(f"\nAVISO: {fallidos} de {len(cuadricula(zona, PASO))} cuadraditos "
              f"fallaron. La lista puede estar incompleta.")

    columnas = ["accion", "nombre", "telefono", "calle", "numero", "web",
                "estado", "segundos", "https", "movil", "argumento", "comprobar_en"]
    salida = f"analisis_{sector}_{ciudad}.xlsx"
    df[columnas].to_excel(salida, index=False)
    print(f"\nGuardado en {salida}")


if __name__ == "__main__":
    main()
