# Conclave "Segunda Misión" — Nuevas ideas

Acta consolidada del conclave de los diez agentes, celebrado en la rama
`ideas/segunda-mision` (base: `main` @ v0.2.2). Objetivo: determinar si conviene
un **segundo core** (`core2/`) o un **nuevo producto** de visión clásica, y en qué
orden. Restricción de mandato: solo OpenCV + NumPy (visión clásica, sin deep
learning), sobre el stack actual (FastAPI + PostgreSQL + frontend vanilla).

## 1. Candidaturas sobre la mesa

| # | Dirección | Tipo | Descripción breve |
|---|-----------|------|-------------------|
| 1 | **Calibración geométrica y colorimétrica con patrón** | Segundo core habilitante | ArUco/Charuco + carta de color → mm reales y ΔE trazables. Resuelve la deuda declarada del contrato actual ("sin patrón de escala no hay milímetros") y la no-comparabilidad inter-cámara que ADR-013 impone. |
| 2 | **Contaje y morfometría de objetos en escena controlada** | Segundo producto | Semillas, granos, piezas: watershed con marcadores sobre transformada de distancia + cadena morfolométrica existente. Métrica auditable por conteo humano. |
| 3 | **Grietas y fisuras por cresta multi-escala** | Segundo core | Detección sin etiquetas por geometría (anomalía unidimensional). Reutiliza ~90 % del realce de nervaduras (`VeinEnhancer` → `CrackDetector`). |
| 4 | **Grading por color y textura (tabaco/grano/té)** | Nuevo producto sobre el core actual | La apariencia como decisión comercial: `H_ab`, croma, browning ratio, GLCM/LBP, fracción en rango. Es donde el dataset actual ya sirve. |
| 5 | **Digitalización de documentos (flat-field + enderezado)** | Segundo core | Motor de normalización sin OCR: estimación de fondo, cuadrilátero de página, Sauvola. Receta madura pero commodity. |
| 6 | **Otra especie foliar con perfil de cultivo** | Parametrización del core 1 (no core2) | Cítricos/vid/soja: mismo fenómeno físico (necrosis sobre verde), otro calibración. Menor costo, valida la arquitectura de inyección de estrategias. |
| 7 | **Microscopía de bajo costo en campo** | Segundo core | Flat-field por sesión, focus-stacking, mosaico clásico. Dependiente de hardware no controlado. |
| 8 | **Textura periódica (Fourier/Gabor) para superficies** | Capacidad del core actual, no producto | Detección de rotura de período en tela/papel. Se funde en el core 1 como descriptor adicional. |
| 9 | **Identificación de especie por forma de hoja** | **VETADA** | Terreno donde DL ganó por construcción; sin dataset de hoja completa. |
| 10 | **Fotogrametría stereo del dosel** | **Bloqueada por dependencia** | Geometría legítima, pero exige la calibración intrínseca de la candidatura 1. |

## 2. Matriz de consolidación

Viabilidad (A/B/C, la peor nota entre pares tras estrés y auditoría), esfuerzo
estimado y potencial de reutilización del stack actual.

