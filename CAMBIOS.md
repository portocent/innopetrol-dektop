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
    self.update()  # ← llamado desde otro hilo
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
    if i % 1000 == 0:
        ...  # dibujar marca
    i += self.step  # 7614.0 + 0.1 + 0.1 + … nunca da exactamente 7700.0
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
index = self.tableWidget.indexAt(clickme.pos())  # ¿qué fila tocó el usuario?
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
    x = df.iat[j, l]  # acceso a pandas celda por celda
    point = QPoint(int(x), int(j * fStep))
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

### 3.4 Interpretación corregible: deshacer, parámetros por zona y modelos de arenas arcillosas

**Deshacer / rehacer (Edición ▸ Deshacer, Ctrl+Z).** Cada pozo tiene su propio historial y el menú dice
qué se va a deshacer ("Deshacer: Quitar track «Resistividad»").

*Cómo está hecho.* La forma clásica es escribir un "comando" por cada operación, con su `undo()` y
`redo()`. Pero en este programa hay muchos lugares que modifican el diseño (editor de tracks, arrastrar el
borde, renombrar, plantillas, petrofísica…), y bastaba con olvidar uno para que esa acción no se pudiera
deshacer. Por eso se usa otra técnica: **instantáneas**. Cada vez que el documento avisa que cambió
(`layoutChanged`, `curvesChanged`, `topsChanged`), se compara el contenido nuevo con el anterior y, si
es distinto, se guarda el par antes/después en un `QUndoStack`. Así cualquier cambio queda registrado,
incluso los que se hagan en código futuro.

*¿No ocupa mucha memoria?* No: el diseño y los topes son unos pocos KB, y las curvas **no se copian**.
Se guardan referencias a los mismos objetos `Curve`, que nunca se modifican después de crearse. Deshacer
un cálculo petrofísico recupera exactamente los mismos arreglos de numpy, sin copiarlos.

*Lo que no se deshace.* Cambiar MD/TVD o las unidades es una forma de *ver* los datos, no un cambio en
ellos (igual que el zoom). Si se deshace algo después de pasar a unidades métricas, el diseño recuperado
se convierte a las unidades actuales, porque cada escala guarda en qué unidad está escrita.

*Una acción, un paso.* Calcular petrofísica agrega curvas y además crea o actualiza dos tracks. Con
`with doc.undo_step(_("Compute petrophysics")):` todo eso queda en un solo paso de deshacer.

**Parámetros por zona.** Los parámetros cambian de una formación a otra: el GR de la arcilla, la densidad
de la matriz, Rw, el exponente m… En la pestaña *Parámetros por zona* hay una tabla con una fila por zona
(entre topes). Una celda vacía usa el valor general. En la fórmula guardada, un parámetro con valores por
zona se escribe en función de la profundidad, para que se pueda leer y recalcular:

```
where((DEPTH >= 8040), 0.02, 0.05)      # Rw = 0.02 desde el tope B, 0.05 en el resto
```

Por eso la calculadora ahora conoce `DEPTH` (profundidad medida) y `TVD` de cada muestra. El resumen de
zonas también usa los cortes propios de cada zona si se definieron.

**Modelos de arenas arcillosas.** Archie supone que sólo el agua conduce la electricidad. En arenas con
arcilla, la arcilla también conduce: la resistividad baja y Archie "ve" más agua de la que hay, por lo que
una arena con petróleo puede descartarse por error. Se agregaron:
- **Simandoux** (forma modificada, n = 2): Sw = a·Rw/(2·φ^m) · [√((Vsh/Rsh)² + 4·φ^m/(a·Rw·Rt)) − Vsh/Rsh].
- **Indonesia** (Poupon y Leveaux, 1971), pensado para agua de formación dulce:
  1/√Rt = [Vsh^(1−Vsh/2)/√Rsh + √(φ^m/(a·Rw))] · Sw^(n/2).

Las dos fórmulas dan exactamente Archie cuando Vsh = 0, y las pruebas lo verifican. Rsh, la resistividad
de la arcilla, se propone la primera vez como la mediana de Rt donde el GR es más alto.

