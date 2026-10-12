# InnoPetrol — Visor de Pozos

Visor de registros de pozo (archivos **LAS 2.0**) para ingenieros de petróleo, escrito en Python con PySide6.

*[English](README.md) · Español*

![Registro con resultados petrofísicos](docs/captura-registro.png)

## Funciones

**Visualización**
- Varios pozos abiertos a la vez (ventanas o pestañas), árbol lateral con cabecera, curvas y topes.
- Plantilla automática **Triple Combo** al abrir un LAS: correlación (GR/SP/CALI con relleno arena-arcilla), profundidad, resistividades (log), densidad-neutrón con cruce de gas, sónico/PEF, petrofísica y permeabilidad.
- Reconoce unos 125 mnemónicos (17 familias de curvas) de distintas compañías de servicio (GR/SGR/GRC, NPHI/TNPH, LLD/ILD/AT90…) y propone escala, color y tipo lineal/log.
- Escalas verticales reales (1:200, 1:500, 1:1000…) o ajuste a la ventana.
- Tracks configurables: curvas, escala lineal o logarítmica, color, grosor, estilo, rellenos entre curvas o contra un valor fijo con 10 patrones.
- Agregar, quitar, mover, renombrar y cambiar el ancho de tracks (arrastrando el borde).
- **Unidades a demanda**: Ver ▸ Sistema de unidades (como en el archivo / petrolero / métrico) o por curva desde
  el árbol del pozo (g/cm³ ↔ kg/m³, µs/ft ↔ µs/m, fracción ↔ %, °F ↔ °C, psi ↔ kPa, in ↔ mm). Los datos guardados
  nunca cambian y los cálculos convierten sus entradas, así que el resultado no depende de cómo vino cada archivo.
- Interfaz en **español o inglés**, se cambia en vivo desde **Ver ▸ Language / Idioma** (al primer arranque usa el idioma del sistema).

**Navegación** (en Mac, ⌘ en lugar de Ctrl)
- Zoom: botones **−** / **+** junto a «Escala» (o Ctrl − / Ctrl +) saltan entre escalas estándar; «Ajustar» muestra el pozo completo (Ctrl 0); en el campo «Escala» se puede escribir una exacta, p. ej. `1:300`.
- Zoom continuo en el cursor: Ctrl + rueda o pellizco en el trackpad.
- Rueda: desplazar · Shift + rueda: horizontal · RePág/AvPág, Inicio/Fin.
- Cursor con lectura de profundidad, zona y valor de todas las curvas en la barra de estado.
- Tabla de datos sincronizada con el cursor.

**Interpretación**
- Topes de formación: agregar con clic derecho, editar en tabla, importar/exportar CSV (columnas en español o inglés).
- Petrofísica: Vsh (lineal, Larionov), porosidad densidad y neutrón-densidad, porosidad efectiva, Sw por **Archie, Simandoux o Indonesia**, banderas de reservorio y pago.
- **Parámetros por zona** (entre topes): GR limpio/arcilla, densidad de matriz y fluido, Rw, a, m, n, Rsh y cortes.
- **Rw a temperatura de formación** (Arps) con gradiente geotérmico sobre TVD o con una curva de temperatura.
- **Elección gráfica de parámetros**: GR limpio/arcilla arrastrando líneas sobre el histograma y Rw arrastrando la línea de agua en el gráfico de Pickett (o ajustándola a los puntos limpios más húmedos), para todo el pozo o una zona.
- **Deshacer / rehacer** (Ctrl+Z / Ctrl+Shift+Z) en cambios de tracks, plantillas, topes, survey, curvas y petrofísica, con un historial por pozo.
- Resumen por zonas: espesor bruto, neto de reservorio, neto de pago, N/G, φ, Sw y Vsh promedio (copiar a Excel o CSV).
- Calculadora de curvas con expresiones (`(2.65 - RHOB) / 1.65`, `where(GR > 75, 1, 0)`) evaluadas de forma segura.
- Estadísticas e histograma por curva y zona (P10/P50/P90).
- Crossplots con color por una tercera curva: libre, **neutrón-densidad** con líneas de litología y **Pickett** con líneas de Sw.
- **Correlación multi-pozo** lado a lado, en profundidad o **aplanada en un tope**, con líneas que unen topes del mismo nombre.