| # | Cand. | Gandalf | Aragorn | Especialistas | Pippin (estrés) | Boromir (auditable) | Frodo (datos) | Viabilidad final | Esfuerzo | Reutilización |
|---|-------|---------|---------|---------------|-----------------|---------------------|---------------|------------------|----------|---------------|
| 1 | Calibración con patrón | **A** | — | Sam A, Merry A−(condición), Gimli B(piezas) | A− | **Sí, día 1** (la referencia la compra el certificado, no la anotación) | A (gold gratis) | **A** | Medio | Alta: io, quality, render, tuning, HTTP, almanaque; habilita mm/ΔE para todas las demás |
| 2 | Contaje/morfometría de objetos | B (→A con 1) | **1.ª (contaje)** | Legolas A(condición), Gimli A, Celebrimbor mínimo esfuerzo | B (B+ con fixture) | **Sí, día 1** (conteo humano; gold-set en días) | A− | **A−** | Medio-bajo | Muy alta: herencia casi total de pipeline, morphometry, render, reporting, layers |
| 3 | Grietas/fisuras | — | 3.ª (con demanda) | Legolas A, Celebrimbor (esfuerzo gráfico alto) | C+/B− (especificidad: nervaduras son crestas) | **No** (anotación píxel cara, doble desacuerdo) | B (manifest caro) | **B−** | Alto | Alta en método (VeinEnhancer), baja en validación y UI |
| 4 | Grading color/textura | — | — | Merry A (si aparece 1), Gimli (descarta como core) | B condicionada / C sola | **No como categoría** (techo = kappa humano); sí como colorimetría | B | **B** | Medio | Total del módulo de descriptores; necesita carta de color para ser defendible |
| 5 | Documentos | — | — | Sam A técnica / B producto | A− técnica, B− producto (commodity) | Parcial (sí geometría, no contenido) | B− (formatos/volumen) | **B−** | Bajo-medio | Alta del preprocesado; no diferencia al proyecto |
| 6 | Otra especie foliar | feature, no core2 | **2.ª (primero esta)** | Legolas B, Pippin B−, Frodo A− | B− (umbrales heredados fallan) | Semi (protocolo golden ya existe; oro nuevo en semanas) | A− | **B+** | Bajo | Prácticamente el 100 % del core; solo perfil de cultivo inyectable |
| 7 | Microscopía | — | — | Sam B | — | — | — | **C** | Alto | Media; dependiente de hardware |
| 8 | Fourier/Gabor textures | B− (se funde) | — | Pippin (menciona textura como no-core) | — | No sin dataset | — | **C como producto** | Medio | Parcial |
| 9 | Especie por forma | **Vetada (C)** | — | — | — | — | — | **V** | — | — |
| 10 | Fotogrametría | C (bloqueada) | — | — | — | — | — | **V por dependencia** | — | — |

## 3. Ranking final (viabilidad × esfuerzo × reutilización)

1. **Calibración con patrón (cand. 1)** — A. El único habilitante: desbloquea mm
   y ΔE para todo lo demás, y es la dirección con la verdad de referencia más
   barata (el certificado del patrón, no anotación humana). Gandalf: *"es el
   único que habilita a los demás"*. Frodo: tabla `calibrations` nueva,
   aditiva, sin tocar el contrato `inspections`. Boromir: auditable día 1, con
   regla anti-circularidad (calibrar en una sesión, evaluar en otra).
2. **Contaje y morfometría de objetos (cand. 2)** — A−. El mejor primer
   *producto*: hereda casi todo el esqueleto (orquestador, morphometry, render,
   reporting, calidad), Celebrimbor lo estima de esfuerzo de diseño mínimo, y
   Boromir lo firma auditable día 1 (conteo humano). Condición de ingreso
   declarada: escena controlada con fixture. Escala física viene de la cand. 1.
3. **Otra especie foliar vía `CropProfile` (cand. 6)** — B+. Menor costo
   absoluto y mayor seguridad de retorno: no es un core2, es la prueba de que la
   inyección de estrategias del core 1 no era decorativa. Aragorn la pone
   primero por riesgo/retorno; Boromir recuerda que el oro nuevo tarda semanas
   con un protocolo que ya está construido.
4. **Grading por color/textura (cand. 4)** — B condicionada. Solo existe sobre
   la cand. 1 (carta en cuadro); sin ella es "una máquina de fabricar disputas
   con clientes" (Pippin). Merry declara el techo: kappa humano, no exactitud.
5. **Grietas (cand. 3)** — B−. Metodológicamente la más elegante (Legolas), pero
   incomprobable día 1 (Boromir), frágil ante especificidad (Pippin: *toda
   cresta es grieta*) y la más cara de representar (Celebrimbor: primitivo de
   línea medida inexistente). Vitrina para después.
6. **Documentos (cand. 5)** — B−. Técnicamente cerrado, comercialmente commodity.
   Como motor de QC de digitalización con métricas trazables tiene hueco; como
   producto, no diferencia.

Descartes: cand. 9 vetada (DL gana ahí), cand. 10 bloqueada por dependencia de
cand. 1, cand. 7 (microscopía) y cand. 8 (Fourier) no justifican core propio.

## 4. Prerrequisitos no negociables (del conclave a la ingeniería)

