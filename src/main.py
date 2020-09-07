# import sys
from PySide2 import QtWidgets
from src.GUI import Ui_MainWindow
from src.lasProcesor import Well
from src.subWindowScroll import subWindowWell
from PySide2.QtCore import ( Slot)
from PySide2.QtGui import (QIcon, Qt, QMouseEvent)
from PySide2.QtWidgets import (QTreeWidgetItem, QApplication)
import os


class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.setWindowIcon(QIcon("statics\\images\\LOGO-08.png"))
        self.menuOptions()
        self.statusBar().showMessage('Ready')
        self.countSubW = 0
        self.mdiArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdiArea.setVerticalScrollBarPolicy(Qt.ScrollBarAsNeeded)
        self.mdiArea.verticalScrollBar().setSingleStep(1)




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
        title = "Loading LAS file"
        well = Well()
        error = well.loadLas(file[0], fileName)
        if not error:
            msg = str(fileName)+" cargado correctamente"
            # self.wells.append(well)
            self.addSubWindow(well, fileName)
            self.fillTreeWell(fileName,well)
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

    def addSubWindow(self, well:Well, name):
        subwindow = subWindowWell(self,well)
        self.mdiArea.addSubWindow(subwindow)
        strId = "# " + str(self.countSubW+1) + " " + name
        self.countSubW = self.countSubW + 1
        subwindow.setWindowTitle(strId)        
        # subwindow.setWell(well)
        subwindow.show()



    def fillTreeWell(self, wellName,well:Well):
        # __sortingEnabled = self.treeWidget.isSortingEnabled()
        qtreewidgetitem1 = QTreeWidgetItem(self.treeWidget)

        self.treeWidget.setSortingEnabled(False)
        qtreewidgetitem1 = self.treeWidget.topLevelItem(len(self.mdiArea.subWindowList())-1)
        strId = "# " + str(self.countSubW) + " " + wellName
        qtreewidgetitem1.setText(0, strId)

        qtreewidgetitem2 = QTreeWidgetItem(qtreewidgetitem1)
        qtreewidgetitem3 = QTreeWidgetItem(qtreewidgetitem1)
        qtreewidgetitem4 = QTreeWidgetItem(qtreewidgetitem1)
        qtreewidgetitem2 = qtreewidgetitem1.child(0)
        qtreewidgetitem2.setText(0, "Info Pozo")
        # Info Pozo
        i = 0
        for p in well.las.well:
            qtreewidgetitemline = QTreeWidgetItem(qtreewidgetitem2)
            qtreewidgetitemline = qtreewidgetitem2.child(i)
            qtreewidgetitemline.setText(0,str(p.mnemonic)+": "+str(p.value) + " "+str(p.unit))
            i+=1
        qtreewidgetitem3 = qtreewidgetitem1.child(1)
        qtreewidgetitem3.setText(0, "Lineas")
        i = 0
        for l in well.las.curves:
            if not str(l.mnemonic).startswith("DEPT"):
                stats = well.stats[l.mnemonic]
                minVal = stats['min']
                maxVal = stats['max']
            qtreewidgetitemline = QTreeWidgetItem(qtreewidgetitem3)
            qtreewidgetitemline = qtreewidgetitem3.child(i)
            qtreewidgetitemline.setText(0,str(l.mnemonic))
            # Lines info
            qtreewidgetitemUnit = QTreeWidgetItem(qtreewidgetitemline)
            qtreewidgetitemDesc = QTreeWidgetItem(qtreewidgetitemline)
            qtreewidgetitemUnit = qtreewidgetitemline.child(0)
            qtreewidgetitemDesc = qtreewidgetitemline.child(1)
            qtreewidgetitemUnit.setText(0, "Unit: " + str(l.unit))
            qtreewidgetitemDesc.setText(0, "Desc: " + str(l.descr))
            if not str(l.mnemonic).startswith("DEPT"):

                qtreewidgetitemMin = QTreeWidgetItem(qtreewidgetitemline)
                qtreewidgetitemMax = QTreeWidgetItem(qtreewidgetitemline)
                qtreewidgetitemMin = qtreewidgetitemline.child(2)
                qtreewidgetitemMax = qtreewidgetitemline.child(3)
                qtreewidgetitemMin.setText(0,"Min: "+str(minVal))
                qtreewidgetitemMax.setText(0, "Max: " + str(maxVal))
            else:
                qtreewidgetitemMin = QTreeWidgetItem(qtreewidgetitemline)
                qtreewidgetitemMax = QTreeWidgetItem(qtreewidgetitemline)
                qtreewidgetitemStep = QTreeWidgetItem(qtreewidgetitemline)
                qtreewidgetitemMin = qtreewidgetitemline.child(2)
                qtreewidgetitemMax = qtreewidgetitemline.child(3)
                qtreewidgetitemStep = qtreewidgetitemline.child(4)
                qtreewidgetitemMin.setText(0, "START: " + str(well.las.well.STRT.value))
                qtreewidgetitemMax.setText(0, "END: " + str(well.las.well.STOP.value))
                qtreewidgetitemStep.setText(0, "STEP: " + str(well.las.well.STEP.value))
            i+=1

        # qtreewidgetitem4 = qtreewidgetitem1.child(2)
        # qtreewidgetitem4.setText(0, "Rellenos")
        # ___qtreewidgetitem5 = ___qtreewidgetitem4.child(0)
    def mouseReleaseEvent(self, event:QMouseEvent):
        print("Released Daddy")

    def mousePressEvent(self, event:QMouseEvent):
        if event.button() == Qt.LeftButton:
            print("Pressed Daddy")



# app = QtWidgets.QApplication(sys.argv)
if __name__ == '__main__':
    MainEventThread = QApplication([])
    window = MainWindow()

    window.show()

    MainEventThread.exec_()
# app.exec_()
