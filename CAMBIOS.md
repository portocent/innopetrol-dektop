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

### 3.7 Mantenibilidad: que cualquiera pueda arreglarlo mañana

El objetivo fue que quien llegue al proyecto lo entienda y lo pueda cambiar sin miedo, sin perder
rendimiento y sin agregar capas innecesarias. Primero se midió y después se corrigió.

**Herramientas que vigilan solas (en la CI y antes de cada commit):**
- **ruff** (lint y formato) con reglas de complejidad: una función de más de 12 caminos o 60
  instrucciones hace fallar la revisión. Así el código no vuelve a crecer en bloques difíciles de leer.
- **mypy** (tipos): encontró 25 problemas, como valores que podían ser `None` sin control. Ahora no
  queda ninguno.
- **pre-commit:** corre ruff y compila las traducciones antes de cada commit.
- **Cobertura de pruebas:** se muestra en cada ejecución. Pasó del 81% al 85%, porque los tres
  diálogos que no tenían pruebas (topes, survey y exportación) ahora las tienen.
- **Formato:** todo el código se formateó una sola vez, en un commit aparte y marcado en
  `.git-blame-ignore-revs`, para que `git blame` siga mostrando quién escribió cada línea.

**Duplicación eliminada.** Había cinco helpers repetidos en varios archivos (campos numéricos, selector
de zonas, lectura de números con coma, búsqueda de columnas en CSV, dos paletas viridis). Ahora hay una
sola copia de cada uno: `ui/widgets.py`, `model/text_tables.py` y `render/colormaps.py`. Al unificar la
lectura de CSV apareció un error escondido: los surveys alineados con espacios de ancho variable no se
leían. Quedó corregido, con una prueba.

**Funciones largas divididas en pasos con nombre:**
- **Evaluador de la calculadora:** antes era una función con 20 ramas. Ahora tiene una tabla que asocia
  cada tipo de elemento de la expresión con su función.
- **Petrofísica:** `build_formulas` se convirtió en pasos ordenados (Vsh → porosidad → saturación →
  volúmenes → banderas). Agregar un modelo nuevo significa tocar un solo paso.
- **Dibujo del encabezado:** una función por tipo de track.
- **Diálogo de petrofísica (715 líneas):** se separó en tres archivos, y cada pestaña se construye en
  su propio método. La decisión de qué tracks de resultados crear y dónde ubicarlos pasó al modelo
  (`model/petro_layout.py`), con pruebas que no necesitan ventanas.
- **Ventana principal:** el estado de la sesión (proyecto, cambios sin guardar, recientes,
  autoguardado) pasó a `ui/session.py`, que se prueba sin widgets. Los textos de ayuda y "Acerca de"
  pasaron a su propio archivo.

**Cómo se comprobó que nada cambió:**
- **Imágenes:** antes de empezar se guardaron imágenes de referencia del registro (con escalas de
  respaldo, relleno por color, volúmenes y encabezado), las fórmulas petrofísicas y los valores de Sw.
  Después de cada refactor se generaron de nuevo y se compararon: tienen que ser idénticas píxel a
  píxel, y lo fueron.
- **Rendimiento:** el tiempo de redibujo se midió intercalando la versión vieja y la nueva, y quedó
  dentro del ruido (menos de 1%).

**Documentación para quien llega**, en inglés para poder compartirla:
- **`docs/ARCHITECTURE.md`:** las capas, el flujo de datos y las cinco reglas que nunca hay que romper
  (por ejemplo, que los datos se guardan siempre en MD y en las unidades del archivo). También indica
  qué código es crítico para el rendimiento.
- **`CONTRIBUTING.md`:** cómo preparar el entorno, las convenciones, y recetas paso a paso para agregar
  una familia de curvas, un tipo de track, un modelo petrofísico, un idioma o una acción.

