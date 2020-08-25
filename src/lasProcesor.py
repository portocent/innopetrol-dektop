import pandas as pd
import numpy as np
import lasio
from PySide2.QtCore import Qt
# import copy
# from PySide2.QtWidgets import *


class Well():
    def __init__(self):
        self.tracks = []


    def loadLas(self, path, name):
        try:

            las = lasio.read(path, autodetect_encoding=True, ignore_header_errors = True)
            self.df = las.df()    # store las file in df variable as pandas dataframe
            self.stats = self.df.describe()
            self.header = las.header
            self.name = name
            self.viewname = name

            return ''
        except Exception as e:
            return str(e.args) 
    
    def addTrack(self,track):
        self.tracks.append(track)
    
    # def remTrack(self,track):
    #     self.tracks.pop()
    # def setSubWindow(self,subWinddow):
    #     self.subWindow=subWinddow
    def popTrack(self):
        self.tracks.pop()


class Track():
    def __init__(self):
        self.lines = []
        self.grids = []
        self.minVal = 99999.25
        self.maxVal = -999.25
     
    def addLine(self,line):
        self.lines.append(line)
    
    def remLine(self,line):
        self.lines.remove(line)

    def addGrid(self,grid):
        self.grids.append(grid)
    
    def remGrid(self,grid):
        self.grids.remove(grid)

    def setMin(self,min):
        if min < self.minVal:
            self.minVal = min

    def setMax(self,max):
        if max > self.maxVal:
            self.maxVal = max


class Line():
    def __init__(self):
        self.name = " "
        self.nameIndex = 0
        self.color = Qt.black
        self.grosor = 1
        self.grosorIndex = 0
        self.estilo = Qt.SolidLine
        self.estiloIndex = 0
        self.log = "Lineal"
        self.logIndex = 0
        self.visible = True
        self.lScale = None
        self.rScale = None
        self.desc = ""


class Grid():
    def __init__(self):
        self.leftLine = " "
        self.leftLineIndex = 0
        self.leftVal = None
        self.rightLine = " "
        self.rightLineIndex = 0
        self.rightVal = None
        self.visible = True
        self.check = False
        self.color = Qt.black
        self.brush = Qt.SolidPattern
        self.brushIndex = 0
        self.description = ""

        


