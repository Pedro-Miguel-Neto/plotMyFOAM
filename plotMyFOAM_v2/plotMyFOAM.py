import os
import glob
import time
import numpy as np
import pandas as pd

from PyQt5.QtWidgets import QWidget, QComboBox, QPushButton, QCheckBox, QHBoxLayout, QVBoxLayout, QFileDialog, \
    QApplication
from PyQt5.QtCore import QRect, QFileSystemWatcher, QTimer
from PyQt5.QtGui import QIcon, QPixmap

import matplotlib.pyplot as plt
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas, \
    NavigationToolbar2QT as NavigationToolbar

import matplotlib

matplotlib.use('Qt5Agg')

class Line:
    def __init__(self, maindir, folder, field, timeNames=None):

        # Read data
        self.read_data(maindir, folder, field, timeNames)

    def read_data(self, maindir, folder, field, timeNames=None):

        start = time.time()

        if timeNames is None:
            self.timeNames = []
        else:
            self.timeNames = timeNames

        self.maindir = maindir
        self.folder = folder
        self.field = field

        # Retrieve a list of valid file paths
        self.fileList = [os.path.join(maindir, folder, x, field) for x in self.timeNames if
                         os.path.isfile(os.path.join(maindir, folder, x, field))]
        # Compute number of rows to skip (OpenFOAM header)  (will work only for a maximum of <nrows> to skip)
        self.rows2skip = \
            int(pd.read_table(self.fileList[0], sep="\s+", usecols=[0], nrows=50, index_col=False).value_counts()['#'])
        # Retrieve data file modified header
        self.header = pd.read_table(self.fileList[0], sep="\s+", nrows=0, skiprows=self.rows2skip).columns[1:]

        dataList = []
        for x in range(len(self.fileList)):
            data = pd.read_table(self.fileList[x], sep="\s+", header=self.rows2skip,
                                 usecols=range(len(self.header)), names=self.header).fillna(0)
            dataList += [data]
            if x == len(self.fileList) - 1:
                # Record file height for reread function
                self.height = len(data)
        self.data = pd.concat(dataList, ignore_index=True)

        end = time.time()
        print('Line method: read_data() time = ' + str(end - start))

    def re_read_data(self, tail):
        data = pd.read_table(self.fileList[-1], sep="\s+", header=self.rows2skip, usecols=range(len(self.header)),
                             names=self.header, dtype="float32").tail(tail).fillna(0)
        # Update dataframe height
        self.height = len(data)
        self.data = pd.concat([self.data, data], ignore_index=True)

    def is_plotted(self, column, value):
        self.plottedColumns[column] = value

    def reset_plottedColumns(self):
        self.plottedColumns = list(bytearray(len(self.header)))


