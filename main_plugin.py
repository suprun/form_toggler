import os
from qgis.PyQt.QtCore import QCoreApplication, QTimer, QTranslator
from qgis.PyQt.QtWidgets import QAction, QActionGroup, QDockWidget, QToolBar
from qgis.PyQt.QtGui import QIcon
from qgis.core import (
    Qgis,
    QgsApplication,
    QgsEditFormConfig,
    QgsMapLayer,
    QgsSettings,
)


GLOBAL_FORM_SUPPRESSION_SETTING = (
    "/digitizing/disable-enter-attribute-values-dialog"
)
LEGACY_GLOBAL_FORM_SUPPRESSION_SETTING = (
    "/qgis/digitizing/disable_enter_attribute_values_dialog"
)
PLUGIN_MENU_NAME = "&Attribute Form Toggle"
BUTTON_LOCATION_SETTING = (
    "/plugins/attribute_form_toggle/button_location"
)
LEGACY_BUTTON_LOCATION_SETTING = "/plugins/form_toggler/button_location"
LAYERS_TOOLBAR_LOCATION = "layers"
PLUGINS_TOOLBAR_LOCATION = "plugins"
MAP_LAYER_TYPE = getattr(QgsMapLayer, "LayerType", QgsMapLayer)
EDIT_FORM_SUPPRESS = getattr(
    QgsEditFormConfig,
    "FeatureFormSuppress",
    QgsEditFormConfig,
)


