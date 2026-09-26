# -*- coding: utf-8 -*-
"""
PRESUPUESTO CABA - 01: arma el modelo de datos del monitor, 2022-2026.

QUE ARMA
--------
Un modelo estrella que leen las dos salidas del proyecto (la web y Power BI):

  datos/hechos.csv          una fila por año x jurisdicción x unidad ejecutora x
                            programa x finalidad-función x inciso-principal x
                            fuente x comuna, con sancionado, vigente y devengado
                            NOMINALES
  datos/dim_*.csv           las descripciones de cada código
  datos/ipc.csv             el factor que lleva cada año a pesos de hoy
  web/datos.json            los agregados que dibuja la página

LOS PESOS
---------
Entre 2022 y 2026 los precios se multiplicaron por más de diez: comparar pesos
corrientes entre años no dice nada. Cada monto se lleva a pesos del último mes
con IPC publicado usando el PROMEDIO ANUAL del IPC nacional (INDEC), porque el
crédito y el gasto se reparten a lo largo del año. Para 2026 el promedio es el
de los meses publicados. Es una aproximación: el gasto no se reparte parejo
mes a mes (aguinaldos, obras que se certifican a fin de año).

LA TRAMPA DEL CLASIFICADOR GEOGRAFICO
-------------------------------------
`geo` marca dónde está la UNIDAD QUE EJECUTA, no dónde cae el gasto: la sede de
gobierno está en Parque Patricios y la comuna 4 se lleva un tercio del total.
Se publica igual porque la fuente lo trae, pero la web lo avisa y no lo muestra
como "plata por barrio".

2026 ES PARCIAL
---------------
El último archivo es el SEGUNDO trimestre: el vigente es el de junio y el
devengado es el acumulado a junio. La ejecución de 2026 no se compara con la de
un año cerrado.

FUENTES
-------
BA Data, presupuesto ejecutado: el cierre del cuarto trimestre de cada año y el
segundo trimestre de 2026. Se bajan solos a `crudo/` (unos 140 MB, fuera de git)
la primera vez; otra carpeta con los mismos archivos se indica con la variable
PRESUPUESTO_CRUDO (sirven también comprimidos en .gz). IPC INDEC, serie
148.3_INIVELNAL_DICI_M_26 de la API de series de tiempo. Población por comuna:
Censo 2022, en `datos/poblacion_comuna_2022.csv`.
"""
from pathlib import Path
import json
import os
import sys
import urllib.request

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
BASE = Path(__file__).resolve().parents[1]
DATOS, WEB = BASE / "datos", BASE / "web"
DATOS.mkdir(exist_ok=True)
WEB.mkdir(exist_ok=True)

CRUDO = Path(os.environ.get("PRESUPUESTO_CRUDO", BASE / "crudo"))
ARCH = {2022: "ejecutado_2022", 2023: "ejecutado_2023", 2024: "ejecutado_2024",
        2025: "ejecutado_2025", 2026: "ejecutado_2026_trim2"}
CDN = "https://cdn.buenosaires.gob.ar/datosabiertos/datasets/ministerio-de-economia-y-finanzas/"
URL = {a: CDN + f"presupuesto-ejecutado/presupuesto-ejecutado-{a}-4.csv" for a in range(2022, 2026)}
URL[2026] = CDN + "presupuesto-ejecutado-2026/presupuesto-ejecutado-2026-2.csv"
CORTE = {a: "anual" for a in ARCH} | {2026: "a junio"}

# los encabezados cambian de año (minúsculas, "Desc_" adelante o "_desc" atrás,
# "Vigente_Trim4_CONT"), pero el ORDEN de las 44 columnas es siempre el mismo
COLS = ["car", "car_desc", "jur", "jur_desc", "sjur", "sjur_desc", "ent", "ent_desc", "og", "og_desc",
        "ue", "ue_desc", "prog", "prog_desc", "sprog", "sprog_desc", "proy", "proy_desc", "act", "act_desc",
        "obra", "obra_desc", "fin", "fin_desc", "fun", "fun_desc", "inc", "inc_desc", "ppal", "ppal_desc",
        "par", "par_desc", "spar", "spar_desc", "eco", "eco_desc", "fte", "fte_desc", "geo", "geo_desc",
        "sancionado", "vigente", "definitivo", "devengado"]