**Archivos**
- Plantillas en JSON (`.ipt.json`): se aplican a otros pozos aunque usen otros mnemónicos. Plantilla por defecto configurable.
- Proyectos (`.ipproj`): pozos, layouts, topes, parámetros y curvas calculadas (guardadas como fórmulas).
- Exportar el registro a **PDF paginado** o **PNG** a escala, **LAS** (con curvas calculadas) y **CSV**.

| Correlación aplanada en un tope | Crossplot neutrón-densidad |
|---|---|
| ![Correlación](docs/captura-correlacion.png) | ![Crossplot](docs/captura-crossplot.png) |

## Instalación y uso

Funciona en **Windows 10/11**, **Linux** (distribuciones con glibc 2.28 o más nueva: Ubuntu 20.04+,
Debian 11+, RHEL/Rocky 8+) y **macOS 12+**. No necesita tarjeta gráfica dedicada.

### Ejecutable (sin instalar Python)

En la pestaña **Actions** del repositorio en GitHub, cada versión genera un `.zip` por sistema
(`InnoPetrol-Windows`, `InnoPetrol-Linux`, `InnoPetrol-macOS`). Descomprimir y ejecutar
`InnoPetrol.exe` (Windows), `InnoPetrol/InnoPetrol` (Linux) o `InnoPetrol.app` (macOS).

En Windows, la primera vez SmartScreen puede advertir que el programa no está firmado:
«Más información» ▸ «Ejecutar de todas formas».

Para generarlo a mano en la máquina de destino:

```bash
uv sync --group build
uv run --group build python packaging/build.py     # resultado en dist/
```

### Desde el código fuente

Requiere [uv](https://docs.astral.sh/uv/), que instala Python y las dependencias automáticamente:

```bash
uv sync
uv run innopetrol                          # abre la aplicación
uv run innopetrol samples/Testdata.las     # abre directamente uno o más LAS
```

En Windows (PowerShell) se instala uv con `irm https://astral.sh/uv/install.ps1 | iex`.

En Linux, Qt necesita algunas librerías del sistema que suelen estar instaladas en escritorios;
en una instalación mínima de Ubuntu/Debian:

```bash
sudo apt install libegl1 libgl1 libxkbcommon0 libxkbcommon-x11-0 libxcb-cursor0 libfontconfig1 libdbus-1-3
```

También se pueden arrastrar archivos `.las` o `.ipproj` a la ventana. En `samples/` hay cuatro pozos de ejemplo.

### Equipos de menor potencia

La aplicación mide cuánto tarda en dibujar en cada máquina. Si un dibujo completo es lento, durante el
zoom, el cambio de tamaño de la ventana o el arrastre del borde de un track muestra una vista previa
liviana y dibuja con calidad completa al terminar el gesto. Mover el cursor y desplazarse reutilizan
lo ya dibujado, así que se mantienen fluidos también en equipos modestos.

## Pruebas

```bash
uv run pytest
```

Las pruebas de interfaz corren sin abrir ventanas (modo *offscreen*). GitHub Actions las ejecuta en
Windows, Linux y macOS en cada cambio, y además construye y prueba el ejecutable de cada sistema
(`.github/workflows/ci.yml`).

## Estructura

```
innopetrol/
  model/     datos y cálculos puros (sin Qt): pozo, escalas, layout, plantillas, mnemónicos,
             calculadora, petrofísica, topes, proyecto
  render/    dibujo con QPainter, compartido por la pantalla y la exportación PDF/PNG
  ui/        ventanas y diálogos PySide6
  locale/    traducciones de la interfaz (gettext: .po editable + .mo compilado)
tests/       pruebas automáticas (pytest + pytest-qt)
packaging/   construcción del ejecutable con PyInstaller
samples/     archivos LAS de ejemplo
```

Para agregar un idioma, ver la sección *Adding a language* del [README en inglés](README.md#adding-a-language).

Para la historia del proyecto y qué cambió respecto de la versión de 2020, ver [CAMBIOS.md](CAMBIOS.md).

## Licencia

InnoPetrol es software libre: se puede redistribuir y modificar bajo los términos de la
**Licencia Pública General Reducida de GNU (LGPL), versión 3 o posterior** (ver
[COPYING.LESSER](COPYING.LESSER) y [COPYING](COPYING)). Se distribuye SIN NINGUNA GARANTÍA.

Componentes de terceros: Qt for Python / PySide6 (LGPLv3), lasio (MIT), NumPy (BSD).