**Lo que se dejó como está, a propósito:**
- **Tamaño de la ventana principal:** tiene unas 1150 líneas. Su parte más grande es la declaración de
  acciones, menús y textos, que se lee de corrido; repartirla en más clases agregaría saltos entre
  archivos sin hacerla más clara.
- **Números en las fórmulas:** las constantes petrofísicas (0,083 de Larionov, 21,5 de Arps) se dejaron
  escritas en las fórmulas. Ponerles nombre las haría más difíciles de comparar con la bibliografía.

### 3.8 Confianza en los números

Un ingeniero adopta una herramienta cuando puede confiar en sus resultados. Hasta ahora las pruebas
comparaban las fórmulas con funciones escritas por el mismo programa, y eso es circular: si las dos se
equivocan igual, nadie se entera. Ahora hay cuatro controles independientes.

**1. Archivos reales.**
- *Herramienta:* `tools/realdata.py` descarga una vez el archivo de LAS públicos del Kansas Geological
  Survey (1498 pozos reales) y con cada uno hace todo el recorrido: lo carga, arma el layout, lo dibuja y
  calcula la petrofísica.
- *Resultado de la primera corrida:* fallaron 68 archivos.
  - **`-1.#IO` y `-1.#IND`:** así escriben un valor inválido los programas de Windows; ahora se leen
    como dato faltante.
  - **Neutrón en cuentas API:** en registros viejos de Kansas el neutrón viene en cuentas API, no en
    porosidad. El layout intentaba aplicarle la escala de porosidad y fallaba. Además, la petrofísica lo
    habría tomado como porosidad sin avisar: ahora una curva cuya unidad es de otro tipo no se usa en el
    cálculo.
  - **Unidades y nombres que el programa no reconocía:** `POR`, que en esos archivos es porosidad en
    %, `DEN`, `DECP`, `BARN`… y mnemónicos como GKUT, NEUT, ENPH, RILM o RHOC.
- *Hoy:* los 1498 pasan. Cada problema encontrado quedó como una prueba con un archivo sintético, porque
  los datos de terceros nunca se guardan en el repositorio. Una CI semanal vuelve a correr el corpus.

**2. Casos calculables a mano.** `tests/test_reference_cases.py` tiene resultados que cualquiera puede
verificar con una calculadora:
- Archie clásico: Sw = 0,25;
- Larionov con IGR = 0,5: 0,1997 y 0,33;
- porosidad en los extremos (matriz pura y agua);
- Arps: 0,0395 ohm·m a 200 °F;
- un cuarto de circunferencia en el survey: TVD = R.

Al escribir estas pruebas, un valor que yo había calculado mal a mano (0,2984 en lugar de 0,2221) hizo
fallar la prueba. Es exactamente para eso que sirven.

**3. Planilla de verificación (Excel).** Desde el diálogo de petrofísica, "Planilla de verificación"
guarda un .xlsx con, por cada muestra:
- las entradas en las unidades que usan las ecuaciones, y los parámetros de su zona;
- las mismas ecuaciones escritas como **fórmulas de Excel**;
- el resultado de InnoPetrol y la diferencia entre ambos.

Si un ingeniero cambia un parámetro en la planilla, las fórmulas se recalculan. Se eligió .xlsx y no CSV
porque las fórmulas de un .xlsx se guardan en notación inglesa y Excel las muestra en el idioma del
usuario; un CSV con fórmulas se rompe en un Excel en español (separador `;`, `RAIZ` en vez de `SQRT`).
Las pruebas evalúan esas fórmulas con **pycel**, un motor de planillas que no tiene nada que ver con
InnoPetrol, y coinciden con InnoPetrol hasta 1e-9 en tres configuraciones: Archie; Simandoux con zonas
y gradiente; Indonesia con curva de temperatura.

