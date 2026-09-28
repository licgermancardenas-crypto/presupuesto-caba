# Presupuesto CABA

**Verlo:** https://licgermancardenas-crypto.github.io/presupuesto-caba/

Monitor del presupuesto de la Ciudad de Buenos Aires, 2022-2026: cuánto se gasta, en qué
(finalidad y función), quién lo gasta (jurisdicción), cómo (objeto del gasto), las quince
comunas y programa por programa.

Toma como idea el [Monitor de Presupuesto CABA](https://juanifernandez.com/presupuesto/) de Juan
Ignacio Fernández, que es una página que embebe un tablero de Power BI publicado en su cuenta. Acá
no se copia su tablero: los datos y las dos salidas se arman desde cero con datos abiertos.

## Qué hay

| Carpeta | Qué es |
|---|---|
| `scripts/01_armar_datos.py` | ETL: lee el crudo, arma el modelo estrella, baja el IPC y escribe los datos de la web |
| `scripts/02_armar_powerbi.py` | Genera `powerbi/` desde cero (pisa lo que se haya tocado a mano en Desktop) |
| `datos/` | `hechos.csv` + `dim_*.csv` + `ipc.csv`: el modelo que usa Power BI |
| `web/` | El monitor propio: `index.html` (todo el presupuesto) y `comunas.html` (mapa y detalle de las quince comunas), con `estilo.css` y `comun.js` compartidos. `hechos.js` es la tabla de hechos que la página filtra y suma en el navegador (año × jurisdicción × programa × obra × función × partida × fuente × comuna); `datos.js`, el IPC y el mapa. Todos los gráficos son filtros: clic en una barra recorta la página y baja de nivel (jurisdicción → programa → obra). Se abre con doble clic, sin servidor, y es lo que publican GitHub Pages y Vercel |
| `powerbi/` | El mismo modelo como proyecto de Power BI (`.pbip`). Ver su README |

## Cómo se actualiza

```
python scripts/01_armar_datos.py
python scripts/02_armar_powerbi.py   # sólo si cambió el modelo; si no, alcanza con refrescar en Desktop
```

La primera vez baja el crudo de BA Data a `crudo/` (unos 140 MB, fuera de git). Si ya lo tenés
en otra carpeta, se indica con la variable `PRESUPUESTO_CRUDO` (sirven también comprimidos en
`.gz`). Cuando BA Data publique un trimestre nuevo, se agrega en `ARCH`, `URL` y `CORTE` del
script y se vuelve a correr.

## Lo que hay que saber para leerlo

- **Pesos constantes.** Cada año se lleva a pesos del último mes con IPC (hoy, agosto de 2026)
  con el promedio anual del IPC nacional del INDEC. Sin eso, 2022 contra 2026 no significa nada:
  los precios se multiplicaron por más de diez.
- **2026 es a junio.** El archivo más nuevo es el del segundo trimestre.
- **El clasificador geográfico no es "plata por barrio".** Marca dónde está la unidad que ejecuta:
  la sede de gobierno está en la comuna 4 y se llevaría un tercio del total. Lo comparable por
  barrio es el gasto de las quince comunas como unidades ejecutoras, que es lo que muestra la web.
- **El organigrama cambió en 2024** (Seguridad se separó de Justicia, se creó Movilidad e
  Infraestructura). Para comparar años, usar finalidad y función, no jurisdicción.
- **El archivo de 2022 viene con las columnas corridas**: cada fila tiene una clave de más al
  principio y le falta la descripción del clasificador económico. El script lo lee con su propio
  esquema y frena si algún año vuelve a traer códigos no numéricos.

## Control

Sancionado 2025 = $14,17 billones corrientes, en línea con los "casi 14 billones" que informó la
Legislatura al aprobar la ley (la diferencia puede venir de cómo se cuentan las contribuciones
figurativas; no está conciliada partida por partida). En pesos de agosto
de 2026, el devengado anual queda entre $18,2 y $19,7 billones de 2022 a 2025.
