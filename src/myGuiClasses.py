import threading

from PySide2.QtWidgets import (QFrame, QLabel, QPushButton)
from PySide2.QtGui import (QBrush, QPen, QPainter, QFontMetrics, QResizeEvent)
from PySide2.QtCore import (Qt, QPointF)
from src.lasProcesor import Track, Line, Grid
import math
import time


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
        self.timer = time.perf_counter()
        for i in yAxisVals:
            if i.mnemonic == "STRT":
                self.st = i.value
            if i.mnemonic == "STOP":
                self.end = i.value
            if i.mnemonic == "STEP":
                self.step = i.value
            if not self.st is None and not self.end is None and not self.step is None:
                break
        self.minVal = 9999999.25
        self.maxVal = -999.25
        self.lLog = 0.1
        self.rLog = 100
        self.lLine = 0
        self.rLine = 10000




    def setHead(self,head):
        self.head = head

    def setTrack(self,track):
        self.track = track

    def paintEvent(self, e):
        super().paintEvent(e)
        qp = QPainter(self)
        metrics = QFontMetrics(qp.font())
        # print("--------------repainted")
        self.tall = metrics.boundingRect(str(100)).height()
        # qp.drawPixmap(100,100,QtGui.QPixmap("cigale1.png"))
        if self.track.lines:
            self.type = self.track.lines[0].log
            self.cycles = self.track.cycles
            # self.drawLines(qp)
        if self.type == "Log" and not self.isdep:
            self.drawTrackLog(qp)
        elif not self.isdep:
            self.drawTrack(qp)
        if not self.isdep:
            self.drawRowMarks(qp)
        else:
            self.drawTags(qp)



    def resizeEvent(self, a0: QResizeEvent):
        # self.draw()
        super().resizeEvent(a0)
        self.timer = time.perf_counter()
        updtDaemon = threading.Thread(target=self.updateTrack, name='updateTrack')
        updtDaemon.setDaemon(True)
        updtDaemon.start()

        # print("Size changed")

    def updateTrack(self):
        time.sleep(1.3)
        self.update()

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

        for i in range(self.track.cycles):
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
        size=self.track.maxVal-self.track.minVal
        conv=self.width()/size
        DrawLinesFlag = False
        lTime = time.perf_counter()
        elapsed = lTime - self.timer

        if elapsed > 1:
            DrawLinesFlag = True
            # self.timer = time.perf_counter()
        i = self.st
        j = 0
        ## For Draw Lines
        lines = []
        linesName = []
        if self.track.lines:
             for l in self.track.lines:
                linesName.append(l.name)
                lines.append([])
        df = self.well.df[linesName]
        # print(df.columns)

        while i < self.end:

            if DrawLinesFlag:
            # Block for generate points
                for l in range(len(self.track.lines)):
                    if self.track.lines[l].log == "Log" and self.track.lines[l].visibleCheck:
                        x = df.iat[j,l]
                        if not math.isnan(x):
                            if x >0 :
                                point = QPointF(self.mapLog(self.track.lLog,self.track.rLog,0,self.width(),x),j*fStep)
                                lines[l].append(point)
                    elif self.track.lines[l].visibleCheck:
                        val = df.iat[j,l]
                        if not math.isnan(val):
                            x = (val-self.track.minVal)*conv
                            point = QPointF(x,j*fStep)
                            lines[l].append(point)
            # end block for generate points
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
        # Drawing Lines
        if DrawLinesFlag:
            for l in range(len(self.track.lines)):
                color = self.track.lines[l].color
                size = self.track.lines[l].grosor
                painter.setPen(QPen(color, size))
                painter.drawPolyline(lines[l])


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
            elif i%10 == 0 and (10*fStep) > self.tall*5:
                painter.drawText(0,(j * fStep) - self.tall/2,self.width(),(j * fStep) +self.tall/2,
                                 Qt.AlignHCenter,str(int(i)))
            elif i%1 == 0 and (10*fStep) > self.tall*10:
                painter.drawText(0,(j * fStep) - self.tall/2,self.width(),(j * fStep) +self.tall/2,
                                 Qt.AlignHCenter,str(int(i)))

            i += self.step
            j += 1

    # def drawLines(self,painter):


class Button(QPushButton):
    def __init__(self, parent=None,well=None,isdep=False):
        self.penColor = Qt.black
        self.penType = Qt.SolidLine
        self.well = well
        self.isdep = isdep
        self.header = self.well.header['Well']
        self.unit = self.header['STRT'].unit
        self.curves = self.well.curves
        self.track = Track()
        super(Button, self).__init__(parent=parent)
        # self.setStyleSheet("background-color:white;")

    def setTrack(self,track):
        self.track = track

    def paintEvent(self, e):
        super().paintEvent(e)
        qp = QPainter(self)

        if self.isdep:
            qp.drawText(0, 0, self.width(),self.height(),
                             Qt.AlignHCenter|Qt.AlignVCenter, "DEPTH\n"+str(self.unit))
        else:
            metrics = QFontMetrics(qp.font())
            fontHeight = metrics.boundingRect(str(100)).height()
            oPen = qp.pen()
            if self.track.lines:
                count = 0
                for l in self.track.lines:
                    qp.setPen(oPen)
                    curve = self.curves[l.name]
                    mnemonic = curve['mnemonic']
                    unit = curve['unit']
                    log = False
                    if l.log == "Log":
                        log = True
                    if l.lScale is None:
                        if log:
                            lScale = self.track.lLog
                        else:
                            lScale = self.track.lLine
                    elif str(l.lScale) == '':
                        if log:
                            lScale = self.track.lLog
                        else:
                            lScale = self.track.lLine
                    else:
                        lScale = l.lScale

                    if l.rScale is None:
                        if log:
                            rScale = self.track.rLog
                        else:
                            rScale = self.track.rLine
                    elif str(l.rScale) == '':
                        if log:
                            rScale = self.track.rLog
                        else:
                            rScale = self.track.rLine
                    else:
                        rScale = l.rScale
                    qp.drawText(0, fontHeight*count, self.width(), fontHeight*2,
                                Qt.AlignHCenter, str(mnemonic)+" (" + str(unit) + ")")
                    rtextLen = metrics.boundingRect(str(round(rScale, 2))).width()
                    ltextLen = metrics.boundingRect(str(round(lScale, 2))).width()
                    qp.drawText(0, fontHeight*(count+1), ltextLen+4, fontHeight*2,
                                Qt.AlignRight, str(round(lScale,2)))
                    qp.drawText(self.width()-4-rtextLen, fontHeight * (count+1), self.width(), fontHeight*2,
                                Qt.AlignLeft, str(round(rScale, 2)))
                    pen = QPen(l.color, l.grosor, l.estilo)
                    qp.setPen(pen)

                    qp.drawLine(ltextLen+5, fontHeight*(count+1.5), self.width() - rtextLen-5, fontHeight*(count+1.5))
                    count += 2





