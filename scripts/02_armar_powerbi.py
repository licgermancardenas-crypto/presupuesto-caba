# -*- coding: utf-8 -*-
"""
PRESUPUESTO CABA - 02: genera el proyecto Power BI (TMDL + PBIR) en powerbi/.

Corre despues de 01. Borra y reescribe el modelo y el reporte: los cambios hechos a mano en
Power BI Desktop se pierden si se vuelve a correr. El parametro CarpetaDatos queda con una ruta
generica (Power BI no acepta rutas relativas): la de cada maquina se pone con la variable
PBI_CARPETA_DATOS o una vez en Desktop. Con la ruta real, no commitear expressions.tmdl.
"""
from pathlib import Path
import csv
import json
import os
import shutil
import uuid

BASE = Path(__file__).resolve().parents[1]
DATOS = BASE / "datos"
OUT = BASE / "powerbi"
SM = OUT / "PresupuestoCABA.SemanticModel"
RP = OUT / "PresupuestoCABA.Report"
NS = uuid.UUID("7b0e8a52-6a1c-4c55-9a55-5a3c0e2f1a01")
tag = lambda *k: str(uuid.uuid5(NS, "|".join(k)))  # noqa: E731  lineageTag estable entre corridas
T = "\t"

if SM.exists():
    shutil.rmtree(SM)
if RP.exists():
    shutil.rmtree(RP)
(SM / "definition" / "tables").mkdir(parents=True)


