# -*- coding: utf-8 -*-

################################################################################
# Form generated from reading UI file 'test2.ui'
##
# Created by: Qt User Interface Compiler version 5.15.0
##
# WARNING! All changes made in this file will be lost when recompiling UI file!
################################################################################

from PySide2.QtCore import (QCoreApplication, QDate, QDateTime, QMetaObject,
                            QObject, QPoint, QRect, QSize, QTime, QUrl, Qt)
from PySide2.QtGui import (QBrush, QColor, QConicalGradient, QCursor, QFont,
                           QFontDatabase, QIcon, QKeySequence, QLinearGradient, QPalette, QPainter,
                           QPixmap, QRadialGradient)
from PySide2.QtWidgets import *


class Ui_MainWindow(object):
    def setupUi(self, MainWindow):
        if not MainWindow.objectName():
            MainWindow.setObjectName(u"MainWindow")
        MainWindow.resize(769, 578)
        MainWindow.setMinimumSize(QSize(100, 400))
        self.actionCargar = QAction(MainWindow)
        self.actionCargar.setObjectName(u"actionCargar")
        self.actionOpen_Database = QAction(MainWindow)
        self.actionOpen_Database.setObjectName(u"actionOpen_Database")
        self.actionOpen_Well = QAction(MainWindow)
        self.actionOpen_Well.setObjectName(u"actionOpen_Well")
        self.actionOpen_Template = QAction(MainWindow)
        self.actionOpen_Template.setObjectName(u"actionOpen_Template")
        self.actionSelect_Well = QAction(MainWindow)
        self.actionSelect_Well.setObjectName(u"actionSelect_Well")
        self.actionManage_Zone_Picks = QAction(MainWindow)
        self.actionManage_Zone_Picks.setObjectName(u"actionManage_Zone_Picks")
        self.actionCustom_Zones = QAction(MainWindow)
        self.actionCustom_Zones.setObjectName(u"actionCustom_Zones")
        self.actionExtract_Petrophysics = QAction(MainWindow)
        self.actionExtract_Petrophysics.setObjectName(
            u"actionExtract_Petrophysics")
        self.actionScatter_Plot = QAction(MainWindow)
        self.actionScatter_Plot.setObjectName(u"actionScatter_Plot")
        self.actionHistogram_Plot = QAction(MainWindow)
        self.actionHistogram_Plot.setObjectName(u"actionHistogram_Plot")
        self.actionHeat_Map = QAction(MainWindow)
        self.actionHeat_Map.setObjectName(u"actionHeat_Map")
        self.actionNeural_Network = QAction(MainWindow)
        self.actionNeural_Network.setObjectName(u"actionNeural_Network")
        self.actionMultiple_Linear_Regression = QAction(MainWindow)
        self.actionMultiple_Linear_Regression.setObjectName(
            u"actionMultiple_Linear_Regression")
        self.actionSupport_Vector_Machine_Regression = QAction(MainWindow)
        self.actionSupport_Vector_Machine_Regression.setObjectName(
            u"actionSupport_Vector_Machine_Regression")
        self.actionLasso_Regression = QAction(MainWindow)
        self.actionLasso_Regression.setObjectName(u"actionLasso_Regression")
        self.actionRidge_Regression = QAction(MainWindow)
        self.actionRidge_Regression.setObjectName(u"actionRidge_Regression")
        self.actionKnearneighbor = QAction(MainWindow)
        self.actionKnearneighbor.setObjectName(u"actionKnearneighbor")
        self.actionDecision_Tree = QAction(MainWindow)
        self.actionDecision_Tree.setObjectName(u"actionDecision_Tree")
        self.actionRandom_Forest = QAction(MainWindow)
        self.actionRandom_Forest.setObjectName(u"actionRandom_Forest")
        self.actionSupport_Vector_Machine_Classifier = QAction(MainWindow)
        self.actionSupport_Vector_Machine_Classifier.setObjectName(
            u"actionSupport_Vector_Machine_Classifier")
        self.actionNeural_Network_2 = QAction(MainWindow)
        self.actionNeural_Network_2.setObjectName(u"actionNeural_Network_2")
        self.actionNaive_Bayes = QAction(MainWindow)
        self.actionNaive_Bayes.setObjectName(u"actionNaive_Bayes")
        self.actionGradient_Boosting_Classifier = QAction(MainWindow)
        self.actionGradient_Boosting_Classifier.setObjectName(
            u"actionGradient_Boosting_Classifier")
        self.centralwidget = QWidget(MainWindow)
        self.centralwidget.setObjectName(u"centralwidget")
        self.gridLayout_2 = QGridLayout(self.centralwidget)
        self.gridLayout_2.setObjectName(u"gridLayout_2")
        self.treeWidget = QTreeWidget(self.centralwidget)
        # __qtreewidgetitem = QTreeWidgetItem(self.treeWidget)
        # __qtreewidgetitem1 = QTreeWidgetItem(__qtreewidgetitem)
        # QTreeWidgetItem(__qtreewidgetitem1)
        # __qtreewidgetitem2 = QTreeWidgetItem(__qtreewidgetitem)
        # QTreeWidgetItem(__qtreewidgetitem2)
        # __qtreewidgetitem3 = QTreeWidgetItem(self.treeWidget)
        # __qtreewidgetitem4 = QTreeWidgetItem(__qtreewidgetitem3)
        # QTreeWidgetItem(__qtreewidgetitem4)
        self.treeWidget.setObjectName(u"treeWidget")
        self.treeWidget.setMinimumSize(QSize(150, 0))
        # self.treeWidget.setMaximumSize(QSize(200, 16777215))
        self.mainSplitter = QSplitter(self.centralwidget)
        self.mainSplitter.setOrientation(Qt.Horizontal)

        self.mainSplitter.addWidget(self.treeWidget)

        self.mdiArea = QMdiArea(self.centralwidget)
        self.mdiArea.setObjectName(u"mdiArea")
        self.mdiArea.setMinimumSize(QSize(475, 0))

        # Sub Windows start here
        # self.subwindow = QWidget()
        # self.subwindow.setObjectName(u"subwindow")
        # self.subwindow.setMinimumSize(QSize(200, 475))
        # self.gridLayout = QGridLayout(self.subwindow)
        # self.gridLayout.setObjectName(u"gridLayout")
        # self.splitter = QSplitter(self.subwindow)
        # self.splitter.setObjectName(u"splitter")
        # self.splitter.setOrientation(Qt.Horizontal)
        # self.frame = QFrame(self.splitter)
        # self.frame.setObjectName(u"frame")

        

        # palette = QPalette()
        # brush = QBrush(QColor(255, 255, 255, 255))
        # brush.setStyle(Qt.SolidPattern)
        # palette.setBrush(QPalette.Active, QPalette.Base, brush)
        # palette.setBrush(QPalette.Active, QPalette.Window, brush)
        # palette.setBrush(QPalette.Inactive, QPalette.Base, brush)
        # palette.setBrush(QPalette.Inactive, QPalette.Window, brush)
        # palette.setBrush(QPalette.Disabled, QPalette.Base, brush)
        # palette.setBrush(QPalette.Disabled, QPalette.Window, brush)
        # self.frame.setPalette(palette)
        # self.frame.setAutoFillBackground(True)
        # self.frame.setFrameShape(QFrame.NoFrame)
        # self.frame.setFrameShadow(QFrame.Raised)
        # self.splitter.addWidget(self.frame)
        # self.frame_2 = QFrame(self.splitter)
        # self.frame_2.setObjectName(u"frame_2")
        # palette1 = QPalette()
        # palette1.setBrush(QPalette.Active, QPalette.Base, brush)
        # palette1.setBrush(QPalette.Active, QPalette.Window, brush)
        # palette1.setBrush(QPalette.Inactive, QPalette.Base, brush)
        # palette1.setBrush(QPalette.Inactive, QPalette.Window, brush)
        # palette1.setBrush(QPalette.Disabled, QPalette.Base, brush)
        # palette1.setBrush(QPalette.Disabled, QPalette.Window, brush)
        # self.frame_2.setPalette(palette1)
        # self.frame_2.setAutoFillBackground(True)
        # self.frame_2.setFrameShape(QFrame.NoFrame)
        # self.frame_2.setFrameShadow(QFrame.Raised)
        # self.splitter.addWidget(self.frame_2)
        # self.gridLayout.addWidget(self.splitter, 0, 0, 1, 1)

        # self.subwindow_2 = QWidget()
        # self.subwindow_2.setObjectName(u"subwindow_2")
        # self.subwindow_2.setMinimumSize(QSize(200, 475))
        # self.mdiArea.addSubWindow(self.subwindow_2)

        self.mainSplitter.addWidget(self.mdiArea)
        self.gridLayout_2.addWidget(self.mainSplitter,0,0,1,1)
        

        MainWindow.setCentralWidget(self.centralwidget)
        self.menubar = QMenuBar(MainWindow)
        self.menubar.setObjectName(u"menubar")
        self.menubar.setGeometry(QRect(0, 0, 769, 21))
        self.menuMenu = QMenu(self.menubar)
        self.menuMenu.setObjectName(u"menuMenu")
        self.menuWell = QMenu(self.menubar)
        self.menuWell.setObjectName(u"menuWell")
        self.menuPlot = QMenu(self.menubar)
        self.menuPlot.setObjectName(u"menuPlot")
        self.menuAdvanced = QMenu(self.menubar)
        self.menuAdvanced.setObjectName(u"menuAdvanced")
        self.menuRegression_Models = QMenu(self.menuAdvanced)
        self.menuRegression_Models.setObjectName(u"menuRegression_Models")
        self.menuClasification_Models = QMenu(self.menuAdvanced)
        self.menuClasification_Models.setObjectName(
            u"menuClasification_Models")
        self.menuHelp = QMenu(self.menubar)
        self.menuHelp.setObjectName(u"menuHelp")
        MainWindow.setMenuBar(self.menubar)
        self.statusbar = QStatusBar(MainWindow)
        self.statusbar.setObjectName(u"statusbar")
        MainWindow.setStatusBar(self.statusbar)

        self.menubar.addAction(self.menuMenu.menuAction())
        self.menubar.addAction(self.menuWell.menuAction())
        self.menubar.addAction(self.menuPlot.menuAction())
        self.menubar.addAction(self.menuAdvanced.menuAction())
        self.menubar.addAction(self.menuHelp.menuAction())
        self.menuMenu.addAction(self.actionCargar)
        self.menuMenu.addAction(self.actionOpen_Database)
        self.menuMenu.addAction(self.actionOpen_Well)
        self.menuMenu.addAction(self.actionOpen_Template)
        self.menuWell.addAction(self.actionSelect_Well)
        self.menuWell.addAction(self.actionManage_Zone_Picks)
        self.menuWell.addAction(self.actionCustom_Zones)
        self.menuWell.addAction(self.actionExtract_Petrophysics)
        self.menuPlot.addAction(self.actionScatter_Plot)
        self.menuPlot.addAction(self.actionHistogram_Plot)
        self.menuPlot.addAction(self.actionHeat_Map)
        self.menuAdvanced.addAction(self.menuClasification_Models.menuAction())
        self.menuAdvanced.addAction(self.menuRegression_Models.menuAction())
        self.menuRegression_Models.addAction(self.actionNeural_Network)
        self.menuRegression_Models.addAction(
            self.actionMultiple_Linear_Regression)
        self.menuRegression_Models.addAction(
            self.actionSupport_Vector_Machine_Regression)
        self.menuRegression_Models.addAction(self.actionLasso_Regression)
        self.menuRegression_Models.addAction(self.actionRidge_Regression)
        self.menuClasification_Models.addAction(self.actionKnearneighbor)
        self.menuClasification_Models.addAction(self.actionDecision_Tree)
        self.menuClasification_Models.addAction(self.actionRandom_Forest)
        self.menuClasification_Models.addAction(
            self.actionSupport_Vector_Machine_Classifier)
        self.menuClasification_Models.addAction(self.actionNeural_Network_2)
        self.menuClasification_Models.addAction(self.actionNaive_Bayes)
        self.menuClasification_Models.addAction(
            self.actionGradient_Boosting_Classifier)

        self.retranslateUi(MainWindow)

        QMetaObject.connectSlotsByName(MainWindow)
    # setupUi

    def retranslateUi(self, MainWindow):
        MainWindow.setWindowTitle(QCoreApplication.translate(
            "MainWindow", u"InnoPetrol", None))
        self.actionCargar.setText(QCoreApplication.translate(
            "MainWindow", u"New Project", None))
        self.actionOpen_Database.setText(
            QCoreApplication.translate("MainWindow", u"Open Project", None))
        self.actionOpen_Well.setText(
            QCoreApplication.translate("MainWindow", u"Add Well", None))
        self.actionOpen_Template.setText(
            QCoreApplication.translate("MainWindow", u"Open Template", None))
        self.actionSelect_Well.setText(
            QCoreApplication.translate("MainWindow", u"Select Well", None))
        self.actionManage_Zone_Picks.setText(
            QCoreApplication.translate("MainWindow", u"Manage Zone/Picks", None))
        self.actionCustom_Zones.setText(
            QCoreApplication.translate("MainWindow", u"Custom Zones", None))
        self.actionExtract_Petrophysics.setText(
            QCoreApplication.translate("MainWindow", u"Extract Petrophysics", None))
        self.actionScatter_Plot.setText(
            QCoreApplication.translate("MainWindow", u"Scatter Plot", None))
        self.actionHistogram_Plot.setText(
            QCoreApplication.translate("MainWindow", u"Histogram Plot", None))
        self.actionHeat_Map.setText(
            QCoreApplication.translate("MainWindow", u"Heat Map", None))
        self.actionNeural_Network.setText(
            QCoreApplication.translate("MainWindow", u"Neural Network", None))
        self.actionMultiple_Linear_Regression.setText(
            QCoreApplication.translate("MainWindow", u"Multiple Linear Regression", None))
        self.actionSupport_Vector_Machine_Regression.setText(QCoreApplication.translate(
            "MainWindow", u"Support Vector Machine Regression", None))
        self.actionLasso_Regression.setText(
            QCoreApplication.translate("MainWindow", u"Lasso Regression", None))
        self.actionRidge_Regression.setText(
            QCoreApplication.translate("MainWindow", u"Ridge Regression", None))
        self.actionKnearneighbor.setText(
            QCoreApplication.translate("MainWindow", u"Knearneighbor", None))
        self.actionDecision_Tree.setText(
            QCoreApplication.translate("MainWindow", u"Decision Tree", None))
        self.actionRandom_Forest.setText(
            QCoreApplication.translate("MainWindow", u"Random Forest", None))
        self.actionSupport_Vector_Machine_Classifier.setText(QCoreApplication.translate(
            "MainWindow", u"Support Vector Machine Classifier", None))
        self.actionNeural_Network_2.setText(
            QCoreApplication.translate("MainWindow", u"Neural Network", None))
        self.actionNaive_Bayes.setText(
            QCoreApplication.translate("MainWindow", u"Naive Bayes", None))
        self.actionGradient_Boosting_Classifier.setText(QCoreApplication.translate(
            "MainWindow", u"Gradient Boosting Classifier", None))
        ___qtreewidgetitem = self.treeWidget.headerItem()
        ___qtreewidgetitem.setText(
            0, QCoreApplication.translate("MainWindow", u"Wells", None))

        # __sortingEnabled = self.treeWidget.isSortingEnabled()
        # self.treeWidget.setSortingEnabled(False)
        # ___qtreewidgetitem1 = self.treeWidget.topLevelItem(0)
        # ___qtreewidgetitem1.setText(
        #     0, QCoreApplication.translate("MainWindow", u"Well 1", None))
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
        # ___qtreewidgetitem5.setText(
        #     0, QCoreApplication.translate("MainWindow", u"CaliOver", None))
        # ___qtreewidgetitem6 = self.treeWidget.topLevelItem(1)
        # ___qtreewidgetitem6.setText(
        #     0, QCoreApplication.translate("MainWindow", u"Well 2", None))
        # ___qtreewidgetitem7 = ___qtreewidgetitem6.child(0)
        # ___qtreewidgetitem7.setText(
        #     0, QCoreApplication.translate("MainWindow", u"Lines", None))
        # ___qtreewidgetitem8 = ___qtreewidgetitem7.child(0)
        # ___qtreewidgetitem8.setText(
        #     0, QCoreApplication.translate("MainWindow", u"LDI", None))
        # self.treeWidget.setSortingEnabled(__sortingEnabled)

        # self.subwindow.setWindowTitle(QCoreApplication.translate("MainWindow", u"Subwindow", None))
        # self.subwindow_2.setWindowTitle(QCoreApplication.translate("MainWindow", u"Subwindow", None))
        self.menuMenu.setTitle(
            QCoreApplication.translate("MainWindow", u"File", None))
        self.menuWell.setTitle(
            QCoreApplication.translate("MainWindow", u"Well", None))
        self.menuPlot.setTitle(
            QCoreApplication.translate("MainWindow", u"Plot", None))
        self.menuAdvanced.setTitle(
            QCoreApplication.translate("MainWindow", u"Advanced", None))
        self.menuRegression_Models.setTitle(
            QCoreApplication.translate("MainWindow", u"Regression Models", None))
        self.menuClasification_Models.setTitle(
            QCoreApplication.translate("MainWindow", u"Clasification Models", None))
        self.menuHelp.setTitle(
            QCoreApplication.translate("MainWindow", u"Help", None))
    # retranslateUi
