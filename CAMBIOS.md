# Cambios: de la versión 2020 a la 2.0

La versión de 2020 ya tenía la idea completa de un visor de registros: pozos en ventanas, tracks con
curvas en escala lineal o log, sombras entre curvas, track de profundidad, zoom a escalas estándar, plantillas
y un árbol con la información del pozo. Lo que fallaba era la base técnica, algo normal cuando uno aprende
Python y Qt al mismo tiempo. Este documento explica qué se cambió y **por qué**, para que sirva también
como material de aprendizaje.

El código anterior sigue en el historial de git (commit `b84d6efc` y anteriores) para comparar.

---

## 1. El proyecto ya no se podía ejecutar

| Problema | Causa | Solución |
|---|---|---|
| No instala | PySide2 5.15 sólo funciona hasta Python 3.10 | Migración a **PySide6** (Qt 6) y Python 3.11+ |
| Dependencias infladas | `requirements.txt` era un `pip freeze` con Sphinx, requests, Babel… | `pyproject.toml` con sólo 4 dependencias reales: pyside6, lasio, numpy, pandas |
| Repositorio de 570 MB | Se había commiteado el virtualenv de Windows (`Lib/`, `Scripts/`) | Se quitó de git (`git rm --cached`) y se agregó `.gitignore`. Los archivos siguen en tu disco |
| Sin iconos en Mac/Linux | Rutas `"statics\\images\\d1.png"` (sólo Windows) y archivos llamados `d1.PNG` | `pathlib` en `innopetrol/resources.py` y nombres de archivo en minúscula |

**Lección:** un entorno virtual no se versiona; se versiona la *descripción* del entorno (`pyproject.toml`
y `uv.lock`) y cada máquina lo recrea con `uv sync`.

---

## 2. Bugs corregidos

### 2.1 Hilos que tocaban la interfaz (crashes aleatorios)

```python
# antes — myGuiClasses.py / subWindowScroll.py
def resizeEvent(self, a0):
    updtDaemon = threading.Thread(target=self.updateTrack)
    updtDaemon.start()

def updateTrack(self):
    time.sleep(1.1)
    self.update()          # ← llamado desde otro hilo
```

Qt **no es thread-safe**: sólo el hilo principal puede tocar widgets. Hacerlo desde otro hilo funciona
"casi siempre" y a veces cierra el programa sin aviso. Además, el truco del `timer` + `DrawLinesFlag`
hacía que las curvas **no se dibujaran** hasta un segundo después de cada cambio.

**Ahora:** no hay hilos. El dibujo es suficientemente rápido (ver §3) como para hacerse en cada `paintEvent`.
Si algún día hace falta trabajo en segundo plano, la herramienta correcta es `QTimer` o `QThread` con señales.

### 2.2 Marcas de profundidad que desaparecían

```python
# antes
i = self.st
while i < self.end:
    if i % 1000 == 0: ...    # dibujar marca
    i += self.step           # 7614.0 + 0.1 + 0.1 + … nunca da exactamente 7700.0
```

Sumar floats acumula error de redondeo (`0.1 + 0.2 != 0.3`). Con paso 0.5 funciona por casualidad
(0.5 es exacto en binario), con 0.1 o 0.2 las marcas se pierden.

**Ahora** (`model/scales.py::depth_ticks`): las marcas se generan como múltiplos enteros del intervalo
(`np.arange(k0, k1) * intervalo`) y el intervalo se elige según cuántos píxeles hay entre marcas, así
también se adaptan al zoom.

### 2.3 Variable de bucle "filtrada"

```python
# antes — dentro del cálculo de sombras
for l in self.track.lines:
    ...
if l.log == "Log":        # ← `l` es la ÚLTIMA línea del bucle anterior, no la del relleno
```

En Python la variable de un `for` sigue existiendo después del bucle. Eso hacía que un relleno contra un
valor fijo usara la escala de otra curva. **Ahora** cada límite del relleno busca explícitamente su curva
(`render/painter.py::_fill_bound`).

### 2.4 La fila equivocada en el editor

```python
# antes — addCurveWindow.py
clickme = QApplication.focusWidget()
index = self.tableWidget.indexAt(clickme.pos())   # ¿qué fila tocó el usuario?
```