def w(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8", newline="\n")


def wj(path, obj):
    w(path, json.dumps(obj, ensure_ascii=False, indent=2) + "\n")


def q(name):
    return f"'{name.replace(chr(39), chr(39) * 2)}'" if any(c in name for c in " .=:'") else name


def header(f):
    with open(DATOS / f, encoding="utf-8") as fh:
        return next(csv.reader(fh))


# ---------------------------------------------------------------------------
# Tablas: (nombre visible, csv, [(columna, sourceColumn, tipoM, tipoTMDL, oculta, descripción, sortBy)],
#          [(nueva col, expresión M)] claves y columnas armadas en Power Query, descripción)
# ---------------------------------------------------------------------------
I, D, S = ("Int64.Type", "int64"), ("type number", "double"), ("type text", "string")
GEO_DESC = ("Ubicación de la UNIDAD QUE EJECUTA el gasto, no del lugar donde cae. La sede de "
            "gobierno está en Parque Patricios (comuna 4): sumar por esta columna NO dice cuánta "
            "plata va a cada barrio.")
TABLAS = {
    "Hechos": dict(csv="hechos.csv", desc="Crédito y gasto por partida agregada. Montos NOMINALES; "
                   "usar las medidas de _Medidas. 2026 es a junio (parcial).",
                   cols=[("anio", I, True), ("car", I, True), ("jur", I, True), ("ue", I, True),
                         ("prog", I, True), ("fin", I, True), ("fun", I, True), ("inc", I, True),
                         ("ppal", I, True), ("fte", I, True), ("geo", I, True),
                         ("sancionado", D, True), ("vigente", D, True), ("devengado", D, True),
                         ("corte", S, False)],
                   nombres={"corte": "Corte"},
                   extra=[("ClaveUE", 'Text.From([jur]) & "|" & Text.From([ue])', True),
                          ("ClaveProg", 'Text.From([jur]) & "|" & Text.From([prog])', True),
                          ("ClaveFinFun", 'Text.From([fin]) & "|" & Text.From([fun])', True),
                          ("ClaveObjeto", 'Text.From([inc]) & "|" & Text.From([ppal])', True)]),
    "Año": dict(csv="ipc.csv", desc="Un registro por ejercicio, con el factor que lleva sus pesos a "
                "pesos del mes indicado en 'Pesos de' (IPC INDEC, promedio anual).",
                cols=[("anio", I, False), ("ipc_promedio", D, False), ("meses", I, False),
                      ("factor", D, False), ("pesos_de", S, False)],
                nombres={"anio": "Año", "ipc_promedio": "IPC promedio", "meses": "Meses con IPC",
                         "factor": "Factor a pesos de hoy", "pesos_de": "Pesos de"}, extra=[]),
    "Carácter": dict(csv="dim_caracter.csv", desc="Administración central u organismo descentralizado.",
                     cols=[("car", I, True), ("car_desc", S, False)], nombres={"car_desc": "Carácter"},
                     extra=[]),
    "Jurisdicción": dict(csv="dim_jurisdiccion.csv", desc="Ministerio, poder u organismo. Con la "
                         "descripción del último año en que aparece el código.",
                         cols=[("jur", I, True), ("jur_desc", S, False)], nombres={"jur_desc": "Jurisdicción"},
                         extra=[]),
    "Unidad ejecutora": dict(csv="dim_unidad_ejecutora.csv", desc="Unidad que ejecuta el gasto, "
                             "dentro de su jurisdicción.",
                             cols=[("jur", I, True), ("ue", I, True), ("ue_desc", S, False)],
                             nombres={"ue_desc": "Unidad ejecutora"},
                             extra=[("ClaveUE", 'Text.From([jur]) & "|" & Text.From([ue])', True)]),
    "Programa": dict(csv="dim_programa.csv", desc="Programa presupuestario. El código se repite entre "
                     "jurisdicciones: la clave es jurisdicción + programa.",
                     cols=[("jur", I, True), ("prog", I, False), ("prog_desc", S, False)],
                     nombres={"prog": "Código de programa", "prog_desc": "Descripción del programa"},
                     extra=[("ClaveProg", 'Text.From([jur]) & "|" & Text.From([prog])', True),
                            ("Programa", 'Text.From([prog]) & " - " & [prog_desc]', False)]),
    "Finalidad y función": dict(csv="dim_finalidad_funcion.csv", desc="Clasificación por finalidad y "
                                "función: para qué se gasta.",
                                cols=[("fin", I, True), ("fun", I, True), ("fin_desc", S, False),
                                      ("fun_desc", S, False)],
                                nombres={"fin_desc": "Finalidad", "fun_desc": "Función"},
                                sort={"fin_desc": "fin"},
                                extra=[("ClaveFinFun", 'Text.From([fin]) & "|" & Text.From([fun])', True)]),
    "Objeto del gasto": dict(csv="dim_objeto_gasto.csv", desc="Clasificación por objeto: en qué se "
                             "gasta (personal, bienes, servicios, transferencias...).",
                             cols=[("inc", I, True), ("ppal", I, True), ("inc_desc", S, False),
                                   ("ppal_desc", S, False)],
                             nombres={"inc_desc": "Inciso", "ppal_desc": "Partida principal"},
                             sort={"inc_desc": "inc"},
                             extra=[("ClaveObjeto", 'Text.From([inc]) & "|" & Text.From([ppal])', True)]),
    "Fuente": dict(csv="dim_fuente.csv", desc="Fuente de financiamiento.",
                   cols=[("fte", I, True), ("fte_desc", S, False)], nombres={"fte_desc": "Fuente"}, extra=[]),
    "Geográfico": dict(csv="dim_geografico.csv", desc=GEO_DESC,
                       cols=[("geo", I, True), ("geo_desc", S, False)],
                       nombres={"geo_desc": "Ubicación de la unidad ejecutora"},
                       coldesc={"geo_desc": GEO_DESC}, extra=[]),
}

errores = []
for nombre, t in TABLAS.items():
    reales = header(t["csv"])
    esperadas = [c for c, *_ in t["cols"]]
    if reales != esperadas:
        errores.append(f"{t['csv']}: CSV {reales} vs modelo {esperadas}")
assert not errores, "\n".join(errores)


def m_particion(t):
    tipos = ", ".join(f'{{"{c}", {tp[0]}}}' for c, tp, _ in t["cols"])
    pasos = [
        f'Origen = Csv.Document(File.Contents(CarpetaDatos & "{t["csv"]}"), '
        '[Delimiter = ",", Encoding = 65001, QuoteStyle = QuoteStyle.Csv])',
        "Encabezados = Table.PromoteHeaders(Origen, [PromoteAllScalars = true])",
        # cultura en-US explícita: el modelo es es-AR y leería el punto decimal como separador de miles
        f'Tipos = Table.TransformColumnTypes(Encabezados, {{{tipos}}}, "en-US")',
    ]
    ult = "Tipos"
    for i, (c, expr, _) in enumerate(t["extra"]):
        paso = f"Agregar{i}"
        pasos.append(f'{paso} = Table.AddColumn({ult}, "{c}", each {expr}, type text)')
        ult = paso
    cuerpo = ",\n".join(T * 5 + p for p in pasos)
    return (T * 4 + "let\n" + cuerpo + "\n" + T * 4 + "in\n" + T * 5 + ult)


def tabla_tmdl(nombre, t):
    L = []
    L.append(f"/// {t['desc']}")
    L.append(f"table {q(nombre)}")
    L.append(f"{T}lineageTag: {tag('t', nombre)}")
    L.append("")
    sort = t.get("sort", {})
    todas = [(c, tp[1], oc) for c, tp, oc in t["cols"]] + [(c, "string", oc) for c, _, oc in t["extra"]]
    for src, dt, oculta in todas:
        vis = t["nombres"].get(src, src)
        d = t.get("coldesc", {}).get(src)
        if d:
            L.append(f"{T}/// {d}")
        L.append(f"{T}column {q(vis)}")
        L.append(f"{T*2}dataType: {dt}")
        if dt == "double":
            L.append(f"{T*2}formatString: #,0")
        if dt == "int64" and src == "anio":
            L.append(f"{T*2}formatString: 0")
        if oculta:
            L.append(f"{T*2}isHidden")
        L.append(f"{T*2}lineageTag: {tag('c', nombre, src)}")
        L.append(f"{T*2}summarizeBy: none")
        L.append(f"{T*2}sourceColumn: {src}")
        if src in sort:
            L.append(f"{T*2}sortByColumn: {q(t['nombres'].get(sort[src], sort[src]))}")
        L.append("")
        L.append(f"{T*2}annotation SummarizationSetBy = User")
        L.append("")
    L.append(f"{T}partition {q(nombre)} = m")
    L.append(f"{T*2}mode: import")
    L.append(f"{T*2}source =")
    L.append(m_particion(t))
    L.append("")
    return "\n".join(L) + "\n"


for nombre, t in TABLAS.items():
    w(SM / "definition" / "tables" / f"{nombre}.tmdl", tabla_tmdl(nombre, t))

# ---- medidas ---------------------------------------------------------------
REAL = ("'Real' = pesos del mes indicado en Año[Pesos de] (2026-08), con el promedio anual del IPC "
        "INDEC de cada ejercicio.")
PARC = "2026 es a junio (segundo trimestre): no se compara con un año cerrado."
MON, PCT = "\\$ #,0", "0.0 %"
MEDIDAS = [
    ("Sancionado", "SUM(Hechos[sancionado])", MON,
     f"Crédito aprobado por la Legislatura, en pesos corrientes de cada año. {PARC}"),
    ("Vigente", "SUM(Hechos[vigente])", MON,
     f"Crédito vigente tras las modificaciones, en pesos corrientes. {PARC}"),
    ("Devengado", "SUM(Hechos[devengado])", MON,
     f"Gasto devengado (ejecutado), en pesos corrientes. {PARC}"),
    ("Sancionado real", "SUMX(Hechos, Hechos[sancionado] * RELATED('Año'[Factor a pesos de hoy]))", MON,
     f"Sancionado a pesos constantes. {REAL}"),
    ("Vigente real", "SUMX(Hechos, Hechos[vigente] * RELATED('Año'[Factor a pesos de hoy]))", MON,
     f"Vigente a pesos constantes. {REAL}"),
    ("Devengado real", "SUMX(Hechos, Hechos[devengado] * RELATED('Año'[Factor a pesos de hoy]))", MON,
     f"Devengado a pesos constantes. {REAL} {PARC}"),
    ("% Ejecución", "DIVIDE([Devengado], [Vigente])", PCT,
     f"Devengado sobre vigente. {PARC}"),
    ("Participación %", "DIVIDE([Devengado real], CALCULATE([Devengado real], ALLSELECTED(Hechos)))", PCT,
     "Parte del devengado real total de lo que está seleccionado (respeta segmentadores y filtros)."),
    ("Var. real interanual %", "\n".join([
        "VAR anio = SELECTEDVALUE('Año'[Año])",
        "VAR actual = [Devengado real]",
        "VAR anterior = CALCULATE([Devengado real], 'Año'[Año] = anio - 1)",
        "VAR parcial = CALCULATE(COUNTROWS(Hechos), 'Año'[Año] = anio, Hechos[Corte] <> \"anual\") > 0",
        "RETURN",
        "\tIF(NOT ISBLANK(anio) && NOT parcial && NOT ISBLANK(anterior), DIVIDE(actual - anterior, anterior))",
    ]), PCT,
     f"Variación del devengado real contra el año anterior. Queda en blanco para 2026, que es parcial. {REAL}"),
]
L = ["/// Tabla de medidas. " + REAL + " " + PARC, "table _Medidas", f"{T}lineageTag: {tag('t', '_Medidas')}", ""]
for n, expr, fmt, desc in MEDIDAS:
    L.append(f"{T}/// {desc}")
    if "\n" in expr:
        L.append(f"{T}measure {q(n)} =")
        L += [T * 3 + x for x in expr.split("\n")]
    else:
        L.append(f"{T}measure {q(n)} = {expr}")
    L.append(f"{T*2}formatString: {fmt}")
    L.append(f"{T*2}lineageTag: {tag('m', n)}")
    L.append("")
L += [f"{T}column Columna", f"{T*2}dataType: string", f"{T*2}isHidden", f"{T*2}lineageTag: {tag('c', '_Medidas')}",
      f"{T*2}summarizeBy: none", f"{T*2}sourceColumn: Columna", "",
      f"{T}partition _Medidas = m", f"{T*2}mode: import", f"{T*2}source =",
      T * 4 + 'let', T * 5 + 'Origen = #table(type table [Columna = text], {})', T * 4 + 'in', T * 5 + 'Origen', ""]
w(SM / "definition" / "tables" / "_Medidas.tmdl", "\n".join(L) + "\n")

# ---- relaciones: todas de la dimensión (1) a Hechos (N), filtro simple ---------
REL = [("anio", "Año", "Año"), ("car", "Carácter", "car"), ("jur", "Jurisdicción", "jur"),
       ("ClaveUE", "Unidad ejecutora", "ClaveUE"), ("ClaveProg", "Programa", "ClaveProg"),
       ("ClaveFinFun", "Finalidad y función", "ClaveFinFun"), ("ClaveObjeto", "Objeto del gasto", "ClaveObjeto"),
       ("fte", "Fuente", "fte"), ("geo", "Geográfico", "geo")]
L = []
for fc, dt, dc in REL:
    L += [f"relationship {tag('r', fc)}", f"{T}fromColumn: Hechos.{q(fc)}", f"{T}toColumn: {q(dt)}.{q(dc)}", ""]
w(SM / "definition" / "relationships.tmdl", "\n".join(L))

carpeta = os.environ.get("PBI_CARPETA_DATOS", r"C:\presupuesto-caba\datos" + "\\")
w(SM / "definition" / "expressions.tmdl",
  f"/// Carpeta con los CSV que arma scripts/01_armar_datos.py. Termina en barra invertida.\n"
  f'expression CarpetaDatos = "{carpeta}" meta [IsParameterQuery=true, Type="Text", IsParameterQueryRequired=true]\n'
  f"{T}lineageTag: {tag('e', 'CarpetaDatos')}\n\n"
  f"{T}annotation PBI_ResultType = Text\n")

w(SM / "definition" / "database.tmdl", "database\n\tcompatibilityLevel: 1567\n")
orden = ["CarpetaDatos", "_Medidas"] + list(TABLAS)
w(SM / "definition" / "model.tmdl", "\n".join([
    "model Model",
    f"{T}culture: es-AR",
    f"{T}defaultPowerBIDataSourceVersion: powerBI_V3",
    f"{T}sourceQueryCulture: es-AR",
    f"{T}dataAccessOptions",
    f"{T*2}legacyRedirects",
    f"{T*2}returnErrorValuesAsNull",
    "",
    f"annotation PBI_QueryOrder = {json.dumps(orden, ensure_ascii=False)}",
    "",
    "annotation __PBI_TimeIntelligenceEnabled = 0",
    "",
    *[f"ref table {q(n)}" for n in ["_Medidas"] + list(TABLAS)],
    "",
]))
wj(SM / "definition.pbism", {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/item/semanticModel/definitionProperties/1.0.0/schema.json",
    "version": "4.0", "settings": {}})

# ---------------------------------------------------------------------------
# Reporte PBIR
# ---------------------------------------------------------------------------
SCH = "https://developer.microsoft.com/json-schemas/fabric/item/report/"
wj(RP / "definition.pbir", {"$schema": SCH + "definitionProperties/2.0.0/schema.json", "version": "4.0",
                            "datasetReference": {"byPath": {"path": "../PresupuestoCABA.SemanticModel"}}})
DEF = RP / "definition"
wj(DEF / "version.json", {"$schema": SCH + "definition/versionMetadata/1.0.0/schema.json", "version": "2.0.0"})
TEMA = "CY25SU12"
shutil.copy(rf"C:\Program Files\Microsoft Power BI Desktop\bin\WebView2Resources\minerva\sharedresources\BaseThemes\{TEMA}.json",
            (RP / "StaticResources/SharedResources/BaseThemes").mkdir(parents=True, exist_ok=True)
            or RP / f"StaticResources/SharedResources/BaseThemes/{TEMA}.json")
wj(DEF / "report.json", {
    "$schema": SCH + "definition/report/3.0.0/schema.json",
    "themeCollection": {"baseTheme": {"name": TEMA, "reportVersionAtImport":
                                      {"visual": "2.4.0", "report": "3.0.0", "page": "2.0.0"},
                                      "type": "SharedResources"}},
    "resourcePackages": [{"name": "SharedResources", "type": "SharedResources",
                          "items": [{"name": TEMA, "path": f"BaseThemes/{TEMA}.json", "type": "BaseTheme"}]}],
    "settings": {"useStylableVisualContainerHeader": True, "exportDataMode": "AllowSummarized",
                 "defaultDrillFilterOtherVisuals": True},
})


def col(ent, prop):
    return {"Column": {"Expression": {"SourceRef": {"Entity": ent}}, "Property": prop}}


def mea(prop):
    return {"Measure": {"Expression": {"SourceRef": {"Entity": "_Medidas"}}, "Property": prop}}


def proj(f):
    k = "Column" if "Column" in f else "Measure"
    ent, prop = f[k]["Expression"]["SourceRef"]["Entity"], f[k]["Property"]
    return {"field": f, "queryRef": f"{ent}.{prop}", "nativeQueryRef": prop}


def lit(v):
    return {"expr": {"Literal": {"Value": v}}}


def titulo(texto):
    return {"title": [{"properties": {"show": lit("true"), "text": lit(f"'{texto}'")}}]}


def visual(page, name, vtype, pos, roles, sort=None, objects=None, title=None):
    v = {"visualType": vtype, "query": {"queryState": {r: {"projections": [proj(f) for f in fs]}
                                                       for r, fs in roles.items()}},
         "drillFilterOtherVisuals": True}
    if sort:
        v["query"]["sortDefinition"] = {"sort": [{"field": sort, "direction": "Descending"}], "isDefaultSort": False}
    if objects:
        v["objects"] = objects
    if title:
        v["visualContainerObjects"] = titulo(title)
    x, y, wd, h = pos
    wj(DEF / "pages" / page / "visuals" / name / "visual.json", {
        "$schema": SCH + "definition/visualContainer/2.4.0/schema.json", "name": name,
        "position": {"x": x, "y": y, "z": 0, "height": h, "width": wd, "tabOrder": 0}, "visual": v})


def pagina(name, display, interacciones=()):
    p = {"$schema": SCH + "definition/page/2.0.0/schema.json", "name": name, "displayName": display,
         "displayOption": "FitToPage", "height": 720, "width": 1280}
    if interacciones:
        p["visualInteractions"] = [{"source": s, "target": t_, "type": "NoFilter"} for s, t_ in interacciones]
    wj(DEF / "pages" / name / "page.json", p)


ANIO = col("Año", "Año")
UNICO = {"selection": [{"properties": {"singleSelect": lit("true")}}]}

# Resumen: el segmentador de año no filtra la serie por año, para que siempre muestre los cinco
pagina("resumen", "Resumen", [("resumen_anio", "resumen_serie")])
visual("resumen", "resumen_anio", "slicer", (20, 20, 230, 160), {"Values": [ANIO]}, objects=UNICO, title="Año")
for i, (n, m) in enumerate([("dev", "Devengado real"), ("vig", "Vigente real"), ("ejec", "% Ejecución")]):
    visual("resumen", f"resumen_card_{n}", "card", (270 + i * 335, 20, 320, 160), {"Values": [mea(m)]}, title=m)
visual("resumen", "resumen_finalidad", "clusteredBarChart", (20, 200, 610, 250),
       {"Category": [col("Finalidad y función", "Finalidad"), col("Finalidad y función", "Función")],
        "Y": [mea("Devengado real")]}, sort=mea("Devengado real"), title="Devengado real por finalidad y función")
visual("resumen", "resumen_jurisdiccion", "clusteredBarChart", (650, 200, 610, 500),
       {"Category": [col("Jurisdicción", "Jurisdicción")], "Y": [mea("Devengado real")]},
       sort=mea("Devengado real"), title="Devengado real por jurisdicción")
visual("resumen", "resumen_serie", "clusteredColumnChart", (20, 470, 610, 230),
       {"Category": [ANIO], "Y": [mea("Devengado real")]}, title="Devengado real por año (2026 a junio)")

pagina("programas", "Programas")
visual("programas", "programas_anio", "slicer", (20, 20, 230, 160), {"Values": [ANIO]}, objects=UNICO, title="Año")
visual("programas", "programas_jur", "slicer", (20, 200, 230, 500),
       {"Values": [col("Jurisdicción", "Jurisdicción")]}, title="Jurisdicción")
visual("programas", "programas_tabla", "tableEx", (270, 20, 990, 680),
       {"Values": [col("Jurisdicción", "Jurisdicción"), col("Programa", "Programa"), mea("Sancionado"),
                   mea("Vigente"), mea("Devengado"), mea("% Ejecución")]},
       sort=mea("Vigente"), title="Programas · pesos corrientes del año elegido")

wj(DEF / "pages" / "pages.json", {"$schema": SCH + "definition/pagesMetadata/1.0.0/schema.json",
                                  "pageOrder": ["resumen", "programas"], "activePageName": "resumen"})

wj(OUT / "PresupuestoCABA.pbip", {
    "$schema": "https://developer.microsoft.com/json-schemas/fabric/pbip/pbipProperties/1.0.0/schema.json",
    "version": "1.0", "artifacts": [{"report": {"path": "PresupuestoCABA.Report"}}],
    "settings": {"enableAutoRecovery": True}})
w(OUT / ".gitignore", "**/.pbi/localSettings.json\n**/.pbi/cache.abf\n")
print("ok", OUT)
