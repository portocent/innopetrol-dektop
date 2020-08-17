# import sys
from PySide2 import QtWidgets
from GUI import Ui_MainWindow
from PySide2 import QtGui
import types
from lasProcesor import Well
from PySide2.QtCore import (QDate, QDateTime, QMetaObject,
                            QObject, QPoint, QRect, QSize, QTime, Qt,
                            Slot, SIGNAL)
from PySide2.QtGui import (QBrush, QColor, QIcon, QPalette, QPen)
from PySide2.QtWidgets import (QFrame, QAction, QWidget, QApplication,
                               QGridLayout, QSplitter, QPushButton, 
                               QTreeWidgetItem, QLabel)
import os


def paintSub(self, event):
    painter = QtGui.QPainter(self)
    brush = QBrush()
    brush.setColor(QtGui.QColor('black'))
    brush.setStyle(Qt.SolidPattern)
    # rect = QRect(0, 0, self.width()-2, self.height()-2)
    # painter.drawRect()
    # currentSize = self.frameGeometry()
    # painter.setPen(QPen(Qt.black, 3, Qt.SolidLine))
    # painter.drawRect(1, 1, self.width()-2, self.height()-2)
    # painter.drawRect(1, 1, self.width()-2, 25)


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        # self.wells = []
        self.setWindowIcon(QIcon("statics\\images\\LOGO-08.png"))
        # self.subwindow.paintEvent = types.MethodType(paintSub,self.subwindow)
        self.menuOptions()
        self.statusBar().showMessage('Ready')
        self.countSubW = 0

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
            self.addSubWindow(well, fileName)
            self.fillTreeWell(fileName)
            self.show_about_dialog(title, msg)
            
        else:
            if file[0]:
                msg = str(fileName)+" no pudo ser cargado archivo inválido:" \
                     + error
                self.show_about_dialog(title, msg)

    def show_about_dialog(self, title, msg):
        msg_box = QtWidgets.QMessageBox()
        msg_box.setIcon(QtWidgets.QMessageBox.Information)
        msg_box.setWindowIcon(QIcon("statics\\images\\LOGO-08.png"))
        msg_box.setText(msg)
        msg_box.setWindowTitle(title)
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Close)
        msg_box.exec_()

    def addSubWindow(self, well, name):
        subwindow = subWindowWell(self)
        self.mdiArea.addSubWindow(subwindow)
        strId = "# " + str(self.countSubW+1) + " " + name
        self.countSubW = self.countSubW + 1
        subwindow.setWindowTitle(strId)        
        subwindow.setWell(well)
        subwindow.show()
    
    def fillTreeWell(self, wellName):
        # __sortingEnabled = self.treeWidget.isSortingEnabled()
        qtreewidgetitem1 = QTreeWidgetItem(self.treeWidget)
        self.treeWidget.setSortingEnabled(False)
        qtreewidgetitem1 = self.treeWidget.topLevelItem(len(self.mdiArea.subWindowList())-1)
        strId = "# " + str(self.countSubW) + " " + wellName
        qtreewidgetitem1.setText(0, strId)
        # ___qtreewidgetitem2 = ___qtreewidgetitem1.child(0)
        # ___qtreewidgetitem2.setText(
        #     0, QCoreApplication.translate("MainWindow", u"Lines", None))
        # ___qtreewidgetitem3 = ___qtreewidgetitem2.child(0)
        # ___qtreewidgetitem3.setText(
        #     0, QCoreApplication.translate("MainWindow", u"Cali", None))
        # ___qtreewidgetitem4 = ___qtreewidgetitem1.child(1)
        # ___qtreewidgetitem4.setText(
        #     0, QCoreApplication.translate("MainWindow", u"Fills", None))
        # ___qtreewidgetitem5 = ___qtreewidgetitem4.child(0)
          

class subWindowWell(QWidget):
    def __init__(self, parent):
        # Sub Windows start here
        super().__init__()
        self.parent = parent
        self.lTracks = []
        self.lSplit = []
        self.setObjectName(u"subwindow")
        # self.setMinimumSize(QSize(200, 475))
        self.setMinimumSize(QSize(200, 200))
        self.gridLayout = QGridLayout(self)
        self.gridLayout.setObjectName(u"gridLayout")
        self.splitter = QSplitter(self)
        # self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        
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
        button = QPushButton(vSplitter)
        button2 = QPushButton(vSplitter2)
        # button.clicked.connect(lambda:self.whichbtn(self.b2))
        
        frame = QFrame(vSplitter)
        vSplitter.addWidget(label)
        vSplitter.addWidget(button)
        vSplitter.addWidget(frame)
        self.lSplit.append(vSplitter)
        self.lSplit.append(vSplitter2)
        # frame.setObjectName(u"frame")
        # Set frame and button names
        frame.setObjectName(u"Track_"+str(self.splitter.count()))
        button.setObjectName(u"button"+str(self.splitter.count()))
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
        frame_2 = QFrame(vSplitter2)
        vSplitter2.addWidget(label2)
        vSplitter2.addWidget(button2)
        vSplitter2.addWidget(frame_2)
        # frame_2.setObjectName(u"frame_2")
        frame_2.setObjectName(u"Track_"+str(self.splitter.count()))
        button2.setObjectName(u"Track_"+str(self.splitter.count()))
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
        frame.paintEvent = types.MethodType(paintSub, frame)
        self.lTracks.append(frame)
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

        # Buttons options
        # button.setText(str(button.objectName))
        # button2.setText(str(button.objectName))

        # set init sizes
        initSize = [20, 50, self.height() - 75]
        vSplitter.setSizes(initSize)
        vSplitter2.setSizes(initSize)

    #   S H O W   P O P U P   M E N U
    def setOverFrame(self, frame):
        self.onFrame = frame

    def showPopup(self, position):
        self.popMenu.exec_(self.mapToGlobal(position))

    @Slot()
    def addTrack(self):
        frameCount = self.splitter.count()

        # Internal Splitter
        vSplitter = QSplitter()
        vSplitter.setOrientation(Qt.Vertical)        
        # Adding a button
        button = QPushButton(vSplitter)
        frame = QFrame(vSplitter)
        # Adding Label tag
        label = QLabel(str(frameCount+1), vSplitter)
        label.setAlignment(Qt.AlignCenter)
        label.setFrameShape(QFrame.Panel)
        label.setFrameShadow(QFrame.Plain)
        label.setLineWidth(2)

        # Adding widgets to splitter
        vSplitter.addWidget(label)
        vSplitter.addWidget(button)
        vSplitter.addWidget(frame)
        vSplitter.setSizes(self.lSplit[0].sizes())
        self.connect(vSplitter, SIGNAL("splitterMoved(int, int)"), lambda x : self.splitterMoved(vSplitter))
        self.lSplit.append(vSplitter)

        frame.setObjectName(u"Track_"+str(frameCount))
        button.setObjectName(u"Track_"+str(frameCount))
        # button.setText(str(button.objectName))
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
        self.lSplit.pop()
        self.lTracks.pop()
        self.splitter.widget(self.splitter.count()-1).deleteLater()

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
        if retval == 1024: #write your required condition/check 
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

    def setWell(self, well):
        self.well = well


# app = QtWidgets.QApplication(sys.argv)
if __name__ == '__main__':
    MainEventThread = QApplication([])
    window = MainWindow()

    window.show()

    MainEventThread.exec_()
# app.exec_()
