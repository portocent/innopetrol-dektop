# import sys
from PySide2 import QtWidgets
from GUI import Ui_MainWindow
from PySide2 import QtGui
import types
from lasProcesor import Well
from PySide2.QtCore import (QDate, QDateTime, QMetaObject,
                            QObject, QPoint, QRect, QSize, QTime, Qt,
                            Slot)
from PySide2.QtGui import (QBrush, QColor, QIcon, QPalette, QPen)
from PySide2.QtWidgets import (QFrame, QAction, QWidget, QApplication,
                               QGridLayout, QSplitter, QPushButton)
import os


def paintSub(self, event):
    painter = QtGui.QPainter(self)
    brush = QBrush()
    brush.setColor(QtGui.QColor('black'))
    brush.setStyle(Qt.SolidPattern)
    # rect = QRect(0, 0, self.width()-2, self.height()-2)
    # painter.drawRect()
    # currentSize = self.frameGeometry()
    painter.setPen(QPen(Qt.black, 3, Qt.SolidLine))
    painter.drawRect(1, 1, self.width()-2, self.height()-2)
    painter.drawRect(1, 1, self.width()-2, 25)


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.wells = []
        self.setWindowIcon(QIcon("statics\\images\\LOGO-08.png"))
        # self.subwindow.paintEvent = types.MethodType(paintSub,self.subwindow)
        self.menuOptions()
        self.statusBar().showMessage('Ready')

    def menuOptions(self):
        # Open Well
        addWellAction = self.actionOpen_Well
        addWellAction.setShortcut('Ctrl+O')
        addWellAction.setStatusTip('Open Well...')       
        addWellAction.triggered.connect(self._browseFile)
        self.menuMenu.removeAction(self.actionOpen_Well)
        self.actionOpen_Well = None
        self.actionOpen_Well = addWellAction
        self.menuMenu.addAction(self.actionOpen_Well)
        # self.actionOpen_Well

    @Slot()
    def _browseFile(self):
        file = QtWidgets.QFileDialog.getOpenFileName(self, "Open LAS", "Default File", "All Files(*)")
        head, fileName = os.path.split(file[0])
        error = ""
        title = "Loading LAS file"
        well = Well()
        error = well.loadLas(file[0], fileName)
        if not error:
            msg = str(fileName)+" cargado correctamente"
            # self.wells.append(well)
            self.addSubWindow(well)
            self.show_about_dialog(title, msg)
        else:
            if file[0]:
                msg = str(fileName)+" no pudo ser cargado archivo inválido:" \
                     + error
                self.show_about_dialog(title, msg)

    def show_about_dialog(self, title, msg):
        msg_box = QtWidgets.QMessageBox()
        msg_box.setIcon(QtWidgets.QMessageBox.Information)
        msg_box.setText(msg)
        msg_box.setWindowTitle(title)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Close)
        msg_box.exec_()

    def addSubWindow(self, well):
        subwindow = subWindowWell()
        self.mdiArea.addSubWindow(subwindow)
        subwindow.setWell(well)
        subwindow.show()


class subWindowWell(QWidget):
    def __init__(self):
        # Sub Windows start here
        super().__init__()
        self.lTracks = []
        self.setObjectName(u"subwindow")
        self.setMinimumSize(QSize(200, 475))
        self.gridLayout = QGridLayout(self)
        self.gridLayout.setObjectName(u"gridLayout")
        self.splitter = QSplitter(self)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        frame = QFrame(self.splitter)
        frame.setObjectName(u"frame")
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
        self.splitter.addWidget(frame)
        frame_2 = QFrame(self.splitter)
        frame_2.setObjectName(u"frame_2")
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
        self.splitter.addWidget(frame_2)
        self.gridLayout.addWidget(self.splitter, 0, 0, 1, 1)
        # Saving frame name
        frame.mouseReleaseEvent = lambda event: self.setOverFrame(frame)
        frame_2.mouseReleaseEvent = lambda event: self.setOverFrame(frame_2)
        # Adding the paint event for drawing
        frame.paintEvent = types.MethodType(paintSub, frame)
        self.lTracks.append(frame)
        self.lTracks.append(frame_2)

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

    #   S H O W   P O P U P   M E N U
    def setOverFrame(self, frame):
        self.onFrame = frame

    def showPopup(self, position):
        self.popMenu.exec_(self.mapToGlobal(position))

    @Slot()
    def addTrack(self):
        frameCount = self.splitter.count()
        frame = QFrame(self.splitter)
        frame.setObjectName(u"Track_"+frameCount)
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
        self.splitter.addWidget(frame)
        # self.splitter.update()
        # Saving over frame
        frame.mouseReleaseEvent = lambda event: self.setOverFrame(frame)
        # Calculate the size for each frame
        sizes = []
        fSize = self.width()/self.splitter.count()
        for s in range(self.splitter.count()):
            sizes.append(fSize)
        self.splitter.setSizes(sizes)

    @Slot()
    def delTrack(self):
        # print("del Track Pressed" + str(self.onFrame))
        # Remove over click track
        # self.onFrame.deleteLater()
        # Remove last track
        self.splitter.widget(self.splitter.count()-1).deleteLater()

        # self.frame.paintEvent = types.MethodType(paintSub, self.frame)
    # def mousePressEvent(self, QMouseEvent):
    #     if QMouseEvent.button() == Qt.LeftButton:
    #         print("Left Button Clicked")
    #     elif QMouseEvent.button() == Qt.RightButton:
    #         #do what you want here
    #         print("Right Button Clicked")
    #         self.popMenu.exec_(self.button.mapToGlobal(point))

    def setWell(self, well):
        self.well = well


# app = QtWidgets.QApplication(sys.argv)
if __name__ == '__main__':
    MainEventThread = QApplication([])
    window = MainWindow()

    window.show()

    MainEventThread.exec_()
# app.exec_()
