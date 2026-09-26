# Presupuesto CABA en Power BI

Proyecto de Power BI Desktop en formato **PBIP**: modelo en TMDL y reporte en PBIR, todo como
texto, para poder versionarlo en git. Lee los CSV que arma `../scripts/01_armar_datos.py`.

## Abrirlo

1. En Power BI Desktop, activá **Archivo › Opciones y configuración › Opciones › Características
   en versión preliminar** › *Store semantic model using TMDL format* y *Store reports using
   enhanced metadata format (PBIR)*. Hacelo una sola vez y reiniciá Desktop.
2. Abrí `PresupuestoCABA.pbip`.
3. La primera vez abre **sin datos**, porque el caché (`.pbi/cache.abf`) no se versiona. Tocá
   **Inicio › Actualizar**.

## Cambiar la carpeta de datos

Power BI no acepta rutas relativas, así que el parámetro `CarpetaDatos` viene con
`C:\presupuesto-caba\datos\`. Si clonaste el repo en otro lado: **Inicio › Transformar datos ›
Editar parámetros**, poné la ruta de tu carpeta `datos\` **con la barra invertida final** y
actualizá. También se puede regenerar con la ruta puesta:
`PBI_CARPETA_DATOS="D:\mi\ruta\datos\" python scripts/02_armar_powerbi.py`.

Ese cambio queda guardado en `expressions.tmdl`: no lo commitees, o tu ruta local queda en el repo.

## Actualizar los datos

1. `python scripts/01_armar_datos.py` desde la raíz del repo.
2. En Desktop, **Inicio › Actualizar**.

## Qué hay

- **Hechos**: 66 mil filas, una por año × jurisdicción × unidad ejecutora × programa ×
  finalidad-función × inciso-principal × fuente × ubicación. Los montos son nominales.
- **Dimensiones**: Año (con el factor IPC), Carácter, Jurisdicción, Unidad ejecutora, Programa,
  Finalidad y función, Objeto del gasto, Fuente y Geográfico. Todas se relacionan 1:N con Hechos,
  con filtro simple. Las claves compuestas (`jur|prog`, `jur|ue`, `fin|fun`, `inc|ppal`) se arman
  en Power Query y están ocultas.
- **_Medidas**:
  - Sancionado, Vigente y Devengado, en pesos corrientes.
  - Sus versiones **reales**, en pesos de agosto de 2026 (promedio anual del IPC INDEC).
  - % Ejecución, Participación % y Var. real interanual %.

Hay dos advertencias que el modelo ya lleva en las descripciones:

- **2026 es a junio.** Su ejecución no se compara con la de un año cerrado, y la variación
  interanual queda en blanco.
- **Geográfico no es "plata por barrio".** Marca dónde está la unidad que ejecuta, y la sede de
  gobierno está en la comuna 4.

## Reporte

- **Resumen**: segmentador de año, tres tarjetas (Devengado real, Vigente real y % Ejecución),
  barras por finalidad-función y por jurisdicción, y columnas por año. La serie por año **no** la
  filtra el segmentador, así que siempre muestra los cinco años.
- **Programas**: segmentadores de año (una sola selección) y de jurisdicción, y una tabla de
  programas con sancionado, vigente, devengado y % de ejecución en pesos corrientes del año
  elegido.

Los visuales tienen formato básico: colores, tamaños de fuente y unidades de las tarjetas quedan
para ajustar a mano en Desktop.

## Publicarlo en la web

1. **Inicio › Publicar**, a un área de trabajo de Power BI. Hace falta una cuenta de Power BI.
2. En app.powerbi.com, abrí el informe y tocá **Archivo › Insertar informe › Publicar en la web
   (público)**. El administrador del tenant tiene que tener habilitado *Publicar en la web*. Si no
   aparece la opción, está deshabilitado.
3. El enlace o el `<iframe>` que da se pega en cualquier página.

Ojo: **Publicar en la web** hace que el informe y sus datos sean visibles para cualquiera con el
enlace. Estos datos son públicos (BA Data e INDEC), pero la regla vale para cualquier otra cosa que
se agregue al modelo.

## Qué se validó y qué no

Se validó:

- **Modelo.** Se deserializó con el `TmdlSerializer` del propio Power BI Desktop 2.152 (marzo de
  2026) y dio 11 tablas, 9 relaciones 1:N, 9 medidas y el parámetro.
- **Reporte.** Los 18 JSON validan contra los esquemas publicados por Microsoft: report 3.0.0,
  page 2.0.0, visualContainer 2.4.0, definitionProperties y pbip.
- **Referencias.** Los 22 campos que usan los visuales existen en el modelo.
- **Datos.** Las claves de las dimensiones son únicas, no hay filas huérfanas en Hechos y los
  órdenes por código (Finalidad y Inciso) son 1:1.

No se validó:

- **El proyecto no se abrió en la interfaz de Desktop.** Las consultas M y el DAX no se
  ejecutaron. Si algo falla, Desktop marca el archivo y la línea al abrir.
- Cómo se ven los visuales.
