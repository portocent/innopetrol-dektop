# import sys
from PySide2 import QtWidgets
from src.GUI import Ui_MainWindow
from PySide2 import QtGui
import types
from src.lasProcesor import Well, Track, Line, Grid
from src.addCurveGUI import Ui_addCurve
from PySide2.QtCore import (QDate, QDateTime, QMetaObject,
                            QObject, QPoint, QRect, QSize, QTime, Qt,
                            Slot, SIGNAL)
from PySide2.QtGui import (QBrush, QColor, QIcon, QPalette, QPen)
from PySide2.QtWidgets import (QFrame, QAction, QWidget, QApplication,
                               QGridLayout, QSplitter, QPushButton, 
                               QTreeWidgetItem, QLabel, QComboBox, QCheckBox,
                               QHBoxLayout, QTableWidgetItem, QApplication,
                               QColorDialog, QDoubleSpinBox, QItemDelegate)
from src.myGuiClasses import Frame, Label
import os
from functools import partial


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
        file = QtWidgets.QFileDialog.getOpenFileName(self, "Open LAS", "Default File", "*.las")
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
        subwindow = subWindowWell(self,well)
        self.mdiArea.addSubWindow(subwindow)
        strId = "# " + str(self.countSubW+1) + " " + name
        self.countSubW = self.countSubW + 1
        subwindow.setWindowTitle(strId)        
        # subwindow.setWell(well)
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
    def __init__(self, parent,well = None):
        # Sub Windows start here
        super().__init__()
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
        button.clicked.connect(partial(self._addLines,1))
        button2 = QPushButton(vSplitter2)
        button2.clicked.connect(partial(self._addLines,2))
        # button.clicked.connect(lambda:self.whichbtn(self.b2))
        
        frame = Frame(vSplitter,self.well.header)
        vSplitter.addWidget(label)
        vSplitter.addWidget(button)
        vSplitter.addWidget(frame)
        self.lSplit.append(vSplitter)
        self.lSplit.append(vSplitter2)
        # frame.setObjectName(u"frame")
        # Set frame and button names
        frame.setObjectName(u"Track_"+str(self.splitter.count()))
        button.setObjectName(u"button_"+str(self.splitter.count()))
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
        frame_2 = Frame(vSplitter2,self.well.header,True)
        vSplitter2.addWidget(label2)
        vSplitter2.addWidget(button2)
        vSplitter2.addWidget(frame_2)
        # frame_2.setObjectName(u"frame_2")
        frame_2.setObjectName(u"Track_"+str(self.splitter.count()))
        button2.setObjectName(u"button_"+str(self.splitter.count()))
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


        # set init sizes
        initSize = [20, 50, self.height() - 70]
        vSplitter.setSizes(initSize)
        vSplitter2.setSizes(initSize)
        initHorizontalSize = [self.width()-self.track2Size, self.track2Size]
        self.splitter.setSizes(initHorizontalSize)


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
        button.setObjectName(u"button_"+str(frameCount))
        button.clicked.connect(partial(self._addLines,frameCount+1))
        frame = Frame(vSplitter,self.well.header)
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
        
        self.connect(vSplitter, SIGNAL("splitterMoved(int, int)"), lambda x : self.splitterMoved(vSplitter))
        self.lSplit.append(vSplitter)

        frame.setObjectName(u"Track_"+str(frameCount))
        
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
        fSize = (self.width()-self.track2Size)/self.splitter.count()
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
        self.splitter.widget(self.splitter.count()-1).deleteLater()

    @Slot()
    def _addLines(self,track):
        dialog = addCurveWindow(self,track)
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
        # Adding Well's Tracks
        wellTrack1 = Track()
        wellTrack2 = Track()
        self.well.addTrack(wellTrack1)
        self.well.addTrack(wellTrack2)

