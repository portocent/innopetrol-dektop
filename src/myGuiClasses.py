from PySide2.QtWidgets import (QFrame, QLabel)
from PySide2.QtGui import (QBrush, QColor, QIcon, QPalette, QPen, QPainter, QFontMetrics)
from PySide2.QtCore import (Qt, QRect)
from src.lasProcesor import Well, Track, Line, Grid
import math


class Label(QLabel):
    def __init__(self, parent=None):
        super(Label, self).__init__(parent=parent)
        self.penColor = Qt.black
        self.penType = Qt.SolidLine
        self.penSize = 1
        self.visible = False
        self.isBrush = False
        self.visibleCheck = False

    def paintEvent(self, e):
        super().paintEvent(e)
        qp = QPainter(self)
        # qp.drawPixmap(100,100,QtGui.QPixmap("cigale1.png"))

        if self.visible:
            if self.isBrush:
                brush = QBrush(self.penColor, self.penType)
                qp.setBrush(brush)
                qp.drawRect(2, 2, self.width() - 2, self.height() - 2)
            else:
                pen = QPen(self.penColor, self.penSize, self.penType)
                qp.setPen(pen)
                qp.drawLine(2, self.height() / 2, self.width() - 2, self.height() / 2)


class Frame(QFrame):
    def __init__(self, parent=None,well=None,isdep=False):
        super(Frame, self).__init__(parent=parent)
        self.track = Track()
        self.type = "Lineal"
        self.cycles = 3
        self.well = well
        self.head = well.header
        self.yScale = 1
        yAxisVals = self.head.get('Well')
        self.st = None
        self.end = None
        self.step = None
        self.isdep = isdep
        for i in yAxisVals:
            if i.mnemonic == "STRT":
                self.st = i.value
            if i.mnemonic == "STOP":
                self.end = i.value
            if i.mnemonic == "STEP":
                self.step = i.value
            if not self.st is None and not self.end is None and not self.step is None:
                break
        self.minVal = 99999.25
        self.maxVal = -999.25


    def setHead(self,head):
        self.head = head

    def setTrack(self,track):
        self.track = track

    def paintEvent(self, e):
        super().paintEvent(e)
        qp = QPainter(self)
        metrics = QFontMetrics(qp.font())
        self.tall = metrics.boundingRect(str(100)).height()
        # qp.drawPixmap(100,100,QtGui.QPixmap("cigale1.png"))

        if self.track.lines:
            self.type = self.track.lines[0].log
            self.drawLines(qp)
        if self.type == "Log" and not self.isdep:
            self.drawTrackLog(qp)
        elif not self.isdep:
            self.drawTrack(qp)
        if not self.isdep:
            self.drawRowMarks(qp)
        else:
            self.drawTags(qp)

    def mapLog(self,l,r,tl,tr,p):
        size=math.log10(r)-math.log10(l)
        conv=(tr-tl)/size
        plog=math.log10(p)
        distancia=(plog-math.log10(l))*conv
        return tl+distancia

    def mapTLog(self,x,max):
        return math.log10(1+x)/math.log10(1+max)

    def mapping(self,l,r,tl,tr,p):
        size=r-l
        conv=(tr-tl)/size
        distancia=(p-l)*conv
        return distancia+tl

    def drawTrack(self, painter):
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(0, 0, self.width() , self.height() )
        step = self.width() /10
        painter.setPen(QPen(Qt.lightGray, 1))
        for i in range(10):
            if i == 5 or i == 0:
                painter.setPen(QPen(Qt.black, 1))
                painter.drawLine(i * step, 0, i * step, self.height())
                painter.setPen(QPen(Qt.lightGray, 1))
            else:
                painter.drawLine(i*step,0,i*step,self.height())

    def drawTrackLog(self, painter):
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(0, 0, self.width() , self.height() )
        step = self.width() /self.cycles
        painter.setPen(QPen(Qt.lightGray, 1))

        for i in range(self.cycles):
            painter.setPen(QPen(Qt.black, 1))
            painter.drawLine(i * step, 0, i * step, self.height())
            for j in range(10):
                painter.setPen(QPen(Qt.lightGray, 1))
                if j>0:
                    painter.drawLine((self.width()/self.cycles)*self.mapTLog(j,10)+(self.width()/self.cycles)*i, 0, \
                                     (self.width()/self.cycles)*self.mapTLog(j,10)+(self.width()/self.cycles)*i, self.height())

    def drawRowMarks(self,painter):
        count = (self.end-self.st ) / self.step
        fStep = self.height()/count
        i = self.st
        j = 0
        while i < self.end:
            if i%1000 == 0:
                painter.setPen(QPen(Qt.darkGray, 2))
                painter.drawLine(0, j * fStep, self.width(), j * fStep)
            elif i%100 == 0 and (1000*fStep) > 4*self.tall:
                painter.setPen(QPen(Qt.gray, 2))
                if (1000*fStep) >= 2*self.tall and count >= 1000:
                    painter.setPen(QPen(Qt.gray, 1))
                painter.drawLine(0, j * fStep, self.width(), j * fStep)
            elif i%10 ==0 and (100*fStep) > 4*self.tall:
                painter.setPen(QPen(Qt.gray, 1))
                painter.drawLine(0, j * fStep, self.width(), j * fStep)
            i += self.step
            j += 1

    def drawTags(self,painter):
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(0, 0, self.width() , self.height() )
        count = (self.end-self.st ) / self.step
        fStep = self.height()/count

        i = self.st
        j = 0
        while i < self.end:
            if i%1000 == 0:
                painter.drawText(0,(j * fStep) - self.tall/2,self.width(),(j * fStep) +self.tall/2,
                                 Qt.AlignHCenter,str(int(i)))
            elif i%100 == 0 and 2*(100*fStep) > self.tall:
                painter.drawText(0,(j * fStep) - self.tall/2,self.width(),(j * fStep) +self.tall/2,
                                 Qt.AlignHCenter,str(int(i)))

            i += self.step
            j += 1

    def drawLines(self,painter):
        for l in self.track.lines:
            points = self.well.df[[l.name,'T']]
        if self.type == "Log":
            mapP = self.mapLog(self.minVal,self.maxVal,0,self.width(),1)
            points.append()