Adivinar la fila por el widget con foco falla con el teclado o con clics rápidos. **Ahora** cada control
se conecta con una función que ya conoce a qué fila pertenece (*closure*), y las filas son dinámicas
(agregar/quitar/subir/bajar) en vez de 16 fijas.

### 2.5 Otros

- Sombras: se recorrían 15 filas de 16 (`range(15)`) y `float(lv.text())` fallaba con la celda vacía.
- Árbol: el ítem de un pozo nuevo se elegía por `len(subWindowList())`; al cerrar uno y abrir otro se
  sobrescribía el ítem equivocado. Al cerrar se buscaba por texto del título. **Ahora** cada ítem guarda
  una referencia directa al documento (`Qt.UserRole`).
- `retval == 1024` → `QMessageBox.Yes` (los números mágicos esconden la intención).
- `Ctrl+C` estaba asignado a "Clear Template" y anulaba copiar.
- El track de profundidad estaba fijo en la posición 2 (`if i != 1` en todo el código). Ahora es un track
  más que se puede mover, duplicar o quitar.

---

## 3. Rendimiento

```python
# antes — por cada paintEvent, por cada muestra, por cada curva
while i < self.end:
    x = df.iat[j, l]                      # acceso a pandas celda por celda
    point = QPoint(int(x), int(j*fStep))
    self.lines[l].append(point)
...
reversedR = copy.deepcopy(self.lines[...])  # copia profunda de miles de QPoint
```

**Ahora:**
- La conversión valor→píxel es **vectorizada con numpy**: una operación sobre el arreglo completo en vez
  de un bucle Python por muestra (`model/scales.py::map_values`).
- Sólo se dibujan las muestras **visibles** (`np.searchsorted` sobre la profundidad).
- Si hay más muestras que píxeles, se conserva el mínimo y máximo de cada grupo (no se pierden picos).
- El scroll es propio (no un `QScrollArea` con un widget de miles de píxeles de alto).

---

### 3.1 Segunda ronda: fluidez de la interfaz

La primera versión 2.0 todavía se sentía lenta. Medido en una pantalla Retina, con el pozo ajustado a la
ventana (la vista inicial):

| Acción | Antes | Ahora |
|---|---|---|
| Mover el cursor (Testdata / CIRA3900) | 177 / 441 ms | ~1 ms |
| Desplazarse (mediana) | 24–418 ms | ~2 ms |
| Paso de zoom | 20–24 ms | 13–17 ms |
| Dibujo completo desde cero | 177–441 ms | 6–27 ms |

Tres causas y tres soluciones:

1. **Todo se redibujaba al mover el mouse.** La línea del cursor pedía `update()` de todo el widget, y eso
   recalculaba y trazaba todas las curvas. Ahora el registro se dibuja en **tiles** (franjas de 256 px
   guardadas como imágenes, `ui/tile_cache.py`). Mover el cursor sólo copia imágenes y repinta la franja
   donde está la línea. Al desplazarse se dibujan sólo las franjas nuevas, y con la aplicación inactiva se
   prepara la siguiente por adelantado. Los topes y el cursor se dibujan encima de los tiles, así nunca
   quedan cortados en un borde.
2. **Trazar miles de segmentos en zigzag con antialiasing es carísimo.** Con el pozo completo en pantalla
   hay varias muestras por píxel, y la polilínea va de lado a lado una y otra vez. Ahora, cuando hay más
   de ~1.5 muestras por fila de píxeles, se dibuja la **envolvente**: una línea horizontal [mín, máx] por
   fila física. Cubre los mismos píxeles y cuesta una fracción (`render/painter.py::_envelope`). A esa
   densidad los guiones no se distinguen, así que las curvas no continuas se muestran semitransparentes.
3. **Crear un objeto `QPointF` por muestra desde Python.** Ahora el `QPolygonF` se reserva una vez y
   numpy escribe directamente en su memoria (`_qpolygon`), sin bucles Python.

El crossplot dibuja los puntos agrupados en 32 niveles de color (una llamada por nivel en lugar de una por
punto). Una prueba automática verifica que mover el cursor no vuelva a dibujar tiles.

### 3.2 Windows, Linux y equipos de menor potencia

