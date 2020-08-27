from PySide2 import QtWidgets
from PySide2 import QtGui
from src.lasProcesor import Track
from src.addCurveWindow import addCurveWindow
from PySide2.QtCore import (QSize, Qt,
                            Slot, SIGNAL, QTimer)
from PySide2.QtGui import (QBrush, QColor, QIcon, QPalette)
from PySide2.QtWidgets import (QFrame, QAction, QWidget,
                               QGridLayout, QSplitter, QPushButton,
                               QLabel)
from src.myGuiClasses import Frame, Button
import time
import threading
from functools import partial


class subWindowWell(QWidget):
    def __init__(self, parent ,well = None):
        # Sub Windows start here
        super().__init__(parent)
        self.parent = parent
        self.lTracks = []
        self.lSplit = []
        self.setObjectName(u"subwindow")
        # self.setMinimumSize(QSize(200, 475))
        self.setMinimumSize(QSize(200, 300))
        self.gridLayout = QGridLayout(self)
        self.gridLayout.setObjectName(u"gridLayout")
        self.splitter = QSplitter(self)
        self.well = well
        wellTrack1 = Track()
        wellTrack2 = Track()
        self.well.addTrack(wellTrack1)
        self.well.addTrack(wellTrack2)
        # self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.track2Size = 50
        # Resize Timer
        self.resizeTimer = QTimer()
        # Internal Splitter
        vSplitter = QSplitter(self)
        vSplitter.setOrientation(Qt.Vertical)
        vSplitter2 = QSplitter(self)
        vSplitter2.setOrientation(Qt.Vertical)

        # Adding Label tag
        label = QLabel("1", vSplitter)
        label.setAlignment(Qt.AlignCenter)
        label2 = QLabel("2", vSplitter2)
        label2.setAlignment(Qt.AlignCenter)
        label.setFrameShape(QFrame.Panel)
        label.setFrameShadow(QFrame.Plain)
        label.setLineWidth(2)
        label2.setFrameShape(QFrame.Panel)
        label2.setFrameShadow(QFrame.Plain)
        label2.setLineWidth(2)

        # Adding a buttons
        button = Button(vSplitter,self.well)
        button.clicked.connect(partial(self._addLines ,1))
        button2 = Button(vSplitter2,self.well,True)
        button2.clicked.connect(partial(self._addLines ,2))
        # button.clicked.connect(lambda:self.whichbtn(self.b2))

        frame = Frame(vSplitter ,self.well)
        vSplitter.addWidget(label)
        vSplitter.addWidget(button)
        vSplitter.addWidget(frame)
        self.lSplit.append(vSplitter)
        self.lSplit.append(vSplitter2)
        # frame.setObjectName(u"frame")
        # Set frame and button names
        frame.setObjectName(u"Track_ " +str(self.splitter.count()))
        button.setObjectName(u"button_ " +str(self.splitter.count()))
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
        self.splitter.addWidget(vSplitter)
        frame_2 = Frame(vSplitter2 ,self.well ,True)
        vSplitter2.addWidget(label2)
        vSplitter2.addWidget(button2)
        vSplitter2.addWidget(frame_2)
        # frame_2.setObjectName(u"frame_2")
        frame_2.setObjectName(u"Track_ " +str(self.splitter.count()))
        button2.setObjectName(u"button_ " +str(self.splitter.count()))
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
        self.splitter.addWidget(vSplitter2)
        self.gridLayout.addWidget(self.splitter, 0, 0, 1, 1)
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
        # frame.minVal = self.well.tracks[0].minVal
        # frame.maxVal = self.well.tracks[0].maxVal
        # frame_2.minVal = self.well.tracks[1].minVal
        # frame_2.maxVal = self.well.tracks[1].maxVal
        self.lTracks.append(frame_2)



        # Adding vertical splitter events conection
        self.connect(vSplitter, SIGNAL("splitterMoved(int, int)"), lambda x : self.splitterMoved(vSplitter))
        self.connect(vSplitter2, SIGNAL("splitterMoved(int, int)"), lambda x : self.splitterMoved(vSplitter2))

        # create actions
        self.addTrackAction = QAction(self)
        self.addTrackAction.setText('Add Track')
        self.addTrackAction.triggered.connect(self.addTrack)
        self.delTrackAction = QAction(self)
        self.delTrackAction.setText('Remove Track')
        self.delTrackAction.triggered.connect(self.delTrack)
        # create context menu
        self.popMenu = QtWidgets.QMenu(self)
        self.popMenu.addAction(self.addTrackAction)
        self.popMenu.addAction(self.delTrackAction)
        #   C O N N E C T   P O P U P   M E N U   T O   O U R   B U T T O N
        self.setContextMenuPolicy(Qt.CustomContextMenu)
        self.customContextMenuRequested.connect(self.showPopup)


        # set init sizes
        initSize = [20, 50, self.height() - 70]
        vSplitter.setSizes(initSize)
        vSplitter2.setSizes(initSize)
        initHorizontalSize = [self.width( ) -self.track2Size, self.track2Size]
        self.splitter.setSizes(initHorizontalSize)


    def resizeEvent(self, event :QtGui.QResizeEvent):
        # print("Resizing")
        for t in self.lTracks:
            t.timer = time.perf_counter()
        updtDaemon = threading.Thread(target=self.updateTracks, name='updateTracks')
        updtDaemon.setDaemon(True)
        updtDaemon.start()

    def updateTracks(self):
        time.sleep(1.1)
        for t in self.lTracks:
            t.update()

    # def mousePressEvent(self, event :QtGui.QMouseEvent):
    #     if event.button() == Qt.LeftButton:
    #         print("Pressed")



    # def keyPressEvent(self, event):
    #     print("Key pressed")
    #   S H O W   P O P U P   M E N U
    def setOverFrame(self, frame):
        self.onFrame = frame

    def showPopup(self, position):
        self.popMenu.exec_(self.mapToGlobal(position))

    @Slot()
    def addTrack(self):
        frameCount = self.splitter.count()

        # Internal Splitter
        vSplitter = QSplitter(self.splitter)
        vSplitter.setOrientation(Qt.Vertical)
        # Adding a button
        button = QPushButton(vSplitter)
        button.setObjectName(u"button_ " +str(frameCount))
        button.clicked.connect(partial(self._addLines ,frameCount +1))
        frame = Frame(vSplitter ,self.well)
        # Adding Label tag
        label = QLabel(str(frameCount +1), vSplitter)
        label.setAlignment(Qt.AlignCenter)
        label.setFrameShape(QFrame.Panel)
        label.setFrameShadow(QFrame.Plain)
        label.setLineWidth(2)

        # Adding widgets to splitter
        vSplitter.addWidget(label)
        vSplitter.addWidget(button)
        vSplitter.addWidget(frame)

        self.connect(vSplitter, SIGNAL("splitterMoved(int, int)"), lambda x : self.splitterMoved(vSplitter))
        self.lSplit.append(vSplitter)

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

        self.splitter.addWidget(vSplitter)
        # vSplitter.setSizes(self.lSplit[0].sizes())
        # self.splitter.update()
        # Saving over frame
        # frame.mouseReleaseEvent = lambda event: self.setOverFrame(frame)
        # Calculate the size for each frame
        sizes = []
        fSize = (self.width( ) -self.track2Size ) /self.splitter.count()
        i = 0
        for s in range(self.splitter.count()):
            if i == 1:
                sizes.append(self.track2Size)
            else:
                sizes.append(fSize)
            i += 1
        self.splitter.setSizes(sizes)

        # Adding Well's Tracks
        wellTrack = Track()
        self.well.addTrack(wellTrack)
        frame.track = self.well.tracks[-1]
        frame.minVal = self.well.tracks[-1].minVal
        frame.maxVal = self.well.tracks[-1].maxVal
        button.setTrack(self.well.tracks[-1])

        # Resize all the another Splitters
        for r in self.lSplit:
            # if self.lSplit[0] is not r:
            r.blockSignals(True)
            r.setSizes(self.lSplit[0].sizes())
            r.blockSignals(False)

    @Slot()
    def delTrack(self):
        # Remove last track
        self.lSplit.pop()
        self.lTracks.pop()
        self.well.popTrack()
        self.splitter.widget(self.splitter.count( ) -1).deleteLater()

    @Slot()
    def _addLines(self ,track):
        dialog = addCurveWindow(self ,track)
        dialog.exec_()
        # dialog.show()

    def splitterMoved(self, sender):
        # Resize all the another Splitters
        for r in self.lSplit:
            if sender is not r:
                r.blockSignals(True)
                r.setSizes(sender.sizes())
                r.blockSignals(False)

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
