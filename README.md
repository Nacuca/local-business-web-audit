# Local Business Digital Presence Audit

Python tooling that finds local businesses in Spanish cities and measures the real
state of their online presence — whether they have a website, whether it actually
loads, and whether it works on a phone.

Built to answer a commercial question with data instead of guesswork: *which
businesses in this district are losing customers because nobody can find them
online?*

```bash
python filtrar_censo.py talleres carabanchel     # 369 car repair shops, from the city registry
python analizador_negocios.py dentistas madrid   # 71 dental clinics, websites checked
python buscar_en_censo.py "carlos daban" 24      # what is registered at this address?
```

---

## The problem

A small business with a broken or missing website loses customers without ever
finding out. Nobody tells the owner that their domain expired, or that their
Google listing points at a dead link.

The tooling measures this at district scale: given a sector and an area, it
returns every business, the state of its website, and a priority ranking.

---

## What it does

Three tools that share a pipeline: **find businesses → check their web presence →
rank them → export a reviewable spreadsheet.**

| Tool | Source | Purpose |
|---|---|---|
| `analizador_negocios.py` | OpenStreetMap (Overpass API) | Finds businesses by sector and city, probes each website, classifies the result |
| `filtrar_censo.py` | Madrid City Council open data | Filters the official premises registry by sector, district and trading status |
| `buscar_en_censo.py` | Madrid City Council open data | Looks up the registered name of whatever operates at a given address |

Output is always an Excel file with one row per business, ranked by commercial
priority, with blank columns for the manual verification step.

---

## Case study: picking the right data source

The interesting engineering decision in this project was not the code — it was
discovering that the original data source was unusable for the target sector, and
measuring it rather than assuming it.

The first version relied entirely on OpenStreetMap. For hairdressers in central
Madrid it returned **213 businesses**. For dental clinics, **71**. For car repair
shops in Carabanchel, a working-class district full of them, it returned **2** —
and a different 2 on each run.

Two separate causes, found by investigating rather than retrying:

**1. The query only asked for nodes.** A small shop inside a building is mapped in
OpenStreetMap as a point (`node`). A workshop occupying a whole industrial unit is
usually drawn as a polygon (`way`). Querying `node[...]` made the script blind to
every business large enough to have its own footprint — which is most car repair
shops. Fixed by querying `nwr[...]` (nodes, ways and relations) with `out center`,
so polygons arrive with a representative coordinate and the rest of the pipeline
does not need to know the difference.

**2. Coverage was genuinely absent.** Even after the fix, the count stayed in the
low single digits. OpenStreetMap is volunteer-maintained, and volunteer mapping
concentrates in city centres and on consumer-facing shopfronts.

The conclusion was to change the source, not the sector. Madrid City Council
publishes a daily-updated **registry of every licensed commercial premises in the
city** — 225,667 rows, with trade name, address, district, economic activity and
trading status. For the same query it returns **369 car repair shops in
Carabanchel** instead of 2.

| Sector / area | OpenStreetMap | City registry |
|---|---|---|
| Car repair, Carabanchel | 2 | 369 |

The lesson generalises: before optimising a pipeline, verify that the source
actually contains the population you are looking for.

---

## Data quality traps

Real administrative data breaks in specific, repeatable ways. Three that cost real
time on this project, and how they are handled now:

**Encoding detection order matters.** The registry file is UTF-8. The loader
originally tried `latin-1` first — and `latin-1` never fails, because it accepts any
byte sequence. It silently swallowed a UTF-8 file and produced mojibake throughout
(`OPAÑEL` → `OPAÃEL`). Strict encodings are now tried first, so a genuinely
`latin-1` file raises `UnicodeDecodeError` and falls through to the permissive one.
Rule of thumb: when detecting encodings, try the strict ones first and leave the
forgiving ones as a last resort.

**Fuzzy column matching needs to be specific.** The registry has 47 columns, several
sharing a keyword: `id_situacion_local` (a numeric code) and `desc_situacion_local`
(the text). Matching the first column containing `situacion` picked the numeric one,
and searching it for the word "open" matched nothing — silently filtering out every
result. Column lookup now requires the descriptive variant explicitly. The same bug
appeared again with street names (`id_vial_acceso` vs `desc_vial_acceso`), producing
addresses like `768000.0, 9.0`.

**Filter by exclusion, not enumeration.** The trading-status filter originally
required the value to contain "open". It now excludes values containing closed,
deregistered or cancelled. If the council relabels the field tomorrow, the exclusion
filter keeps working; the enumeration filter would have silently returned zero rows
again.

