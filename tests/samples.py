import sys
from PySide2 import QtGui, QtCore, QtWidgets

class ApplicationWindow(QtWidgets.QMainWindow):
    def __init__(self):
        QtWidgets.QMainWindow.__init__(self)
        self.setAttribute(QtCore.Qt.WA_DeleteOnClose)
        self.setWindowTitle("Cluster View")
        self.initUI()

        self.window.setFocus()
        self.setCentralWidget(self.window)
        self.showMaximized()

    def splitterMoved(self, sender) :
        print ("ok", sender)
        receiver = self.split2 if sender is self.split3 else self.split3
        receiver.blockSignals(True)
        receiver.setSizes(sender.sizes())
        receiver.blockSignals(False)

    def initUI(self) :
        self.window = QtWidgets.QWidget()

        self.editor1 = QtWidgets.QTextEdit()
        self.editor2 = QtWidgets.QTextEdit()
        self.editor3 = QtWidgets.QTextEdit()
        self.editor4 = QtWidgets.QTextEdit()

        self.split1 = QtWidgets.QSplitter()
        self.split2 = QtWidgets.QSplitter()
        self.split3 = QtWidgets.QSplitter()
        self.split2.setOrientation(QtCore.Qt.Vertical)
        self.split3.setOrientation(QtCore.Qt.Vertical)

        self.split2.addWidget(self.editor1)
        self.split2.addWidget(self.editor2)
        self.split3.addWidget(self.editor3)
        self.split3.addWidget(self.editor4)

        self.connect(self.split2, QtCore.SIGNAL("splitterMoved(int, int)"), lambda x : self.splitterMoved(self.split2))
        self.connect(self.split3, QtCore.SIGNAL("splitterMoved(int, int)"), lambda x : self.splitterMoved(self.split3))

        self.split1.addWidget(self.split2)
        self.split1.addWidget(self.split3)

        self.layout = QtWidgets.QHBoxLayout()
        self.layout.addWidget(self.split1)
        self.window.setLayout(self.layout)

def main() :
    qApp = QtWidgets.QApplication(sys.argv)
    qApp.setStyle('cleanlooks')
    aw = ApplicationWindow()
    aw.show()
    sys.exit(qApp.exec_())

if __name__ == '__main__':
    main()