# Analizador de negocios locales

Herramienta en Python que analiza la presencia digital de los negocios de un
sector y una ciudad: los localiza en OpenStreetMap, comprueba el estado real de
su página web y devuelve un Excel priorizado.

```
python analizador_negocios.py dentistas madrid
```

---

## El problema

Un negocio local sin presencia digital decente pierde clientes sin enterarse: no
aparece cuando alguien lo busca, o su web está caída y nadie se lo ha dicho.

Según el INE, solo el **37% de las microempresas españolas** tiene página web,
frente al 84,5% de las empresas de diez o más empleados. El problema es real y
está concentrado justo en los negocios más pequeños.

Esta herramienta lo mide: dado un sector y una ciudad, dice qué negocios hay y
en qué estado está la web de cada uno.

---

## Qué hace

1. **Descarga** los negocios del sector en la zona indicada desde OpenStreetMap,
   troceando la consulta en una cuadrícula para no exceder los límites de la API.
2. **Limpia** los resultados: extrae los campos útiles, descarta registros sin
   nombre y elimina duplicados por identificador.
3. **Comprueba** cada web probando varias formas de la dirección, y mide si
   responde, si va por HTTPS, si está preparada para móvil y cuánto tarda.
4. **Clasifica** cada negocio en una acción comercial, descartando cadenas y
   franquicias.
5. **Exporta** a Excel, ordenado por prioridad, avisando si la descarga quedó
   incompleta.

---

## Instalación

Requiere Python 3.9 o superior.

```bash
git clone https://github.com/<tu-usuario>/analizador-negocios.git
cd analizador-negocios
pip install -r requirements.txt
```

---

## Uso

```bash
# Sector y ciudad por defecto (dentistas en Madrid)
python analizador_negocios.py

# Otro sector
python analizador_negocios.py peluquerias

# Otro sector y otra ciudad
python analizador_negocios.py talleres valencia

# Ver las opciones disponibles
python analizador_negocios.py --sectores
python analizador_negocios.py --ciudades
```

**Sectores incluidos:** dentistas, peluquerías, talleres, veterinarios,
gimnasios, restaurantes, inmobiliarias, fisios, abogados y academias.

**Ciudades incluidas:** Madrid, Barcelona, Valencia, Sevilla, Zaragoza, Málaga,
Bilbao, Murcia, Alicante, Valladolid y Granada.

Añadir un sector nuevo es una entrada en el diccionario `SECTORES` con su
etiqueta de OpenStreetMap. Para una ciudad nueva, basta con copiar las cuatro
coordenadas del recuadro desde la pestaña *Exportar* de openstreetmap.org.

---

## Resultado

Genera `analisis_<sector>_<ciudad>.xlsx` con una fila por negocio:

| accion | nombre | telefono | estado | argumento |
|---|---|---|---|---|
| 1 - web caida | Clínica Ejemplo | +34 91 ... | no responde | Su web no carga por ninguna vía. Comprobado. |
| 2 - verificar | Dental Ejemplo | +34 91 ... | sin web en OSM (verificar) | Posible sin web. Comprobar antes de contactar. |
| 3 - web mejorable | Centro Ejemplo | +34 91 ... | ok | Su web no está adaptada a móvil, tarda 6.2s en cargar. |
| 4 - web correcta | Ejemplo Dental | +34 91 ... | ok | Su web funciona correctamente. |
| DESCARTAR | Cadena Ejemplo | +34 91 ... | ok | Cadena o franquicia: no deciden en el local. |

Incluye además columnas de diagnóstico (código HTTP, tiempo de carga, HTTPS,
adaptación a móvil) y un enlace de búsqueda para verificar cada caso dudoso.

### Ejecución real: dentistas en el centro de Madrid

| Resultado | Negocios |
|---|---|
| Analizados | 71 |
| Web caída | 9 |
| Sin web registrada (a verificar) | 29 |
| Web mejorable | 2 |
| Web correcta | 19 |
| Cadenas descartadas | 12 |

---

## Cómo funciona por dentro

Las decisiones de diseño que hacen que funcione en condiciones reales:

**Consultas troceadas.** Overpass es un servicio gratuito que descarta las
consultas costosas con un error 504. En vez de pedir toda la zona de golpe, se
parte en rectángulos de kilómetro y pico y se pide uno a uno.

**Varios servidores con reintentos.** Se prueban tres instancias de Overpass en
orden. Se descartó una cuarta al comprobar que solo servía datos de Suiza:
respondía correctamente y devolvía cero resultados.

**Errores de red controlados.** Un timeout es una excepción, no un código de
estado. Capturarlo es lo que permite que un servidor caído no interrumpa la
ejecución entera.

**Dos identidades.** Ante la API pública el script se identifica como lo que es;
ante las webs comerciales se presenta como un navegador, porque muchas rechazan
peticiones automáticas.

**Deduplicación por identificador.** Los cuadrados de la cuadrícula comparten
bordes, así que un negocio en el límite aparece dos veces. Se elimina por
`osm_id` y no por nombre, porque dos negocios distintos pueden llamarse igual.

**Columnas honestas.** La ausencia de web en OpenStreetMap no demuestra que el
negocio no tenga web, así que la columna se llama `sin web en OSM (verificar)` y
no `sin web`. El programa cuenta además cuántos cuadrados fallaron y lo avisa,
para que nunca se confunda una lista incompleta con una lista completa.

---

## Limitaciones conocidas

- **Cobertura parcial.** OpenStreetMap lo mantienen voluntarios: faltan negocios
  y algunos registros están desactualizados. Sirve para encontrar candidatos, no
  como censo.
- **"Sin web" no está verificado.** Solo significa que OpenStreetMap no tiene la
  web registrada. Requiere comprobación manual, para lo que se incluye la columna
  con el enlace de búsqueda.
- **"Web caída" tiene un matiz.** Significa que el script no accede por tres vías
  distintas. Algunos sitios bloquean peticiones automáticas y funcionan bien en un
  navegador, así que conviene abrirlos antes de afirmarlo.
- **El filtro de cadenas es una lista fija.** Reconoce las marcas incluidas; una
  franquicia pequeña no la detecta.
- **Depende de un servicio gratuito.** Si Overpass está saturado, la ejecución
  puede quedar incompleta. El programa avisa cuando ocurre.

---

## Fuente de datos

Datos de [OpenStreetMap](https://www.openstreetmap.org), obtenidos mediante la
[API de Overpass](https://wiki.openstreetmap.org/wiki/Overpass_API). Disponibles
bajo licencia [ODbL](https://opendatacommons.org/licenses/odbl/), que permite su
uso citando la fuente.

No se emplea scraping: toda la información se obtiene a través de APIs públicas
destinadas a ese fin.