MONTOS = ["sancionado", "vigente", "devengado"]
CLAVE = ["car", "jur", "ue", "prog", "fin", "fun", "inc", "ppal", "fte", "geo"]
num = lambda s: pd.to_numeric(s.str.replace(".", "", regex=False).str.replace(",", ".", regex=False),  # noqa: E731
                              errors="coerce").fillna(0)


# 2022 tiene las mismas 44 columnas pero otro contenido: cada fila empieza con una
# clave compuesta ("55-0-0-55-7342-...") que el encabezado no nombra, y a cambio
# no trae la descripción del clasificador económico. Leída con el encabezado,
# todo queda corrido un lugar salvo los cuatro montos del final
COLS_2022 = ["clave"] + [c for c in COLS if c != "eco_desc"]


def bajar(anio):
    CRUDO.mkdir(parents=True, exist_ok=True)
    destino = CRUDO / (ARCH[anio] + ".csv")
    print("  bajando", URL[anio])
    req = urllib.request.Request(URL[anio], headers={"User-Agent": "Mozilla/5.0"})
    destino.write_bytes(urllib.request.urlopen(req, timeout=600).read())
    return destino


def leer(anio):
    arch = next(CRUDO.glob(ARCH[anio] + ".csv*"), None) or bajar(anio)
    cols = COLS_2022 if anio == 2022 else COLS
    d = pd.read_csv(arch, sep=";", encoding="latin-1", dtype=str, low_memory=False, header=None, skiprows=1)
    assert d.shape[1] == len(cols), f"{arch.name}: {d.shape[1]} columnas, se esperaban {len(cols)}"
    d.columns = cols
    d = d.reindex(columns=COLS)
    d = d.dropna(subset=["jur"]).reset_index(drop=True)
    for c in MONTOS:
        d[c] = num(d[c].astype(str))
    for c in CLAVE:
        d[c] = pd.to_numeric(d[c], errors="coerce").fillna(-1).astype(int)
    d["anio"] = anio
    return d


print("crudo:", CRUDO)
R = pd.concat([leer(a) for a in ARCH], ignore_index=True)
# un código que no es número es la señal de un archivo con las columnas corridas
mal = R[(R[CLAVE] < 0).any(axis=1)]
assert mal.empty, f"códigos no numéricos (¿columnas corridas?):\n{mal.groupby('anio').size()}"
for c in [c for c in COLS if c.endswith("_desc")]:
    R[c] = R[c].fillna("").str.strip().str.replace(r"\s+", " ", regex=True)

# ---- IPC -------------------------------------------------------------------
url = ("https://apis.datos.gob.ar/series/api/series/?ids=148.3_INIVELNAL_DICI_M_26"
       "&start_date=2022-01-01&format=csv")
try:
    # la API rechaza con 403 el User-Agent por defecto de Python
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    ipc = pd.read_csv(urllib.request.urlopen(req, timeout=60))
    ipc.to_csv(DATOS / "_ipc_mensual.csv", index=False)
except Exception as e:  # sin red se usa la última copia bajada
    print("  sin red para el IPC, uso la copia:", e)
    ipc = pd.read_csv(DATOS / "_ipc_mensual.csv")
ipc.columns = ["mes", "ipc"]
ipc["anio"] = ipc.mes.str[:4].astype(int)
ult_mes, ult_ipc = ipc.mes.iloc[-1][:7], ipc.ipc.iloc[-1]
I = ipc.groupby("anio").agg(ipc_promedio=("ipc", "mean"), meses=("ipc", "size")).loc[list(ARCH)]
I["factor"] = ult_ipc / I.ipc_promedio
I["pesos_de"] = ult_mes
I.round(4).to_csv(DATOS / "ipc.csv")

# ---- dimensiones -----------------------------------------------------------
# la descripción de un código puede cambiar de año (un ministerio que se
# renombra): manda la del año más reciente en que aparece