1. **Extraer el esqueleto de orquestación** de `LeafInspector` (flujo con corte
   en compuerta, trazas, fingerprint) a una base compartida `core/common/`, con
   `NotALeaf` → `OutOfDomain` genérico. Sin esto, "segundo core" = copiar el
   orquestador, y dos orquestadores copiados se contradicen (Aragorn).
2. **`ScaleCalibration` inmutable + banda de error de borde + registro por
   componente** (Gimli): nace antes que cualquier medida en mm; publicar un valor sin incertidumbre queda prohibido por contrato.
3. **Perfil inyectable antes que polimorfismo de esquema** (Aragorn/Frodo):
   primero `CropProfile` con el contrato `InspectionResult` intacto; después,
   si hay dos productos, discriminator `product` y migración. El `payload
   jsonb` ya es el punto de extensión.
4. **El perfil/la calibración entran al `method_fingerprint`** (ADR-016): si
   no, el informe de lote promedia calibraciones distintas mintiendo.
5. **Unidad de muestreo declarada por dirección, nunca por archivo** (Frodo/
   Boromir, lección 210/1680): sesión de captura (calibración), escena/lote de
   objetos (conteo), hoja física/planta (especie), tramo de superficie (grietas).
6. **Ningún umbral se publica calibrado y evaluado en los mismos datos**
   (Boromir): splits por hash de unidad, pre-registrados.

## 5. Rutas recomendadas

### Ruta A — "El Instrumento" (recomendada por el conclave)
1. **core2/calib** (cand. 1): detección de Charuco/carta, homografía, flat-field,
   ΔE00 con incertidumbre. Tabla `calibrations`, gold gratis.
2. Deuda del punto 4.2 sobre el core actual (beneficia al producto publicado).
3. **core2/count** (cand. 2): watershed con marcadores + morfometría por objeto,
   heredando el 80 %+ del stack. Overlay con barra de escala (patrimonio de
   Celebrimbor para todo lo futuro).

### Ruta B — "El Jardín Amplio" (menor riesgo, menor ambición)
1. **CropProfile** (cand. 6) sobre el core 1: una segunda especie valida la
   arquitectura sin duplicar repo ni dataset ajeno.
2. Con el perfil funcionando, extraer `core/common/` y re-evaluar la Ruta A
   desde una arquitectura probada.

### Ruta C — "El Mercado Cercano"
Grading (cand. 4) sobre el dataset propio, pero **exige cand. 1 primero** y un
panel de acuerdos con clientes sobre el techo de kappa. Solo con demanda explícita.

## 6. Votaciones y disidencias

- **Unanimidad habilitante**: 1 va antes que 2, 4 y 10. Nadie propuso una
  dirección de medida física que no dependa de calibración.
- **Disidencia de Aragorn**: prefiere cand. 6 como primer paso (mínimo riesgo,
  prueba de arquitectura) aunque acepte 2 como segundo.
- **Disidencia de Legolas**: si el conclave obliga a un solo tiro de producto,
  grietas (por herencia de método); Boromir lo veta hasta tener oro humano.
- **Autocrítica de Merry**: 7 de 8 descriptores actuales no mueven ninguna
  decisión; cualquier producto nuevo nace con ablación pre-registrada.
- **Advertencia de Pippin**: el modo de fallo del casa es "medida con cara
  buena"; todo core2 nace con compuerta y rechazo honesto o no nace.

## 7. Próximos pasos si se aprueba la Ruta A

1. ADR-024 (Gandalf): "La medición se calibra contra un patrón, no contra la
   buena suerte" — con presupuesto de incertidumbre en el `InspectionResult`.
2. ADR de pre-requisito (Gandalf/Aragorn): extracción del esqueleto vs. copia
   de core2; renombrado de excepciones.
3. Prototipo en `sandbox/` de detección Charuco + homografía (Pippin estresa
   antes de que nadie lo nombre módulo).
4. Sesión de captura de patrones (Frodo: 20–30 tomas, dedup por sha256).
5. Criterios de falsación aprobados por Boromir antes de publicar número alguno
   (RMS reproyección, error sobre patrón conocido, ΔE00 mediano/p95, CV de
   flat-field, MAE de conteo).

---
*Acta firmada por: gandalf, aragorn, sam, legolas, gimli, merry, pippin,
boromir, celebrimbor, frodo. Rama: `ideas/segunda-mision`.*