class AttributeFormTogglePlugin:
    def __init__(self, iface):
        self.iface = iface
        self.action = None
        self.layer_tree_toolbar = None
        self.button_location = None
        self.location_action_group = None
        self.location_separator_action = None
        self.layers_toolbar_location_action = None
        self.plugins_toolbar_location_action = None
        self.settings_timer = None
        self.is_active_mode = False
        
        # Визначаємо шлях до папки плагіна
        self.plugin_dir = os.path.dirname(__file__)
        
        # Локалізація
        locale = QgsApplication.locale()
        locale_candidates = (locale, locale.split('_')[0])
        for locale_name in dict.fromkeys(locale_candidates):
            locale_path = os.path.join(
                self.plugin_dir,
                'i18n',
                f'attribute_form_toggle_{locale_name}.qm',
            )
            if os.path.exists(locale_path):
                self.translator = QTranslator()
                self.translator.load(locale_path)
                QCoreApplication.installTranslator(self.translator)
                break

    def tr(self, message):
        return QCoreApplication.translate(
            'AttributeFormTogglePlugin',
            message,
        )

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
        self.action = QAction(
            self.tr("Disable Form"),
            self.iface.mainWindow(),
        )
        self.action.setCheckable(True)
        self.action.setToolTip(
            self.tr(
                "Temporarily disable attribute form when adding features. "
                "Global setting: Settings → Options → Digitizing."
            )
        )
        
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

        self.create_location_actions()
        settings = QgsSettings()
        if settings.contains(BUTTON_LOCATION_SETTING):
            saved_location = settings.value(
                BUTTON_LOCATION_SETTING,
                LAYERS_TOOLBAR_LOCATION,
                type=str,
            )
        else:
            saved_location = settings.value(
                LEGACY_BUTTON_LOCATION_SETTING,
                LAYERS_TOOLBAR_LOCATION,
                type=str,
            )
            settings.setValue(BUTTON_LOCATION_SETTING, saved_location)
            settings.sync()
        self.set_button_location(saved_location, save=False)

        for menu_action in (
            self.action,
            self.location_separator_action,
            self.layers_toolbar_location_action,
            self.plugins_toolbar_location_action,
        ):
            self.iface.addPluginToMenu(PLUGIN_MENU_NAME, menu_action)
        self.set_plugin_submenu_icon()

        self.settings_timer = QTimer(self.iface.mainWindow())
        self.settings_timer.setInterval(1000)
        self.settings_timer.timeout.connect(self.update_action_availability)
        self.settings_timer.start()
        self.update_action_availability()

    def unload(self):
        if self.settings_timer:
            self.settings_timer.stop()
            self.settings_timer.timeout.disconnect(
                self.update_action_availability
            )
            self.settings_timer.deleteLater()
            self.settings_timer = None

        if self.action:
            self.remove_main_action_from_toolbar()
            for menu_action in (
                self.action,
                self.location_separator_action,
                self.layers_toolbar_location_action,
                self.plugins_toolbar_location_action,
            ):
                self.iface.removePluginMenu(PLUGIN_MENU_NAME, menu_action)
        
        try:
            self.iface.currentLayerChanged.disconnect(self.on_layer_changed)
        except (TypeError, RuntimeError):
            pass
            
        self.restore_layer_form(self.iface.activeLayer())

    def create_location_actions(self):
        parent = self.iface.mainWindow()
        self.location_action_group = QActionGroup(parent)
        self.location_action_group.setExclusive(True)

        self.layers_toolbar_location_action = QAction(
            self.tr("Button on Layers toolbar"),
            parent,
        )
        self.layers_toolbar_location_action.setCheckable(True)
        self.location_action_group.addAction(
            self.layers_toolbar_location_action
        )
        self.layers_toolbar_location_action.triggered.connect(
            lambda checked: self.set_button_location(
                LAYERS_TOOLBAR_LOCATION
            ) if checked else None
        )

        self.plugins_toolbar_location_action = QAction(
            self.tr("Button on Plugins toolbar"),
            parent,
        )
        self.plugins_toolbar_location_action.setCheckable(True)
        self.location_action_group.addAction(
            self.plugins_toolbar_location_action
        )
        self.plugins_toolbar_location_action.triggered.connect(
            lambda checked: self.set_button_location(
                PLUGINS_TOOLBAR_LOCATION
            ) if checked else None
        )

        self.location_separator_action = QAction(parent)
        self.location_separator_action.setSeparator(True)

    def set_button_location(self, location, save=True):
        if location not in (
            LAYERS_TOOLBAR_LOCATION,
            PLUGINS_TOOLBAR_LOCATION,
        ):
            location = LAYERS_TOOLBAR_LOCATION

        if location == LAYERS_TOOLBAR_LOCATION and not self.layer_tree_toolbar:
            location = PLUGINS_TOOLBAR_LOCATION

        if self.button_location != location:
            self.remove_main_action_from_toolbar()
            if location == LAYERS_TOOLBAR_LOCATION:
                self.layer_tree_toolbar.addAction(self.action)
            else:
                self.iface.addToolBarIcon(self.action)
            self.button_location = location

        self.layers_toolbar_location_action.setChecked(
            location == LAYERS_TOOLBAR_LOCATION
        )
        self.plugins_toolbar_location_action.setChecked(
            location == PLUGINS_TOOLBAR_LOCATION
        )

        if save:
            settings = QgsSettings()
            settings.setValue(BUTTON_LOCATION_SETTING, location)
            settings.sync()

    def remove_main_action_from_toolbar(self):
        if self.button_location == LAYERS_TOOLBAR_LOCATION:
            if self.layer_tree_toolbar:
                self.layer_tree_toolbar.removeAction(self.action)
        elif self.button_location == PLUGINS_TOOLBAR_LOCATION:
            self.iface.removeToolBarIcon(self.action)
        self.button_location = None

    def set_plugin_submenu_icon(self):
        icon_path = os.path.join(self.plugin_dir, "icon.svg")
        plugin_icon = QIcon(icon_path)
        if plugin_icon.isNull():
            return

        for menu_action in self.iface.pluginMenu().actions():
            submenu = menu_action.menu()
            if submenu and self.action in submenu.actions():
                submenu.menuAction().setIcon(plugin_icon)
                return

    def update_action_availability(self):
        if not self.action:
            return

        settings = QgsSettings()
        settings.sync()
        setting_key = GLOBAL_FORM_SUPPRESSION_SETTING
        if Qgis.QGIS_VERSION_INT < 33000:
            setting_key = LEGACY_GLOBAL_FORM_SUPPRESSION_SETTING

        legacy_value = settings.value(
            LEGACY_GLOBAL_FORM_SUPPRESSION_SETTING,
            False,
            type=bool,
        )
        global_suppression_enabled = settings.value(
            setting_key,
            legacy_value,
            type=bool,
        )
        self.action.setEnabled(not global_suppression_enabled)

        if global_suppression_enabled:
            tooltip = self.tr(
                "Disabled because form pop-up suppression is enabled "
                "globally. Change it in Settings → Options → Digitizing."
            )
        else:
            tooltip = self.tr(
                "Temporarily disable attribute form when adding features. "
                "Global setting: Settings → Options → Digitizing."
            )
        self.action.setToolTip(tooltip)

    def toggle_mode(self, checked):
        self.is_active_mode = checked
        
        # ЗМІНА ІКОНКИ
        if checked:
            self.action.setIcon(self.icon_active)
        else:
            self.action.setIcon(self.icon_default)
            
        self.on_layer_changed(self.iface.activeLayer())
        
        status = (
            self.tr("Temporarily disabled")
            if checked
            else self.tr("Enabled")
        )
        self.iface.messageBar().pushMessage(
            self.tr("Attribute Form Toggle"),
            status,
            level=Qgis.MessageLevel.Info,
            duration=2,
        )

    def on_layer_changed(self, layer):
        if not layer or layer.type() != MAP_LAYER_TYPE.VectorLayer:
            return
        form_config = layer.editFormConfig()
        suppress_mode = (
            EDIT_FORM_SUPPRESS.SuppressOn
            if self.is_active_mode
            else EDIT_FORM_SUPPRESS.SuppressDefault
        )
        form_config.setSuppress(suppress_mode)
        layer.setEditFormConfig(form_config)

    def restore_layer_form(self, layer):
        if layer and layer.type() == MAP_LAYER_TYPE.VectorLayer:
            form_config = layer.editFormConfig()
            form_config.setSuppress(EDIT_FORM_SUPPRESS.SuppressDefault)
            layer.setEditFormConfig(form_config)