def dim(claves, desc, nombre):
    t = (R.sort_values("anio").groupby(claves).tail(1)[claves + desc]
         .sort_values(claves).reset_index(drop=True))
    t.to_csv(DATOS / f"dim_{nombre}.csv", index=False)
    return t


dim(["car"], ["car_desc"], "caracter")
J = dim(["jur"], ["jur_desc"], "jurisdiccion")
dim(["jur", "ue"], ["ue_desc"], "unidad_ejecutora")
P = dim(["jur", "prog"], ["prog_desc"], "programa")
F = dim(["fin", "fun"], ["fin_desc", "fun_desc"], "finalidad_funcion")
O = dim(["inc", "ppal"], ["inc_desc", "ppal_desc"], "objeto_gasto")
dim(["fte"], ["fte_desc"], "fuente")
dim(["geo"], ["geo_desc"], "geografico")

# ---- hechos ----------------------------------------------------------------
H = R.groupby(["anio"] + CLAVE, as_index=False)[MONTOS].sum()
H = H[(H[MONTOS] != 0).any(axis=1)]
H["corte"] = H.anio.map(CORTE)
H.to_csv(DATOS / "hechos.csv", index=False)

# ---- control -----------------------------------------------------------------
T = H.groupby("anio")[MONTOS].sum()
T["ejecucion_%"] = 100 * T.devengado / T.vigente
T["devengado_real_billones"] = T.devengado * I.factor / 1e12
print(f"\nhechos: {len(H):,} filas · pesos de {ult_mes}")
print((T[MONTOS] / 1e12).round(2).assign(**{"ejec %": T["ejecucion_%"].round(1),
                                               "deveng. real": T.devengado_real_billones.round(2)}).to_string())

# ---- agregados para la web -------------------------------------------------
H["jur_desc"] = H.jur.map(J.set_index("jur").jur_desc)
H = H.merge(F, on=["fin", "fun"]).merge(O, on=["inc", "ppal"]).merge(P, on=["jur", "prog"])


def agg(por, top=None):
    g = H.groupby(["anio"] + por, as_index=False)[MONTOS].sum()
    if top:
        g = g.sort_values("vigente", ascending=False).groupby("anio").head(top)
    return g.round(0).to_dict("records")


web = {
    "pesos_de": ult_mes,
    "factor": I.factor.round(6).to_dict(),
    "corte": CORTE,
    "totales": agg([]),
    "jurisdicciones": agg(["jur", "jur_desc"]),
    "finalidades": agg(["fin", "fin_desc"]),
    "funciones": agg(["fin", "fin_desc", "fun", "fun_desc"]),
    "incisos": agg(["inc", "inc_desc"]),
    "programas": agg(["jur", "jur_desc", "prog", "prog_desc"]),
}
# las quince comunas como UNIDADES EJECUTORAS (lo comparable entre barrios), con
# la población del censo 2022 para el gasto por habitante
ue = pd.read_csv(DATOS / "dim_unidad_ejecutora.csv")
com = ue[ue.ue_desc.str.fullmatch(r"Comuna \d{1,2}", case=False)]
c = (H.merge(com, on=["jur", "ue"]).assign(comuna=lambda x: x.ue_desc.str.extract(r"(\d+)")[0].astype(int))
     .groupby(["anio", "comuna"], as_index=False)[MONTOS].sum())
pob = pd.read_csv(DATOS / "poblacion_comuna_2022.csv", index_col=0).poblacion
c["poblacion"] = c.comuna.map(pob)
web["comunas"] = c.round(0).to_dict("records")
# un .js y no un .json: la página tiene que andar abierta con doble clic, y el
# navegador no deja hacer fetch de un archivo local
js = "window.DATOS = " + json.dumps(web, ensure_ascii=False, separators=(",", ":")) + ";\n"
(WEB / "datos.js").write_text(js, encoding="utf-8")
(WEB / "datos.json").unlink(missing_ok=True)
print("\n->", DATOS, "\n->", WEB / "datos.js", f"({(WEB / 'datos.js').stat().st_size / 1e3:.0f} kB)")
