from cx_Freeze import setup, Executable



setup(name="Visualizador de Pozos",
version="1.0",
description="Visualizador de pozos petroleros Copyrigth 2020",
author="InnoPetrol S.A.",
author_email="portocent@gmail.com",
license="EOM",
executables = [Executable(script = "main.py", base = "Win32GUI")])