**4. Ecuaciones a la vista y control de calidad.**
- *Ecuaciones:* Ayuda ▸ Ecuaciones y referencias muestra cada ecuación con sus variables, cuándo vale y
  su referencia (Archie 1942, Simandoux 1963, Poupon y Leveaux 1971, Arps 1953, Taylor y Mason 1972…).
  En el diálogo de petrofísica, un "?" junto a cada método muestra la ecuación elegida, y el árbol del
  pozo indica de dónde sale cada curva calculada.
- *Control de calidad:* después de calcular, el programa informa por zona lo que conviene revisar. Por
  ejemplo, "Sw mayor que 1 en el 42% de la zona B antes de limitar: Rw o m pueden ser demasiado altos".
  Para eso evalúa la misma fórmula sin el recorte final, así que no hay una segunda implementación que
  se pueda desincronizar.

### 3.9 Control de calidad de curvas

**Pozo malo.** Donde el pozo está derrumbado, la herramienta de densidad pierde contacto con la pared
y mide barro, no roca. Interpretar ese tramo daría porosidades altísimas y "petróleo" que no existe. En
el diálogo de petrofísica hay ahora una sección "Pozo malo":
- *Cuándo se marca:* el tramo se marca cuando el caliper supera al trépano en más de lo indicado
  (1 pulgada por defecto) o cuando la corrección de densidad (|DRHO|) es grande (0,15 g/cm³).
- *Qué pasa en ese tramo:* no se usan densidad ni neutrón, así que porosidad, Sw y espesor útil quedan
  vacíos.
- *Cómo se ve:* la bandera `BADHOLE` aparece en gris en el track de banderas.
- *Cuándo está activo:* se activa sola cuando el pozo tiene caliper o DRHO. Los proyectos guardados
  antes no cambian, porque el parámetro nuevo vale "apagado" por defecto.
- *Unidades:* se convierten dentro de la fórmula (un caliper en mm contra un trépano en pulgadas
  funciona).

**Edición de curvas.** Con Pozo ▸ "Editar curva" (o clic derecho sobre la curva en el árbol) se puede:
- corrimiento de profundidad: mover la curva para alinearla con otra corrida o con un núcleo;
- quitar picos;
- mediana móvil;
- suavizado.

El resultado siempre es una **curva nueva con fórmula**, por ejemplo `despike(GR, 7, 3)`: la original no
se toca, se puede deshacer y el proyecto la recalcula. Los filtros quedaron también como funciones de la
calculadora.

*Una lección del dato real.* El primer filtro de picos comparaba cada muestra con la dispersión de
**toda** la curva. En el GR real de ejemplo cambiaba 182 muestras (el 8%), y en la densidad 554 (el
25%): tomaba por picos la variabilidad normal de las capas. Además, en curvas escalonadas la
dispersión robusta (MAD) da 0. Se cambió por el **filtro de Hampel**, el método estándar, que mide la
dispersión dentro de cada ventana con un piso igual al cambio típico entre muestras. Ahora cambia
entre 3 y 8 muestras en curvas reales, y sigue eliminando todos los picos inyectados en las pruebas.

**Normalización entre pozos** (Análisis ▸ "Normalizar una curva entre pozos"). Dos pozos con
herramientas o calibraciones distintas leen distinto la misma arcilla. Para cada pozo se toman los
percentiles bajo y alto (P5 y P95) dentro de una zona común, y se llevan a los del pozo de referencia
con una transformación lineal. Se crea `GRN` en cada pozo, cada una con su propio paso de deshacer. El
histograma multipozo permite ver antes y después. La referencia es Shier (2004), que figura con las
demás en Ayuda ▸ Ecuaciones y referencias.

### 3.10 Interacción: selección de intervalos, intervalos y núcleos

**Seleccionar un intervalo con el mouse.** Arrastrando sobre el registro se marca una banda celeste con
su techo, su base y el **espesor**, que hace las veces de regla. Un clic o Esc la borra. Con clic
derecho sobre el registro aparece el menú "Intervalo seleccionado":
- estadísticas e histograma de ese tramo;
- acercar el zoom a la selección;
- exportarla a LAS o CSV;
- crear una zona, que agrega los topes de techo y base;
- agregarla como intervalo (punzado, ensayo, comentario…).

