# -*- coding: utf-8 -*-
"""
PRESUPUESTO CABA - 03: arma los datos del mapa de obras (web/obras.js).

QUE ES
------
BA Obras, el observatorio de obras urbanas del Gobierno de la Ciudad: una fila
por obra, con ubicación, etapa, tipo, área responsable, monto del contrato,
fechas, avance y contratista. Es OTRA fuente que el presupuesto ejecutado y no
comparte ningún código con él: no se puede sumar ni cruzar con los programas.

LO QUE HAY QUE SABER
--------------------
- No está al día: la última obra que figura empieza a fines de 2024, y hay
  obras "en obra" con fin previsto en 2023. La etapa es la última cargada.
- El monto es el del CONTRATO, en pesos de la fecha en que empezó la obra. Se
  lleva a pesos del último mes con IPC usando el IPC nacional mensual (INDEC),
  que arranca en diciembre de 2016: las obras anteriores (o sin fecha) quedan
  sólo en pesos corrientes.
- La carga es despareja (la misma etapa escrita de varias formas, comunas como
  "7, 8 y 9", puntos fuera de la Ciudad). Se normaliza acá; la comuna sale de
  las coordenadas, no de la columna.

FUENTES
-------
BA Data, dataset "BA Obras" (observatorio-de-obras-urbanas.csv): se baja solo a
`crudo/ba_obras.csv`. IPC INDEC, serie 148.3_INIVELNAL_DICI_M_26. Contorno de
las comunas: `crudo/comunas.geojson` (lo baja el script 01).
"""
from pathlib import Path
import json
import os
import re
import sys
import urllib.request

import pandas as pd
from shapely.geometry import Point, shape

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = Path(__file__).resolve().parents[1]
DATOS, WEB = BASE / "datos", BASE / "web"
CRUDO = Path(os.environ.get("PRESUPUESTO_CRUDO", BASE / "crudo"))
URL = ("https://cdn.buenosaires.gob.ar/datosabiertos/datasets/secretaria-general-y-relaciones-internacionales/"
       "ba-obras/observatorio-de-obras-urbanas.csv")


def bajar(url, destino):
    print("  bajando", url)
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    destino.write_bytes(urllib.request.urlopen(req, timeout=300).read())


arch = CRUDO / "ba_obras.csv"
if not arch.exists():
    CRUDO.mkdir(parents=True, exist_ok=True)
    bajar(URL, arch)
d = pd.read_csv(arch, sep=None, engine="python", encoding="latin-1", dtype=str)
print("BA Obras:", len(d), "filas")
limpio = lambda s: s.fillna("").str.replace("\xad", "", regex=False).str.replace(r"\s+", " ", regex=True).str.strip()  # noqa: E731
for c in d.columns:
    d[c] = limpio(d[c])

# ---- etapa: cuatro grupos, y la etiqueta original para el detalle ------------
GRUPO = {
    "finalizada": "fin", "en obra": "obra", "en ejecución": "obra", "en curso": "obra",
    "en licitación": "plan", "adjudicada": "plan", "en armado de pliegos": "plan", "en proyecto": "plan",
    "anteproyecto": "plan", "proyecto finalizado": "plan",
    "paralizada": "freno", "rescisión": "freno", "neutralizada": "freno", "desestimada": "freno",
    "finalizada/desestimada": "freno",
}
d["grupo"] = d.etapa.str.lower().map(GRUPO)
assert d.grupo.notna().all(), f"etapas sin grupo: {sorted(d[d.grupo.isna()].etapa.unique())}"
d["etapa"] = d.etapa.str.capitalize()

# ---- tipo ------------------------------------------------------------------
def tipo(t):
    t = t.lower()
    if "hidr" in t or t == "infraestructura":
        return "Hidráulica e infraestructura"
    if t.startswith("vivienda"):
        return "Vivienda"
    if t.startswith("espacio público") or t == "patio de juegos":
        return "Espacio público"
    return {"arquitectura": "Arquitectura", "escuelas": "Escuelas", "salud": "Salud",
            "transporte": "Transporte"}.get(t, "Otras")


d["tipo"] = d.tipo.map(tipo)

# ---- números y fechas ---------------------------------------------------------
num = lambda s: pd.to_numeric(s.str.replace(r"[^\d,.-]", "", regex=True).str.replace(".", "", regex=False)  # noqa: E731
                              .str.replace(",", ".", regex=False), errors="coerce")
d["monto"] = num(d.monto_contrato)
d.loc[d.monto <= 0, "monto"] = None
d["avance"] = num(d.porcentaje_avance.str.replace("%", "", regex=False)).clip(0, 100)
# las coordenadas vienen con coma decimal o con puntos de miles ("-34.578.254"): en
# Buenos Aires la latitud es -34,… y la longitud -58,…, así que alcanza con los dígitos
def coord(s):
    dig = re.sub(r"\D", "", s)
    return -float(dig[:2] + "." + dig[2:]) if s.strip().startswith("-") and len(dig) > 2 else None


