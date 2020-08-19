# -*- coding: utf-8 -*-

################################################################################
## Form generated from reading UI file 'ventanaCurvas.ui'
##
## Created by: Qt User Interface Compiler version 5.15.0
##
## WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QDate, QDateTime, QMetaObject,
    QObject, QPoint, QRect, QSize, QTime, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont,
    QFontDatabase, QIcon, QKeySequence, QLinearGradient, QPalette, QPainter,
    QPixmap, QRadialGradient)
from PySide2.QtWidgets import *


class Ui_addCurve(object):
    def setupUi(self, addCurve):
        if not addCurve.objectName():
            addCurve.setObjectName(u"addCurve")
        addCurve.resize(793, 512)
        self.gridLayout = QGridLayout(addCurve)
        self.gridLayout.setObjectName(u"gridLayout")
        self.tabWidget = QTabWidget(addCurve)
        self.tabWidget.setObjectName(u"tabWidget")
        self.tabCurvas = QWidget()
        self.tabCurvas.setObjectName(u"tabCurvas")
        self.gridLayout_2 = QGridLayout(self.tabCurvas)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.tableWidget = QTableWidget(self.tabCurvas)
        if (self.tableWidget.columnCount() < 9):
            self.tableWidget.setColumnCount(9)
        __qtablewidgetitem = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(0, __qtablewidgetitem)
        __qtablewidgetitem1 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(1, __qtablewidgetitem1)
        __qtablewidgetitem2 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(2, __qtablewidgetitem2)
        __qtablewidgetitem3 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(3, __qtablewidgetitem3)
        __qtablewidgetitem4 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(4, __qtablewidgetitem4)
        __qtablewidgetitem5 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(5, __qtablewidgetitem5)
        __qtablewidgetitem6 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(6, __qtablewidgetitem6)
        __qtablewidgetitem7 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(7, __qtablewidgetitem7)
        __qtablewidgetitem8 = QTableWidgetItem()
        self.tableWidget.setHorizontalHeaderItem(8, __qtablewidgetitem8)
        if (self.tableWidget.rowCount() < 16):
            self.tableWidget.setRowCount(16)
        __qtablewidgetitem9 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(0, __qtablewidgetitem9)
        __qtablewidgetitem10 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(1, __qtablewidgetitem10)
        __qtablewidgetitem11 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(2, __qtablewidgetitem11)
        __qtablewidgetitem12 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(3, __qtablewidgetitem12)
        __qtablewidgetitem13 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(4, __qtablewidgetitem13)
        __qtablewidgetitem14 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(5, __qtablewidgetitem14)
        __qtablewidgetitem15 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(6, __qtablewidgetitem15)
        __qtablewidgetitem16 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(7, __qtablewidgetitem16)
        __qtablewidgetitem17 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(8, __qtablewidgetitem17)
        __qtablewidgetitem18 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(9, __qtablewidgetitem18)
        __qtablewidgetitem19 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(10, __qtablewidgetitem19)
        __qtablewidgetitem20 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(11, __qtablewidgetitem20)
        __qtablewidgetitem21 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(12, __qtablewidgetitem21)
        __qtablewidgetitem22 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(13, __qtablewidgetitem22)
        __qtablewidgetitem23 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(14, __qtablewidgetitem23)
        __qtablewidgetitem24 = QTableWidgetItem()
        self.tableWidget.setVerticalHeaderItem(15, __qtablewidgetitem24)
        self.tableWidget.setObjectName(u"tableWidget")

        self.gridLayout_2.addWidget(self.tableWidget, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tabCurvas, "")
        self.tabShading = QWidget()
        self.tabShading.setObjectName(u"tabShading")
        self.gridLayout_3 = QGridLayout(self.tabShading)
        self.gridLayout_3.setObjectName(u"gridLayout_3")
        self.tableWidget_2 = QTableWidget(self.tabShading)
        if (self.tableWidget_2.columnCount() < 9):
            self.tableWidget_2.setColumnCount(9)
        __qtablewidgetitem25 = QTableWidgetItem()
        self.tableWidget_2.setHorizontalHeaderItem(0, __qtablewidgetitem25)
        __qtablewidgetitem26 = QTableWidgetItem()
        self.tableWidget_2.setHorizontalHeaderItem(1, __qtablewidgetitem26)
        __qtablewidgetitem27 = QTableWidgetItem()
        self.tableWidget_2.setHorizontalHeaderItem(2, __qtablewidgetitem27)
        __qtablewidgetitem28 = QTableWidgetItem()
        self.tableWidget_2.setHorizontalHeaderItem(3, __qtablewidgetitem28)
        __qtablewidgetitem29 = QTableWidgetItem()
        self.tableWidget_2.setHorizontalHeaderItem(4, __qtablewidgetitem29)
        __qtablewidgetitem30 = QTableWidgetItem()
        self.tableWidget_2.setHorizontalHeaderItem(5, __qtablewidgetitem30)
        __qtablewidgetitem31 = QTableWidgetItem()
        self.tableWidget_2.setHorizontalHeaderItem(6, __qtablewidgetitem31)
        __qtablewidgetitem32 = QTableWidgetItem()
        self.tableWidget_2.setHorizontalHeaderItem(7, __qtablewidgetitem32)
        __qtablewidgetitem33 = QTableWidgetItem()
        self.tableWidget_2.setHorizontalHeaderItem(8, __qtablewidgetitem33)
        if (self.tableWidget_2.rowCount() < 15):
            self.tableWidget_2.setRowCount(15)
        __qtablewidgetitem34 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(0, __qtablewidgetitem34)
        __qtablewidgetitem35 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(1, __qtablewidgetitem35)
        __qtablewidgetitem36 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(2, __qtablewidgetitem36)
        __qtablewidgetitem37 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(3, __qtablewidgetitem37)
        __qtablewidgetitem38 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(4, __qtablewidgetitem38)
        __qtablewidgetitem39 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(5, __qtablewidgetitem39)
        __qtablewidgetitem40 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(6, __qtablewidgetitem40)
        __qtablewidgetitem41 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(7, __qtablewidgetitem41)
        __qtablewidgetitem42 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(8, __qtablewidgetitem42)
        __qtablewidgetitem43 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(9, __qtablewidgetitem43)
        __qtablewidgetitem44 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(10, __qtablewidgetitem44)
        __qtablewidgetitem45 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(11, __qtablewidgetitem45)
        __qtablewidgetitem46 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(12, __qtablewidgetitem46)
        __qtablewidgetitem47 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(13, __qtablewidgetitem47)
        __qtablewidgetitem48 = QTableWidgetItem()
        self.tableWidget_2.setVerticalHeaderItem(14, __qtablewidgetitem48)
        self.tableWidget_2.setObjectName(u"tableWidget_2")

        self.gridLayout_3.addWidget(self.tableWidget_2, 0, 0, 1, 1)

        self.tabWidget.addTab(self.tabShading, "")

        self.gridLayout.addWidget(self.tabWidget, 0, 0, 1, 1)

        self.frame = QFrame(addCurve)
        self.frame.setObjectName(u"frame")
        self.frame.setMinimumSize(QSize(0, 25))
        self.frame.setFrameShape(QFrame.StyledPanel)
        self.frame.setFrameShadow(QFrame.Raised)
        self.okButton = QPushButton(self.frame)
        self.okButton.setObjectName(u"okButton")
        self.okButton.setGeometry(QRect(440, 0, 75, 23))
        self.aplicarButton = QPushButton(self.frame)
        self.aplicarButton.setObjectName(u"aplicarButton")
        self.aplicarButton.setGeometry(QRect(530, 0, 75, 23))
        self.closeButton = QPushButton(self.frame)
        self.closeButton.setObjectName(u"closeButton")
        self.closeButton.setGeometry(QRect(620, 0, 75, 23))

        self.gridLayout.addWidget(self.frame, 1, 0, 1, 1)


        self.retranslateUi(addCurve)

        self.tabWidget.setCurrentIndex(0)


        QMetaObject.connectSlotsByName(addCurve)
    # setupUi

    def retranslateUi(self, addCurve):
        addCurve.setWindowTitle(QCoreApplication.translate("addCurve", u"Dialog", None))
        ___qtablewidgetitem = self.tableWidget.horizontalHeaderItem(0)
        ___qtablewidgetitem.setText(QCoreApplication.translate("addCurve", u"Curva", None));
        ___qtablewidgetitem1 = self.tableWidget.horizontalHeaderItem(1)
        ___qtablewidgetitem1.setText(QCoreApplication.translate("addCurve", u"Escala Izquierda", None));
        ___qtablewidgetitem2 = self.tableWidget.horizontalHeaderItem(2)
        ___qtablewidgetitem2.setText(QCoreApplication.translate("addCurve", u"Escala Derecha", None));
        ___qtablewidgetitem3 = self.tableWidget.horizontalHeaderItem(3)
        ___qtablewidgetitem3.setText(QCoreApplication.translate("addCurve", u"Visible", None));
        ___qtablewidgetitem4 = self.tableWidget.horizontalHeaderItem(4)
        ___qtablewidgetitem4.setText(QCoreApplication.translate("addCurve", u"Log", None));
        ___qtablewidgetitem5 = self.tableWidget.horizontalHeaderItem(5)
        ___qtablewidgetitem5.setText(QCoreApplication.translate("addCurve", u"Color", None));
        ___qtablewidgetitem6 = self.tableWidget.horizontalHeaderItem(6)
        ___qtablewidgetitem6.setText(QCoreApplication.translate("addCurve", u"Grosor", None));
        ___qtablewidgetitem7 = self.tableWidget.horizontalHeaderItem(7)
        ___qtablewidgetitem7.setText(QCoreApplication.translate("addCurve", u"Estilo", None));
        ___qtablewidgetitem8 = self.tableWidget.horizontalHeaderItem(8)
        ___qtablewidgetitem8.setText(QCoreApplication.translate("addCurve", u"Dise\u00f1o", None));
        ___qtablewidgetitem9 = self.tableWidget.verticalHeaderItem(0)
        ___qtablewidgetitem9.setText(QCoreApplication.translate("addCurve", u"1", None));
        ___qtablewidgetitem10 = self.tableWidget.verticalHeaderItem(1)
        ___qtablewidgetitem10.setText(QCoreApplication.translate("addCurve", u"2", None));
        ___qtablewidgetitem11 = self.tableWidget.verticalHeaderItem(2)
        ___qtablewidgetitem11.setText(QCoreApplication.translate("addCurve", u"3", None));
        ___qtablewidgetitem12 = self.tableWidget.verticalHeaderItem(3)
        ___qtablewidgetitem12.setText(QCoreApplication.translate("addCurve", u"4", None));
        ___qtablewidgetitem13 = self.tableWidget.verticalHeaderItem(4)
        ___qtablewidgetitem13.setText(QCoreApplication.translate("addCurve", u"5", None));
        ___qtablewidgetitem14 = self.tableWidget.verticalHeaderItem(5)
        ___qtablewidgetitem14.setText(QCoreApplication.translate("addCurve", u"6", None));
        ___qtablewidgetitem15 = self.tableWidget.verticalHeaderItem(6)
        ___qtablewidgetitem15.setText(QCoreApplication.translate("addCurve", u"7", None));
        ___qtablewidgetitem16 = self.tableWidget.verticalHeaderItem(7)
        ___qtablewidgetitem16.setText(QCoreApplication.translate("addCurve", u"8", None));
        ___qtablewidgetitem17 = self.tableWidget.verticalHeaderItem(8)
        ___qtablewidgetitem17.setText(QCoreApplication.translate("addCurve", u"9", None));
        ___qtablewidgetitem18 = self.tableWidget.verticalHeaderItem(9)
        ___qtablewidgetitem18.setText(QCoreApplication.translate("addCurve", u"10", None));
        ___qtablewidgetitem19 = self.tableWidget.verticalHeaderItem(10)
        ___qtablewidgetitem19.setText(QCoreApplication.translate("addCurve", u"11", None));
        ___qtablewidgetitem20 = self.tableWidget.verticalHeaderItem(11)
        ___qtablewidgetitem20.setText(QCoreApplication.translate("addCurve", u"12", None));
        ___qtablewidgetitem21 = self.tableWidget.verticalHeaderItem(12)
        ___qtablewidgetitem21.setText(QCoreApplication.translate("addCurve", u"13", None));
        ___qtablewidgetitem22 = self.tableWidget.verticalHeaderItem(13)
        ___qtablewidgetitem22.setText(QCoreApplication.translate("addCurve", u"14", None));
        ___qtablewidgetitem23 = self.tableWidget.verticalHeaderItem(14)
        ___qtablewidgetitem23.setText(QCoreApplication.translate("addCurve", u"15", None));
        ___qtablewidgetitem24 = self.tableWidget.verticalHeaderItem(15)
        ___qtablewidgetitem24.setText(QCoreApplication.translate("addCurve", u"16", None));
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabCurvas), QCoreApplication.translate("addCurve", u"Curvas", None))
        ___qtablewidgetitem25 = self.tableWidget_2.horizontalHeaderItem(0)
        ___qtablewidgetitem25.setText(QCoreApplication.translate("addCurve", u"Curva Izq.", None));
        ___qtablewidgetitem26 = self.tableWidget_2.horizontalHeaderItem(1)
        ___qtablewidgetitem26.setText(QCoreApplication.translate("addCurve", u"Valor fijo Izq.", None));
        ___qtablewidgetitem27 = self.tableWidget_2.horizontalHeaderItem(2)
        ___qtablewidgetitem27.setText(QCoreApplication.translate("addCurve", u"Curva Der.", None));
        ___qtablewidgetitem28 = self.tableWidget_2.horizontalHeaderItem(3)
        ___qtablewidgetitem28.setText(QCoreApplication.translate("addCurve", u"Valor Fijo Der.", None));
        ___qtablewidgetitem29 = self.tableWidget_2.horizontalHeaderItem(4)
        ___qtablewidgetitem29.setText(QCoreApplication.translate("addCurve", u"Visible", None));
        ___qtablewidgetitem30 = self.tableWidget_2.horizontalHeaderItem(5)
        ___qtablewidgetitem30.setText(QCoreApplication.translate("addCurve", u"Color", None));
        ___qtablewidgetitem31 = self.tableWidget_2.horizontalHeaderItem(6)
        ___qtablewidgetitem31.setText(QCoreApplication.translate("addCurve", u"Patr\u00f3n", None));
        ___qtablewidgetitem32 = self.tableWidget_2.horizontalHeaderItem(7)
        ___qtablewidgetitem32.setText(QCoreApplication.translate("addCurve", u"Relleno", None));
        ___qtablewidgetitem33 = self.tableWidget_2.horizontalHeaderItem(8)
        ___qtablewidgetitem33.setText(QCoreApplication.translate("addCurve", u"Descripci\u00f3n", None));
        ___qtablewidgetitem34 = self.tableWidget_2.verticalHeaderItem(0)
        ___qtablewidgetitem34.setText(QCoreApplication.translate("addCurve", u"1", None));
        ___qtablewidgetitem35 = self.tableWidget_2.verticalHeaderItem(1)
        ___qtablewidgetitem35.setText(QCoreApplication.translate("addCurve", u"2", None));
        ___qtablewidgetitem36 = self.tableWidget_2.verticalHeaderItem(2)
        ___qtablewidgetitem36.setText(QCoreApplication.translate("addCurve", u"3", None));
        ___qtablewidgetitem37 = self.tableWidget_2.verticalHeaderItem(3)
        ___qtablewidgetitem37.setText(QCoreApplication.translate("addCurve", u"4", None));
        ___qtablewidgetitem38 = self.tableWidget_2.verticalHeaderItem(4)
        ___qtablewidgetitem38.setText(QCoreApplication.translate("addCurve", u"5", None));
        ___qtablewidgetitem39 = self.tableWidget_2.verticalHeaderItem(5)
        ___qtablewidgetitem39.setText(QCoreApplication.translate("addCurve", u"6", None));
        ___qtablewidgetitem40 = self.tableWidget_2.verticalHeaderItem(6)
        ___qtablewidgetitem40.setText(QCoreApplication.translate("addCurve", u"7", None));
        ___qtablewidgetitem41 = self.tableWidget_2.verticalHeaderItem(7)
        ___qtablewidgetitem41.setText(QCoreApplication.translate("addCurve", u"8", None));
        ___qtablewidgetitem42 = self.tableWidget_2.verticalHeaderItem(8)
        ___qtablewidgetitem42.setText(QCoreApplication.translate("addCurve", u"9", None));
        ___qtablewidgetitem43 = self.tableWidget_2.verticalHeaderItem(9)
        ___qtablewidgetitem43.setText(QCoreApplication.translate("addCurve", u"10", None));
        ___qtablewidgetitem44 = self.tableWidget_2.verticalHeaderItem(10)
        ___qtablewidgetitem44.setText(QCoreApplication.translate("addCurve", u"11", None));
        ___qtablewidgetitem45 = self.tableWidget_2.verticalHeaderItem(11)
        ___qtablewidgetitem45.setText(QCoreApplication.translate("addCurve", u"12", None));
        ___qtablewidgetitem46 = self.tableWidget_2.verticalHeaderItem(12)
        ___qtablewidgetitem46.setText(QCoreApplication.translate("addCurve", u"13", None));
        ___qtablewidgetitem47 = self.tableWidget_2.verticalHeaderItem(13)
        ___qtablewidgetitem47.setText(QCoreApplication.translate("addCurve", u"14", None));
        ___qtablewidgetitem48 = self.tableWidget_2.verticalHeaderItem(14)
        ___qtablewidgetitem48.setText(QCoreApplication.translate("addCurve", u"16", None));
        self.tabWidget.setTabText(self.tabWidget.indexOf(self.tabShading), QCoreApplication.translate("addCurve", u"Sombras", None))
        self.okButton.setText(QCoreApplication.translate("addCurve", u"OK", None))
        self.aplicarButton.setText(QCoreApplication.translate("addCurve", u"Aplicar", None))
        self.closeButton.setText(QCoreApplication.translate("addCurve", u"Cerrar", None))
    # retranslateUi

