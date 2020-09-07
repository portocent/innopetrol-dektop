import copy, math

from PySide2 import QtWidgets
from src.lasProcesor import Line, Grid
from src.addCurveGUI import Ui_addCurve
from PySide2.QtCore import ( QSize, Qt, Slot)
from PySide2.QtGui import (QIcon)
from PySide2.QtWidgets import ( QWidget, QPushButton,
                               QComboBox, QCheckBox,
                               QHBoxLayout, QTableWidgetItem, QApplication,
                               QColorDialog, QItemDelegate, QDoubleSpinBox)
from src.myGuiClasses import Label



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
        logopt = [" " ,"Lineal" ,"Log"]
        linesOpt = [QIcon("statics\\images\\solid.png"), QIcon("statics\\images\\dash.png"),
                    QIcon("statics\\images\\dashdot.png") ,QIcon("statics\\images\\dot.png"),
                    QIcon("statics\\images\\dashdotdot.png")]
        widthOpt = [1 ,2 ,3 ,4 ,5 ,6 ,7 ,8]
        iconSizeLine = QSize(95, 21)
        iconSize = QSize(91, 30)
        self.rowColor = []
        # realFormat = RealDelegate()
        # self.tableWidget.setItemDelegateForColumn(1 ,realFormat)
        # self.tableWidget.setItemDelegateForColumn(2 ,realFormat)
        # self.tableWidget_2.setItemDelegateForColumn(1 ,realFormat)
        # self.tableWidget_2.setItemDelegateForColumn(3 ,realFormat)

        comboList = []
        comboWidthList = []
        comboLinesList = []
        checkBoxLines = []
        colorButtonList = []
        comboBrushList = []
        colorButton2List = []
        self.comboLcurve = []
        self.comboRcurve = []
        self.choosedLines = []
        # Grids combobox values
        # Combo Box


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
            lay_out.setContentsMargins(0 ,0 ,0 ,0)
            cell_widget.setLayout(lay_out)
            # Addig the color choice
            colorButton = QPushButton("Color" ,self.tableWidget)
            label = Label(self.tableWidget)


            # self.rowColor.append("#000000")
            for op in items:
                combo.addItem(op)
            for op in logopt:
                comboLog.addItem(op)
            count = 0
            for op in linesOpt:
                comboLines.addItem(op ,str(count))
                count += 1
            for op in widthOpt:
                comboWidth.addItem(str(op))
            self.tableWidget.setCellWidget(i ,0 ,combo)
            self.tableWidget.setCellWidget(i ,3 ,cell_widget)
            self.tableWidget.setCellWidget(i ,4 ,comboLog)
            self.tableWidget.setCellWidget(i ,5 ,colorButton)
            self.tableWidget.setCellWidget(i ,6 ,comboWidth)
            self.tableWidget.setCellWidget(i ,7 ,comboLines)
            self.tableWidget.setCellWidget(i ,8 ,label)



            # Tag Sombras ################################
            lCurve = QComboBox()
            lCurve.addItem(" ")
            rCurve = QComboBox()
            rCurve.addItem(" ")
            comboBrush = QComboBox()

            comboBrush.setIconSize(iconSize)
            comboBrush.addItem(" ")
            comboBrush.addItem(QIcon("statics\\images\\d1.png") ,"1")
            comboBrush.addItem(QIcon("statics\\images\\d2.png") ,"2")
            comboBrush.addItem(QIcon("statics\\images\\d3.png") ,"3")
            comboBrush.addItem(QIcon("statics\\images\\d4.png") ,"4")
            comboBrush.addItem(QIcon("statics\\images\\d5.png") ,"5")
            comboBrush.addItem(QIcon("statics\\images\\d6.png") ,"6")
            comboBrush.addItem(QIcon("statics\\images\\d7.png") ,"7")
            comboBrush.addItem(QIcon("statics\\images\\d8.png") ,"8")
            comboBrush.addItem(QIcon("statics\\images\\d9.png") ,"9")
            comboBrush.addItem(QIcon("statics\\images\\d10.png") ,"10")
            # for op in items:
            #     lCurve.addItem(op)
            #     rCurve.addItem(op)
            # Visible CheckBox
            checkWidget = QWidget()
            lay_out2 = QHBoxLayout(checkWidget)
            check2 = QCheckBox()
            lay_out2.addWidget(check2)
            lay_out2.setAlignment(Qt.AlignCenter)
            lay_out2.setContentsMargins(0 ,0 ,0 ,0)
            checkWidget.setLayout(lay_out2)
            label2 = Label()
            label2.isBrush = True
            # Shading Color
            colorButton2 = QPushButton("Color")

            # Filling Shading table
            self.tableWidget_2.setCellWidget(i ,0 ,lCurve)
            self.tableWidget_2.setCellWidget(i ,2 ,rCurve)
            self.tableWidget_2.setCellWidget(i ,4 ,checkWidget)
            self.tableWidget_2.setCellWidget(i ,5 ,colorButton2)
            self.tableWidget_2.setCellWidget(i ,6 ,comboBrush)
            self.tableWidget_2.setCellWidget(i ,7 ,label2)
            comboList.append(combo)
            comboWidthList.append(comboWidth)
            comboLinesList.append(comboLines)
            colorButtonList.append(colorButton)
            comboBrushList.append(comboBrush)
            colorButton2List.append(colorButton2)
            checkBoxLines.append(check)
            self.comboLcurve.append(lCurve)
            self.comboRcurve.append(rCurve)

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
            self.comboRcurve[i].currentIndexChanged.connect(self.pickLineGrid)
            self.comboLcurve[i].currentIndexChanged.connect(self.pickLineGrid)
        self.tabWidget.currentChanged.connect(self.changetab)

    def changetab(self):
        self.choosedLines = []
        self.choosedLines.append(" ")
        for row in range(16):
            name = self.tableWidget.cellWidget(row, 0).currentText()
            if name != " ":
                self.choosedLines.append(name)
        for line in range(len(self.comboRcurve)):
            self.comboRcurve[line].blockSignals(True)
            self.comboLcurve[line].blockSignals(True)
            prevRval = self.comboRcurve[line].currentText()
            prevLval = self.comboLcurve[line].currentText()
            self.comboRcurve[line].clear()
            self.comboLcurve[line].clear()
            self.comboRcurve[line].addItems(self.choosedLines)
            self.comboLcurve[line].addItems(self.choosedLines)
            rindex = self.comboRcurve[line].findText(prevRval, Qt.MatchFixedString)
            lindex = self.comboLcurve[line].findText(prevLval, Qt.MatchFixedString)
            if rindex >= 0:
                self.comboRcurve[line].setCurrentIndex(rindex)
            if lindex >= 0:
                self.comboLcurve[line].setCurrentIndex(lindex)
            self.comboRcurve[line].blockSignals(False)
            self.comboLcurve[line].blockSignals(False)

    def loadLines(self):
        row = 0
        lines = self.parent.well.tracks[self.trackNum - 1].lines
        self.choosedLines = []
        for linea in lines:
            name = linea.nameIndex
            width = linea.grosorIndex
            penType = linea.estiloIndex
            log = linea.logIndex
            visible = linea.visible
            l = linea.lvScale
            r = linea.rvScale
            check = self.tableWidget.cellWidget(row, 3).findChildren(QCheckBox)
            # Filling Grids Choose Lines
            self.choosedLines.append(linea.name)
            # Setting Options
            self.tableWidget.cellWidget(row ,0).setCurrentIndex(name)

            rItem = QTableWidgetItem()
            if not r is None:
                rItem.setData(Qt.DisplayRole ,str(r))
            lItem = QTableWidgetItem()
            if not l is None:
                lItem.setData(Qt.DisplayRole ,str(l))
            self.tableWidget.setItem(row ,2 ,rItem)
            self.tableWidget.setItem(row ,1 ,lItem)
            self.tableWidget.cellWidget(row ,4).setCurrentIndex(log)
            self.tableWidget.cellWidget(row ,6).setCurrentIndex(width)
            self.tableWidget.cellWidget(row ,7).setCurrentIndex(penType)
            label = self.tableWidget.cellWidget(row ,8)
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
        self.changetab()
        errorLines = self.passValidateLines()
        errorGrids = self.passValidateGrids()
        if not errorLines and not errorGrids:
            self.saveLines()
            self.saveGrids()
            self.parent.update()
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
        self.parent.well.tracks[self.trackNum - 1].minVal = 99999.25
        self.parent.well.tracks[self.trackNum - 1].maxVal = -999.25
        minUserVal = None
        maxUserVal = None
        for row in range(16):
            name = self.tableWidget.cellWidget(row, 0).currentText()
            nameIndex = self.tableWidget.cellWidget(row, 0).currentIndex()
            if name != " ":
                l = None
                r = None
                if not self.tableWidget.item(row, 1) is None:
                    l = self.tableWidget.item(row, 1).text()
                if not self.tableWidget.item(row, 2) is None:
                    r = self.tableWidget.item(row, 2).text()
                check = self.tableWidget.cellWidget(row, 3).findChildren(QCheckBox)
                log = self.tableWidget.cellWidget(row, 4).currentText()
                logIndex = self.tableWidget.cellWidget(row, 4).currentIndex()
                label = self.tableWidget.cellWidget(row, 8)
                widthIndex = self.tableWidget.cellWidget(row, 6).currentIndex()
                styleIndex = self.tableWidget.cellWidget(row, 7).currentIndex()

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
                if not self.tableWidget.item(row, 1) is None:
                    if l:
                        if log == "Log":
                            linea.setlScale(float(l))
                        else:
                            linea.lScale = float(l)
                            linea.lvScale = float(l)
                if not self.tableWidget.item(row, 2) is None:
                    if r:
                        if log == "Log":
                            linea.setrScale(float(r))
                        else:
                            linea.rScale = float(r)
                            linea.rvScale = float(r)
                stats = self.parent.well.stats[name]
                minVal = stats['min']
                maxVal = stats['max']
                linea.minVal = copy.copy(minVal)
                linea.maxVal = copy.copy(maxVal)

                if not l is None:
                    if l:
                        if minUserVal is None:
                            minUserVal = float(l)
                        else:
                            if minUserVal < float(l):
                                minUserVal = float(l)

                if not r is None:
                    if r:
                        if maxUserVal is None:
                            maxUserVal = float(r)
                        else:
                            if maxUserVal > float(r):
                                maxUserVal = float(r)


                self.parent.well.tracks[self.trackNum - 1].addLine(linea)
                self.parent.well.tracks[self.trackNum - 1].setMin(minVal)
                self.parent.well.tracks[self.trackNum - 1].setMax(maxVal)
                if linea.log != "Log":
                    self.parent.well.tracks[self.trackNum - 1].setMinLine(minVal)
                    self.parent.well.tracks[self.trackNum - 1].setMaxLine(maxVal)



        if not minUserVal is None:
            self.parent.well.tracks[self.trackNum - 1].minVal = minUserVal
            self.parent.well.tracks[self.trackNum - 1].getLandR()
        if not maxUserVal is None:
            self.parent.well.tracks[self.trackNum - 1].maxVal = maxUserVal
            self.parent.well.tracks[self.trackNum - 1].getLandR()
        self.parent.lTracks[self.trackNum - 1].recalculate = True


                # wellTrack.append(linea)
                # print("Fin")

    def passValidateLines(self):
        for row in range(16):
            name = self.tableWidget.cellWidget(row, 0).currentText()
            l = self.tableWidget.item(row, 1)
            r = self.tableWidget.item(row, 2)
            log = self.tableWidget.cellWidget(row, 4).currentText()
            lIsNone = l is None
            rIsNone = r is None


            if name != " ":
                if not l is None or not r is None:
                    if not lIsNone:
                        if l.text() != "":

                            try:
                                leftS = float(l.text())
                            except ValueError:
                                return ("Los valores de la escala deben ser numéricos")
                            if log == "Log":
                                if leftS < 0:
                                    return "Pestaña curvas fila "+str(row+1)+": Las escalas logaritmicas deben ser positivas"
                    if not rIsNone:
                        if r.text() != "":

                            try:
                                rightS = float(r.text())
                            except ValueError:
                                return ("Los valores de la escala deben ser numéricos")
                            if log == "Log":
                                if rightS < 0:
                                    return "Pestaña curvas fila "+str(row+1)+": Las escalas logaritmicas deben ser positivas"
                    # if not rIsNone and not lIsNone:
                        # if l.text() != "" and r.text() != "":
                            # if leftS >= rightS:
                                # return "Pestaña curvas fila "+str(row+1)+": Escala izquierda inferior o igual a la derecha"

                if log == " ":
                    return "Pestaña curvas fila "+str(row+1)+": Tipo de lína no seleccionada: Log/Lineal"
        return ""

    def loadGrids(self):
        row = 0
        grids = self.parent.well.tracks[self.trackNum - 1].grids
        for line in range(len(self.comboRcurve)):
            self.comboRcurve[line].clear()
            self.comboLcurve[line].clear()
            self.comboRcurve[line].addItem(" ")
            self.comboLcurve[line].addItem(" ")
            self.comboRcurve[line].addItems(self.choosedLines)
            self.comboLcurve[line].addItems(self.choosedLines)

        for grid in grids:
            leftLine = grid.leftLine
            leftVal = str(grid.leftVal)
            rightLine = grid.rightLine
            rightVal = str(grid.rightVal)
            checkVal = grid.check
            brush = grid.brushIndex
            penType = grid.brush
            penColor = grid.color

            check = self.tableWidget_2.cellWidget(row, 4).findChildren(QCheckBox)
            check[0].setChecked(checkVal)

            lindex = self.tableWidget_2.cellWidget(row, 0).findText(leftLine, Qt.MatchFixedString)
            if lindex >= 0:
                self.tableWidget_2.cellWidget(row, 0).setCurrentIndex(lindex)
            rindex = self.tableWidget_2.cellWidget(row, 2).findText(rightLine, Qt.MatchFixedString)
            if rindex >= 0:
                self.tableWidget_2.cellWidget(row, 2).setCurrentIndex(rindex)
            # self.tableWidget_2.cellWidget(row, 0).setItems(self.choosedLines)
            # self.tableWidget_2.cellWidget(row, 2).setItems(self.choosedLines)
            # self.tableWidget_2.cellWidget(row, 0).setCurrentIndex(leftLine)
            # self.tableWidget_2.cellWidget(row, 2).setCurrentIndex(rightLine)
            self.tableWidget_2.cellWidget(row, 6).setCurrentIndex(brush)
            label = self.tableWidget_2.cellWidget(row, 7)
            if leftLine == " ":
                lItem = QTableWidgetItem()
                lItem.setData(Qt.DisplayRole, leftVal)
                self.tableWidget_2.setItem(row, 1, lItem)
            if rightLine == " ":
                rItem = QTableWidgetItem()
                rItem.setData(Qt.DisplayRole, rightVal)
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
            namer = self.tableWidget_2.cellWidget(row, 2).currentText()
            namelIndex = self.tableWidget_2.cellWidget(row, 0).currentIndex()
            lv = self.tableWidget_2.item(row, 1)
            lvBool = False
            if not lv is None:
                if lv.text() == "":
                    lvBool = True
            else:
                lvBool = True

            if namel != " " or not lvBool:
                namerIndex = self.tableWidget_2.cellWidget(row, 2).currentIndex()
                rv = self.tableWidget_2.item(row, 3)
                fill = self.tableWidget_2.cellWidget(row, 6).currentIndex()
                check = self.tableWidget_2.cellWidget(row, 4).findChildren(QCheckBox)
                label = self.tableWidget_2.cellWidget(row, 7)
                description = ""
                if not self.tableWidget_2.item(row, 8) is None:
                    description = self.tableWidget_2.item(row, 8).text()

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
                grid.description = str(description)
                self.parent.well.tracks[self.trackNum - 1].addGrid(grid)
                # wellTrack.append(linea)
                # print("Fin")

    def passValidateGrids(self):
        for row in range(15):
            namel = self.tableWidget_2.cellWidget(row, 0).currentText()
            namer = self.tableWidget_2.cellWidget(row, 2).currentText()
            lv = self.tableWidget_2.item(row, 1)
            lvBool = False
            rv = self.tableWidget_2.item(row, 3)
            rvBool = False
            fill = self.tableWidget_2.cellWidget(row, 6).currentText()
            if not lv is None:
                if lv.text() == "":
                    lvBool = True
                else:
                    try:
                        float(lv.text())
                    except ValueError:
                        return ("El valor izquierdo debe ser numérico")
            else:
                lvBool = True

            if not rv is None:
                if rv.text() == "":
                    rvBool = True
                else:
                    try:
                        float(rv.text())
                    except ValueError:
                        return ("El valor derecho debe ser numérico")
            else:
                rvBool = True

            if not lvBool or  namel != " ":
                if rvBool and namer == " ":
                        return "Pestaña Sombras fila "+str(row+1)+": Debe seleccionar una linea derecha o ingresar un valor fijo"
                if fill == " ":
                    return "Pestaña Sombras fila "+str(row+1)+": Debe seleccionar un patrón de relleno"

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
        self.tableWidget_2.setItem(i, j + 1, item)

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
        label = self.tableWidget.cellWidget(i, 8)
        label.visibleCheck = checkBox[0].isChecked()
        label.update()

    @Slot()
    def paintLabel(self, ix):
        # combo = self.sender()
        clickme = QApplication.focusWidget()
        index = self.tableWidget.indexAt(clickme.pos())
        i = index.row()
        label = self.tableWidget.cellWidget(i, 8)

        if ix != 0:
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
        label = self.tableWidget.cellWidget(i, 8)
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
        label = self.tableWidget.cellWidget(i, 8)
        label.penSize = ix + 1
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
            label = self.tableWidget.cellWidget(i, 8)

            button.clicked.connect(self.color_picker)
            label.penColor = color
            self.tableWidget.setCellWidget(i, 5, button)
            # self.rowColor[i-1] = color

    ################ Shading Events ######################
    @Slot()
    def setStyleBrush(self, ix):
        clickme = QApplication.focusWidget()
        index = self.tableWidget_2.indexAt(clickme.pos())
        i = index.row()
        label = self.tableWidget_2.cellWidget(i, 7)
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
            label = self.tableWidget_2.cellWidget(i, 7)
            label.penColor = color
            # if label.visible:
            label.update()

class RealDelegate(QItemDelegate):
    def createEditor(self, parent, option, index):
        realSpinBox = QDoubleSpinBox(parent)
        realSpinBox.setMinimum(-100000)
        realSpinBox.setMaximum(100000)
        realSpinBox.setSpecialValueText("")
        realSpinBox.setValue(math.nan)
        # realSpinBox.setValue()
        return realSpinBox