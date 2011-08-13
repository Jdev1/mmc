# -*- coding: utf-8 -*-

"""The user interface for our app"""


import os
import sys
import logging
import datetime
# PyQt4, PySide stuff
from qtimport import *

# Import the compiled UI module
import gui_resources
from file_carving_ui import Ui_filecarvingWidget
from mainwindow import Ui_MainWindow
from mm_context import CContext
from gui_options import CGuiOptions
from preprocessing import preprocessing_context
from preprocessing import fsstat_context
from reassembly.reassembly import reassembly_context

class Jobs:
    NONE=0x0
    CLASSIFY=0x1
    REASSEMBLE=0x2

class CThreadWorker(QtCore.QThread):
    sProgress = QtCore.Signal(int)
    sFinished = QtCore.Signal()
    sResult = QtCore.Signal(bool, int, int)

    def __init__(self, pOptions, pContext, pJobs):
        super(CThreadWorker, self).__init__()
        self.mOptions = pOptions
        self.mContext = pContext
        self.mJobs = pJobs
        self.mRunningJob = Jobs.NONE
        self.mLastTs = datetime.datetime.now()

    def progressCallback(self, pProgress):
        if self.mJobs & Jobs.CLASSIFY == Jobs.CLASSIFY \
                and \
                self.mJobs & Jobs.REASSEMBLE == Jobs.REASSEMBLE:
                    if self.mRunningJob & Jobs.REASSEMBLE == Jobs.REASSEMBLE:
                        self.sProgress.emit(85 + pProgress * 0.15)
                    else:
                        self.sProgress.emit(pProgress * 0.85)
        else:
            self.sProgress.emit(pProgress)

    def finishedCallback(self):
        #self.sProgress.emit(100)
        self.sFinished.emit()

    def resultCallback(self, pHeader, pOffset, pSize):
        self.sResult.emit(pHeader, pOffset, pSize)

    def run(self):
        if self.mJobs & Jobs.CLASSIFY == Jobs.CLASSIFY:
            self.mRunningJob = Jobs.CLASSIFY
            self.mContext.runClassify(self.mOptions, self)
        if self.mJobs & Jobs.REASSEMBLE == Jobs.REASSEMBLE:
            self.mRunningJob = Jobs.REASSEMBLE
            self.mContext.runReassembly(self.mOptions, self)


