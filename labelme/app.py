import functools
import os.path
import re
import warnings
import webbrowser

from qtpy import QtCore
from qtpy.QtCore import Qt
from qtpy import QtGui
from qtpy import QtWidgets

from labelme import __appname__
from labelme import QT5

from labelme.config import get_config
from labelme.label_file import LabelFile
from labelme.label_file import LabelFileError
from labelme.shape import DEFAULT_FILL_COLOR
from labelme.shape import DEFAULT_LINE_COLOR
from labelme.shape import Shape
from labelme.utils import addActions
from labelme.utils import fmtShortcut
from labelme.utils import newAction
from labelme.utils import newIcon
from labelme.utils import struct
from labelme.widgets import Canvas
from labelme.widgets import ColorDialog
from labelme.widgets import EscapableQListWidget
from labelme.widgets import LabelDialog
from labelme.widgets import LabelQListWidget
from labelme.widgets import ToolBar
from labelme.widgets import ZoomWidget
import requests
import json
import cv2


# FIXME
# - [medium] Set max zoom value to something big enough for FitWidth/Window

# TODO(unknown):
# - [high] Add polygon movement with arrow keys
# - [high] Deselect shape when clicking and already selected(?)
# - [low,maybe] Open images with drag & drop.
# - [low,maybe] Preview images on file dialogs.
# - Zoom is too "steppy".

color_for_hard = QtGui.QColor(0, 255, 0, 128)
color_for_soft = QtGui.QColor(70, 130, 180, 255)
color_for_hemo = QtGui.QColor(255, 0, 0, 128)
color_for_micr = QtGui.QColor(255, 0, 255, 255)

class WindowMixin(object):
    def menu(self, title, actions=None):
        menu = self.menuBar().addMenu(title)
        if actions:
            addActions(menu, actions)
        return menu

    def toolbar(self, title, actions=None):
        toolbar = ToolBar(title)
        toolbar.setObjectName('%sToolBar' % title)
        # toolbar.setOrientation(Qt.Vertical)
        toolbar.setToolButtonStyle(Qt.ToolButtonTextUnderIcon)
        if actions:
            addActions(toolbar, actions)
        self.addToolBar(Qt.LeftToolBarArea, toolbar)
        return toolbar