**Compatibilidad**
- *Codificación de texto.* Muchos LAS de compañías latinoamericanas vienen en Windows-1252
  ("Compañía") y otros en UTF-8. Sin la librería `chardet`, lasio probaba Windows-1252 primero y un
  archivo UTF-8 se leía como "CompaÃ±Ã­a". Ahora se prueba UTF-8, luego Windows-1252 y luego Latin-1
  (`model/well.py::detect_encoding`).
- *Escritura.* En Windows, Python abre los archivos en cp1252 por defecto: exportar un LAS con "φ" en
  una descripción fallaba. Ahora siempre se escribe en UTF-8, y los CSV llevan BOM para que Excel en
  Windows muestre bien los acentos.
- *Extensiones.* `POZO.LAS` o `PROYECTO.IPPROJ` se reconocen sin importar mayúsculas (Windows no las distingue).
- *Sin consola.* El lanzador se declara como `gui-scripts`: en Windows no aparece una ventana negra.
- *Escalado de pantalla.* Se verificó que no aparezcan costuras entre tiles con escalas de 125 %, 150 % y 175 %.

**Equipos lentos.** Con el CPU limitado a ~4 veces más lento (núcleos de eficiencia en modo de baja
prioridad), cursor y desplazamiento seguían fluidos, pero redimensionar la ventana (85 ms), arrastrar el
borde de un track (77 ms) y el zoom (37 ms) se sentían trabados. Ahora el canvas **mide su propio costo de
dibujo**. Si una pantalla completa cuesta más de 30 ms, durante el gesto muestra los tiles anteriores
estirados (zoom, redimensionar) o una línea guía (arrastre), con 1–6 ms por cuadro, y dibuja con calidad
completa 160 ms después de que el gesto termina. En máquinas rápidas no cambia nada.

**Instalación más liviana.** `pyside6-essentials` en lugar de `pyside6` (350 MB en lugar de 1,2 GB en macOS;
sólo se usan QtCore, QtGui y QtWidgets) y sin pandas, que sólo se usaba para escribir el CSV.

**Ejecutables.** `packaging/build.py` genera con PyInstaller un ejecutable que no necesita Python
(~85 MB). GitHub Actions corre las pruebas en Windows, Linux y macOS y construye el ejecutable de cada
uno. Además lo arranca con `--smoke-test`, que abre un LAS, dibuja y sale con código 0 si todo funcionó.

### 3.3 Código en inglés e interfaz en varios idiomas

Para poder compartir el proyecto, todo el código (comentarios, docstrings, mensajes) quedó en inglés y la
interfaz se puede usar en inglés o español, cambiando el idioma en vivo desde **Ver ▸ Language / Idioma**.

**Cómo funciona (gettext, el estándar de Python).** Los textos se escriben en inglés en el código y se
marcan con `_()`:

```python
QMessageBox.warning(self, _("Export"), _("Could not export: {error}").format(error=e))
```

`innopetrol/i18n.py` busca la traducción en el catálogo del idioma activo
(`innopetrol/locale/es/LC_MESSAGES/innopetrol.po`, compilado a `.mo`). La búsqueda se hace en cada llamada,
por eso el cambio de idioma afecta a todo lo que se dibuja después. Los diálogos propios de Qt
(Aceptar/Cancelar, selector de archivos) se traducen con los catálogos que ya trae PySide6.

**Reglas que conviene saber:**
- *Placeholders con nombre*, nunca f-strings dentro de `_()`: el traductor necesita poder mover
  `{well}` de lugar ("Curvas no encontradas en {well}") y una f-string ya llega armada.
- *Frases completas*: `_("left")` + `_("bound")` no se traduce bien; `_("Left bound")` sí.
- *`_` no puede usarse como variable descartable* (`for _ in range(4)`, `path, _ = QFileDialog...`).
  Es una costumbre muy común en Python, pero si `_` es la función de traducción, esa variable la tapa y
  el programa falla al traducir. Se renombraron 30 casos y hay una prueba que revisa el código con `ast`
  para que no vuelva a pasar.
- *Constantes a nivel de módulo* (nombres de familias de curvas, métodos de Vsh) se marcan con `N_()`
  y se traducen recién al mostrarse, porque cuando se carga el módulo todavía no se sabe el idioma.
- *Lo que es dato del usuario no se traduce*: títulos de tracks ya creados, nombres de topes,
  descripciones de curvas calculadas guardadas en proyectos.

