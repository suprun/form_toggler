def classFactory(iface):
    from .main_plugin import FormTogglerPlugin
    return FormTogglerPlugin(iface)