import sys
from PySide2 import QtWidgets
from GUI import Ui_MainWindow
from PySide2 import QtGui,QtCore
from PySide2.QtCore import Qt
from PySide2.QtCore import Slot
import types
from lasProcesor import  *
import os

def paintSub(self, event):
    painter = QtGui.QPainter(self)
    #brush = QtGui.QBrush()
    # brush.setColor(QtGui.QColor('black'))
    # brush.setStyle(Qt.SolidPattern)
    #rect = QtCore.QRect(0, 0, painter.device().width(), painter.device().height())
    #painter.fillRect(rect, brush)
    currentSize  = self.frameGeometry()
    painter.drawRect(1, 1, self.width()-2,self.height()-2) 
    #painter.set()
    #painter.end()
class MainWindow(QtWidgets.QMainWindow, Ui_MainWindow):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.setupUi(self)
        self.wells=[]
        #self.subwindow.paintEvent = types.MethodType(paintSub,self.subwindow)
        self.menuOptions()
        self.frame.paintEvent = types.MethodType(paintSub,self.frame)
        self.statusBar().showMessage('Ready')
        
        
    def menuOptions(self):
        #Open Well
        addWellAction=self.actionOpen_Well
        addWellAction.setShortcut('Ctrl+O')
        addWellAction.setStatusTip('Open Well...')       
        addWellAction.triggered.connect(self._browseFile)
        self.menuMenu.removeAction(self.actionOpen_Well)
        self.actionOpen_Well=None
        self.actionOpen_Well=addWellAction
        self.menuMenu.addAction(self.actionOpen_Well)
        #self.actionOpen_Well
    @Slot()    
    def _browseFile(self):
        #option=QtWidgets.QFileDialog.options()
        file=QtWidgets.QFileDialog.getOpenFileName(self,"Open LAS","Default File","All Files(*)")
        head, fileName=os.path.split(file[0])
        error=""
        title="Loading LAS file"
        well = Well()
        error=well.loadLas(file[0],fileName)
        if not error:
            msg=str(fileName)+" cargado correctamente"
            self.wells.append(well)
        else:
            msg=str(fileName)+" no pudo ser cargado archivo inválido:\n" + error
            
            #title="Loading LAS file"            
        self.show_about_dialog(title,msg)
        #print(file[0])
    def show_about_dialog(self,title,msg): ## NUEVA LÍNEA
        msg_box = QtWidgets.QMessageBox() ## NUEVA LÍNEA
        msg_box.setIcon(QtWidgets.QMessageBox.Information) ## NUEVA LÍNEA
        msg_box.setText(msg) ## NUEVA LÍNEA
        msg_box.setWindowTitle(title) ## NUEVA LÍNEA
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Close) ## NUEVA LÍNEA
        msg_box.exec_() ## NUEVA LÍNEA
    def addSubWindow(self,well):
        self.subwindows=[]
        subwindow = QWidget()
        subwindow.setObjectName(u"subwindow")
        subwindow.setMinimumSize(QSize(200, 475))
        self.gridLayout = QGridLayout(self.subwindow)
        self.gridLayout.setObjectName(u"gridLayout")
        self.splitter = QSplitter(self.subwindow)
        self.splitter.setObjectName(u"splitter")
        self.splitter.setOrientation(Qt.Horizontal)
        self.frame = QFrame(self.splitter)
        self.frame.setObjectName(u"frame")
        
        palette = QPalette()
        brush = QBrush(QColor(255, 255, 255, 255))
        brush.setStyle(Qt.SolidPattern)
        palette.setBrush(QPalette.Active, QPalette.Base, brush)
        palette.setBrush(QPalette.Active, QPalette.Window, brush)
        palette.setBrush(QPalette.Inactive, QPalette.Base, brush)
        palette.setBrush(QPalette.Inactive, QPalette.Window, brush)
        palette.setBrush(QPalette.Disabled, QPalette.Base, brush)
        palette.setBrush(QPalette.Disabled, QPalette.Window, brush)
        self.frame.setPalette(palette)
        self.frame.setAutoFillBackground(True)
        self.frame.setFrameShape(QFrame.NoFrame)
        self.frame.setFrameShadow(QFrame.Raised)
        self.splitter.addWidget(self.frame)
        self.frame_2 = QFrame(self.splitter)
        self.frame_2.setObjectName(u"frame_2")
        palette1 = QPalette()
        palette1.setBrush(QPalette.Active, QPalette.Base, brush)
        palette1.setBrush(QPalette.Active, QPalette.Window, brush)
        palette1.setBrush(QPalette.Inactive, QPalette.Base, brush)
        palette1.setBrush(QPalette.Inactive, QPalette.Window, brush)
        palette1.setBrush(QPalette.Disabled, QPalette.Base, brush)
        palette1.setBrush(QPalette.Disabled, QPalette.Window, brush)
        self.frame_2.setPalette(palette1)
        self.frame_2.setAutoFillBackground(True)
        self.frame_2.setFrameShape(QFrame.NoFrame)
        self.frame_2.setFrameShadow(QFrame.Raised)
        self.splitter.addWidget(self.frame_2)
        self.gridLayout.addWidget(self.splitter, 0, 0, 1, 1)    
        self.mdiArea.addSubWindow(self.subwindow)        


app = QtWidgets.QApplication(sys.argv)
window = MainWindow()

window.show()
app.exec_()