class addCurveWindow(QtWidgets.QDialog, Ui_addCurve):
    def __init__(self, subwindow, track):
        super().__init__(subwindow)
        self.setupUi(self)
        self.parent = subwindow
        self.trackNum = track
        self.setWindowTitle(str(self.parent.windowTitle()) + " - Track " + str(track))
        # self.wells = []
        self.setWindowIcon(QIcon("statics\\images\\LOGO-08.png"))
        self.loadWellData()
        self.okButton.clicked.connect(self.clickOkButton)

        # self.subwindow.paintEvent = types.MethodType(paintSub,self.subwindow)

    
    def loadWellData(self):
        well = self.parent.well
        items = []
        items = well.df.columns
        logopt = [" ","Lineal","Log"]
        linesOpt = [QIcon("statics\\images\\solid.png"), QIcon("statics\\images\\dash.png"),
        QIcon("statics\\images\\dashdot.png"),QIcon("statics\\images\\dot.png"), 
        QIcon("statics\\images\\dashdotdot.png")]
        widthOpt = [1,2,3,4,5,6,7,8]
        iconSizeLine = QSize(95, 21)
        iconSize = QSize(91, 30)
        self.rowColor = []
        realFormat = RealDelegate()
        self.tableWidget.setItemDelegateForColumn(1,realFormat)
        self.tableWidget.setItemDelegateForColumn(2,realFormat)
        self.tableWidget_2.setItemDelegateForColumn(1,realFormat)
        self.tableWidget_2.setItemDelegateForColumn(3,realFormat)

        comboList = []
        comboWidthList = []
        comboLinesList = []
        checkBoxLines = []
        colorButtonList = []
        comboBrushList = []
        colorButton2List = []
        comboLcurve = []
        comboRcurve = []

        # combo box
        for i in range(16):
            # Tag Curvas ###########################################
            
            # Combo Box
            combo = QComboBox(self.tableWidget)
            # Disable all except first
            # if i != 0:
            #     combo.setEnabled(False)
            comboLog = QComboBox(self)
            comboLines = QComboBox(self)
            comboLines.setIconSize(iconSizeLine)
            comboWidth = QComboBox(self)
            combo.addItem(" ")
            # CheckBox
            cell_widget = QWidget()
            lay_out = QHBoxLayout(cell_widget) 
            check = QCheckBox(self)
            lay_out.addWidget(check)
            lay_out.setAlignment(Qt.AlignCenter)
            lay_out.setContentsMargins(0,0,0,0)
            cell_widget.setLayout(lay_out)
            # Addig the color choice
            colorButton = QPushButton("Color",self.tableWidget)
            label = Label(self.tableWidget)

            
            # self.rowColor.append("#000000")
            for op in items:
                combo.addItem(op)
            for op in logopt:
                comboLog.addItem(op)
            count = 0
            for op in linesOpt:
                comboLines.addItem(op,str(count))
                count+=1
            for op in widthOpt:
                comboWidth.addItem(str(op))               
            self.tableWidget.setCellWidget(i,0,combo)
            self.tableWidget.setCellWidget(i,3,cell_widget)
            self.tableWidget.setCellWidget(i,4,comboLog)
            self.tableWidget.setCellWidget(i,5,colorButton)
            self.tableWidget.setCellWidget(i,6,comboWidth)
            self.tableWidget.setCellWidget(i,7,comboLines)
            self.tableWidget.setCellWidget(i,8,label)
            


            # Tag Sombras ################################
            
            # Combo Box
            lCurve = QComboBox()
            lCurve.addItem(" ")
            rCurve = QComboBox()
            rCurve.addItem(" ")
            comboBrush = QComboBox()
            
            comboBrush.setIconSize(iconSize)
            comboBrush.addItem(" ")
            comboBrush.addItem(QIcon("statics\\images\\d1.png"),"1")
            comboBrush.addItem(QIcon("statics\\images\\d2.png"),"2")
            comboBrush.addItem(QIcon("statics\\images\\d3.png"),"3")
            comboBrush.addItem(QIcon("statics\\images\\d4.png"),"4")
            comboBrush.addItem(QIcon("statics\\images\\d5.png"),"5")
            comboBrush.addItem(QIcon("statics\\images\\d6.png"),"6")
            comboBrush.addItem(QIcon("statics\\images\\d7.png"),"7")
            comboBrush.addItem(QIcon("statics\\images\\d8.png"),"8")
            comboBrush.addItem(QIcon("statics\\images\\d9.png"),"9")
            comboBrush.addItem(QIcon("statics\\images\\d10.png"),"10")
            for op in items:
                lCurve.addItem(op)
                rCurve.addItem(op)
            # Visible CheckBox
            checkWidget = QWidget()
            lay_out2 = QHBoxLayout(checkWidget) 
            check2 = QCheckBox()
            lay_out2.addWidget(check2)
            lay_out2.setAlignment(Qt.AlignCenter)
            lay_out2.setContentsMargins(0,0,0,0)
            checkWidget.setLayout(lay_out2)
            label2 = Label()
            label2.isBrush = True
            # Shading Color
            colorButton2 = QPushButton("Color")

            # Filling Shading table
            self.tableWidget_2.setCellWidget(i,0,lCurve)
            self.tableWidget_2.setCellWidget(i,2,rCurve)
            self.tableWidget_2.setCellWidget(i,4,checkWidget)
            self.tableWidget_2.setCellWidget(i,5,colorButton2)
            self.tableWidget_2.setCellWidget(i,6,comboBrush)
            self.tableWidget_2.setCellWidget(i,7,label2)
            comboList.append(combo)
            comboWidthList.append(comboWidth)
            comboLinesList.append(comboLines)
            colorButtonList.append(colorButton)
            comboBrushList.append(comboBrush)
            colorButton2List.append(colorButton2)
            checkBoxLines.append(check)
            comboLcurve.append(lCurve)
            comboRcurve.append(rCurve)

        # Out of For  
        # Load states
        self.loadLines()
        self.loadGrids()
        for i in range(16):
            # Events Lines
            comboList[i].currentIndexChanged.connect(self.paintLabel)
            comboWidthList[i].currentIndexChanged.connect(self.setWidthPen)
            comboLinesList[i].currentIndexChanged.connect(self.setStylePen)
            colorButtonList[i].clicked.connect(self.color_picker)
            checkBoxLines[i].clicked.connect(self.enableLabel)
            # Events Brush
            comboBrushList[i].currentIndexChanged.connect(self.setStyleBrush)
            colorButton2List[i].clicked.connect(self.color_pickerS)
            comboRcurve[i].currentIndexChanged.connect(self.pickLineGrid)
            comboLcurve[i].currentIndexChanged.connect(self.pickLineGrid)


    def loadLines(self):
        row = 0
        lines = self.parent.well.tracks[self.trackNum - 1].lines
        for linea in lines:
            name = linea.nameIndex
            width = linea.grosorIndex
            penType = linea.estiloIndex
            log = linea.logIndex
            visible = linea.visible
            l = linea.lScale
            r = linea.rScale
            check = self.tableWidget.cellWidget(row, 3).findChildren(QCheckBox)
            
            # Setting Options
            self.tableWidget.cellWidget(row,0).setCurrentIndex(name)

            rItem = QTableWidgetItem()
            rItem.setData(Qt.DisplayRole,r)
            lItem = QTableWidgetItem()
            lItem.setData(Qt.DisplayRole,l)
            self.tableWidget.setItem(row,2,rItem)
            self.tableWidget.setItem(row,1,lItem)
            self.tableWidget.cellWidget(row,4).setCurrentIndex(log)
            self.tableWidget.cellWidget(row,6).setCurrentIndex(width)
            self.tableWidget.cellWidget(row,7).setCurrentIndex(penType)
            label = self.tableWidget.cellWidget(row,8)
            check[0].setChecked(linea.visibleCheck)
            label.penColor = linea.color
            label.penType = linea.estilo 
            label.penSize = linea.grosor
            label.isBrush = False
            label.visible = True
            # self.tableWidget.removeCellWidget(row,8)
            # self.tableWidget.setCellWidget(row,8,label)
            label.update()
            row += 1

    @Slot()
    def clickOkButton(self):
        errorLines = self.passValidateLines()
        errorGrids = self.passValidateGrids()
        if not errorLines and not errorGrids:
            self.saveLines()
            self.saveGrids()
            self.close()
        else:
            msg_box = QtWidgets.QMessageBox()
            msg_box.setIcon(QtWidgets.QMessageBox.Information)
            msg_box.setWindowIcon(QIcon("statics\\images\\LOGO-08.png"))
            msg_box.setText(errorLines +"\n" + errorGrids)
            msg_box.setWindowTitle("Error en los campos")
            msg_box.setStandardButtons(QtWidgets.QMessageBox.Close)
            msg_box.exec_()


    def saveLines(self):

        self.parent.well.tracks[self.trackNum - 1].lines = []
        for row in range(16):
            name = self.tableWidget.cellWidget(row,0).currentText()
            nameIndex = self.tableWidget.cellWidget(row,0).currentIndex()
            if name != " ":

                l = self.tableWidget.item(row, 1).text()
                r = self.tableWidget.item(row, 2).text()
                check = self.tableWidget.cellWidget(row, 3).findChildren(QCheckBox)
                log = self.tableWidget.cellWidget(row,4).currentText()
                logIndex = self.tableWidget.cellWidget(row,4).currentIndex()
                label = self.tableWidget.cellWidget(row,8)
                widthIndex = self.tableWidget.cellWidget(row,6).currentIndex()
                styleIndex = self.tableWidget.cellWidget(row,7).currentIndex()


                linea = Line()
                linea.name = name
                linea.nameIndex = nameIndex
                linea.color = label.penColor
                linea.grosor = label.penSize
                linea.grosorIndex = widthIndex
                linea.estilo = label.penType
                linea.estiloIndex = styleIndex
                linea.log = log
                linea.logIndex = logIndex
                linea.visibleCheck = check[0].isChecked()
                linea.lScale = float(l)
                linea.rScale = float(r)
                self.parent.well.tracks[self.trackNum - 1].lines.append(linea)
                # wellTrack.append(linea)
                # print("Fin")

    def passValidateLines(self):
        for row in range(16):
            name = self.tableWidget.cellWidget(row,0).currentText()
            l = self.tableWidget.item(row, 1)
            r = self.tableWidget.item(row, 2)
            log = self.tableWidget.cellWidget(row,4).currentText()
            if name != " ":
                if l is None or r is None:
                    return "Escala vacía"
                else:
                    leftS = float(l.text())
                    rightS = float(r.text())
                if leftS >= rightS:
                    return "Escala izquierda inferior o igual a la derecha"
                if log == " ":
                    # if leftS <= 0
                    return "Tipo de lína no seleccionada: Log/Lineal"
        return ""

    def loadGrids(self):
        row = 0
        grids = self.parent.well.tracks[self.trackNum - 1].grids
        for grid in grids:
            leftLine = grid.leftLineIndex
            leftVal = grid.leftVal
            rightLine = grid.rightLineIndex
            rightVal = grid.rightVal
            checkVal = grid.check
            brush = grid.brushIndex
            penType = grid.brush
            penColor = grid.color

            check = self.tableWidget_2.cellWidget(row, 4).findChildren(QCheckBox)
            check[0].setChecked(checkVal)
            self.tableWidget_2.cellWidget(row, 0).setCurrentIndex(leftLine)
            self.tableWidget_2.cellWidget(row, 2).setCurrentIndex(rightLine)
            self.tableWidget_2.cellWidget(row, 6).setCurrentIndex(brush)
            label = self.tableWidget_2.cellWidget(row, 7)
            if leftLine == 0:
                lItem = QTableWidgetItem()
                lItem.setData(Qt.DisplayRole,leftVal)
                self.tableWidget_2.setItem(row, 1, lItem)
            if rightLine == 0:
                rItem = QTableWidgetItem()
                rItem.setData(Qt.DisplayRole,rightVal)
                self.tableWidget_2.setItem(row, 3, rItem)
            label.isBrush = True
            label.penType = penType
            label.penColor = penColor
            label.visible = True
            label.update()

            row += 1


    def saveGrids(self):
        self.parent.well.tracks[self.trackNum - 1].grids = []
        for row in range(15):
            namel = self.tableWidget_2.cellWidget(row, 0).currentText()
            namelIndex = self.tableWidget_2.cellWidget(row, 0).currentIndex()
            lv = self.tableWidget_2.item(row, 1)
            lvBool = False
            if not lv is None:
                if lv.text() == "":
                    lvBool = True
            else:
                lvBool = True

            if namel != " " or not lvBool:
                namer = self.tableWidget_2.cellWidget(row, 2).currentText()
                namerIndex = self.tableWidget_2.cellWidget(row, 2).currentIndex()
                rv = self.tableWidget_2.item(row, 3)
                fill = self.tableWidget_2.cellWidget(row, 6).currentIndex()
                check = self.tableWidget_2.cellWidget(row, 4).findChildren(QCheckBox)
                label = self.tableWidget_2.cellWidget(row, 7)
                description = ""
                if not self.tableWidget_2.item(row, 3) is None:
                    description = self.tableWidget_2.item(row, 3).text()


                grid = Grid()
                grid.leftLineIndex = namelIndex
                grid.leftLine = namel
                if namelIndex == 0:
                    grid.leftVal = float(lv.text())
                grid.rightLineIndex = namerIndex
                grid.rightLine = namer
                if namerIndex == 0:
                    grid.rightVal = float(rv.text())
                grid.check = check[0].isChecked()
                grid.color = label.penColor
                grid.brush = label.penType
                grid.brushIndex = fill
                grid.description = description
                self.parent.well.tracks[self.trackNum - 1].grids.append(grid)
                # wellTrack.append(linea)
                # print("Fin")

    def passValidateGrids(self):
        for row in range(15):
            namel = self.tableWidget_2.cellWidget(row,0).currentText()
            namer = self.tableWidget_2.cellWidget(row, 2).currentText()
            lv = self.tableWidget_2.item(row, 1)
            lvBool = False
            rv = self.tableWidget_2.item(row, 3)
            rvBool = False
            fill = self.tableWidget_2.cellWidget(row,6).currentText()
            if not lv is None:
                if lv.text() == "":
                    lvBool = True
            else:
                lvBool = True

            if not rv is None:
                if rv.text() == "":
                    rvBool = True
            else:
                rvBool = True

            if not lvBool or namel != " ":
                if rvBool and namer == " ":
                    return "Debe seleccionar una linea derecha o ingresar un valor fijo"
                if fill == " ":
                    return "Debe seleccionar un patrón de relleno"


        return ""

    @Slot()
    def pickLineGrid(self, ix):
        # combo = self.sender()
        clickme = QApplication.focusWidget()
        index = self.tableWidget_2.indexAt(clickme.pos())
        i = index.row()
        j = index.column()
        name = self.tableWidget_2.cellWidget(i, j).currentText()
        item = QTableWidgetItem()
        flags = item.flags()
        self.tableWidget_2.setItem(i, j + 1,item)

        if name != " ":
            flags = flags & ~Qt.ItemIsEnabled
            item.setFlags(flags)
        else:
            item.setFlags(flags)



    @Slot()
    def enableLabel(self):
        # combo = self.sender()
        clickme = QApplication.focusWidget()
        index = self.tableWidget.indexAt(clickme.pos())
        i = index.row()
        checkBox = self.tableWidget.cellWidget(i, 3).findChildren(QCheckBox)
        label = self.tableWidget.cellWidget(i,8)
        label.visibleCheck = checkBox[0].isChecked()
        label.update()

    @Slot()
    def paintLabel(self, ix):
        # combo = self.sender()
        clickme = QApplication.focusWidget()
        index = self.tableWidget.indexAt(clickme.pos())
        i = index.row()
        label = self.tableWidget.cellWidget(i,8)        

        if ix != 0 :
            label.visible = True
            # if i < 15:
            #     nextCombo = self.tableWidget.cellWidget(i+1,0)
                # nextCombo.setEnabled(True)
            label.update()
        else:
            label.visible = False
            label.update()

    @Slot()
    def setStylePen(self, ix):
        clickme = QApplication.focusWidget()
        index = self.tableWidget.indexAt(clickme.pos())
        i = index.row()
        label = self.tableWidget.cellWidget(i,8) 
        switcher = {
            0: Qt.SolidLine,
            1: Qt.DashLine,
            2: Qt.DashDotLine,
            3: Qt.DotLine,
            4: Qt.DashDotDotLine
        }      
        label.penType = switcher.get(ix)
        label.update()

    @Slot()
    def setWidthPen(self, ix):
        # combo = self.sender()
        clickme = QApplication.focusWidget()
        index = self.tableWidget.indexAt(clickme.pos())
        i = index.row()
        label = self.tableWidget.cellWidget(i,8) 
        label.penSize = ix+1
        label.update()
          
    @Slot()
    def color_picker(self):
        # Get clicked widget
        clickme = QApplication.focusWidget()
        color = QColorDialog.getColor()

        if color.isValid():
            button = QPushButton("Seleccionar Color")
            # get clicked widget Pos
            index = self.tableWidget.indexAt(clickme.pos())
            
            i = index.row()
            label = self.tableWidget.cellWidget(i,8)

            button.clicked.connect(self.color_picker)
            label.penColor = color
            self.tableWidget.setCellWidget(i,5,button)
            # self.rowColor[i-1] = color