---

## Verifying a "dead website" claim

The most commercially useful output — *this business's website is down* — is also
the easiest to get wrong, so it is cross-checked against independent evidence.

An HTTP request failing is weak evidence: the site may block automated requests,
or the network path may be filtered. **DNS resolution is much stronger.** If the
domain does not resolve at all, the domain has expired or lost its DNS, and no
browser anywhere will reach it.

Applied to the nine dental clinics flagged as down, 7 of 9 domains failed to
resolve — confirmed dead. The other two resolved, and were correctly identified as
false positives.

Two further checks turned out to be essential before acting on any result:

- **Is the business still trading?** A dead domain often means a dead business.
  One clinic flagged as a prime candidate was marked permanently closed.
- **Has it simply moved?** Another had let its old domain lapse and rebuilt on a
  new one. The registry data said "no website"; reality said "new website".

`buscar_en_censo.py` exists because of a third case: a business trading under one
name on its sign, another on its Google listing, and a third on its licence. The
registry resolves which legal entity operates at an address.

---

## Output

`analisis_<sector>_<city>.xlsx`, one row per business:

| accion | nombre | telefono | estado | argumento |
|---|---|---|---|---|
| 1 - web caida | Example Clinic | +34 91 ... | no responde | Site does not load by any route. Verified. |
| 2 - verificar | Example Dental | +34 91 ... | sin web en OSM | Possibly no website. Verify before contacting. |
| 3 - web mejorable | Example Centre | +34 91 ... | ok | Not mobile-ready, 6.2s load time. |
| 4 - web correcta | Example Ltd | +34 91 ... | ok | Site works correctly. |
| DESCARTAR | Example Chain | +34 91 ... | ok | Chain or franchise: decisions are not made locally. |

Plus diagnostic columns (HTTP status, load time, HTTPS, mobile viewport) and a
prepared search link for every case needing manual confirmation.

**Real run — dental clinics, central Madrid:** 71 analysed, 9 with dead websites,
29 with no registered website, 2 improvable, 19 working, 12 chains discarded.

---

## Design decisions

**Tiled queries.** Overpass rejects expensive queries with a 504. The area is split
into ~1.3 km tiles and requested one at a time.

**Multiple servers with retries.** Three Overpass instances are tried in order. A
fourth was dropped after testing showed it served only Swiss data — responding
correctly, returning zero results.

**Network errors are exceptions, not status codes.** Catching timeouts is what
stops one unreachable server from ending the whole run.

**Two identities.** The script identifies itself honestly to the public API, and
presents a browser user agent to commercial websites, many of which reject
automated requests outright.

**Deduplication by type and id.** Grid tiles share edges, so businesses on a
boundary appear twice. OpenStreetMap numbers nodes and ways independently, so
node 123 and way 123 are different businesses — deduplication uses both fields.

**Honest column names.** The absence of a website in OpenStreetMap does not prove
the business has none, so the column is called `sin web en OSM (verificar)`, not
`sin web`. Failed tiles are counted and reported, so an incomplete list is never
mistaken for a complete one.

---

## Known limitations

- **OpenStreetMap coverage is partial** and skews towards city centres and
  consumer-facing shops. Useful for finding candidates, not as a census. The
  municipal registry is the better source where it exists.
- **The registry covers Madrid only.** Other Spanish cities publish comparable
  datasets in incompatible formats.
- **The registry has no website or phone field.** Contact details still require a
  separate lookup.
- **Registry data lags reality.** Licence transfers and closures take time to
  appear, so a premises may trade under a different name than the one registered.
- **"Website down" needs confirmation.** The DNS check makes it reliable for
  expired domains; sites that merely block automated requests need a browser.
- **Chain filtering is a fixed list.** Known brands are detected; a small local
  franchise is not.

---

## Installation

Python 3.9+.

```bash
git clone https://github.com/Nacuca/<repo>.git
cd <repo>
pip install -r requirements.txt
```

For the registry tools, download the **Actividades** CSV from the Madrid open data
portal and place it in the project folder.

---

## Data sources

- [OpenStreetMap](https://www.openstreetmap.org) via the
  [Overpass API](https://wiki.openstreetmap.org/wiki/Overpass_API), under
  [ODbL](https://opendatacommons.org/licenses/odbl/).
- [Censo de locales y actividades](https://datos.madrid.es/dataset/200085-0-censo-locales),
  Madrid City Council open data portal, updated daily.

No scraping is used. All data comes from public APIs and open data downloads
intended for that purpose.
