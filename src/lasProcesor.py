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
    
    def addTrack(self,track):
        self.tracks.append(track)
    
    def remTrack(self,track):
        self.tracks.pop()
    # def setSubWindow(self,subWinddow):
    #     self.subWindow=subWinddow


class Track():
    def __init__(self):
        self.lines = []
        self.grids = []
     
    def addLine(self,line):
        self.lines.append(line)
    
    def remLine(self,line):
        self.lines.remove(line)

    def addGrid(self,grid):
        self.grids.append(grid)
    
    def remGrid(self,grid):
        self.grids.remove(grid)


class Line():
    def __init__(self):
        self.name = " "
        self.color = Qt.black
        self.grosor = 1
        self.estilo = Qt.SolidLine
        self.log = "Lineal"
        self.visible = True
        self.lScale = 0
        self.rScale = 1000
        self.desc = ""

class Shade():
    def __init__(self):
        self.leftLine = " "
        self.leftVal = 0
        self.rightLine = " "
        self.rightVal = 0
        self.visible = True
        self.color = Qt.black
        self.brush = Qt.SolidPattern

        


