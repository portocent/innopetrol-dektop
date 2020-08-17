from PySide2 import QtGui, QtCore, QtWidgets


tableWidget = QtWidgets.QTableWidget()
tableWidget.setItemDelegate(QtWidgets.QItemDelegate())
tableWidget.setColumnCount(1)

for i in range(5):
    tableWidget.insertRow(i)
    item = QtWidgets.QTableWidgetItem("Item %02d" % (i+1))
    item.setBackground(QtGui.QColor(255, 25+30*i, 75))
    tableWidget.setItem(i, 0, item)

try:
    import hou
    tableWidget.setParent(hou.ui.mainQtWindow(), QtCore.Qt.Window)
except:
    pass

tableWidget.show()