# Create a class for our main window
class Gui_Qt(QtGui.QMainWindow):

    def __init__(self, parent=None):
        super(Gui_Qt, self).__init__(parent)

        self.__mLock = QtCore.QMutex()

        #lLoader = QtUiTools.QUiLoader()
        #lFile = QtCore.QFile(":/images/icon_mm_carver.png")
        #lFile.open(QtCore.QFile.ReadOnly)
        #lIcon = lLoader.load(lFile, self)
        #self.customwidget = lLoader.load(lFile, self)
        #lFile.close()

        self.ui = Ui_MainWindow()
        self.ui.setupUi(self)
        #self.setWindowIcon(lIcon)
        
        #lLoader = QtUiTools.QUiLoader()
        #lFile = QtCore.QFile(":/forms/file_carving_ui.ui")
        #lFile.open(QtCore.QFile.ReadOnly)
        #self.customwidget = lLoader.load(lFile, self)
        #lFile.close()
        #self.setCentralWidget(self.customwidget)

        self.centralwidget = QtGui.QWidget()
        self.customwidget = Ui_filecarvingWidget()
        self.customwidget.setupUi(self.centralwidget)
        self.setCentralWidget(self.centralwidget)

        # adjust widget elements
        for lPreprocessor in preprocessing_context.CPreprocessing.getPreprocessors():
            self.customwidget.preprocessing.addItem(lPreprocessor['name'])

        self.customwidget.outputformat.addItem("MKV")
        self.customwidget.outputformat.addItem("JPEG")
        self.customwidget.outputformat.addItem("PNG")

        for lCPU in reversed(range(CContext.getCPUs())):
            self.customwidget.maxCPUs.addItem(str(lCPU + 1))

        for lAssembly in reassembly_context.CReassembly.getAssemblyMethods():
            self.customwidget.assemblyMethod.addItem(lAssembly)

        self.customwidget.blockStatus.addItem("allocated")
        self.customwidget.blockStatus.addItem("unallocated")

        self.customwidget.resultTable.setColumnCount(4)
        self.customwidget.resultTable.setHorizontalHeaderLabels(("Header", "Fragment", "Offset", "Size"))
        self.customwidget.resultTable.horizontalHeader().setResizeMode(QtGui.QHeaderView.Stretch)
        self.customwidget.resultTable.verticalHeader().setVisible(False)
        self.numRowsResult = 0

        self.customwidget.progressBar.setMaximum(100)
        self.customwidget.progressBar.setMinimum(0)

        # actions
        self.ui.actionExit.triggered.connect(self.on_actionExit_triggered)
        self.ui.actionAbout.triggered.connect(self.on_actionAbout_triggered)
        self.ui.actionChooseOutputDir.triggered.connect(self.on_outputDirButton_clicked)
        self.ui.actionOpenImage.triggered.connect(self.on_inputFileButton_clicked)
        self.customwidget.classifyButton.clicked.connect(self.on_classifyButton_clicked)
        self.customwidget.reassembleButton.clicked.connect(self.on_reassembleButton_clicked)
        self.customwidget.processButton.clicked.connect(self.on_processButton_clicked)
        self.customwidget.inputFileButton.clicked.connect(self.on_inputFileButton_clicked)
        self.customwidget.outputDirButton.clicked.connect(self.on_outputDirButton_clicked)
        self.customwidget.inputFile.textChanged.connect(self.on_inputFile_changed)

        # init values
        self.customwidget.inputFile.setText("data/image_ref_h264_ntfs.img")
        self.customwidget.outputDir.setText("/tmp/temp")

    def on_actionExit_triggered(self): 
        self.close()

    def on_inputFile_changed(self, pPath):
        if os.path.exists(pPath):
            lOptions = self.__getOptions()
            lGeometry = fsstat_context.CFsStatContext.getFsGeometry(lOptions)
            logging.info("FS Info: " + str(lGeometry))
            self.customwidget.offset.setText(str(lGeometry.offset))
            self.customwidget.fragmentSize.setText(str(lGeometry.blocksize))
            self.customwidget.fsInfo.setText("FS Info: " + str(lGeometry))
        else:
            self.customwidget.fsInfo.setText("<html><font color=\"#FF0000\">Imagefile does not exist.</font></html>")

    def on_actionAbout_triggered(self, pChecked=None):
        QtGui.QMessageBox.about(self, "Multimedia File Carver",
            "<html>Developed by Rainer Poisel, Vasileios Miskos and Manfred Ruzicka\n &copy; 2011 St. Poelten University of Applied Sciences</html>")

    def on_inputFileButton_clicked(self, pChecked=None):
        lFilename = QtGui.QFileDialog.getOpenFileName(self, \
                "Choose Image", \
                os.path.dirname(self.customwidget.inputFile.text()), \
                "All Files (*)")
        if lFilename[0] != "":
            self.customwidget.inputFile.setText(lFilename[0])

    def on_outputDirButton_clicked(self, pChecked=None):
        lDialog = QtGui.QFileDialog()
        lDialog.setFileMode(QtGui.QFileDialog.Directory)
        lFilename = lDialog.getExistingDirectory(self, \
                "Choose Output Directory", \
                os.path.dirname(self.customwidget.outputDir.text()), \
                QtGui.QFileDialog.ShowDirsOnly)
        if lFilename != "":
            self.customwidget.outputDir.setText(lFilename)

    def on_processButton_clicked(self, pChecked=None):
        if not os.path.exists(self.customwidget.inputFile.text()):
            QtGui.QMessageBox.about(self, "Error",
                "Please make sure that your input file exists.")
            return
        elif not os.path.isdir(self.customwidget.outputDir.text()):
            QtGui.QMessageBox.about(self, "Error",
                "Please make sure that your output directory exists.")
            return
        elif self.__mLock.tryLock() == True:
            self.mLastTs = datetime.datetime.now()
            self.mContext = CContext()
            self.__clearFragments()
            self.customwidget.progressBar.setValue(0)
            self.__startWorker(Jobs.CLASSIFY|Jobs.REASSEMBLE)

    def on_reassembleButton_clicked(self, pChecked=None):
        if len(self.mContext.getH264Fragments()) is 0:
            QtGui.QMessageBox.about(self, "Error",
                "What would you like to reassemble? No H.264 headers have been classified yet!")
        elif self.__mLock.tryLock() == True:
            self.mLastTs = datetime.datetime.now()
            #self.mContext = CContext()
            self.customwidget.progressBar.setValue(0)
            self.__startWorker(Jobs.REASSEMBLE)

    def on_classifyButton_clicked(self, pChecked=None):
        if not os.path.exists(self.customwidget.inputFile.text()):
            QtGui.QMessageBox.about(self, "Error",
                "Please make sure that your input file exists.")
            return
        elif not os.path.isdir(self.customwidget.outputDir.text()):
            QtGui.QMessageBox.about(self, "Error",
                "Please make sure that your output directory exists.")
            return
        elif self.__mLock.tryLock() == True:
            self.mLastTs = datetime.datetime.now()
            self.mContext = CContext()
            self.__clearFragments()
            self.customwidget.progressBar.setValue(0)
            self.__startWorker(Jobs.CLASSIFY)

    def __clearFragments(self):
        lCnt = self.customwidget.resultTable.rowCount() - 1
        while (lCnt >= 0):
            self.customwidget.resultTable.removeRow(lCnt)
            lCnt -= 1
        self.numRowsResult = 0
        self.customwidget.resultTable.update()


    def __enableElements(self, pEnabled):
        self.customwidget.classifyButton.setEnabled(pEnabled)
        self.customwidget.reassembleButton.setEnabled(pEnabled)
        self.customwidget.processButton.setEnabled(pEnabled)
        # TODO add all elements that should be deactivated

    def __startWorker(self, pJob):
        lOptions = self.__getOptions()
        self.__mWorker = CThreadWorker(lOptions, self.mContext, pJob)
        self.__mWorker.sProgress.connect(self.on_progress_callback, \
                QtCore.Qt.QueuedConnection)
        self.__mWorker.sFinished.connect(self.on_finished_callback, \
                QtCore.Qt.QueuedConnection)
        self.__mWorker.sResult.connect(self.on_result_callback, \
                QtCore.Qt.QueuedConnection)
        self.__enableElements(False)
        self.__mWorker.start(QtCore.QThread.IdlePriority)

    def __getOptions(self):
        lOptions = CGuiOptions()
        lOptions.preprocess = self.customwidget.preprocessing.currentText()
        if self.customwidget.outputformat.currentText() == "PNG":
            lOptions.outputformat = "%08d.png"
        elif self.customwidget.outputformat.currentText() == "MKV":
            lOptions.outputformat = "movie.mkv"
        else:
            lOptions.outputformat = "%08d.jpg"
        lOptions.imagefile = self.customwidget.inputFile.text()
        lOptions.output = self.customwidget.outputDir.text()
        lOptions.offset = int(self.customwidget.offset.text())
        lOptions.fragmentsize = int(self.customwidget.fragmentSize.text())
        lOptions.incrementsize = lOptions.fragmentsize
        lOptions.blockgap = int(self.customwidget.blockGap.text())
        lOptions.minfragsize = int(self.customwidget.minimumFragmentSize.text())
        lOptions.hdrsize = int(self.customwidget.headerSize.text())
        lOptions.extractsize = int(self.customwidget.extractSize.text()) * 1024
        lOptions.assemblymethod = self.customwidget.assemblyMethod.currentText()
        lOptions.minpicsize = int(self.customwidget.minPicSize.text())
        lOptions.similarity = int(self.customwidget.similarity.text())
        lOptions.blockstatus = self.customwidget.blockStatus.currentText()
        lOptions.maxcpus = int(self.customwidget.maxCPUs.currentText())
        lOptions.verbose = False
        return lOptions

    def on_result_callback(self, pHeader, pOffset, pSize):
        self.customwidget.resultTable.insertRow(self.numRowsResult)

        if pHeader == True:
            lItem = QtGui.QTableWidgetItem("H")
        else:
            lItem = QtGui.QTableWidgetItem("")
        lItem.setFlags(QtCore.Qt.ItemIsEnabled)
        lItem.setTextAlignment(QtCore.Qt.AlignCenter)
        self.customwidget.resultTable.setItem(self.numRowsResult, 0, lItem)

        lItem = QtGui.QTableWidgetItem("Fragment " + str(self.numRowsResult + 1))
        lItem.setFlags(QtCore.Qt.ItemIsEnabled)
        lItem.setTextAlignment(QtCore.Qt.AlignCenter)
        self.customwidget.resultTable.setItem(self.numRowsResult, 1, lItem)

        lItem = QtGui.QTableWidgetItem(str(pOffset))
        lItem.setFlags(QtCore.Qt.ItemIsEnabled)
        self.customwidget.resultTable.setItem(self.numRowsResult, 2, lItem)

        lItem = QtGui.QTableWidgetItem(str(pSize))
        lItem.setFlags(QtCore.Qt.ItemIsEnabled)
        self.customwidget.resultTable.setItem(self.numRowsResult, 3, lItem)

        self.numRowsResult += 1

    def on_progress_callback(self, pValue):
        lDelta = datetime.datetime.now() - self.mLastTs
        self.customwidget.duration.setText(str(lDelta))
        if 0 <= pValue <= 100:
            self.customwidget.progressBar.setValue(pValue)

    def on_finished_callback(self):
        lDelta = datetime.datetime.now() - self.mLastTs
        self.customwidget.duration.setText(str(lDelta))
        self.__mLock.unlock()
        self.__enableElements(True)


class CMain:
    def __init__(self):
        logging.basicConfig(format='%(asctime)s %(levelname)s %(message)s', level=logging.DEBUG)
        self.__mApp = QtGui.QApplication(sys.argv)
        self.__mWindow = Gui_Qt()

    def run(self):
        self.__mWindow.show()
        lReturn = self.__mApp.exec_()
        sys.exit(lReturn)


def main():
    lMain = CMain()
    lMain.run()

if __name__ == "__main__":
    main()