**Un error que apareció gracias a la traducción.** El diálogo de petrofísica buscaba los tracks por su
título ("Densidad - Neutrón", "Resultados petrofísicos"). Con la interfaz en inglés esos títulos son otros
y el programa habría duplicado los tracks de resultados. Ahora los busca por las curvas que contienen.

**Pruebas.** Fallan si algún texto del código no tiene traducción, si una traducción pierde un
`{placeholder}`, si el `.mo` quedó desactualizado respecto del `.po`, o si `_` se usa como variable.
También verifican el cambio de idioma en vivo y que la elección se recuerde al reiniciar.

## 4. Arquitectura

```
antes                                   ahora
─────────────────────────────           ───────────────────────────────────────────
main.py         ventana + árbol +       model/   datos y cálculos sin Qt (testeables)
                plantillas + pickle     render/  dibujo con QPainter (pantalla = PDF = PNG)
subWindowScroll zoom ×6 funciones       ui/      ventanas y diálogos
myGuiClasses    dibujo + datos +
                cálculo de sombras
lasProcesor     clases con enums Qt
GUI.py          generado (sin .ui)
subWindow.py    copia vieja duplicada
```

Ideas clave:

- **Separar modelo y vista.** `Well`, `TrackSpec`, `CurveStyle`, `FillSpec` son `@dataclass` sin Qt.
  Se pueden probar con `pytest` sin abrir ventanas y reutilizar (exportar, correlacionar, scripts).
- **Una sola función de dibujo** (`render/painter.py`) sirve para la pantalla, el PNG y el PDF. Antes,
  exportar habría significado reescribir todo el dibujo.
- **Señales Qt** (`WellDocument.layoutChanged`, `cursorMoved`…): cuando cambia el pozo, cada vista se
  actualiza sola. Así la tabla de datos sigue al cursor y la correlación ve los topes nuevos.
- **No repetir código:** `changeZoom1x`…`changeZoom100x` (6 copias) → `set_scale(n)`.

---

## 5. Plantillas: de pickle a JSON

`pickle` guardaba objetos Python con enums de Qt adentro. Problemas: **ejecuta código** al cargar un
archivo (un `.temp` ajeno puede ser malicioso), no se puede leer ni editar, y se rompe al renombrar una clase.

Ahora las plantillas son JSON legibles (`*.ipt.json`), con versión de formato, y guardan la **familia** de
cada curva: una plantilla hecha con `SGR`/`LLD`/`TNPH` funciona en un pozo que tiene `GR`/`ILD`/`NPHI`.

---

## 6. Lo que se construyó (lo que el proyecto buscaba)

- Escala vertical **física** (1:500 significa 1 m de pozo = 2 mm en pantalla/papel), no `400*largo/escala`.
- Navegación con rueda, zoom en el cursor, lectura de valores, tabla de datos.
- Gestión de tracks: agregar/quitar/mover/renombrar, ancho arrastrando el borde.
- Exportar a PDF paginado, PNG, LAS y CSV.
- Plantilla Triple Combo automática y reconocimiento de mnemónicos.
- Topes de formación, petrofísica básica (Vsh, φ, Sw Archie, net pay), resumen por zonas.
- Calculadora de curvas **segura**: analiza la expresión con `ast` y sólo permite operaciones
  aritméticas y funciones de una lista blanca; nunca usa `eval()`.
- Crossplots (libre, neutrón-densidad, Pickett), estadísticas con histograma.
- Correlación multi-pozo aplanada en un tope.
- Proyectos que guardan todo, con las curvas calculadas como fórmulas reproducibles.

## 7. Pruebas automáticas

El proyecto original no tenía pruebas (la carpeta `tests/` tenía tutoriales). Ahora hay 54 pruebas
(`uv run pytest`, ~4 s) que cubren carga de los LAS de ejemplo, escalas, plantillas entre pozos, fórmulas
petrofísicas contra valores conocidos, intentos de inyección en la calculadora, exportación y la interfaz
en modo offscreen (incluido el bug del árbol al cerrar pozos).

## 8. Limitaciones conocidas

- Las líneas de litología del crossplot neutrón-densidad son aproximaciones lineales, no las cartas
  de cada compañía de servicio.
- No hay profundidad vertical verdadera (TVD) ni datos de desviación; todo es profundidad medida.
- Las plantillas `.temp` de la versión 2020 (pickle) no se importan.
