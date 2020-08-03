import sys
from PySide2 import QtWidgets
from test1 import Ui_MainWindow
from PySide2 import QtGui,QtCore
from PySide2.QtCore import Qt
from PySide2.QtCore import Slot
import types

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
        msg=str(file[0])+" cargado correctamente"
        title="Loading LAS file"
        self.show_about_dialog(title,msg)
        print(file[0])
    def show_about_dialog(self,title,msg): ## NUEVA LÍNEA
        msg_box = QtWidgets.QMessageBox() ## NUEVA LÍNEA
        msg_box.setIcon(QtWidgets.QMessageBox.Information) ## NUEVA LÍNEA
        msg_box.setText(msg) ## NUEVA LÍNEA
        msg_box.setWindowTitle(title) ## NUEVA LÍNEA
        msg_box.setStandardButtons(QtWidgets.QMessageBox.Close) ## NUEVA LÍNEA
        msg_box.exec_() ## NUEVA LÍNEA        


app = QtWidgets.QApplication(sys.argv)
window = MainWindow()

window.show()
app.exec_()