for c in ["lat", "lng"]:
    d[c] = pd.to_numeric(d[c].map(coord), errors="coerce")
fecha = lambda s: pd.to_datetime(s, errors="coerce", dayfirst=True)  # noqa: E731
d["inicio"], d["fin"] = fecha(d.fecha_inicio), fecha(d.fecha_fin_inicial)
d.loc[d.inicio.dt.year < 2000, "inicio"] = pd.NaT
d.loc[d.fin.dt.year < 2000, "fin"] = pd.NaT

# ---- comuna: la de las coordenadas; los puntos fuera de la Ciudad no van al mapa
geos = {int(f["properties"]["comuna"]): shape(f["geometry"])
        for f in json.loads((CRUDO / "comunas.geojson").read_text(encoding="utf-8"))["features"]}


def comuna(lat, lng):
    if pd.isna(lat) or pd.isna(lng):
        return 0
    p = Point(lng, lat)
    return next((n for n, g in geos.items() if g.covers(p)), 0)


d["com"] = [comuna(a, b) for a, b in zip(d.lat, d.lng)]
fuera = (d.com == 0) & d.lat.notna()
print(f"  con ubicación en la Ciudad: {(d.com > 0).sum()} · fuera de la Ciudad: {fuera.sum()} · sin coordenadas: {d.lat.isna().sum()}")
d.loc[d.com == 0, ["lat", "lng"]] = None

# ---- pesos de hoy -----------------------------------------------------------
url = ("https://apis.datos.gob.ar/series/api/series/?ids=148.3_INIVELNAL_DICI_M_26"
       "&start_date=2016-12-01&format=csv&limit=1000")
try:
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ipc = pd.read_csv(urllib.request.urlopen(req, timeout=60))
    ipc.to_csv(DATOS / "_ipc_mensual_largo.csv", index=False)
except Exception as e:  # sin red se usa la última copia bajada
    print("  sin red para el IPC, uso la copia:", e)
    ipc = pd.read_csv(DATOS / "_ipc_mensual_largo.csv")
ipc.columns = ["mes", "ipc"]
ipc["mes"] = ipc.mes.str[:7]
ult_mes, ult = ipc.mes.iloc[-1], ipc.ipc.iloc[-1]
factor = (ult / ipc.set_index("mes").ipc).to_dict()
d["factor"] = d.inicio.dt.strftime("%Y-%m").map(factor)
d["monto_real"] = d.monto * d.factor
print(f"  con monto: {d.monto.notna().sum()} · llevado a pesos de {ult_mes}: {d.monto_real.notna().sum()}")

# ---- salida -----------------------------------------------------------------
TIPOS = sorted(d.tipo.unique(), key=lambda t: (t == "Otras", -(d.tipo == t).sum()))
AREAS = sorted(d.area_responsable.replace("", "Sin dato").unique())
d["area_responsable"] = d.area_responsable.replace("", "Sin dato")
url_ok = lambda s: s if re.match(r"^https://[\w.-]+\.gob\.ar/", s) else ""  # noqa: E731
mes = lambda s: s.dt.strftime("%Y-%m").fillna("").tolist()  # noqa: E731
redondo = lambda s, n=0: [None if pd.isna(x) else (round(float(x), n) if n else int(round(x))) for x in s]  # noqa: E731

obras = {
    "pesos_de": ult_mes,
    "tipos": TIPOS, "areas": AREAS,
    "cols": {
        "nombre": d.nombre.tolist(), "entorno": d.entorno.tolist(), "etapa": d.etapa.tolist(), "grupo": d.grupo.tolist(),
        "tipo": [TIPOS.index(t) for t in d.tipo], "area": [AREAS.index(a) for a in d.area_responsable],
        "com": d.com.tolist(), "barrio": d.barrio.tolist(), "dir": d.direccion.tolist(),
        "lat": redondo(d.lat, 5), "lng": redondo(d.lng, 5),
        "monto": redondo(d.monto), "real": redondo(d.monto_real),
        "inicio": mes(d.inicio), "fin": mes(d.fin), "avance": redondo(d.avance),
        "empresa": d.licitacion_oferta_empresa.tolist(), "contratacion": d.contratacion_tipo.tolist(),
        "link": [url_ok(x) for x in d.link_interno], "foto": [url_ok(x) for x in d.imagen_1],
    },
}
(WEB / "obras.js").write_text("window.OBRAS = " + json.dumps(obras, ensure_ascii=False, separators=(",", ":")) + ";\n",
                              encoding="utf-8")
print("->", WEB / "obras.js", f"({(WEB / 'obras.js').stat().st_size / 1e3:.0f} kB)")
print(d.groupby("grupo").size().to_string())