La selección se dibuja en pantalla en profundidad de visualización (MD, TVD…), pero todo lo que se
guarda se convierte antes a MD, como el resto de los datos.

*Decisión de diseño:* el arrastre normal selecciona y el clic simple sigue eligiendo el track. Los
dos gestos se distinguen por un umbral de 4 píxeles de movimiento, así no hace falta ninguna tecla.

**Cursor sincronizado en la correlación.** Todas las columnas comparten escala y alineación, así que
la misma altura en pantalla es el mismo nivel correlacionado. Al mover el mouse sobre un pozo, la línea
del cursor aparece en todos, y cada uno muestra su propia profundidad. La implementación es simple: el
lienzo avisa la altura y los demás dibujan la línea ahí, sin recalcular profundidades.

**Track de intervalos.** Punzados, ensayos (DST), pérdidas, intervalos coroneados, corridas y
comentarios:
- se guardan en el pozo en MD, con deshacer y en el proyecto;
- se editan en una tabla (Pozo ▸ Intervalos…) o se importan de CSV, con encabezados en inglés o en
  español; el tipo se reconoce por palabras como "punzado", "DST" o "pérdida";
- se dibujan en un track propio con el color y el patrón de su tipo.

**Datos de núcleo** (Pozo ▸ Importar datos de núcleo):
- *Lectura:* un CSV con una columna de profundidad y columnas numéricas, con las unidades entre
  paréntesis.
- *Ubicación:* cada muestra se coloca en la muestra del registro más cercana; si dos caen en la misma,
  se promedian. Así se dibujan como puntos sobre las curvas del registro.
- *Ajustes:* se puede indicar si las profundidades del núcleo están en m o ft y un corrimiento
  núcleo–registro.
- *En el proyecto:* se guardan las profundidades y los valores originales, no la grilla, así se pueden
  volver a ubicar al reabrirlo aunque cambie el archivo LAS.

### 3.11 Escala: proyectos con cientos de pozos

**Tres estados de un pozo.** Antes, pozo del proyecto = ventana abierta: cada pozo creaba siempre una
ventana y cerrarla lo sacaba del proyecto. Con 300 pozos eran 300 ventanas y todo leído en memoria.
Ahora un pozo puede estar:
- *en el proyecto:* sólo su **resumen** (nombre, rango de profundidad, curvas con unidad, ubicación,
  UWI, campo y compañía), sin leer sus datos. Se ve en el árbol en cursiva y gris;
- *cargado:* sus datos están en memoria y las herramientas lo pueden usar;
- *con ventana:* además se ve su registro.

Cerrar la ventana ya no pierde nada (por eso ya no pregunta). Desde el árbol: doble clic abre un pozo
no cargado, "Descargar de memoria" libera sus datos sin perder sus cambios y "Quitar del proyecto…"
lo saca (pide confirmación; el archivo no se toca).

**El proyecto guarda el resumen** de cada pozo (formato versión 2). Al abrirlo se cargan sólo los pozos
que tenían la ventana abierta al guardar; el resto queda listado. Un pozo no cargado se reescribe
**idéntico** al guardar, así nunca se pierde nada de un pozo que no se tocó. Los proyectos de la
versión 1 abren como antes (todos los pozos), y su resumen se lee del encabezado del archivo.

*Medido con 500 LAS reales de Kansas:* abrir el proyecto tarda **0,02 s**. Leer sólo el encabezado de
un LAS (`lasio` con `ignore_data=True`) cuesta 12 ms contra 45 ms de la lectura completa.

*Decisión de diseño:* las herramientas multipozo (correlación, crossplot, histograma, normalización)
trabajan con los pozos **cargados**. Para usar otros, se cargan antes desde el árbol.

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
