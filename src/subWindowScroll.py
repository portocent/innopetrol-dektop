from PySide2 import QtWidgets
from PySide2 import QtGui
from src.lasProcesor import Track
from src.addCurveWindow import addCurveWindow
from PySide2.QtCore import (QSize, Qt,
                            Slot, SIGNAL, QTimer)
from PySide2.QtGui import (QBrush, QColor, QIcon, QPalette)
from PySide2.QtWidgets import (QFrame, QAction, QWidget,
                               QGridLayout, QSplitter, QPushButton,
                               QLabel, QMenu, QScrollBar, QScrollArea)
from src.myGuiClasses import Frame, Button
import time
import threading, copy
from functools import partial


class subWindowWell(QWidget):
    def __init__(self, parent ,well = None):
        # Sub Windows start here
        super().__init__(parent)
        self.parent = parent
        self.lTracks = []
        self.lSplit = []
        self.setObjectName(u"subwindow")
        self.frameScroll = QScrollArea(self)
        self.headScroll = QScrollArea(self)
        # self.setMinimumSize(QSize(200, 475))
        self.setMinimumSize(QSize(220, 300))
        self.defaultSize = QSize(220, 475)
        self.gridLayout = QGridLayout(self)
        self.gridLayout.setObjectName(u"gridLayout")
        self.splitter = QSplitter(self)
        self.headSplitter = QSplitter(self)
        self.frameSplitter = QSplitter(self)
        # self.frameSplitter = QSplitter(self)
        self.well = well
        self.st = None
        self.end = None
        self.step = None
        self.trackLong = 0
        if not self.well is None:
            self.header = well.header
            self.trackConst = self.header.get('Well')
            for i in self.trackConst:
                if i.mnemonic == "STRT":
                    self.st = i.value
                if i.mnemonic == "STOP":
                    self.end = i.value
                if i.mnemonic == "STEP":
                    self.step = i.value
                if not self.st is None and not self.end is None and not self.step is None:
                    self.trackLong = (self.end - self.st)
                    break
        wellTrack1 = Track()
        wellTrack2 = Track()
        self.well.addTrack(wellTrack1)
        self.well.addTrack(wellTrack2)
        # self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Vertical)
        self.headSplitter.setOrientation(Qt.Horizontal)
        self.frameSplitter.setOrientation(Qt.Horizontal)
        self.track2Size = 50
        # Resize Timer
        self.resizeTimer = QTimer()
        # External Layout

        # Internal Splitter
        iSplitter = QSplitter(self)
        iSplitter.setOrientation(Qt.Vertical)
        iSplitter2 = QSplitter(self)
        iSplitter2.setOrientation(Qt.Vertical)

        # Adding scrolling to vSplitters
        

        # Adding Label tag
        label = QLabel("1", iSplitter)
        label.setAlignment(Qt.AlignCenter)
        label2 = QLabel("2", iSplitter2)
        label2.setAlignment(Qt.AlignCenter)
        label.setFrameShape(QFrame.Panel)
        label.setFrameShadow(QFrame.Plain)
        label.setLineWidth(2)
        label2.setFrameShape(QFrame.Panel)
        label2.setFrameShadow(QFrame.Plain)
        label2.setLineWidth(2)

        # Adding a buttons
        button = Button(iSplitter,self.well)
        button.clicked.connect(partial(self._addLines ,1))
        button2 = Button(iSplitter2,self.well,True)
        # button2.clicked.connect(partial(self._addLines ,2))
        # button.clicked.connect(lambda:self.whichbtn(self.b2))

        frame = Frame(self.frameSplitter ,self.well)
        iSplitter.addWidget(label)
        iSplitter.addWidget(button)
        self.frameSplitter.addWidget(frame)
        self.headSplitter.addWidget(iSplitter)
        # self.lSplit.append(vSplitter)
        # self.lSplit.append(vSplitter2)
        # frame.setObjectName(u"frame")
        # Set frame and button names
        frame.setObjectName(u"Track_ " +str(self.frameSplitter.count()))
        button.setObjectName(u"button_ " +str(self.frameSplitter.count()))
        palette = QPalette()
        self.brush = QBrush(QColor(255, 255, 255, 255))
        self.brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.Base, self.brush)
        palette.setBrush(QPalette.Active, QPalette.Window, self.brush)
        palette.setBrush(QPalette.Inactive, QPalette.Base, self.brush)
        palette.setBrush(QPalette.Inactive, QPalette.Window, self.brush)
        palette.setBrush(QPalette.Disabled, QPalette.Base, self.brush)
        palette.setBrush(QPalette.Disabled, QPalette.Window, self.brush)
        frame.setPalette(palette)
        frame.setAutoFillBackground(True)
        frame.setFrameShape(QFrame.NoFrame)
        frame.setFrameShadow(QFrame.Raised)
        # Adding the splitter instead of the Frame
        # self.splitter.addWidget(frame)

        frame_2 = Frame(self.frameSplitter ,self.well ,True)
        iSplitter2.addWidget(label2)
        iSplitter2.addWidget(button2)
        self.frameSplitter.addWidget(frame_2)
        self.headSplitter.addWidget(iSplitter2)

        self.frameScroll.setWidget(self.frameSplitter)
        self.frameScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.frameScroll.setWidgetResizable(True)
        self.headScroll.setWidget(self.headSplitter)
        self.headScroll.setVerticalScrollBarPolicy(Qt.ScrollBarAlwaysOn)
        self.headScroll.setWidgetResizable(True)
        self.splitter.addWidget(self.headScroll)
        self.splitter.addWidget(self.frameScroll)

        # frame_2.setObjectName(u"frame_2")
        frame_2.setObjectName(u"Track_ " +str(self.frameSplitter.count()))
        button2.setObjectName(u"button_ " +str(self.frameSplitter.count()))
        palette1 = QPalette()
        palette1.setBrush(QPalette.Active, QPalette.Base, self.brush)
        palette1.setBrush(QPalette.Active, QPalette.Window, self.brush)
        palette1.setBrush(QPalette.Inactive, QPalette.Base, self.brush)
        palette1.setBrush(QPalette.Inactive, QPalette.Window, self.brush)
        palette1.setBrush(QPalette.Disabled, QPalette.Base, self.brush)
        palette1.setBrush(QPalette.Disabled, QPalette.Window, self.brush)
        frame_2.setPalette(palette1)
        frame_2.setAutoFillBackground(True)
        frame_2.setFrameShape(QFrame.NoFrame)
        frame_2.setFrameShadow(QFrame.Raised)


        self.gridLayout.addWidget(self.splitter, 0, 0, 1, 1)
        # self.gridLayout.addWidget(self.,0,1,1,1)
        # Saving frame name
        frame.mouseReleaseEvent = lambda event: self.setOverFrame(frame)
        frame_2.mouseReleaseEvent = lambda event: self.setOverFrame(frame_2)
        # Adding the paint event for drawing
        # frame.paintEvent = types.MethodType(paintSub, frame)
        frame.track = self.well.tracks[0]
        frame_2.track = self.well.tracks[1]
        button.setTrack(self.well.tracks[0])
        button2.setTrack(self.well.tracks[1])


        self.lTracks.append(frame)
        self.lTracks.append(frame_2)

        # Adding vertical splitter events conection
        self.connect(self.headSplitter, SIGNAL("splitterMoved(int, int)"), lambda x : self.splitterMoved(self.headSplitter))
        self.connect(self.frameSplitter, SIGNAL("splitterMoved(int, int)"), lambda x : self.splitterMoved(self.frameSplitter))

        # create actions
        self.addTrackAction = QAction(self)
        self.addTrackAction.setText('Add Track')
        self.addTrackAction.triggered.connect(self.addTrack)
        self.delTrackAction = QAction(self)
        self.delTrackAction.setText('Remove Track')
        self.delTrackAction.triggered.connect(self.delTrack)
        self.zoomDx = QAction("Ajustar ventana",self)
        self.zoomDx.triggered.connect(self.changeZoomDx)
        self.zoom1x = QAction("1000", self)
        self.zoom1x.setCheckable(True)
        self.zoom1x.triggered.connect(self.changeZoom1x)
        self.zoom2x = QAction("500",self)
        self.zoom2x.setCheckable(True)
        self.zoom2x.triggered.connect(self.changeZoom2x)
        self.zoom4x = QAction("100",self)
        self.zoom4x.setCheckable(True)
        self.zoom4x.triggered.connect(self.changeZoom4x)
        self.zoom10x = QAction("50",self)
        self.zoom10x.setCheckable(True)
        self.zoom10x.triggered.connect(self.changeZoom10x)
        self.zoom50x = QAction("25",self)
        self.zoom50x.setCheckable(True)
        self.zoom50x.triggered.connect(self.changeZoom50x)
        self.zoom100x = QAction("10",self)
        self.zoom100x.setCheckable(True)
        self.zoom100x.triggered.connect(self.changeZoom100x)


        # create context menu
        self.popMenu = QMenu(self)
        self.zoomMenu = QMenu("Zoom",self)

        self.zoomMenu.addAction(self.zoomDx)
        self.zoomMenu.addAction(self.zoom1x)
        self.zoomMenu.addAction(self.zoom2x)
        self.zoomMenu.addAction(self.zoom4x)
        self.zoomMenu.addAction(self.zoom10x)
        self.zoomMenu.addAction(self.zoom50x)
        self.zoomMenu.addAction(self.zoom100x)
        self.popMenu.addAction(self.addTrackAction)
        self.popMenu.addAction(self.delTrackAction)
        self.popMenu.addMenu(self.zoomMenu)
        #   C O N N E C T   P O P U P   M E N U   T O   O U R   B U T T O N
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showPopup)


        # set init sizes
        initSize = [70, self.height() - 70]
        self.splitter.setSizes(initSize)
        iSplitter.setSizes([20,50])
        iSplitter2.setSizes([20,50])

        wSize = self.width()
        self.headSplitter.blockSignals(True)
        self.frameSplitter.blockSignals(True)

        self.headSplitter.setSizes([wSize-self.track2Size,self.track2Size])
        self.frameSplitter.setSizes([wSize-self.track2Size,self.track2Size])
        self.headSplitter.blockSignals(False)
        self.frameSplitter.blockSignals(False)

        # initHorizontalSize = [self.width( ) -self.track2Size, self.track2Size]

    def changeZoomDx(self):
        # size = QSize(210, 350)
        # size.setHeight(size.height())
        QMdiSubwindow = self.parentWidget()
        size = QMdiSubwindow.size()
        size.setHeight(self.parent.mdiArea.height())
        oldSplitSizes = self.splitter.sizes()
        QMdiSubwindow.resize(size)
        newSplitSizes = self.splitter.sizes()
        newSizeDraw = newSplitSizes[0] + newSplitSizes[1]
        oldSplitSizes[1] = newSizeDraw - oldSplitSizes[0]
        self.splitter.blockSignals(True)
        self.splitter.setSizes(oldSplitSizes)
        self.splitter.blockSignals(False)
        self.update()

    def changeZoom1x(self):
        scale = 1000
        # QMdiSubwindow = self.parentWidget()
        # width = QMdiSubwindow.width()
        # height = QMdiSubwindow.height()
        oldSplitSizes = self.splitter.sizes()
        newSplitSizes = self.splitter.sizes()
        # oldFrameSize = oldSplitSizes[0]
        newFrameSize = 400*self.trackLong/scale
        newSizeDraw = newSplitSizes[0] + newFrameSize
        oldSplitSizes[1] = newSizeDraw - newSplitSizes[0]
        self.splitter.setSizes(oldSplitSizes)
        self.zoom2x.setChecked(False)
        self.zoom4x.setChecked(False)
        self.zoom10x.setChecked(False)
        self.zoom50x.setChecked(False)
        self.zoom100x.setChecked(False)
        self.zoom1x.setChecked(True)
        for t in range(self.frameSplitter.count()):
            self.frameSplitter.widget(t).setMinimumHeight(newFrameSize)
        self.update()


    def changeZoom2x(self):
        scale = 500
        oldSplitSizes = self.splitter.sizes()
        newSplitSizes = self.splitter.sizes()
        # oldFrameSize = oldSplitSizes[0]
        newFrameSize = 400*self.trackLong/scale
        newSizeDraw = newSplitSizes[0] + newFrameSize
        oldSplitSizes[1] = newSizeDraw - newSplitSizes[0]
        self.splitter.setSizes(oldSplitSizes)
        self.zoom1x.setChecked(False)
        self.zoom4x.setChecked(False)
        self.zoom10x.setChecked(False)
        self.zoom50x.setChecked(False)
        self.zoom100x.setChecked(False)
        self.zoom2x.setChecked(True)
        for t in range(self.frameSplitter.count()):
            self.frameSplitter.widget(t).setMinimumHeight(newFrameSize)
        self.update()

    def changeZoom4x(self):
        scale = 100
        oldSplitSizes = self.splitter.sizes()
        newSplitSizes = self.splitter.sizes()
        # oldFrameSize = oldSplitSizes[0]
        newFrameSize = 400 * self.trackLong / scale
        newSizeDraw = newSplitSizes[0] + newFrameSize
        oldSplitSizes[1] = newSizeDraw - newSplitSizes[0]
        self.splitter.setSizes(oldSplitSizes)
        self.zoom2x.setChecked(False)
        self.zoom1x.setChecked(False)
        self.zoom10x.setChecked(False)
        self.zoom50x.setChecked(False)
        self.zoom100x.setChecked(False)
        self.zoom4x.setChecked(True)
        for t in range(self.frameSplitter.count()):
            self.frameSplitter.widget(t).setMinimumHeight(newFrameSize)
        self.update()

    def changeZoom10x(self):
        scale = 50
        oldSplitSizes = self.splitter.sizes()
        newSplitSizes = self.splitter.sizes()
        # oldFrameSize = oldSplitSizes[0]
        newFrameSize = 400*self.trackLong/scale
        newSizeDraw = newSplitSizes[0] + newFrameSize
        oldSplitSizes[1] = newSizeDraw - newSplitSizes[0]
        self.splitter.setSizes(oldSplitSizes)
        self.zoom2x.setChecked(False)
        self.zoom4x.setChecked(False)
        self.zoom1x.setChecked(False)
        self.zoom50x.setChecked(False)
        self.zoom100x.setChecked(False)
        self.zoom10x.setChecked(True)
        for t in range(self.frameSplitter.count()):
            self.frameSplitter.widget(t).setMinimumHeight(newFrameSize)
        self.update()


    def changeZoom50x(self):
        scale = 25
        oldSplitSizes = self.splitter.sizes()
        newSplitSizes = self.splitter.sizes()
        # oldFrameSize = oldSplitSizes[0]
        newFrameSize = 400 * self.trackLong / scale
        newSizeDraw = newSplitSizes[0] + newFrameSize
        oldSplitSizes[1] = newSizeDraw - newSplitSizes[0]
        self.splitter.setSizes(oldSplitSizes)
        self.zoom2x.setChecked(False)
        self.zoom4x.setChecked(False)
        self.zoom10x.setChecked(False)
        self.zoom1x.setChecked(False)
        self.zoom100x.setChecked(False)
        self.zoom50x.setChecked(True)
        for t in range(self.frameSplitter.count()):
            self.frameSplitter.widget(t).setMinimumHeight(newFrameSize)
        self.update()

    def changeZoom100x(self):
        scale = 10
        oldSplitSizes = self.splitter.sizes()
        newSplitSizes = self.splitter.sizes()
        # oldFrameSize = oldSplitSizes[0]
        newFrameSize = 400 * self.trackLong / scale
        newFrameSize = 400 * self.trackLong / scale
        newSizeDraw = newSplitSizes[0] + newFrameSize
        oldSplitSizes[1] = newSizeDraw - newSplitSizes[0]
        self.splitter.setSizes(oldSplitSizes)
        self.zoom2x.setChecked(False)
        self.zoom4x.setChecked(False)
        self.zoom10x.setChecked(False)
        self.zoom50x.setChecked(False)
        self.zoom1x.setChecked(False)
        self.zoom100x.setChecked(True)
        for t in range(self.frameSplitter.count()):
            self.frameSplitter.widget(t).setMinimumHeight(newFrameSize)
        self.update()


    def resizeEvent(self, event :QtGui.QResizeEvent):
        # print("Resizing")
        super().resizeEvent(event)
        for t in self.lTracks:
            t.timer = time.perf_counter()
        updtDaemon = threading.Thread(target=self.updateTracks, name='updateTracks')
        updtDaemon.setDaemon(True)
        updtDaemon.start()



    def updateTracks(self):
        time.sleep(1.5)
        self.update()
        self.parent.update()

    # def mousePressEvent(self, event :QtGui.QMouseEvent):
    #     if event.button() == Qt.LeftButton:
    #         print("Pressed")


    #   S H O W   P O P U P   M E N U
    def setOverFrame(self, frame):
        self.onFrame = frame

    def mousePressEvent(self, event:QtGui.QMouseEvent):
        #
        for t in self.lTracks:
            t.timer = time.perf_counter() -5
            # print(str(t.timer))
            t.repaint()
        self.update()


    def enterEvent(self, event):
        # print ("Mouse Entered")
        for t in self.lTracks:
            t.timer = time.perf_counter() -5
            # print(str(t.timer))
            t.blockSignals(True)
            t.repaint()
            t.blockSignals(False)
        self.update()
        return super(subWindowWell, self).enterEvent(event)

    def leaveEvent(self, event):
        print("Leave Window")
        return super(subWindowWell, self).enterEvent(event)

    def showPopup(self, position):
        self.popMenu.exec_(self.mapToGlobal(position))

    @Slot()
    def addTrack(self):
        frameCount = self.frameSplitter.count()

        # Internal Splitter
        iSplitter = QSplitter(self)
        iSplitter.setOrientation(Qt.Vertical)
        # Adding a button
        button = Button(iSplitter,self.well)
        button.setObjectName(u"button_ " +str(frameCount))
        button.clicked.connect(partial(self._addLines ,frameCount +1))
        frame = Frame(self.frameSplitter ,self.well)
        # Adding Label tag
        label = QLabel(str(frameCount +1), iSplitter)
        label.setAlignment(Qt.AlignCenter)
        label.setFrameShape(QFrame.Panel)
        label.setFrameShadow(QFrame.Plain)
        label.setLineWidth(2)
        # New label for fill space
        label2 = QLabel()
        label2.setMinimumSize(QSize(self.frameScroll.verticalScrollBar().width(),0))

        # Adding widgets to splitter
        iSplitter.addWidget(label)
        iSplitter.addWidget(button)
        prevH = self.headSplitter.widget(1)
        iSplitter.setSizes(prevH.sizes())
        self.headSplitter.addWidget(iSplitter)
        self.frameSplitter.addWidget(frame)
        # Vertical Splitter sizes:


        frame.setObjectName(u"Track_ " +str(frameCount))

        # button.setText(str(button.objectName()))
        palette1 = QPalette()
        palette1.setBrush(QPalette.Active, QPalette.Base, self.brush)
        palette1.setBrush(QPalette.Active, QPalette.Window, self.brush)
        palette1.setBrush(QPalette.Inactive, QPalette.Base, self.brush)
        palette1.setBrush(QPalette.Inactive, QPalette.Window, self.brush)
        palette1.setBrush(QPalette.Disabled, QPalette.Base, self.brush)
        palette1.setBrush(QPalette.Disabled, QPalette.Window, self.brush)
        frame.setPalette(palette1)
        frame.setAutoFillBackground(True)
        frame.setFrameShape(QFrame.NoFrame)
        frame.setFrameShadow(QFrame.Raised)
        self.lTracks.append(frame)

        # self.splitter.addWidget(vSplitter)
        # vSplitter.setSizes(self.lSplit[0].sizes())
        # self.splitter.update()
        # Saving over frame
        # frame.mouseReleaseEvent = lambda event: self.setOverFrame(frame)
        # Calculate the size for each frame
        sizes = []
        fSize = (self.frameSplitter.width( ) -self.track2Size ) /self.frameSplitter.count()
        i = 0
        for s in range(self.frameSplitter.count()):
            if i == 1:
                sizes.append(self.track2Size)
            else:
                sizes.append(fSize)
            i += 1
        self.frameSplitter.setSizes(sizes)

        # Adding Well's Tracks
        wellTrack = Track()
        self.well.addTrack(wellTrack)
        frame.track = self.well.tracks[-1]
        frame.minVal = self.well.tracks[-1].minVal
        frame.maxVal = self.well.tracks[-1].maxVal
        button.setTrack(self.well.tracks[-1])

        # Resize all the another Splitters
        self.headSplitter.blockSignals(True)
        self.headSplitter.setSizes(self.frameSplitter.sizes())
        self.headSplitter.blockSignals(False)

    @Slot()
    def delTrack(self):
        # Remove last track
        if len(self.lTracks) > 2:
            self.lTracks.pop()
            self.well.popTrack()
            self.frameSplitter.widget(self.frameSplitter.count( ) -1).deleteLater()
            self.headSplitter.widget(self.headSplitter.count() - 1).deleteLater()

    @Slot()
    def _addLines(self ,track):
        dialog = addCurveWindow(self ,track)
        dialog.exec_()
        # dialog.show()

    def splitterMoved(self, sender):
        if sender is self.headSplitter:
            self.frameSplitter.blockSignals(True)
            self.frameSplitter.setSizes(sender.sizes())
            self.frameSplitter.blockSignals(False)
        elif sender is self.frameSplitter:
            self.headSplitter.blockSignals(True)
            self.headSplitter.setSizes(sender.sizes())
            self.headSplitter.blockSignals(False)


    def closeEvent(self, event):
        msg = QtWidgets.QMessageBox()
        msg.setIcon(QtWidgets.QMessageBox.Warning)
        msg.setWindowIcon(QIcon("statics\\images\\LOGO-08.png"))
        msg.setText("Está seguro de querer cerrar el pozo" + self.well.name + "?")
        # msg.setInformativeText("This is additional information")
        msg.setWindowTitle("Cerrar pozo")
        # msg.setDetailedText("The details are as follows:")
        msg.setStandardButtons(QtWidgets.QMessageBox.Ok | QtWidgets.QMessageBox.Cancel)
        # msg.buttonClicked.connect(msgbtn)
        retval = msg.exec_()
        # Get the Window title
        name = str(self.windowTitle())
        # looking for the item in the tree
        t = self.parent.treeWidget.findItems(name, Qt.MatchWrap)
        # print ("Number:", t)
        # self.parent.treeWidget.removeItemWidget(t[0], 0)
        # Remove the item in the tree
        self.parent.treeWidget.takeTopLevelItem(self.parent.treeWidget.indexOfTopLevelItem(t[0]))
        # if click in ok then exit
        if retval == 1024:  # write your required condition/check
            event.accept()
        else:
            event.ignore()

            # self.frame.paintEvent = types.MethodType(paintSub, self.frame)
    # def mousePressEvent(self, QMouseEvent):
    #     if QMouseEvent.button() == Qt.LeftButton:
    #         print("Left Button Clicked")
    #     elif QMouseEvent.button() == Qt.RightButton:
    #         #do what you want here
    #         print("Right Button Clicked")
    #         self.popMenu.exec_(self.button.mapToGlobal(point))



    # for t in self.lTracks:
    #     t.setUpdatesEnabled(True)

    def setWell(self, well):
        self.well = well
        # Adding Well's Tracks
        wellTrack1 = Track()
        wellTrack2 = Track()
        self.well.addTrack(wellTrack1)
        self.well.addTrack(wellTrack2)
