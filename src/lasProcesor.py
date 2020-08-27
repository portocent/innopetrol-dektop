# import pandas as pd
# import numpy as np
import lasio
from PySide2.QtCore import Qt



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
            self.curves = las.curves

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
            self.getLandR()

    def setMax(self,max):
        if max > self.maxVal:
            self.maxVal = max
            self.getLandR()

    def getLandR(self):
        if self.minVal > 0 :
            l = 1
            r = 10
            if self.minVal <= 1:
                l = 0.1
            elif self.minVal <= 10:
                l = 1
            elif self.minVal <= 100:
                l = 10
            elif self.minVal <= 1000:
                l = 100
            elif self.minVal <= 10000:
                l = 1000
            else:
                l = 10000


            if self.maxVal <= 1:
                r = 1
            elif self.maxVal <= 10:
                r = 10
            elif self.maxVal <= 100:
                r = 100
            elif self.maxVal <= 1000:
                r = 1000
            elif self.maxVal <= 10000:
                r = 10000
            elif self.maxVal <= 100000:
                r = 100000
            else:
                r = 1000000
            self.lLog = l
            self.rLog = r
            lsize = len(str(int(l)))
            rsize = len(str(int(r)))
            self.cycles = rsize - lsize
            if l<1:
                self.cycles += 1
        else:
            self.lLine = self.minVal
            self.rLine = self.maxVal


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
        self.visibleCheck = False
        self.lScale = None
        self.rScale = None
        self.desc = ""

    def setlScale(self,l):
        if l <= 1:
            self.lScale = 0.1
        elif l <= 10:
            self.lScale = 1
        elif l <= 100:
            self.lScale = 10
        elif l <= 1000:
            self.lScale = 100
        elif l <= 10000:
            self.lScale = 1000
        else:
            self.lScale = 10000

    def setrScale(self,r):
        if r <= 1:
            self.rScale = 1
        elif r <= 10:
            self.rScale = 10
        elif r <= 100:
            self.rScale = 100
        elif r <= 1000:
            self.rScale = 1000
        elif r <= 10000:
            self.rScale = 10000
        elif r <= 100000:
            self.rScale = 100000
        else:
            self.rScale = 1000000



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

        