**Rw a temperatura de formación (Arps).** Rw se mide en el laboratorio a una temperatura, pero en el
pozo el agua está más caliente y conduce mejor: Rw₂ = Rw₁·(T₁ + 21,5)/(T₂ + 21,5) en °C (6,77 en °F). La
temperatura sale de un gradiente geotérmico aplicado a la **TVD**, no a la MD (en un pozo desviado la
diferencia es grande), o de una curva de temperatura convertida a la unidad elegida. Se generan las
curvas `TFORM` (temperatura) y `RWT` (Rw corregida). No se llama `TEMP` para no pisar una curva de
temperatura que venga en el archivo.

**Elegir parámetros sobre los gráficos.** Escribir parámetros a mano es la principal fuente de errores:
- *GR limpio y de arcilla*: en el histograma se arrastran dos líneas (verde y marrón). Un clic mueve la
  línea más cercana; P5/P95 las pone en los percentiles 5 y 95.
- *Rw en el gráfico de Pickett*: en escala log-log, cada Sw de Archie es una recta de pendiente −1/m. Se
  arrastra la recta de agua (Sw = 1) sobre los puntos de menor resistividad. "Ajustar a los puntos más
  húmedos" la ubica sola, con el percentil 5 de Rw aparente = Rt·φ^m/a. Los puntos arcillosos
  (Vsh > 0,35) se ven en gris claro y no se usan en el ajuste, porque la arcilla también tiene
  resistividad baja y tiraría la recta hacia abajo. Este error apareció al revisar el gráfico con datos
  reales: el primer ajuste daba Rw = 0,012 en lugar de 0,044.
- Desde la pestaña de zonas, las dos herramientas trabajan sólo con los datos de la zona seleccionada y
  escriben el resultado en su fila.

### 3.5 Presentación profesional

**Escalas de respaldo (wrap-around).** En los registros impresos, cuando el GR supera el borde derecho de
su escala (por ejemplo 150 API), la curva no se corta: se vuelve a dibujar desde el borde izquierdo, a
trazos, como si la escala siguiera en 150–300. Se activa por curva con la columna *Respaldo* del editor
de tracks, y el encabezado muestra la escala de respaldo. El desplazamiento se hace en píxeles (un ancho
de track), así que en escala logarítmica funciona igual: 0,2–2000 ohm·m continúa en 2000–200 000.

**Rellenos con color por valor.** Un relleno puede tomar, en cada profundidad, el color que corresponde al
valor de su curva: amarillo en arena limpia y marrón en arcilla, con la paleta de rayos gamma. El color sale
de la posición de la curva en su escala, así que respeta escalas invertidas y logarítmicas.

*Cómo se dibuja rápido.* En vez de un rectángulo por muestra (podrían ser miles), se toma una muestra por
fila de píxeles, y las filas consecutivas del mismo color se unen en un solo polígono escalonado. El costo
depende de la altura en pantalla, no de la cantidad de datos.

*Un problema que apareció en el PDF.* La primera versión dibujaba una línea por fila. En pantalla se veía
bien, pero los visores de PDF suavizan los bordes de cada línea por separado y aparecían rayas finas.
Agrupar las filas en polígonos eliminó los bordes internos.

**Track de volúmenes (litología / fluidos).** Es el resultado típico de una interpretación: de izquierda a
derecha, arcilla (VSH), matriz (VMAT), hidrocarburo (BVH) y agua (BVW), que suman 1. La petrofísica ahora
calcula esas curvas (VMAT = 1 − VSH − φe, BVW = φe·Sw, BVH = φe·(1 − Sw)) y agrega el track. También se
agrega desde el menú contextual. Si una curva se muestra en %, el track la convierte a fracción.

*Un error evitado.* Al principio VMAT, BVW y BVH compartían una "familia" de curvas. Al aplicar una
plantilla a un pozo sin BVH, el programa habría puesto BVW en su lugar, y el agua se habría dibujado como
hidrocarburo. Ahora cada una tiene su propia familia, y una prueba lo verifica.

**Encabezado de registro.** La primera página del PDF (y el PNG) empieza con un bloque con el nombre del
pozo y los datos del archivo: compañía, campo, ubicación, UWI, compañía de servicio y fecha. Además
incluye cómo se dibujó el registro: referencia de profundidad, intervalo, escala, elevación, survey,
archivo y fecha de impresión. Las páginas siguientes llevan sólo la línea de título. Se puede desactivar
en el diálogo de exportación.