################ Shading Events ######################
    @Slot()
    def setStyleBrush(self, ix):
        clickme = QApplication.focusWidget()
        index = self.tableWidget_2.indexAt(clickme.pos())
        i = index.row()
        label = self.tableWidget_2.cellWidget(i,7)
        switcher = {
            0: Qt.SolidPattern,
            1: Qt.SolidPattern,
            2: Qt.Dense1Pattern,
            3: Qt.Dense2Pattern,
            4: Qt.Dense3Pattern,
            5: Qt.Dense5Pattern,
            6: Qt.Dense6Pattern,
            7: Qt.HorPattern,
            8: Qt.VerPattern,
            9: Qt.BDiagPattern,
            10: Qt.DiagCrossPattern
        }
        label.penType = switcher.get(ix)
        if ix != 0:
                label.visible = True
        else:
                label.visible = False
        label.update()              
                   
    @Slot()
    def color_pickerS(self):
        # Get clicked widget
        clickme = QApplication.focusWidget()
        color = QColorDialog.getColor()

        if color.isValid():
            index = self.tableWidget_2.indexAt(clickme.pos())
            i = index.row()
            label = self.tableWidget_2.cellWidget(i,7)
            label.penColor = color
            # if label.visible:
            label.update()

class RealDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        realSpinBox = QDoubleSpinBox(parent)
        realSpinBox.setMinimum(-100000)
        realSpinBox.setMaximum(100000)
        # realSpinBox.setValue()
        return realSpinBox




# app = QtWidgets.QApplication(sys.argv)
if __name__ == '__main__':
    MainEventThread = QApplication([])
    window = MainWindow()

    window.show()

    MainEventThread.exec_()
# app.exec_()
