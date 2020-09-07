import copy
import threading

from PySide2.QtWidgets import (QFrame, QLabel, QPushButton)
from PySide2.QtGui import (QBrush, QPen, QPainter, QFontMetrics, QResizeEvent)
from PySide2.QtCore import (Qt, QPointF, QPoint, QRect)
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
        self.maxVal = -9999999.25
        self.lLog = 0.1
        self.rLog = 100
        self.lLine = 0
        self.rLine = 10000
        self.recalculate = True
        self.lines = []
        self.grids = []
        self.gridsL = []
        self.gridsR = []
        self.gridsCalc = []


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
        # super().paintEvent(e)



    def resizeEvent(self, a0: QResizeEvent):
        # self.draw()
        super().resizeEvent(a0)
        self.timer = time.perf_counter()
        updtDaemon = threading.Thread(target=self.updateTrack, name='updateTrack')
        updtDaemon.setDaemon(True)
        updtDaemon.start()


        # print("Size changed")

    def updateTrack(self):
        time.sleep(1.1)
        self.recalculate = True
        # # self.update()
        # vsplit = self.parent()
        # subw = vsplit.parent()

        # # subw.update()
        # subWell = subw.parent().parent().parent()
        # for t in subWell.lTracks:
        #     t.update()
        # # sizes = subWell.size()
        # vsplit.update()
        # subw.update()
        # subw.parent().update()
        # subw.parent().parent().update()
        # subWell.update()

        # self.update()

        # subWell.parent().update()
        # print("breack")

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
        # size=self.track.maxVal-self.track.minVal
        # conv=self.width()/size
        DrawLinesFlag = False
        lTime = time.perf_counter()
        elapsed = lTime - self.timer
        # If time elapsed between now and the latest change is less than 1 second
        if elapsed > 1:
            DrawLinesFlag = True
            # self.timer = time.perf_counter()
        i = self.st
        j = 0
        linesName = []
        if self.track.lines:
            for l in self.track.lines:
                linesName.append(l.name)

        df = self.well.df[linesName]
        # print(df.columns)
        # Init vars if recalculate == True
        if self.recalculate:
            self.lines = []
            self.gridsL = []
            self.gridsR = []
            if self.type == "Log":
                isLog = True
            if self.track.lines:
                for l in self.track.lines:
                    self.lines.append([])

        while i < self.end:

            # I have to recalculate all points again
            if self.recalculate :
            # Block for generate points
            ## For Draw Lines
                for l in range(len(self.track.lines)):
                    if self.track.lines[l].log == "Log" and self.track.lines[l].visibleCheck:
                        x = df.iat[j,l]
                        if not math.isnan(x):
                            if x >0 :
                                if x < self.track.lLog:
                                    x = copy.copy(self.track.lLog)
                                if x > self.track.rLog:
                                    x = copy.copy(self.track.rLog)
                                lx = int(self.mapLog(self.track.lLog, self.track.rLog, 0, self.width(), x))
                                if j > 0:
                                    if not math.isnan(df.iat[j-1,l]):
                                        prevlx = int(self.mapLog(self.track.lLog,self.track.rLog,0,self.width(),df.iat[j-1,l]))
                                        # if lx != prevlx:
                                        point = QPoint(lx, int(j * fStep))
                                        self.lines[l].append(point)
                                    else:
                                        point = QPoint(lx, int(j * fStep))
                                        self.lines[l].append(point)
                                else:
                                    point = QPoint(lx,int(j*fStep))
                                    self.lines[l].append(point)
                    elif self.track.lines[l].visibleCheck:
                        val = df.iat[j,l]
                        if not math.isnan(val):
                            left = copy.copy(self.track.minValLine)
                            right = copy.copy(self.track.maxValLine)
                            st = self.track.minValLine
                            if not self.track.lines[l].lvScale is None:
                                left = copy.copy(self.track.lines[l].lvScale)
                            if not self.track.lines[l].rvScale is None:
                                right = copy.copy(self.track.lines[l].rvScale)
                            size =  right - left
                            conv = self.width() / size
                            x = (val-left) * conv
                            point = QPoint(int(x),int(j*fStep))
                            self.lines[l].append(point)


            # end block for generate points
            if i%1000 == 0:
                painter.setPen(QPen(Qt.darkGray, 2))
                painter.drawLine(0, j * fStep, self.width(), j * fStep)
            elif i%100 == 0 and (1000*fStep) > 4*self.tall:
                if (100*fStep) >= 4*self.tall and count >= 1000:
                    painter.setPen(QPen(Qt.gray, 2))
                else:
                    painter.setPen(QPen(Qt.gray, 1))
                painter.drawLine(0, j * fStep, self.width(), j * fStep)
            elif i%10 ==0 and (100*fStep) > 4*self.tall:
                if (10*fStep) > 4*self.tall:
                    painter.setPen(QPen(Qt.gray, 2))
                else:
                    painter.setPen(QPen(Qt.gray, 1))
                painter.drawLine(0, j * fStep, self.width(), j * fStep)
            elif i%1 ==0 and (10*fStep) > 10*self.tall:
                painter.setPen(QPen(Qt.gray, 1))
                painter.drawLine(0, j * fStep, self.width(), j * fStep)

            i += self.step
            j += 1
        # Calculating Grids
        if self.recalculate:
            self.gridsL = []
            self.gridsR = []
            self.gridsCalc = []
            for g in self.track.grids:
                findl = False
                findr = False
                for l in self.track.lines:
                    if g.leftLine == l.name:
                        self.gridsL.append(self.track.lines.index(l))
                        findl = True
                    if g.rightLine == l.name:
                        self.gridsR.append(self.track.lines.index(l))
                        findr = True
                    if findl and findr:
                        break
                if findl and findr:
                    reversedR = copy.deepcopy(self.lines[self.gridsR[-1]])

                    for pl,pr in zip(self.lines[self.gridsL[-1]],reversedR):
                        if pl.x() > pr.x():
                            pr.setX(pl.x())
                    reversedR.reverse()
                    out = []
                    out += self.lines[self.gridsL[-1]] + reversedR
                    self.gridsCalc.append(out)
                elif findl and isinstance(g.rightVal, float):
                    left = self.track.minValLine
                    right = self.track.maxValLine
                    if not self.track.lines[self.gridsL[-1]].lvScale is None:
                        left = copy.copy(self.track.lines[self.gridsL[-1]].lvScale)
                    if not self.track.lines[self.gridsL[-1]].rvScale is None:
                        right = copy.copy(self.track.lines[self.gridsL[-1]].rvScale)
                    if l.log == "Log":
                        x = int(self.mapLog(self.track.lLog, self.track.rLog, 0, self.width(), g.rightVal))
                    else:
                        size = right - left
                        conv = self.width() / size
                        x = (g.rightVal - left) * conv

                    leftPoints = copy.deepcopy(self.lines[self.gridsL[-1]])
                    for pl in leftPoints:
                        if pl.x() > x:
                            pl.setX(x)
                    out = []
                    out += leftPoints + [QPoint(x,self.height()),QPoint(x,0)]
                    self.gridsCalc.append(out)
                elif findr and isinstance(g.leftVal, float):
                    left = copy.copy(self.track.minValLine)
                    right = copy.copy(self.track.maxValLine)
                    if not self.track.lines[self.gridsR[-1]].lvScale is None:
                        left = copy.copy(self.track.lines[self.gridsR[-1]].lvScale)
                    if not self.track.lines[self.gridsR[-1]].rvScale is None:
                        right = copy.copy(self.track.lines[self.gridsR[-1]].rvScale)
                    if l.log == "Log":
                        x = int(self.mapLog(self.track.lLog, self.track.rLog, 0, self.width(), g.leftVal))
                    else:
                        size = right - left
                        conv = self.width() / size
                        # x = (g.leftVal - left) * conv
                        x = int(self.mapping(left, right, 0, self.width(), g.leftVal))
                    rightPoints = copy.deepcopy(self.lines[self.gridsR[-1]])
                    for pr in rightPoints:
                        if pr.x() < x:
                            pr.setX(x)
                    rightPoints.reverse()
                    out = []
                    out += [QPoint(x, 0), QPoint(x, self.height())]
                    out += rightPoints
                    self.gridsCalc.append(out)
            # en calculating grids

        # Drawing Lines
        if DrawLinesFlag:
            for g in range(len(self.track.grids)):
                if self.track.grids[g].check:
                    color = self.track.grids[g].color
                    type = self.track.grids[g].brush
                    brush = QBrush(color, type)
                    painter.setBrush(brush)
                    painter.drawPolygon(self.gridsCalc[g])

            for l in range(len(self.track.lines)):
                color = self.track.lines[l].color
                size = self.track.lines[l].grosor
                style = self.track.lines[l].estilo
                painter.setPen(QPen(color, size, style))
                painter.drawPolyline(self.lines[l])
            self.recalculate = False



    def drawTags(self,painter):
        painter.setPen(QPen(Qt.black, 2))
        painter.drawRect(0, 0, self.width() , self.height() )
        count = (self.end-self.st ) / self.step
        fStep = self.height()/count
        font = painter.font()
        higFont = copy.copy(painter.font())
        higFont.setPointSizeF(font.pointSize()*1.1)

        i = self.st
        j = 0
        while i < self.end:
            if i%1000 == 0:
                higFont.setBold(True)
                painter.setFont(higFont)
                painter.drawText(0,(j * fStep) - self.tall/2,self.width(),(j * fStep) +self.tall/2,
                                 Qt.AlignHCenter,str(int(i)))
            elif i%100 == 0 and (1000*fStep) > self.tall*15:
                higFont.setBold(False)
                painter.setFont(higFont)
                painter.drawText(0,(j * fStep) - self.tall/2,self.width(),(j * fStep) +self.tall/2,
                                 Qt.AlignHCenter,str(int(i)))
            elif i%10 == 0 and (100*fStep) > self.tall*15:
                if (10*fStep) > self.tall*15:
                    font.setBold(True)
                else:
                    font.setBold(False)
                painter.setFont(font)
                painter.drawText(0,(j * fStep) - self.tall/2,self.width(),(j * fStep) +self.tall/2,
                                 Qt.AlignHCenter,str(int(i)))
            elif i%1 == 0 and (10*fStep) > self.tall*15:
                font.setBold(False)
                painter.setFont(font)
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
            elements = 0
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

                    if log:
                        lScale = copy.copy(self.track.lLog)
                        rScale = copy.copy(self.track.rLog)
                    else:
                        lScale = self.track.minValLine
                        rScale = self.track.maxValLine
                        if not l.lvScale is None:
                            lScale = l.lvScale
                        if not l.rvScale is None:
                            rScale = l.rvScale


                    qp.drawText(0, fontHeight*count, self.width(), fontHeight*2,
                                Qt.AlignHCenter, str(mnemonic)+" (" + str(unit) + ")")
                    rtextLen = metrics.boundingRect(str(round(rScale, 2))).width()
                    ltextLen = metrics.boundingRect(str(round(lScale, 2))).width()
                    space = metrics.boundingRect(str(0)).width() *2
                    qp.drawText(0, fontHeight*(count+1), ltextLen+space, fontHeight*2,
                                Qt.AlignRight, str(round(lScale,2)))
                    qp.drawText(self.width()-space-rtextLen, fontHeight * (count+1), self.width(), fontHeight*2,
                                Qt.AlignLeft, str(round(rScale, 2)))
                    pen = QPen(l.color, l.grosor, l.estilo)
                    qp.setPen(pen)

                    qp.drawLine(ltextLen+space*2, fontHeight*(count+1.5), self.width() - rtextLen-space*2, fontHeight*(count+1.5))
                    count += 2
                    elements+=1

                elements+=3
                pen = QPen(Qt.black, 1, Qt.SolidLine)
                qp.setPen(pen)
                font = qp.font()
                higFont = copy.copy(qp.font())
                higFont.setPointSizeF(font.pointSize() * 2)
                higFont.setBold(True)

                for g in self.track.grids:
                    text = " " + g.description + " "
                    color = g.color
                    type = g.brush
                    textLen = metrics.boundingRect(text).width()
                    brush = QBrush(color, type)
                    qp.setPen(pen)
                    qp.setBrush(brush)
                    qp.drawRect(QRect(0,fontHeight*(elements), self.width() / 2 - textLen / 2,fontHeight))
                    qp.drawRect(QRect(self.width() / 2 + textLen / 2, fontHeight * (elements), self.width() / 2 - textLen / 2, fontHeight))
                    qp.drawText(self.width()/2 - textLen/2, fontHeight * elements, textLen, fontHeight,
                                Qt.AlignHCenter, text)
                    elements += 1


