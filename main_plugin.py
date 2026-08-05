import os
from qgis.PyQt.QtCore import QCoreApplication, QTranslator
from qgis.PyQt.QtWidgets import QAction, QDockWidget, QToolBar
from qgis.PyQt.QtGui import QIcon
from qgis.core import Qgis, QgsEditFormConfig, QgsMapLayer, QgsApplication

class FormTogglerPlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.layer_tree_toolbar = None
        self.is_active_mode = False 
        
        # Визначаємо шлях до папки плагіна
        self.plugin_dir = os.path.dirname(__file__)
        
        # Локалізація
        locale = QgsApplication.locale().split('_')[0] 
        locale_path = os.path.join(self.plugin_dir, 'i18n', f'form_toggler_{locale}.qm')
        if os.path.exists(locale_path):
            self.translator = QTranslator()
            self.translator.load(locale_path)
            QCoreApplication.installTranslator(self.translator)

    def tr(self, message):
        return QCoreApplication.translate('FormTogglerPlugin', message)

    def get_attributes_form_icon(self):
        """Стандартна іконка форми (для стану 'Вимкнено')"""
        candidates = [
            "/propertyicons/formView.svg",
            "/mIconFormView.svg",
            "/mActionFormView.svg",
            "/mActionOpenTable.svg"  
        ]
        for candidate in candidates:
            icon = QgsApplication.getThemeIcon(candidate)
            if not icon.isNull():
                return icon
        return QIcon()

    def get_cancel_icon(self):
        """Ваша власна іконка з папки плагіна (для стану 'Увімкнено')"""
        # Шукаємо файл icon-cancel.svg безпосередньо в папці плагіна
        icon_path = os.path.join(self.plugin_dir, 'icon-cancel.svg')
        
        if os.path.exists(icon_path):
            return QIcon(icon_path)
        else:
            # Якщо файл не знайдено, повертаємо системну іконку скасування як запасну
            return QgsApplication.getThemeIcon("/mActionDeleteSelected.svg")

    def initGui(self):
        self.action = QAction(self.tr("Disable Form"), self.iface.mainWindow())
        self.action.setCheckable(True)
        self.action.setToolTip(self.tr("Temporarily disable attribute form"))
        
        # Підготовлюємо обидві іконки
        self.icon_default = self.get_attributes_form_icon()
        self.icon_active = self.get_cancel_icon()
        
        # Встановлюємо початкову іконку
        self.action.setIcon(self.icon_default)
        
        self.action.toggled.connect(self.toggle_mode)
        self.iface.currentLayerChanged.connect(self.on_layer_changed)
        
        # Додавання на панель шарів
        layer_dock = self.iface.mainWindow().findChild(QDockWidget, "Layers")
        if layer_dock:
            self.layer_tree_toolbar = layer_dock.findChild(QToolBar)
            if self.layer_tree_toolbar:
                self.layer_tree_toolbar.addAction(self.action)
        
        if not self.layer_tree_toolbar:
            self.iface.addToolBarIcon(self.action)
            
        self.iface.addPluginToMenu("&Form Toggler", self.action)

    def unload(self):
        if self.action:
            if self.layer_tree_toolbar:
                self.layer_tree_toolbar.removeAction(self.action)
            else:
                self.iface.removeToolBarIcon(self.action)
            self.iface.removePluginMenu("&Form Toggler", self.action)
        
        try:
            self.iface.currentLayerChanged.disconnect(self.on_layer_changed)
        except: pass
            
        self.restore_layer_form(self.iface.activeLayer())

    def toggle_mode(self, checked):
        self.is_active_mode = checked
        
        # ЗМІНА ІКОНКИ
        if checked:
            self.action.setIcon(self.icon_active)
        else:
            self.action.setIcon(self.icon_default)
            
        self.on_layer_changed(self.iface.activeLayer())
        
        status = self.tr("Temporarily disabled") if checked else self.tr("Enabled")
        self.iface.messageBar().pushMessage(self.tr("Form Toggler"), status, level=Qgis.MessageLevel.Info, duration=2)

    def on_layer_changed(self, layer):
        if not layer or layer.type() != QgsMapLayer.VectorLayer:
            return
        form_config = layer.editFormConfig()
        form_config.setSuppress(QgsEditFormConfig.SuppressOn if self.is_active_mode else QgsEditFormConfig.SuppressDefault)
        layer.setEditFormConfig(form_config)

    def restore_layer_form(self, layer):
        if layer and layer.type() == QgsMapLayer.VectorLayer:
            form_config = layer.editFormConfig()
            form_config.setSuppress(QgsEditFormConfig.SuppressDefault)
            layer.setEditFormConfig(form_config)