# import sys
from PySide2 import QtWidgets
from src.GUI import Ui_MainWindow
from src.lasProcesor import Well
from src.subWindowScroll import subWindowWell
from PySide2.QtCore import ( Slot)
from PySide2.QtGui import (QIcon, Qt)
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
    # def mouseReleaseEvent(self, event:QtGui.QMouseEvent):
    #     print("Released Daddy")
    #
    # def mousePressEvent(self, event:QtGui.QMouseEvent):
    #     if event.button() == Qt.LeftButton:
    #         print("Pressed Daddy")



# app = QtWidgets.QApplication(sys.argv)
if __name__ == '__main__':
    MainEventThread = QApplication([])
    window = MainWindow()

    window.show()

    MainEventThread.exec_()
# app.exec_()