**Picar topes en la correlación.** Se escribe o elige el nombre del tope, se activa *Picar topes* y se hace
clic en cada pozo:
- un segundo clic en el mismo pozo mueve el tope;
- el tope toma el mismo color que ya tiene en los otros pozos, así las líneas de correlación se leen bien;
- el clic derecho permite poner el tope, crear uno nuevo o quitar el que está cerca;
- Ctrl+Z deshace el último cambio hecho desde esa ventana.

La profundidad del clic se convierte a MD antes de guardarla, así que funciona igual con la correlación en
TVD/TVDSS o aplanada en otro tope. Los topes se guardan en el pozo original (con su historial de
deshacer), y su ventana se actualiza al instante.

### 3.6 Despliegue y escala

**Instaladores.** Hasta ahora la CI generaba un `.zip` por sistema. Ahora genera lo que cada usuario espera:
- **Windows:** un instalador hecho con Inno Setup. Instala por usuario, sin pedir permisos de
  administrador, agrega accesos directos y asocia los archivos `.ipproj` para que se abran con doble clic.
- **macOS:** una imagen `.dmg` con el acceso a Aplicaciones para arrastrar la app.
- **Linux:** un `.tar.gz` con `install.sh`, que agrega el programa al menú de aplicaciones. Se usa tar
  en vez de zip porque conserva los permisos de ejecución.

La CI no se conforma con generarlos: instala el `.exe` en modo silencioso, descomprime el tar y monta el
DMG, y en cada caso el programa instalado tiene que arrancar y dibujar un pozo.

La **firma de código** requiere certificados pagos (Apple Developer, 99 USD por año; un certificado de
Windows o Azure Trusted Signing). `docs/DISTRIBUTION.md` explica las opciones y los pasos.

**Autoguardado y recuperación.** Si hay cambios sin guardar, cada 2 minutos se guarda una copia del
proyecto en la carpeta de datos del programa. Al cerrar normalmente se borra; si al arrancar sigue ahí,
el programa no se cerró bien y ofrece recuperarla. La copia se escribe primero en un archivo temporal y
después se renombra (`os.replace`), así un corte de luz a mitad de la escritura nunca deja un archivo
roto.

**Errores sin cerrar el programa.** Un error no previsto antes cerraba la aplicación. Ahora `sys.excepthook`
lo intercepta:
- escribe el traceback completo en `innopetrol.log` (archivo rotativo de 1 MB × 3);
- guarda los pozos abiertos por las dudas;
- muestra un diálogo con los detalles.

Si falla algo mientras informa el error, sólo se registra, para no entrar en un bucle.

**Alias de mnemónicos editables.** Cada compañía nombra sus curvas a su manera. En *Plantilla ▸ Alias de
mnemónicos…* se agregan nombres a cada familia, y se exportan e importan en JSON para que todo el equipo
use los mismos. Un alias del usuario tiene prioridad, así que también sirve para corregir uno incorporado:
por ejemplo, si en tu compañía "RT" es una resistividad media.

**Mapa base.** La ubicación sale del encabezado, aceptando X/Y o latitud/longitud con muchas grafías y
también en grados-minutos-segundos (`58° 26' 29.9" N`), o se ingresa en el diálogo de survey. Un 0/0 se
descarta, porque muchos archivos lo traen como "sin dato". Con el survey se dibuja la trayectoria, y
para latitud/longitud la longitud se multiplica por cos(latitud) para que un kilómetro mida lo mismo en
las dos direcciones. Haciendo clic en los pozos en orden se arma una sección, y "Correlacionar
seleccionados" abre la correlación con ese orden.

**Crossplots e histogramas multipozo.** Al tildar otros pozos:
- se busca la curva equivalente por nombre o por familia (SGR en un pozo, GR en otro);
- se convierte a las unidades del pozo activo (densidad en kg/m³ y en g/cm³ quedan juntas);
- las zonas se eligen por nombre de tope, y cada pozo usa sus propios topes;
- el crossplot pasa a colorear por pozo, y el histograma dibuja un contorno por pozo con P10/P50/P90 de
  cada uno.

Es la herramienta para ver si hace falta normalizar el GR antes de calcular Vsh en varios pozos.

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
- Simandoux está resuelto para n = 2 (la forma cerrada publicada); con otro n el programa usa n = 2 en ese modelo.
- El gradiente geotérmico se aplica sobre la TVD medida desde la referencia del pozo (KB/DF), no desde el
  terreno; la diferencia es de pocos grados en pozos con mesa rotaria alta.
- Las plantillas `.temp` de la versión 2020 (pickle) no se importan.