class Widget(QWidget):
    def __init__(self, parent=None):
        super().__init__(parent)

        # Define application settings
        self.maindir = None
        self.setGeometry(275, 150, 1536, 512)  # Set the main-window position (x, y) and size (w, h)
        self.setWindowTitle('plotMyFOAM')
        appIcon = QPixmap("./plotMyFOAM.png").scaled(100, 100, 1,
                                                     1)  # (Width, height, scaleFactorMode, smoothPictureMode)
        self.setWindowIcon(QIcon(appIcon))

        # Declare figure axes and widget for plotting and displaying the figure
        self.fig, self.ax = plt.subplots()
        self.figure_widget = FigureCanvas(self.fig)
        plt.tight_layout()

        # Declare combo box widgets
        comboWidgetList = ['case', 'folder', 'field', 'column']
        self.comboWidgetList = [x + 'Combo' for x in comboWidgetList]
        self.comboWidgetFunctions = [x + '_changed' for x in comboWidgetList]  # @@@ unused for now
        for x in self.comboWidgetList:
            self.__dict__[x] = QComboBox()
            self.__dict__[x].setSizeAdjustPolicy(0)

        # Declare push button widgets
        buttonWidgetList = ['findFolder', 'clearPlot', 'updatePlot']
        self.buttonWidgetList = [x + 'Button' for x in buttonWidgetList]
        buttonWidgetCaptions = ['', '', '']
        buttonWidgetToolTips = ['Find a case folder', 'Clear plot', 'Update the plot']
        self.buttonWidgetFunctions = ['select_dir', 'clear_plot', 'refresh_data']  # @@@ unused for now
        for x, y, z in zip(self.buttonWidgetList, buttonWidgetCaptions, buttonWidgetToolTips):
            self.__dict__[x] = QPushButton(y)
            self.__dict__[x].setToolTip(z)

        self.findFolderButton.setFlat(True)
        self.imageFindFolder = QPixmap("./open-folder.png").scaled(20, 20, 1, 1)
        self.findFolderButton.setIcon(QIcon(self.imageFindFolder))
        self.findFolderButton.setIconSize(self.imageFindFolder.rect().size())

        self.clearPlotButton.setFlat(True)
        self.imageClearPlot = QPixmap("./paint-roller.png").scaled(20, 20, 1, 1)
        self.clearPlotButton.setIcon(QIcon(self.imageClearPlot))
        self.clearPlotButton.setIconSize(self.imageClearPlot.rect().size())

        self.updatePlotButton.setFlat(True)
        self.imageReload = QPixmap("./reload.png").scaled(20, 20, 1, 1)
        self.updatePlotButton.setIcon(QIcon(self.imageReload))
        self.updatePlotButton.setIconSize(self.imageReload.rect().size())
        self.updatePlotButton.setEnabled(False)

        # Declare other widgets
        self.toolbar = NavigationToolbar(self.figure_widget, self)
        self.watcher = QFileSystemWatcher([])

        self.checkBox = QCheckBox()
        self.checkBox.setGeometry(QRect(190, 80, 41, 22))
        self.checkBox.setStyleSheet("QCheckBox::indicator {width: 40px; height: 40px;}"
                                    "QCheckBox::indicator:unchecked {image: url(./switch-off.png);}"
                                    "QCheckBox::indicator:checked {image: url(./switch-on.png);}")
        self.checkBox.setToolTip('Enable/disable automatic refresher')

        self.timer = QTimer()
        self.timer.setSingleShot(True)

        # Declare file dialog widget
        self.dialog = QFileDialog(self, directory='~', caption='Open data file')
        self.dialog.setAcceptMode(QFileDialog.AcceptOpen)
        self.dialog.setFileMode(QFileDialog.Directory)

        # Define widget layout
        vlayout = QVBoxLayout(self)
        hlayout = QHBoxLayout()
        # Add widgets to horizontal layout
        hWidgetList = ['findFolderButton',
                       'caseCombo',
                       'folderCombo',
                       'fieldCombo',
                       'columnCombo',
                       'clearPlotButton',
                       'updatePlotButton',
                       'checkBox',
                       'toolbar']  # @@@ Merge the two lists and find a way to index the order

        for x in hWidgetList:
            hlayout.addWidget(self.__dict__[x])
        hlayout.addStretch(1)  # Fill blank space with N empty boxes from the sides
        # Add widgets to vertical layout
        vlayout.addLayout(hlayout)
        vlayout.addWidget(self.figure_widget)

        # Declare this global variable
        self.line = []
        self.modifiedFiles = []
        self.updateTimesList = []
        self.case_dict = {}

        # Connect widget signals to the appropriate functions       #@@@ Add a loop here maybe?
        self.caseCombo.textActivated.connect(self.case_changed)
        self.folderCombo.textActivated.connect(self.folder_changed)
        self.fieldCombo.textActivated.connect(self.field_changed)
        self.columnCombo.textActivated.connect(self.column_changed)
        self.findFolderButton.clicked.connect(self.select_dir)
        self.clearPlotButton.clicked.connect(self.clear_plot)
        self.updatePlotButton.clicked.connect(self.update_plot)
        self.watcher.fileChanged.connect(self.file_modification_update_1)
        self.watcher.directoryChanged.connect(self.dir_modification_update)
        self.checkBox.stateChanged.connect(self.checkBox_State)
        self.timer.timeout.connect(self.file_modification_update_2)

    def dir_modification_update(self, path):

        print(self.line_x.timeNames)

        print('\nA directory was modifed\n'+path)
        print('Directories: ' + str(self.watcher.directories()) + ' are being watched')

        maindir = os.path.join(path.split('/postProcessing')[0], 'postProcessing')
        folder = os.path.basename(path)
        self.folderNames = np.unique([os.path.basename(x) for x in glob.glob(maindir + '/*')])
        self.timeNames = np.unique([os.path.basename(x) for x in glob.glob(maindir + 2 * '/*')])
        self.fileNames = np.unique([os.path.basename(x) for x in glob.glob(maindir + 3 * '/*')])

        if path == maindir:
            for folder in self.folderNames:
                fieldname = os.path.join(self.maindir, folder)
                if os.path.isdir(fieldname) and folder not in [self.folderCombo.itemText(i) for i in range(self.folderCombo.count())]:
                    self.folderCombo.addItem(folder)

        for field in self.fileNames:
            for x in self.timeNames:
                filename = os.path.join(self.maindir, self.folderCombo.currentText(), x, field)
                if os.path.isfile(filename) and field not in [self.fieldCombo.itemText(i) for i in range(self.fieldCombo.count())]:
                    self.fieldCombo.addItem(field)

        flag = False
        for x in self.line:
            # Apply when times were added and at least one column is plotted # @@@ Does this leave space for data which does not get refreshed?
            # This assumes that times are not deleted, therefore the length always increases
            if (maindir, folder) == (x.maindir, x.folder) and len(self.timeNames) > len(x.fileList):
                # Apply only if the automatic refresher is on and there are plotted columns
                if self.checkBox.checkState() and sum(x.plottedColumns) > 0:
                    # Read the data, update the global line pointer, and activate the flag
                    x.read_data(x.maindir, x.folder, x.field, self.timeNames)
                    self.line_x = x
                    flag = True
                else:
                    # Set button state to enabled
                    self.updatePlotButton.setEnabled(True)
                    self.updateTimesList.append(x)
        # Trigger the replot if the flag was activated
        if flag:
            self.re_plot_data()

    # Function to select the case directory through the file dialog
    def select_dir(self):

        # Scan 'postProcessing/' folder for readable data
        if self.dialog.exec():
            print('\nCurrent case: ' + os.path.basename(self.dialog.selectedFiles()[0]) + '\n')
            # Define folder, time and file lists
            if os.path.isdir(os.path.join(self.dialog.selectedFiles()[0], 'postProcessing')):
                # Add option to the case combo box
                self.caseCombo.addItem(os.path.basename(self.dialog.selectedFiles()[0]))
                self.caseCombo.setCurrentIndex(-1)
                # Define the main directory
                self.maindir = os.path.join(self.dialog.selectedFiles()[0], 'postProcessing')
                # Create another variable to keep the last accepted folder, in case of the dialog cancellation
                self.currentMaindir = self.maindir
                # Add the full path to the case dictionary in the event the case combo box is triggered
                self.case_dict[os.path.basename(self.dialog.selectedFiles()[0])] = self.maindir
                # Add the main directory to the folder watch list
                self.watcher.addPath(self.maindir)
                # Create the names of some auxiliary lists
                comboList = ['folder', 'time', 'file']
                fieldList = [x + 'List' for x in comboList]
                fieldNames = [x + 'Names' for x in comboList]
                # Retrieve folder and file names from OpenFOAM postProcessing
                for f in range(len(fieldList)):
                    self.__dict__[fieldNames[f]] = np.unique([os.path.basename(x) for x in glob.glob(self.maindir + (f + 1) * '/*')])
                # Clear combo boxes and add dummy options (except for the case combo box)
                [self.__dict__[x].clear() for x in self.comboWidgetList[1:]]
                # Add options to folder combo box
                for folder in self.folderNames:
                    fieldname = os.path.join(self.maindir, folder)
                    if os.path.isdir(fieldname):
                        self.folderCombo.addItem(folder)
                self.folderCombo.setCurrentIndex(-1)
            else:
                print('\n_error_#01: the chosen directory does not CONTAIN a "postProcessing" folder\n')

    def case_changed(self, case):
        print('CASE CHANGED')
        case_changed_start = time.time()

        self.maindir = self.case_dict[case]
        # Create another variable to keep the last accepted folder, in case of the dialog cancellation
        self.currentMaindir = self.maindir
        comboList = ['folder', 'time', 'file']
        fieldList = [x + 'List' for x in comboList]
        fieldNames = [x + 'Names' for x in comboList]
        # Retrieve folder and file names from OpenFOAM postProcessing
        for f in range(len(fieldList)):
            self.__dict__[fieldNames[f]] = np.unique(
                [os.path.basename(x) for x in glob.glob(self.maindir + (f + 1) * '/*')])
        # Clear combo boxes and add dummy options
        [self.__dict__[x].clear() for x in self.comboWidgetList[1:]]
        # Add options to folder combo box
        for folder in self.folderNames:
            fieldname = os.path.join(self.maindir, folder)
            if os.path.isdir(fieldname):
                self.folderCombo.addItem(folder)
        self.folderCombo.setCurrentIndex(-1)

        case_changed_end = time.time()
        print('CASE CHANGED time = ' + str(case_changed_end - case_changed_start))

    # Function to connect the folder combo box options to the file combo box options
    def folder_changed(self, folder):
        print('FOLDER CHANGED')
        folder_changed_start = time.time()

        self.folder = folder  # @@@ Is there a way to eliminate this line?
        # Clear file and column combo boxes
        [self.__dict__[x].clear() for x in self.comboWidgetList[2:]]
        # Add options to file combo box
        for field in self.fileNames:
            for x in self.timeNames:
                filename = os.path.join(self.maindir, folder, x, field)
                if os.path.isfile(filename) and field not in [self.fieldCombo.itemText(i) for i in range(self.fieldCombo.count())]:
                    self.fieldCombo.addItem(field)
        self.fieldCombo.setCurrentIndex(-1)

        folder_changed_end = time.time()
        print('FOLDER CHANGED time = ' + str(folder_changed_end - folder_changed_start))

    # Function to read all files from different time folders, and of the same field, and concatenate the data
    def read_data(self):
        print('READ DATA')
        read_data_start = time.time()

        # Check if any Line instance is about to get duplicated
        which_line = list(map(lambda x: (self.line[x].maindir, self.line[x].folder, self.line[x].field) == (
            self.maindir, self.folder, self.field), range(len(self.line))))
        # Apply when there are plotted columns
        if sum(which_line) > 0:
            # Define pointer for selected line
            self.line_x = self.line[np.where(which_line)[0][0]]
            # Read the new data associated to that line and replace the old data
            self.line_x.read_data(self.maindir, self.folder, self.field,
                                  self.timeNames)  # @@@ This line should not execute unless a file is modified
        else:
            # Read the new data associated to that line and add the new line
            self.line.append(Line(self.maindir, self.folder, self.field, self.timeNames))
            # Initialize the plottedColumns list as bool(zeros)
            self.line[-1].reset_plottedColumns()
            # Define pointer for selected line
            self.line_x = self.line[-1]

        read_data_end = time.time()
        print('READ DATA time = ' + str(read_data_end - read_data_start))

    # Function to trigger the draw
    def plot_data(self):
        print('PLOT DATA')
        plot_data_start = time.time()

        # Update the times for unplotted lines
        if self.line_x in self.updateTimesList:
            self.read_data()
            self.updateTimesList.remove(self.line_x)

        # Apply only to columns that are not plotted
        if not self.line_x.plottedColumns[self.line_x.header.get_loc(self.column)]:
            # Actual plot commands
            self.line_x.data.plot(x=self.line_x.header[0], y=self.column, ax=self.ax, legend=False, grid=True)
            # Define labels
            self.ax.set_ylabel(self.line_x.field + ' - Column: ' + self.column)
            self.ax.set_xlabel(self.line_x.header[1])
            # Declare tight limits and trigger the draw
            plt.tight_layout()
            self.fig.canvas.draw()
            # Indicate the column as plotted
            self.line_x.is_plotted(self.line_x.header.get_loc(self.column), 1)
        else:
            print("The requested line is already plotted.")
        print('plotted columns = ' + str(self.line_x.plottedColumns))
        # Add all times to the file watcher list
        self.watcher.addPath(os.path.join(self.maindir, self.folder))
        self.watcher.addPaths(self.line_x.fileList)
        print('Directories: ' + str(self.watcher.directories()) + ' are being watched')
        print('Files: ' + str(self.watcher.files()) + ' are being watched')

        plot_data_end = time.time()
        print('PLOT DATA time = ' + str(plot_data_end - plot_data_start))

    # Function to connect the file combo box options to the plot application
    def field_changed(self, field):
        print('FIELD CHANGED')
        field_changed_start = time.time()

        self.field = field  # @@@ Is there a way to eliminate this line?
        self.read_data()  # Call for read_data()
        # Clear column combo box options
        self.columnCombo.clear()
        # Add new options to the column combo box
        for column in range(1, len(self.line_x.data.columns)):
            self.columnCombo.addItem(self.line_x.data.columns[column])
        # Declare column combo box initial option as undefined
        self.columnCombo.setCurrentIndex(-1)

        field_changed_end = time.time()
        print('FIELD CHANGED time = ' + str(field_changed_end - field_changed_start))

    # Function to connect the column combo box options to the plot application
    def column_changed(self, column):
        print('COLUMN CHANGED')
        column_changed_start = time.time()

        self.column = column  # @@@ Is there a way to eliminate this line?
        self.plot_data()  # Call for plot_data()

        column_changed_end = time.time()
        print('COLUMN CHANGED time = ' + str(column_changed_end - column_changed_start))

    # Function to reread the last valid time file and append only the new results
    def re_read_data(self, tail):
        print('RE_READ DATA')
        re_read_data_start = time.time()

        self.line_x.re_read_data(tail)

        re_read_data_end = time.time()
        print('RE_READ time = ' + str(re_read_data_end - re_read_data_start))

    # Replot all lines that were already plotted
    def re_plot_data(self):
        print('RE_PLOT DATA')
        re_plot_data_start = time.time()

        # Clear the plotted lines and axes
        self.ax.cla()
        # Loop over all lines and find which columns were plotted (and plot them)
        for x in self.line:
            print('plotted columns = ' + str(x.plottedColumns))
            if sum(x.plottedColumns) > 0:
                for y in range(len(x.plottedColumns)):
                    if x.plottedColumns[y]:
                        # Actual plot commands
                        x.data.plot(x=x.header[0], y=x.header[y], ax=self.ax, legend=False, grid=True)
                        # Define labels
                        self.ax.set_ylabel(x.field + ' - Column: ' + x.header[y])
                        self.ax.set_xlabel(x.header[1])
                        print('Line: ' + str(self.line.index(x)) + ' - Column: ' + str(y) + ' was replotted.')
                        # Indicate the column as plotted
                        x.is_plotted(y, 1)
        # Declare tight limits and trigger the draw
        plt.tight_layout()
        self.fig.canvas.draw()

        re_plot_data_end = time.time()
        print('RE_PLOT DATA time = ' + str(re_plot_data_end - re_plot_data_start))

    # Function to automatically update the plot data once a watched file modification is triggered
    # It is also connected to the
    def update_plot(self):
        print('UPDATE PLOT')
        update_plot_start = time.time()

        for x in self.updateTimesList:
            # Update the Line key variables
            (self.maindir, self.folder, self.field) = (x.maindir, x.folder, x.field)
            self.read_data()  # Call for read_data()

        # Loop over all modified files and find to which lines they belong (and read/re_read their data)
        for path in self.modifiedFiles:
            # Create a flag to break out of the middle loop
            flag = False
            for x in range(len(self.line)):
                for y in self.line[x].fileList:
                    if path == y:
                        self.line_x = self.line[x]
                        # Compute how many lines were added to the file
                        tail = len(open(path).readlines()) - 1 - self.line[x].rows2skip - self.line[x].height
                        if tail > 0 and path == self.line[x].fileList[-1]:
                            self.re_read_data(tail)  # Call for reread_data()
                        else:
                            # Update the Line key variables
                            (self.maindir, self.folder, self.field, self.timeNames) = \
                                (self.line[x].maindir, self.line[x].folder, self.line[x].field, self.line[x].timeNames)
                            self.read_data()  # Call for read_data()
                        # Activate break flag and break out of the inner loop
                        flag = True
                        break
                # Break out of the middle loop
                if flag:
                    break
        print('Modified file list = ' + str(self.modifiedFiles))
        # Re_add the modified files to the watcher list
        self.watcher.addPaths(self.modifiedFiles)
        # Reset the modified files list
        self.modifiedFiles = []
        self.re_plot_data()  # Call for re_plot_data()
        # Set button state to disabled
        self.updatePlotButton.setEnabled(False)

        update_plot_end = time.time()
        print('UPDATE PLOT time = ' + str(update_plot_end - update_plot_start))

    # Function to create a list of modified files and trigger the start of the timer
    # This function was required to deal with the multiple event triggers when several
    # files are modified simultaneously. To trigger the read_data and plot_data functions
    # only once the files must be changed and added within the stipulated time interval.
    def file_modification_update_1(self, path):
        print('FILE MODIFICATION UPDATE 1')
        file_modification_update_1_start = time.time()

        print('File: ' + str(path) + ' was modified')
        # Apply only to paths which are not currently in the modifiedFiles list
        if path not in self.modifiedFiles:
            self.modifiedFiles.append(path)
        # Start the single-shot timer for update plot
        self.timer.start(50)

        file_modification_update_1_end = time.time()
        print('FILE MODIFICATION UPDATE 1 time = ' + str(
            file_modification_update_1_end - file_modification_update_1_start))

    # Function to connect the timer timeout with the plot_update function
    def file_modification_update_2(self):
        print('FILE MODIFICATION UPDATE 2')
        file_modification_update_2_start = time.time()

        # Apply only if the automatic refresher is on
        if self.checkBox.checkState():
            # Clear the plotted lines and axes
            self.update_plot()  # Call for update_plot()
        else:
            # Set button state to enabled
            self.updatePlotButton.setEnabled(True)
            # Re_add the modified files to the watcher list
            self.watcher.addPaths(self.modifiedFiles)
        print('Directories: ' + str(self.watcher.directories()) + ' are being watched')
        print('Files: ' + str(self.watcher.files()) + ' are being watched')

        file_modification_update_2_end = time.time()
        print('FILE MODIFICATION UPDATE 2 time = ' + str(
            file_modification_update_2_end - file_modification_update_2_start))

    # Function to connect the clear plot button with the plot_clear function
    def clear_plot(self):
        print('CLEAR PLOT')
        clear_plot_start = time.time()

        # Clear plotted lines and axes
        self.ax.cla()
        # Apply when no column is currently selected in the column combo box
        if self.columnCombo.currentText() == '':
            # Declare tight limits and trigger the draw
            plt.tight_layout()
            self.fig.canvas.draw()
            print('No columns are currently selected.')

        else:
            # Update Line key variables
            (self.maindir, self.folder, self.field, self.column) = (
                self.currentMaindir,
                self.folderCombo.currentText(),
                self.fieldCombo.currentText(),
                self.columnCombo.currentText())

            # Check if any Line instance is about to get duplicated
            which_line = list(map(lambda x: (self.line[x].maindir, self.line[x].folder, self.line[x].field) == (
                self.maindir, self.folder, self.field), range(len(self.line))))
            self.line_x = self.line[np.where(which_line)[0][0]]
            self.timeNames = self.line_x.timeNames

            # Remove the watch over other field files
            self.watcher.removePaths(self.watcher.files())
            # Reset all plottedColumn lists
            [self.line[x].reset_plottedColumns() for x in range(len(self.line))]

            # Clear plotted lines and axes
            self.plot_data()  # Call for plot_data()

        clear_plot_end = time.time()
        print('CLEAR PLOT time = ' + str(clear_plot_end - clear_plot_start))

    # Print refresh mode
    def checkBox_State(self, state):
        if state == 0:
            print('\nRefresh setting changed to: MANUAL\n')
        else:
            print('\nRefresh setting changed to: AUTOMATIC\n')
            if self.updatePlotButton.isEnabled():
                self.update_plot()  # Call for update_plot()


# Initialize the application
if __name__ == '__main__':
    app = QApplication([])
    # app.setApplicationName('pp')
    widget = Widget()
    widget.show()
    app.exec()

# To do: Fix plot labels and legends when multiple lines are plotted.
# To do: Check which instance variables can be given as arguments to functions instead (saving memory).
# To do: Record colors for each column.
# To do: Add a way to blit the plot, but only if the automatic refresher is on.
# To do: Add a way to save all of toolbar's configurations when refreshing the plot.
# To do: Start thinking about adding the PyFoam applications for case setup.