class MainWindow(QtWidgets.QMainWindow, WindowMixin):
    FIT_WINDOW, FIT_WIDTH, MANUAL_ZOOM = 0, 1, 2

    def __init__(self, config=None, filename=None, output=None):
        # see labelme/config/default_config.yaml for valid configuration
        self.cloud_config = json.load(open("config.json", 'r'))
        if config is None:
            config = get_config()
        self._config = config

        super(MainWindow, self).__init__()
        self.setWindowTitle(__appname__)

        # Whether we need to save or not.
        self.dirty = False

        self._noSelectionSlot = False

        # Main widgets and related state.
        self.labelDialog = LabelDialog(
            parent=self,
            labels=self._config['labels'],
            sort_labels=self._config['sort_labels'],
            show_text_field=self._config['show_label_text_field'],
            completion=self._config['label_completion'],
        )

        self.labelList = LabelQListWidget()
        self.lastOpenDir = None

        self.flag_dock = self.flag_widget = None
        self.flag_dock = QtWidgets.QDockWidget('视网膜病变等级', self)
        self.flag_dock.setObjectName('Flags')
        self.flag_widget = QtWidgets.QListWidget()
        if config['flags']:
            self.loadFlags({k: False for k in config['flags']})
        self.flag_dock.setWidget(self.flag_widget)
        self.flag_widget.itemChanged.connect(self.setDirty)

        self.labelList.itemActivated.connect(self.labelSelectionChanged)
        self.labelList.itemSelectionChanged.connect(self.labelSelectionChanged)
        self.labelList.itemDoubleClicked.connect(self.editLabel)
        # Connect to itemChanged to detect checkbox changes.
        self.labelList.itemChanged.connect(self.labelItemChanged)
        self.labelList.setDragDropMode(
            QtWidgets.QAbstractItemView.InternalMove)
        self.labelList.setParent(self)
        self.dock = QtWidgets.QDockWidget('并发症标签', self)
        self.dock.setObjectName('Labels')
        self.dock.setWidget(self.labelList)

        self.uniqLabelList = EscapableQListWidget()
        self.uniqLabelList.setToolTip(
            "Select label to start annotating for it. "
            "Press 'Esc' to deselect.")
        if self._config['labels']:
            self.uniqLabelList.addItems(self._config['labels'])
            self.uniqLabelList.sortItems()
        self.labelsdock = QtWidgets.QDockWidget(u'并发症区域列表', self)
        self.labelsdock.setObjectName(u'Label List')
        self.labelsdock.setWidget(self.uniqLabelList)

        self.fileSearch = QtWidgets.QLineEdit()
        self.fileSearch.setPlaceholderText('Search Filename')
        self.fileSearch.textChanged.connect(self.fileSearchChanged)
        self.fileListWidget = QtWidgets.QListWidget()
        self.fileListWidget.itemSelectionChanged.connect(
            self.fileSelectionChanged
        )
        fileListLayout = QtWidgets.QVBoxLayout()
        fileListLayout.setContentsMargins(0, 0, 0, 0)
        fileListLayout.setSpacing(0)
        fileListLayout.addWidget(self.fileSearch)
        fileListLayout.addWidget(self.fileListWidget)
        self.filedock = QtWidgets.QDockWidget(u'文件列表', self)
        self.filedock.setObjectName(u'Files')
        fileListWidget = QtWidgets.QWidget()
        fileListWidget.setLayout(fileListLayout)
        self.filedock.setWidget(fileListWidget)

        self.zoomWidget = ZoomWidget()
        self.colorDialog = ColorDialog(parent=self)

        self.canvas = self.labelList.canvas = Canvas(
            epsilon=self._config['epsilon'],
        )
        self.canvas.zoomRequest.connect(self.zoomRequest)

        scrollArea = QtWidgets.QScrollArea()
        scrollArea.setWidget(self.canvas)
        scrollArea.setWidgetResizable(True)
        self.scrollBars = {
            Qt.Vertical: scrollArea.verticalScrollBar(),
            Qt.Horizontal: scrollArea.horizontalScrollBar(),
        }
        self.canvas.scrollRequest.connect(self.scrollRequest)

        self.canvas.newShape.connect(self.newShape)
        self.canvas.shapeMoved.connect(self.setDirty)
        self.canvas.selectionChanged.connect(self.shapeSelectionChanged)
        self.canvas.drawingPolygon.connect(self.toggleDrawingSensitive)

        self.setCentralWidget(scrollArea)

        self.addDockWidget(Qt.RightDockWidgetArea, self.flag_dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.labelsdock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.dock)
        self.addDockWidget(Qt.RightDockWidgetArea, self.filedock)

        # Actions
        action = functools.partial(newAction, self)
        shortcuts = self._config['shortcuts']
        quit = action('&退出', self.close, shortcuts['quit'], 'quit',
                      'Quit application')
        open_ = action('&打开 文件', self.openFile, shortcuts['open'], 'open',
                       '打开图像或标注文件')
        opendir = action('&打开 文件夹', self.openDirDialog,
                         shortcuts['open_dir'], 'open', u'打开文件夹')
        openNextImg = action('&下一张', self.openNextImg,
                             shortcuts['open_next'], 'next', u'打开下一张图片')

        openPrevImg = action('&上一张', self.openPrevImg,
                             shortcuts['open_prev'], 'prev', u'打开上一张图片')
        save = action('&保存', self.saveFile, shortcuts['save'], 'save',
                      '将标签保存到标注文件', enabled=False)
        saveAs = action('&保存到', self.saveFileAs, shortcuts['save_as'],
                        'save-as', 'Save labels to a different file',
                        enabled=False)
        close = action('&关闭', self.closeFile, shortcuts['close'], 'close',
                       'Close current file')
        color1 = action('选择线条颜色', self.chooseColor1,
                        shortcuts['edit_line_color'], 'color_line',
                        'Choose polygon line color')
        color2 = action('选择填充颜色', self.chooseColor2,
                        shortcuts['edit_fill_color'], 'color',
                        'Choose polygon fill color')

        createMode = action(
            '勾画 病变区域',
            lambda: self.toggleDrawMode(False, createMode='polygon'),
            shortcuts['create_polygon'],
            'objects',
            '开始绘制多边形',
            enabled=True,
        )
        createRectangleMode = action(
            '创建 矩形',
            lambda: self.toggleDrawMode(False, createMode='rectangle'),
            shortcuts['create_rectangle'],
            'objects',
            'Start drawing rectangles',
            enabled=True,
        )
        createLineMode = action(
            '创建 线条',
            lambda: self.toggleDrawMode(False, createMode='line'),
            shortcuts['create_line'],
            'objects',
            'Start drawing lines',
            enabled=True,
        )
        createPointMode = action(
            '创建 点',
            lambda: self.toggleDrawMode(False, createMode='point'),
            shortcuts['create_point'],
            'objects',
            'Start drawing points',
            enabled=True,
        )
        editMode = action('编辑 病变区域', self.setEditMode,
                          shortcuts['edit_polygon'], 'edit',
                          '移动或编辑多边形', enabled=True)

        delete = action('删除 病变区域', self.deleteSelectedShape,
                        shortcuts['delete_polygon'], 'cancel',
                        '删除', enabled=True)
        copy = action('复制 病变区域', self.copySelectedShape,
                      shortcuts['duplicate_polygon'], 'copy',
                      '复制选中的多边形',
                      enabled=False)
        undoLastPoint = action('撤销上一个点', self.canvas.undoLastPoint,
                               shortcuts['undo_last_point'], 'undo',
                               'Undo last drawn point', enabled=False)
        addPoint = action('向该边添加点', self.canvas.addPointToEdge,
                          None, 'edit', 'Add point to the nearest edge',
                          enabled=False)

        undo = action('撤销', self.undoShapeEdit, shortcuts['undo'], 'undo',
                      '撤销上一步操作', enabled=False)

        hideAll = action('&隐藏 多边形',
                         functools.partial(self.togglePolygons, False),
                         icon='eye', tip='Hide all polygons', enabled=False)
        showAll = action('&显示 多边形',
                         functools.partial(self.togglePolygons, True),
                         icon='eye', tip='Show all polygons', enabled=False)

        help = action('&打开教程', self.tutorial, icon='help',
                      tip='Show tutorial page')

        zoom = QtWidgets.QWidgetAction(self)
        zoom.setDefaultWidget(self.zoomWidget)
        self.zoomWidget.setWhatsThis(
            "Zoom in or out of the image. Also accessible with"
            " %s and %s from the canvas." %
            (fmtShortcut('%s,%s' % (shortcuts['zoom_in'],
                                    shortcuts['zoom_out'])),
             fmtShortcut("Ctrl+Wheel")))
        self.zoomWidget.setEnabled(False)

        zoomIn = action('放大', functools.partial(self.addZoom, 10),
                        shortcuts['zoom_in'], 'zoom-in',
                        '放大图片', enabled=False)
        zoomOut = action('缩小', functools.partial(self.addZoom, -10),
                         shortcuts['zoom_out'], 'zoom-out',
                         '缩小图片', enabled=False)
        zoomOrg = action('原始大小',
                         functools.partial(self.setZoom, 100),
                         shortcuts['zoom_to_original'], 'zoom',
                         '恢复原始大小', enabled=False)
        fitWindow = action('适应于 窗口', self.setFitWindow,
                           shortcuts['fit_window'], 'fit-window',
                           '依据窗口调节图片大小', checkable=True,
                           enabled=False)
        fitWidth = action('适应于 宽度', self.setFitWidth,
                          shortcuts['fit_width'], 'fit-width',
                          '依据宽度调节图片大小',
                          checkable=True, enabled=False)
        # Group zoom controls into a list for easier toggling.
        zoomActions = (self.zoomWidget, zoomIn, zoomOut, zoomOrg,
                       fitWindow, fitWidth)
        self.zoomMode = self.MANUAL_ZOOM
        self.scalers = {
            self.FIT_WINDOW: self.scaleFitWindow,
            self.FIT_WIDTH: self.scaleFitWidth,
            # Set to one to scale to 100% when loading files.
            self.MANUAL_ZOOM: lambda: 1,
        }

        edit = action('&编辑 标签', self.editLabel, shortcuts['edit_label'],
                      'edit', 'Modify the label of the selected polygon',
                      enabled=False)

        shapeLineColor = action(
            '选择线条颜色', self.chshapeLineColor, icon='color-line',
            tip='Change the line color for this specific shape', enabled=False)
        shapeFillColor = action(
            '选择填充颜色', self.chshapeFillColor, icon='color',
            tip='Change the fill color for this specific shape', enabled=False)
        fill_drawing = action(
            '绘画中填充区域',
            lambda x: self.canvas.setFillDrawing(x),
            None,
            'color',
            'Fill polygon while drawing',
            checkable=True,
            enabled=True,
        )
        fill_drawing.setChecked(True)
        # moveShape = action('&移动', self.moveShape)

        # Lavel list context menu.
        labelMenu = QtWidgets.QMenu()
        addActions(labelMenu, (edit, delete))
        self.labelList.setContextMenuPolicy(Qt.CustomContextMenu)
        self.labelList.customContextMenuRequested.connect(
            self.popLabelListMenu)

        # Store actions for further handling.
        self.actions = struct(
            save=save, saveAs=saveAs, open=open_, close=close,
            lineColor=color1, fillColor=color2,
            delete=delete, edit=edit, copy=copy,
            undoLastPoint=undoLastPoint, undo=undo,
            addPoint=addPoint,
            createMode=createMode, editMode=editMode,
            createRectangleMode=createRectangleMode,
            createLineMode=createLineMode,
            createPointMode=createPointMode,
            shapeLineColor=shapeLineColor, shapeFillColor=shapeFillColor,
            zoom=zoom, zoomIn=zoomIn, zoomOut=zoomOut, zoomOrg=zoomOrg,
            fitWindow=fitWindow, fitWidth=fitWidth,
            zoomActions=zoomActions,
            fileMenuActions=(open_, opendir, save, saveAs, close, quit),
            tool=(),
            editMenu=(edit, copy, delete, None, undo, undoLastPoint,
                      None, color1, color2),
            # menu shown at right click
            menu=(
                createMode,
                # createRectangleMode,
                # createLineMode,
                # createPointMode,
                editMode,
                edit,
                addPoint,
                copy,
                delete,
                # shapeLineColor,
                # shapeFillColor,
                undo,
                undoLastPoint,
                # addPoint,
            ),
            onLoadActive=(
                close,
                createMode,
                createRectangleMode,
                createLineMode,
                createPointMode,
                editMode,
            ),
            onShapesPresent=(saveAs, hideAll, showAll),
        )

        self.canvas.edgeSelected.connect(self.actions.addPoint.setEnabled)

        self.menus = struct(
            file=self.menu('&文件'),
            edit=self.menu('&编辑'),
            view=self.menu('&视图'),
            help=self.menu('&帮助'),
            recentFiles=QtWidgets.QMenu('打开 最近文件'),
            labelList=labelMenu,
        )

        addActions(self.menus.file, (open_, openNextImg, openPrevImg, opendir,
                                     self.menus.recentFiles,
                                     save, saveAs, close, None, quit))
        addActions(self.menus.help, (help,))
        addActions(self.menus.view, (
            self.flag_dock.toggleViewAction(),
            self.labelsdock.toggleViewAction(),
            self.dock.toggleViewAction(),
            self.filedock.toggleViewAction(),
            None,
            fill_drawing,
            None,
            hideAll,
            showAll,
            None,
            zoomIn,
            zoomOut,
            zoomOrg,
            None,
            fitWindow,
            fitWidth,
            None,
        ))

        self.menus.file.aboutToShow.connect(self.updateFileMenu)

        # Custom context menu for the canvas widget:
        addActions(self.canvas.menus[0], self.actions.menu)
        addActions(self.canvas.menus[1], (
            action('&粘贴', self.copyShape),
            action('&移动', self.moveShape)))

        self.tools = self.toolbar('工具')
        # Menu buttons on Left
        self.actions.tool = (
            open_,
            opendir,
            openNextImg,
            openPrevImg,
            save,
            None,
            createMode,
            editMode,
            copy,
            delete,
            undo,
            None,
            zoomIn,
            # zoom,
            zoomOut,
            fitWindow,
            fitWidth,
        )

        self.statusBar().showMessage('%s已启动' % __appname__)
        self.statusBar().show()

        # Application state.
        self.image = QtGui.QImage()
        self.imagePath = None
        if self._config['auto_save'] and output is not None:
            warnings.warn('如果`auto_save`被选中, `output`警告将被无视，'
                          '并且输出的文件名将自动设定为 IMAGE_BASENAME.json.')
        self.labeling_once = output is not None
        self.output = output
        self.recentFiles = []
        self.maxRecent = 7
        self.lineColor = None
        self.fillColor = None
        self.otherData = None
        self.zoom_level = 100
        self.fit_window = False

        if filename is not None and os.path.isdir(filename):
            self.importDirImages(filename, load=False)
        else:
            self.filename = filename

        if config['file_search']:
            self.fileSearch.setText(config['file_search'])
            self.fileSearchChanged()

        # XXX: Could be completely declarative.
        # Restore application settings.
        self.settings = QtCore.QSettings('labelme', 'labelme')
        # FIXME: QSettings.value can return None on PyQt4
        self.recentFiles = self.settings.value('recentFiles', []) or []
        size = self.settings.value('window/size', QtCore.QSize(600, 500))
        position = self.settings.value('window/position', QtCore.QPoint(0, 0))
        self.resize(size)
        self.move(position)
        # or simply:
        # self.restoreGeometry(settings['window/geometry']
        self.restoreState(
            self.settings.value('window/state', QtCore.QByteArray()))
        self.lineColor = QtGui.QColor(
            self.settings.value('line/color', Shape.line_color))
        self.fillColor = QtGui.QColor(
            self.settings.value('fill/color', Shape.fill_color))
        Shape.line_color = self.lineColor
        Shape.fill_color = self.fillColor

        # Populate the File menu dynamically.
        self.updateFileMenu()
        # Since loading the file may take some time,
        # make sure it runs in the background.
        if self.filename is not None:
            self.queueEvent(functools.partial(self.loadFile, self.filename))

        # Callbacks:
        self.zoomWidget.valueChanged.connect(self.paintCanvas)

        self.populateModeActions()

        # self.firstStart = True
        # if self.firstStart:
        #    QWhatsThis.enterWhatsThisMode()

    # Support Functions

    def noShapes(self):
        return not self.labelList.itemsToShapes

    def populateModeActions(self):
        tool, menu = self.actions.tool, self.actions.menu
        self.tools.clear()
        addActions(self.tools, tool)
        self.canvas.menus[0].clear()
        addActions(self.canvas.menus[0], menu)
        self.menus.edit.clear()
        actions = (
            self.actions.createMode,
            self.actions.createRectangleMode,
            self.actions.createLineMode,
            self.actions.createPointMode,
            self.actions.editMode,
        )
        addActions(self.menus.edit, actions + self.actions.editMenu)

    def setDirty(self):
        if self._config['auto_save']:         # 自动保存的处理---------------------------------------
            label_file = os.path.splitext(self.imagePath)[0] + '.json'
            self.saveLabels(label_file)
            return

        self.dirty = True
        self.actions.save.setEnabled(True)
        self.actions.undo.setEnabled(self.canvas.isShapeRestorable)
        title = __appname__
        if self.filename is not None:
            title = '{} - {}*'.format(title, self.filename)
        self.setWindowTitle(title)

    def setClean(self):
        self.dirty = False
        self.actions.save.setEnabled(False)
        self.actions.createMode.setEnabled(True)
        self.actions.createRectangleMode.setEnabled(True)
        self.actions.createLineMode.setEnabled(True)
        self.actions.createPointMode.setEnabled(True)
        title = __appname__
        if self.filename is not None:
            title = '{} - {}'.format(title, self.filename)
        self.setWindowTitle(title)

    def toggleActions(self, value=True):
        """Enable/Disable widgets which depend on an opened image."""
        for z in self.actions.zoomActions:
            z.setEnabled(value)
        for action in self.actions.onLoadActive:
            action.setEnabled(value)

    def queueEvent(self, function):
        QtCore.QTimer.singleShot(0, function)

    def status(self, message, delay=5000):
        self.statusBar().showMessage(message, delay)

    def resetState(self):
        self.labelList.clear()
        self.filename = None
        self.imagePath = None
        self.imageData = None
        self.labelFile = None
        self.otherData = None
        self.canvas.resetState()

    def currentItem(self):
        items = self.labelList.selectedItems()
        if items:
            return items[0]
        return None

    def addRecentFile(self, filename):
        if filename in self.recentFiles:
            self.recentFiles.remove(filename)
        elif len(self.recentFiles) >= self.maxRecent:
            self.recentFiles.pop()
        self.recentFiles.insert(0, filename)

    # Callbacks

    def undoShapeEdit(self):
        self.canvas.restoreShape()
        self.labelList.clear()
        self.loadShapes(self.canvas.shapes)
        self.actions.undo.setEnabled(self.canvas.isShapeRestorable)

    def tutorial(self):
        url = 'https://github.com/wkentaro/labelme/tree/master/examples/tutorial'  # NOQA
        webbrowser.open(url)

    def toggleAddPointEnabled(self, enabled):
        self.actions.addPoint.setEnabled(enabled)

    def toggleDrawingSensitive(self, drawing=True):
        """Toggle drawing sensitive.

        In the middle of drawing, toggling between modes should be disabled.
        """
        self.actions.editMode.setEnabled(not drawing)
        self.actions.undoLastPoint.setEnabled(drawing)
        self.actions.undo.setEnabled(not drawing)

    def toggleDrawMode(self, edit=True, createMode='polygon'):
        self.canvas.setEditing(edit)
        self.canvas.createMode = createMode
        if edit:
            self.actions.createMode.setEnabled(True)
            self.actions.createRectangleMode.setEnabled(True)
            self.actions.createLineMode.setEnabled(True)
            self.actions.createPointMode.setEnabled(True)
        else:
            if createMode == 'polygon':
                self.actions.createMode.setEnabled(False)
                self.actions.createRectangleMode.setEnabled(True)
                self.actions.createLineMode.setEnabled(True)
                self.actions.createPointMode.setEnabled(True)
            elif createMode == 'rectangle':
                self.actions.createMode.setEnabled(True)
                self.actions.createRectangleMode.setEnabled(False)
                self.actions.createLineMode.setEnabled(True)
                self.actions.createPointMode.setEnabled(True)
            elif createMode == 'line':
                self.actions.createMode.setEnabled(True)
                self.actions.createRectangleMode.setEnabled(True)
                self.actions.createLineMode.setEnabled(False)
                self.actions.createPointMode.setEnabled(True)
            elif createMode == 'point':
                self.actions.createMode.setEnabled(True)
                self.actions.createRectangleMode.setEnabled(True)
                self.actions.createLineMode.setEnabled(True)
                self.actions.createPointMode.setEnabled(False)
            else:
                raise ValueError('不支持创建这种形式的标注：%s' % createMode)
        self.actions.editMode.setEnabled(not edit)

    def setEditMode(self):
        self.toggleDrawMode(True)

    def updateFileMenu(self):
        current = self.filename

        def exists(filename):
            return os.path.exists(str(filename))

        menu = self.menus.recentFiles
        menu.clear()
        files = [f for f in self.recentFiles if f != current and exists(f)]
        for i, f in enumerate(files):
            icon = newIcon('labels')
            action = QtWidgets.QAction(
                icon, '&%d %s' % (i + 1, QtCore.QFileInfo(f).fileName()), self)
            action.triggered.connect(functools.partial(self.loadRecent, f))
            menu.addAction(action)

    def popLabelListMenu(self, point):
        self.menus.labelList.exec_(self.labelList.mapToGlobal(point))

    def validateLabel(self, label):
        # no validation
        if self._config['validate_label'] is None:
            return True

        for i in range(self.uniqLabelList.count()):
            label_i = self.uniqLabelList.item(i).text()
            if self._config['validate_label'] in ['exact', 'instance']:
                if label_i == label:
                    return True
            if self._config['validate_label'] == 'instance':
                m = re.match(r'^{}-[0-9]*$'.format(label_i), label)
                if m:
                    return True
        return False

    def editLabel(self, item=None):
        if not self.canvas.editing():
            return
        item = item if item else self.currentItem()
        text = self.labelDialog.popUp(item.text())
        if text is None:
            return
        if not self.validateLabel(text):
            self.errorMessage('无效标签',
                              "Invalid label '{}' with validation type '{}'"
                              .format(text, self._config['validate_label']))
            return
        item.setText(text)
        self.setDirty()
        if not self.uniqLabelList.findItems(text, Qt.MatchExactly):
            self.uniqLabelList.addItem(text)
            self.uniqLabelList.sortItems()

    def fileSearchChanged(self):
        self.importDirImages(
            self.lastOpenDir,
            pattern=self.fileSearch.text(),
            load=False,
        )

    def fileSelectionChanged(self):
        items = self.fileListWidget.selectedItems()
        if not items:
            return
        item = items[0]

        if not self.mayContinue():
            return

        currIndex = self.imageList.index(str(item.text()))
        if currIndex < len(self.imageList):
            filename = self.imageList[currIndex]
            if filename:
                self.loadFile(filename)

    # React to canvas signals.
    def shapeSelectionChanged(self, selected=False):
        if self._noSelectionSlot:
            self._noSelectionSlot = False
        else:
            shape = self.canvas.selectedShape
            if shape:
                item = self.labelList.get_item_from_shape(shape)
                item.setSelected(True)
            else:
                self.labelList.clearSelection()
        self.actions.delete.setEnabled(selected)
        self.actions.copy.setEnabled(selected)
        self.actions.edit.setEnabled(selected)
        self.actions.shapeLineColor.setEnabled(selected)
        self.actions.shapeFillColor.setEnabled(selected)

    def addLabel(self, shape):
        item = QtWidgets.QListWidgetItem(shape.label)
        item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
        item.setCheckState(Qt.Checked)
        self.labelList.itemsToShapes.append((item, shape))
        self.labelList.addItem(item)
        if not self.uniqLabelList.findItems(shape.label, Qt.MatchExactly):
            self.uniqLabelList.addItem(shape.label)
            self.uniqLabelList.sortItems()
        self.labelDialog.addLabelHistory(item.text())
        for action in self.actions.onShapesPresent:
            action.setEnabled(True)

    def remLabel(self, shape):
        item = self.labelList.get_item_from_shape(shape)
        self.labelList.takeItem(self.labelList.row(item))

    def loadShapes(self, shapes):
        for shape in shapes:
            self.addLabel(shape)
        self.canvas.loadShapes(shapes)

    def loadLabels(self, shapes):
        s = []
        for label, points, line_color, fill_color in shapes:
            shape = Shape(label=label)
            # print(label)    # ------------------------------------------
            for x, y in points:
                shape.addPoint(QtCore.QPoint(x, y))
                # print(x, y) # ------------------------------------------
            shape.close()
            s.append(shape)
            if line_color:
                shape.line_color = QtGui.QColor(*line_color)
            if fill_color:
                shape.fill_color = QtGui.QColor(*fill_color)
        self.loadShapes(s)

    def loadFlags(self, flags):
        self.flag_widget.clear()
        for key, flag in flags.items():
            item = QtWidgets.QListWidgetItem(key)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Checked if flag else Qt.Unchecked)
            self.flag_widget.addItem(item)

    def saveLabels(self, filename):
        lf = LabelFile()

        def format_shape(s):
            return dict(label=str(s.label),
                        # line_color=s.line_color.getRgb()
                        # if s.line_color != self.lineColor else None,
                        # fill_color=s.fill_color.getRgb()
                        # if s.fill_color != self.fillColor else None,
                        points=[(p.x(), p.y()) for p in s.points])

        shapes = [format_shape(shape) for shape in self.labelList.shapes]
        flags = {}
        for i in range(self.flag_widget.count()):
            item = self.flag_widget.item(i)
            key = item.text()
            flag = item.checkState() == Qt.Checked
            flags[key] = flag
        try:
            # imagePath = os.path.relpath(
            #     self.imagePath, os.path.dirname(filename))
            # print("1.", self.imagePath)     # 绝对路径
            # print("2.", imagePath)          # 相对路径
            imageData = self.imageData if self._config['store_data'] else None
            lf.save(
                filename=filename,
                shapes=shapes,
                imagePath=self.imagePath,
                # imagePath2=imagePath,
                # imageData=imageData,
                # lineColor=self.lineColor.getRgb(),
                # fillColor=self.fillColor.getRgb(),
                otherData=self.otherData,
                flags=flags,
            )
            self.labelFile = lf
            items = self.fileListWidget.findItems(
                self.imagePath, Qt.MatchExactly
            )
            if len(items) > 0:
                if len(items) != 1:
                    raise RuntimeError('存在重复文件。')
                items[0].setCheckState(Qt.Checked)


            # disable allows next and previous image to proceed
            # self.filename = filename
            return True
        except LabelFileError as e:
            self.errorMessage('保存标签错误', '<b>%s</b>' % e)
            return False

    def copySelectedShape(self):
        self.addLabel(self.canvas.copySelectedShape())
        # fix copy and delete
        self.shapeSelectionChanged(True)

    def labelSelectionChanged(self):
        item = self.currentItem()
        if item and self.canvas.editing():
            self._noSelectionSlot = True
            shape = self.labelList.get_shape_from_item(item)
            self.canvas.selectShape(shape)

    def labelItemChanged(self, item):
        shape = self.labelList.get_shape_from_item(item)
        label = str(item.text())
        if label != shape.label:
            shape.label = str(item.text())
            print(shape.label)
            if shape.label == '硬性渗出':
                shape.line_color = color_for_hard
            elif shape.label == '软性渗出':
                shape.line_color = color_for_soft
            elif shape.label == '视网膜出血':
                shape.line_color = color_for_hemo
            elif shape.label == '微血管瘤':
                shape.line_color = color_for_micr
            self.setDirty()
            self.canvas.update()
        else:  # User probably changed item visibility
            self.canvas.setShapeVisible(shape, item.checkState() == Qt.Checked)

    # Callback functions:

    def newShape(self):
        """Pop-up and give focus to the label editor.

        position MUST be in global coordinates.
        """
        items = self.uniqLabelList.selectedItems()
        text = None
        if items:
            text = items[0].text()
        text = self.labelDialog.popUp(text)
        if text is not None and not self.validateLabel(text):
            self.errorMessage('无效的标签',
                              "Invalid label '{}' with validation type '{}'"
                              .format(text, self._config['validate_label']))
            text = None
        if text is None:
            self.canvas.undoLastLine()
            self.canvas.shapesBackups.pop()
        else:
            print('text:', text)    # ---------------------------------------------------
            self.addLabel(self.canvas.setLastLabel(text))
            self.actions.editMode.setEnabled(True)
            self.actions.undoLastPoint.setEnabled(False)
            self.actions.undo.setEnabled(True)
            self.setDirty()
            self.canvas.update()

    def scrollRequest(self, delta, orientation):
        units = - delta * 0.1  # natural scroll
        bar = self.scrollBars[orientation]
        bar.setValue(bar.value() + bar.singleStep() * units)

    def setZoom(self, value):
        self.actions.fitWidth.setChecked(False)
        self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.MANUAL_ZOOM
        self.zoomWidget.setValue(value)

    def addZoom(self, increment=10):
        self.setZoom(self.zoomWidget.value() + increment)
        self.canvas.setEpsilon(-1 *increment * 0.025)

    def zoomRequest(self, delta, pos):
        canvas_width_old = self.canvas.width()

        units = delta * 0.1
        self.addZoom(units)

        canvas_width_new = self.canvas.width()
        if canvas_width_old != canvas_width_new:
            canvas_scale_factor = canvas_width_new / canvas_width_old

            x_shift = round(pos.x() * canvas_scale_factor) - pos.x()
            y_shift = round(pos.y() * canvas_scale_factor) - pos.y()

            self.scrollBars[Qt.Horizontal].setValue(
                self.scrollBars[Qt.Horizontal].value() + x_shift)
            self.scrollBars[Qt.Vertical].setValue(
                self.scrollBars[Qt.Vertical].value() + y_shift)

    def setFitWindow(self, value=True):
        if value:
            self.actions.fitWidth.setChecked(False)
        self.zoomMode = self.FIT_WINDOW if value else self.MANUAL_ZOOM
        self.adjustScale()

    def setFitWidth(self, value=True):
        if value:
            self.actions.fitWindow.setChecked(False)
        self.zoomMode = self.FIT_WIDTH if value else self.MANUAL_ZOOM
        self.adjustScale()

    def togglePolygons(self, value):
        for item, shape in self.labelList.itemsToShapes:
            item.setCheckState(Qt.Checked if value else Qt.Unchecked)

    def loadFile(self, filename=None):
        """Load the specified file, or the last opened file if None."""
        # changing fileListWidget loads file
        token = self.cloud_config['token']
        pre_label_ip = self.cloud_config['pre_label_ip']
        get_img_ip = self.cloud_config['get_img_ip']
        cloud_save_ip = self.cloud_config['cloud_save_ip']

        if (filename in self.imageList and
                self.fileListWidget.currentRow() !=
                self.imageList.index(filename)):
            self.fileListWidget.setCurrentRow(self.imageList.index(filename))
            self.fileListWidget.repaint()
            return

        self.resetState()
        self.canvas.setEnabled(False)
        if filename is None:
            filename = self.settings.value('filename', '')
        filename = str(filename)
        if not QtCore.QFile.exists(filename):
            self.errorMessage(
                '打开文件失败', '没有这个文件：<b>%s</b>' % filename)
            return False
        # assumes same name, but json extension
        self.status("Loading %s..." % os.path.basename(str(filename)))


        self.imageData = read(filename, None)
        if self.imageData is not None:
            # the filename is image not JSON
            self.imagePath = filename
            print('imagePath:', self.imagePath)
        label_file = os.path.splitext(filename)[0] + '.json'

        image = QtGui.QImage.fromData(self.imageData)
        if image.isNull():
            formats = ['*.{}'.format(fmt.data().decode())
                       for fmt in QtGui.QImageReader.supportedImageFormats()]
            self.errorMessage(
                '打开文件错误',
                '<p>请确认<i>{0}</i>图像文件存在。<br/>'
                '支持的文件格式：{1}</p>'
                .format(filename, ','.join(formats)))
            self.status("读取%s错误" % filename)
            return False
        self.image = image
        self.filename = filename

        if QtCore.QFile.exists(label_file) and \
                LabelFile.isLabelFile(label_file):
            try:
                self.labelFile = LabelFile(filename=label_file)
                # FIXME: PyQt4 installed via Anaconda fails to load JPEG
                # and JSON encoded images.
                # https://github.com/ContinuumIO/anaconda-issues/issues/131
                # if QtGui.QImage.fromData(self.labelFile.imageData).isNull():
                #     raise LabelFileError(
                #         '从标注文件中加载图像错误\n'
                #         '也许是因为在Anaconda下使用PyQt4造成的'
                #         '如果您使用Anaconda，我们建议您使用PyQt5。')
            except LabelFileError as e:
                self.errorMessage(
                    '打开文件错误',
                    "<p><b>%s</b></p>"
                    "<p>请确认<i>%s</i>标注文件存在并且未损坏。"
                    % (e, label_file))
                self.status("读取%s错误" % label_file)
                return False
            # self.imageData = self.labelFile.imageData
            # self.imagePath = os.path.join(os.path.dirname(label_file),
            #                               self.labelFile.imagePath)
            crop_name = 'crop_' + self.filename.split('/')[-1]
            crop_path = '../crop_img/' + crop_name
            if QtCore.QFile.exists(crop_path):
                self.imageData = read(crop_path, None)
                image = QtGui.QImage.fromData(self.imageData)
            else:
                print('crop_img/ has no img named as', crop_name)
                cloud_path = self.labelFile.imagePath
                try:
                    imgData = requests.get(get_img_ip + cloud_path)
                    print('get!!!')
                    crop_name = 'crop_' + self.filename.split('/')[-1]
                    crop_path = '../crop_img/' + crop_name
                    with open(crop_path, 'wb') as f:
                        f.write(imgData.content)
                        f.close()
                    self.imageData = read(crop_path, None)
                    image = QtGui.QImage.fromData(self.imageData)
                except:
                    print('cloud has no img as', cloud_path)
            self.lineColor = QtGui.QColor(*self.labelFile.lineColor)
            self.fillColor = QtGui.QColor(*self.labelFile.fillColor)
            self.otherData = self.labelFile.otherData
            self.setClean()
        else:
            mb = QtWidgets.QMessageBox
            msg = '要在标注"{}"之前进行模型预标注吗？'.format(os.path.basename(str(filename)))
            answer = mb.question(self,
                                 '进行预标注？',
                                 msg,
                                 mb.Yes | mb.No,
                                 mb.Yes)
            if answer == mb.Yes:
                # 云端存储----------------------------
                data = {"token": token}
                files = {
                    "img": open(filename, "rb")
                }
                r = requests.post(pre_label_ip, data, files=files)
                # r = requests.post("http://127.0.0.1:8000/postimg/", data, files=files)
                print(r.text)
                result = json.loads(r.text)
                if result.get('status') == 200:
                    data = result.get('results')
                    print(data)
                    imgPath = data['imgPath']
                    imgPath = imgPath[1:]
                    print('imgPath:', get_img_ip + imgPath)
                    imgData = requests.get(get_img_ip + imgPath)
                    print('get!!!')
                    crop_name = 'crop_' + filename.split('/')[-1]
                    crop_path = '../crop_img/' + crop_name
                    with open(crop_path, 'wb') as f:
                        f.write(imgData.content)
                        f.close()
                    self.imageData = read(crop_path, None)
                    # print('get1 !!!')
                    image = QtGui.QImage.fromData(self.imageData)
                    print('cropimage OK!!!!')

                    shapes = data['shapes']
                    for shape in shapes:
                        points = shape['points']
                        new_points = self.simplify(points)
                        if new_points == None:
                            shapes.remove(shape)
                        else:
                            shape['points'] = new_points

                    self.labelFile = LabelFile(data=data)
                    self.imagePath = self.labelFile.imagePath
                    self.lineColor = QtGui.QColor(*self.labelFile.lineColor)
                    self.fillColor = QtGui.QColor(*self.labelFile.fillColor)
                    self.otherData = self.labelFile.otherData
                    print('module OK')
                    self.setDirty()
                else:
                    self.labelFile = None
                    self.setClean()
                    print('module error')
            else:  # answer == mb.Cancel
                try:
                    data = {"token": token}
                    files = {
                        "img": open(self.imagePath, "rb")
                    }
                    r = requests.post(cloud_save_ip, data, files=files)
                    print(r.text)
                    result = json.loads(r.text)
                    if result.get('status') == 200:
                        print("img_path", result.get('img_path'))
                        self.imagePath = result.get('img_path')
                    else:
                        print('error')
                except Exception as e:
                    print(e)
                self.labelFile = None
                self.setClean()
            # Load image:
            # read data first and store for saving into label file.

        if self._config['keep_prev']:
            prev_shapes = self.canvas.shapes
        self.canvas.loadPixmap(QtGui.QPixmap.fromImage(image))
        print('image OK')
        if self._config['flags']:
            self.loadFlags({k: False for k in self._config['flags']})
        # if self._config['keep_prev']:
        #     self.loadShapes(prev_shapes)
        print('flags OK')
        if self.labelFile:
            self.loadLabels(self.labelFile.shapes)
            if self.labelFile.flags is not None:
                self.loadFlags(self.labelFile.flags)
        print('labels OK')
        self.canvas.setEnabled(True)
        self.adjustScale(initial=True)
        self.paintCanvas()
        self.addRecentFile(self.filename)
        self.toggleActions(True)
        self.status("Loaded %s" % os.path.basename(str(filename)))
        return True

    def simplify(self, points):
        if len(points) < 3:
            return None
        elif len(points) <= 5:
            return points
        flag = True
        while flag:
            flag = False
            for i in range(len(points) - 1):
                a = points[i]
                b = points[i + 1]
                dis = (a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2
                if dis < 6:
                    c = [(a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0]
                    points.pop(i)
                    points.pop(i)
                    points.insert(i, c)
                    if i < len(points) - 1:
                        flag = True
                    break
            if len(points) <= 5:
                flag = False
        for i in range(len(points)):
            point = points[i]
            points[i] = [int(point[0]), int(point[1])]
        return points

    def resizeEvent(self, event):
        if self.canvas and not self.image.isNull()\
           and self.zoomMode != self.MANUAL_ZOOM:
            self.adjustScale()
        super(MainWindow, self).resizeEvent(event)

    def paintCanvas(self):
        assert not self.image.isNull(), "没有图像"
        self.canvas.scale = 0.01 * self.zoomWidget.value()
        self.canvas.adjustSize()
        self.canvas.update()

    def adjustScale(self, initial=False):
        value = self.scalers[self.FIT_WINDOW if initial else self.zoomMode]()
        self.zoomWidget.setValue(int(100 * value))

    def scaleFitWindow(self):
        """Figure out the size of the pixmap to fit the main widget."""
        e = 2.0  # So that no scrollbars are generated.
        w1 = self.centralWidget().width() - e
        h1 = self.centralWidget().height() - e
        a1 = w1 / h1
        # Calculate a new scale value based on the pixmap's aspect ratio.
        w2 = self.canvas.pixmap.width() - 0.0
        h2 = self.canvas.pixmap.height() - 0.0
        a2 = w2 / h2
        return w1 / w2 if a2 >= a1 else h1 / h2

    def scaleFitWidth(self):
        # The epsilon does not seem to work too well here.
        w = self.centralWidget().width() - 2.0
        return w / self.canvas.pixmap.width()

    def closeEvent(self, event):
        if not self.mayContinue():
            event.ignore()
        self.settings.setValue(
            'filename', self.filename if self.filename else '')
        self.settings.setValue('window/size', self.size())
        self.settings.setValue('window/position', self.pos())
        self.settings.setValue('window/state', self.saveState())
        self.settings.setValue('line/color', self.lineColor)
        self.settings.setValue('fill/color', self.fillColor)
        self.settings.setValue('recentFiles', self.recentFiles)
        # ask the use for where to save the labels
        # self.settings.setValue('window/geometry', self.saveGeometry())

    # User Dialogs #

    def loadRecent(self, filename):
        if self.mayContinue():
            self.loadFile(filename)

    def openPrevImg(self, _value=False):
        if not self.mayContinue():
            return

        if len(self.imageList) <= 0:
            return

        if self.filename is None:
            return

        currIndex = self.imageList.index(self.filename)
        if currIndex - 1 >= 0:
            filename = self.imageList[currIndex - 1]
            if filename:
                print("prev filename:", filename)   #------------------------------------------
                self.loadFile(filename)

    def openNextImg(self, _value=False, load=True):
        if not self.mayContinue():
            return

        if len(self.imageList) <= 0:
            return

        filename = None
        if self.filename is None:
            filename = self.imageList[0]
        else:
            currIndex = self.imageList.index(self.filename)
            if currIndex + 1 < len(self.imageList):
                filename = self.imageList[currIndex + 1]
            else:
                filename = self.imageList[-1]
        self.filename = filename
        if self.filename and load:
            print("next filename:", filename)   # ------------------------------------------------
            self.loadFile(self.filename)

    def openFile(self, _value=False):
        if not self.mayContinue():
            return
        path = os.path.dirname(str(self.filename)) if self.filename else '.'
        formats = ['*.{}'.format(fmt.data().decode())
                   for fmt in QtGui.QImageReader.supportedImageFormats()]
        filters = "图像或标注文件（%s）" % ' '.join(
            formats + ['*%s' % LabelFile.suffix])
        filename = QtWidgets.QFileDialog.getOpenFileName(
            self, '%s - 选择图像或标签文件' % __appname__,
            path, filters)

        if QT5:
            filename, _ = filename
        filename = str(filename)
        if filename:
            print("openFile: ", filename)
            self.loadFile(filename)


    def saveFile(self, _value=False):
        assert not self.image.isNull(), "不能保存，没有图像"
        if self._config['flags'] or self.hasLabels():
            if self.labelFile:
                print("labelFile")
                # DL20180323 - overwrite when in directory
                if self.labelFile.filename != None:
                    self._saveFile(self.labelFile.filename)
                else:
                    label_file = os.path.splitext(self.filename)[0] + '.json'
                    print(label_file)
                    self._saveFile(label_file)
            elif self.output:
                print("output")
                self._saveFile(self.output)
            else:
                print("saveFileDialog()")
                label_file = os.path.splitext(self.filename)[0] + '.json'
                self._saveFile(label_file)
                # self._saveFile(self.saveFileDialog())

    def saveFileAs(self, _value=False):
        assert not self.image.isNull(), "不能保存，没有图像"
        if self.hasLabels():
            self._saveFile(self.saveFileDialog())

    def saveFileDialog(self):
        caption = '%s - 选择文件' % __appname__
        filters = '标注文件（*%s）' % LabelFile.suffix
        dlg = QtWidgets.QFileDialog(self, caption, self.currentPath(), filters)
        dlg.setDefaultSuffix(LabelFile.suffix[1:])
        dlg.setAcceptMode(QtWidgets.QFileDialog.AcceptSave)
        dlg.setOption(QtWidgets.QFileDialog.DontConfirmOverwrite, False)
        dlg.setOption(QtWidgets.QFileDialog.DontUseNativeDialog, False)
        basename = os.path.splitext(self.filename)[0]
        default_labelfile_name = os.path.join(
            self.currentPath(), basename + LabelFile.suffix)
        filename = dlg.getSaveFileName(
            self, '选择文件', default_labelfile_name,
            '标注文件（*%s）' % LabelFile.suffix)
        if QT5:
            filename, _ = filename
        filename = str(filename)    # json_Path
        return filename

    def _saveFile(self, filename):
        if filename and self.saveLabels(filename):
            self.addRecentFile(filename)
            self.setClean()
            if self.labeling_once:
                self.close()

    def closeFile(self, _value=False):
        if not self.mayContinue():
            return
        self.resetState()
        self.setClean()
        self.toggleActions(False)
        self.canvas.setEnabled(False)
        self.actions.saveAs.setEnabled(False)

    # Message Dialogs. #
    def hasLabels(self):
        if not self.labelList.itemsToShapes:
            self.errorMessage(
                '没有绘制标签',
                '你必须至少绘制一个标签区域来保存标注文件')
            return False
        return True

    def mayContinue(self):
        if not self.dirty:
            return True
        mb = QtWidgets.QMessageBox
        msg = '要在关闭"{}"之前保存标注文件吗？'.format(self.filename)
        answer = mb.question(self,
                             '保存标注文件？',
                             msg,
                             mb.Save | mb.Discard | mb.Cancel,
                             mb.Save)
        if answer == mb.Discard:
            return True
        elif answer == mb.Save:
            self.saveFile()
            return True
        else:  # answer == mb.Cancel
            return False

    def errorMessage(self, title, message):
        return QtWidgets.QMessageBox.critical(
            self, title, '<p><b>%s</b></p>%s' % (title, message))

    def currentPath(self):
        return os.path.dirname(str(self.filename)) if self.filename else '.'

    def chooseColor1(self):
        color = self.colorDialog.getColor(
            self.lineColor, '选择线条颜色', default=DEFAULT_LINE_COLOR)
        if color:
            self.lineColor = color
            # Change the color for all shape lines:
            Shape.line_color = self.lineColor
            self.canvas.update()
            self.setDirty()

    def chooseColor2(self):
        color = self.colorDialog.getColor(
            self.fillColor, '选择填充颜色', default=DEFAULT_FILL_COLOR)
        if color:
            self.fillColor = color
            Shape.fill_color = self.fillColor
            self.canvas.update()
            self.setDirty()

    def deleteSelectedShape(self):
        yes, no = QtWidgets.QMessageBox.Yes, QtWidgets.QMessageBox.No
        msg = '你将永久删除这个多边形，' \
              '确定删除吗？'
        if yes == QtWidgets.QMessageBox.warning(self, '注意', msg,
                                                yes | no):
            self.remLabel(self.canvas.deleteSelected())
            self.setDirty()
            if self.noShapes():
                for action in self.actions.onShapesPresent:
                    action.setEnabled(False)

    def chshapeLineColor(self):
        color = self.colorDialog.getColor(
            self.lineColor, '选择线条颜色', default=DEFAULT_LINE_COLOR)
        if color:
            self.canvas.selectedShape.line_color = color
            self.canvas.update()
            self.setDirty()

    def chshapeFillColor(self):
        color = self.colorDialog.getColor(
            self.fillColor, '选择填充颜色', default=DEFAULT_FILL_COLOR)
        if color:
            self.canvas.selectedShape.fill_color = color
            self.canvas.update()
            self.setDirty()

    def copyShape(self):
        self.canvas.endMove(copy=True)
        self.addLabel(self.canvas.selectedShape)
        self.setDirty()

    def moveShape(self):
        self.canvas.endMove(copy=False)
        self.setDirty()

    def openDirDialog(self, _value=False, dirpath=None):
        if not self.mayContinue():
            return

        defaultOpenDirPath = dirpath if dirpath else '.'
        if self.lastOpenDir and os.path.exists(self.lastOpenDir):
            defaultOpenDirPath = self.lastOpenDir
        else:
            defaultOpenDirPath = os.path.dirname(self.filename) \
                if self.filename else '.'

        targetDirPath = str(QtWidgets.QFileDialog.getExistingDirectory(
            self, '%s - 打开文件夹' % __appname__, defaultOpenDirPath,
            QtWidgets.QFileDialog.ShowDirsOnly |
            QtWidgets.QFileDialog.DontResolveSymlinks))
        # print("open dir: ", targetDirPath)
        self.importDirImages(targetDirPath)

    @property
    def imageList(self):
        lst = []
        for i in range(self.fileListWidget.count()):
            item = self.fileListWidget.item(i)
            lst.append(item.text())
        return lst

    def importDirImages(self, dirpath, pattern=None, load=True):
        if not self.mayContinue() or not dirpath:
            return

        self.lastOpenDir = dirpath
        self.filename = None
        self.fileListWidget.clear()
        for filename in self.scanAllImages(dirpath):
            if pattern and pattern not in filename:
                continue
            label_file = os.path.splitext(filename)[0] + '.json'
            item = QtWidgets.QListWidgetItem(filename)
            item.setFlags(Qt.ItemIsEnabled | Qt.ItemIsSelectable)
            if QtCore.QFile.exists(label_file) and \
                    LabelFile.isLabelFile(label_file):
                item.setCheckState(Qt.Checked)
            else:
                item.setCheckState(Qt.Unchecked)
            self.fileListWidget.addItem(item)
        self.openNextImg(load=load)

    def scanAllImages(self, folderPath):
        extensions = ['.%s' % fmt.data().decode("ascii").lower()
                      for fmt in QtGui.QImageReader.supportedImageFormats()]
        images = []

        for root, dirs, files in os.walk(folderPath):
            for file in files:
                if file.lower().endswith(tuple(extensions)):
                    relativePath = os.path.join(root, file)
                    images.append(relativePath)
        images.sort(key=lambda x: x.lower())
        return images


def read(filename, default=None):
    try:
        with open(filename, 'rb') as f:
            return f.read()
    except Exception:
        return default
