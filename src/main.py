# import sys
import pickle

from PySide2 import QtWidgets
from src.GUI import Ui_MainWindow, QAction, QFileDialog
from src.lasProcesor import Well, Track
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
        self.template = None

        qtreewidgetitem1 = QTreeWidgetItem(self.treeWidget)
        qtreewidgetitem1 = self.treeWidget.topLevelItem(0)
        qtreewidgetitem1.setText(0,"Plantilla:")


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
        self.saveTempAction = QAction(self)
        self.saveTempAction.setText('Save Template')
        self.saveTempAction.setShortcut('Ctrl+T')
        self.saveTempAction.setStatusTip('Save Template...')
        self.saveTempAction.triggered.connect(self.saveTemplate)
        self.menuMenu.addAction(self.saveTempAction)
        # Load Template
        self.loadTempAction = QAction(self)
        self.loadTempAction.setText('Load Template')
        self.loadTempAction.setShortcut('Ctrl+L')
        self.loadTempAction.setStatusTip('Load Template...')
        self.loadTempAction.triggered.connect(self.loadTemplate)
        self.menuMenu.addAction(self.loadTempAction)
        # Remove Template
        self.remTempAction = QAction(self)
        self.remTempAction.setText('Clear Template')
        self.remTempAction.setShortcut('Ctrl+C')
        self.remTempAction.setStatusTip('Clear Template...')
        self.remTempAction.triggered.connect(self.remTemplate)
        self.menuMenu.addAction(self.remTempAction)

    @Slot()
    def saveTemplate(self):
        # tracks = self.well.tracks
        if self.mdiArea.subWindowList():
            tracks = self.mdiArea.currentSubWindow().widget().well.tracks
            fileName = QFileDialog.getSaveFileName(self, 'Guardar Plantilla', os.path.expanduser("~"),
                                                   '*.temp')
            if fileName[0]:
                with open(fileName[0], 'wb') as out_s:
                    for o in tracks:
                        # print('WRITING: {} ({})'.format(
                        #     o.name, o.name_backwards))
                        pickle.dump(o, out_s)

    def loadTemplate(self):
        fileName = QFileDialog.getOpenFileName(self, 'Cargar Plantilla', os.path.expanduser("~"),
                                               '*.temp')
        if fileName[0]:
            ltracks = []
            head, name = os.path.split(fileName[0])
            with open(fileName[0], 'rb') as in_s:
                while True:
                    try:
                        o = pickle.load(in_s)
                    except EOFError:
                        break
                    else:
                        ltracks.append(o)

            self.template = ltracks
            qtreewidgetitem = QTreeWidgetItem(self.treeWidget)

            self.treeWidget.setSortingEnabled(False)
            qtreewidgetitem = self.treeWidget.topLevelItem(0)
            strId = "Plantilla: " + name
            qtreewidgetitem.setText(0, strId)
            # qtreewidgetitem2 = QTreeWidgetItem(qtreewidgetitem)
            # qtreewidgetitem2 = qtreewidgetitem.child(0)
            # qtreewidgetitem2.setText(0, "Tracks:")
            # Tracks
            i = 0
            for t in ltracks:
                if i != 1:
                    qtreewidgetitemtrack = QTreeWidgetItem(qtreewidgetitem)
                    qtreewidgetitemtrack = qtreewidgetitem.child(i)
                    qtreewidgetitemtrack.setText(0, "Track " + str(i+1)+":")
                    qtreewidgetitemlines = QTreeWidgetItem(qtreewidgetitemtrack)
                    qtreewidgetitemlines = qtreewidgetitemtrack.child(0)
                    qtreewidgetitemlines.setText(0, "Lines:")
                    qtreewidgetitemgrids = QTreeWidgetItem(qtreewidgetitemtrack)
                    qtreewidgetitemgrids = qtreewidgetitemtrack.child(1)
                    qtreewidgetitemgrids.setText(0, "Grids:")
                    j = 0
                    for l in t.lines:
                        qtreewidgetitemline = QTreeWidgetItem(qtreewidgetitemlines)
                        qtreewidgetitemline = qtreewidgetitemlines.child(j)
                        qtreewidgetitemline.setText(0, l.name)
                        j+=1


                    j = 0
                    for g in t.grids:
                        qtreewidgetitemgrid = QTreeWidgetItem(qtreewidgetitemgrids)
                        qtreewidgetitemgrid = qtreewidgetitemgrids.child(j)
                        if g.leftLine == " ":
                            l = g.leftVal
                        else:
                            l = g.leftLine
                        r = g.rightLine
                        if r == " ":
                            r = g.rightVal
                        qtreewidgetitemgrid.setText(0, "Left: " + str(l) + " - Right: " + str(r))
                        j += 1

                i += 1


    def remTemplate(self):
        self.template = None
        t = self.treeWidget.findItems("Plantilla:", Qt.MatchStartsWith)
        self.treeWidget.takeTopLevelItem(self.treeWidget.indexOfTopLevelItem(t[0]))
        qtreewidgetitem = QTreeWidgetItem(self.treeWidget)
        self.treeWidget.setSortingEnabled(False)
        qtreewidgetitem = self.treeWidget.topLevelItem(0)
        strId = "Plantilla:"
        qtreewidgetitem.setText(0, strId)

        #

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
        qtreewidgetitem1 = self.treeWidget.topLevelItem(len(self.mdiArea.subWindowList()))
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
