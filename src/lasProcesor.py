import pandas as pd
import numpy as np
import lasio
# import copy
# from PySide2.QtWidgets import *


class Well():
    def __init__(self):
        self.tracks = []

    def loadLas(self, path, name):
        try:

            las = lasio.read(path, autodetect_encoding=True, ignore_header_errors = True)
            self.df = las.df()    # store las file in df variable as pandas dataframe
            self.name = name
            self.viewname = name
            return ''
        except Exception as e:
            return str(e.args) 
    # def setSubWindow(self,subWinddow):
    #     self.subWindow=subWinddow


class Track():
    def __init__(self):
        self.lines = pd.DataFrame()
        self.grids = pd.DataFrame()
        self.header = pd.DataFrame()

