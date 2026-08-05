# Attribute Form Toggle

<p align="left">
  <img src="https://img.shields.io/badge/QGIS-3.16%E2%80%934.x-589632?logo=qgis&logoColor=white" alt="QGIS 3.16–4.x">
  <img src="https://img.shields.io/badge/category-Vector-blue" alt="Category — Vector">
</p>

Attribute Form Toggle is a QGIS plugin that lets you temporarily disable the
automatic opening of the attribute form after creating a feature with a single
click.

## Demo

![Attribute Form Toggle demo](demo.gif)

It is useful for rapid digitizing workflows where attributes do not need to be
entered after adding each geometry. Complements the **Reuse last entered attribute values** option under
**Settings → Options → Digitizing**: QGIS retains previously entered values,
while the plugin controls whether the attribute form opens after each new
feature.

The plugin does not override or change the global QGIS **Suppress attribute
form pop-up after feature creation** option. When that option is enabled under
**Settings → Options → Digitizing**, QGIS already suppresses the form, so the
plugin action is disabled until the global option is turned off.

## Features

- Enables or disables the attribute form for the active vector layer.
- Automatically applies the selected mode when switching to another vector
  layer.
- Lets you place the main button on either the Layers toolbar or the Plugins
  toolbar.
- Changes the button icon according to the current mode.
- Displays a short notification when the mode changes.
- Respects the global QGIS **Suppress attribute form pop-up after feature
  creation** option without overriding or changing it. While the option is
  enabled, the plugin action is disabled and its tooltip shows the corresponding
  QGIS settings path.
- Complements the **Reuse last entered attribute values** checkbox under
  **Settings → Options → Digitizing**: QGIS retains previously entered values,
  while the plugin controls whether the attribute form opens after each new
  feature.
- Includes compiled translations and their source files for all languages
  shipped with supported QGIS versions.

## Requirements

- QGIS 3.16 or later.
- No additional Python dependencies are required.

The plugin uses `qgis.PyQt` modules and therefore does not depend directly on a
specific PyQt version.

## Installation

1. Download the plugin ZIP archive from the repo folder.
2. In QGIS, open **Plugins → Manage and Install Plugins**.
3. Select the **Install from ZIP** tab.
4. Choose the downloaded archive and click **Install Plugin**.
5. If necessary, enable **Attribute Form Toggle** in the list of installed
   plugins.

## Usage

1. Select a vector layer in the Layers panel.
2. Click **Disable Form** on the Layers toolbar or select it from the
   **Attribute Form Toggle** menu.
3. Add new features. The attribute form will no longer open automatically.
4. Click the button again to restore the default QGIS behavior for the active
   layer.

Open **Plugins → Attribute Form Toggle** and select **Button on Layers
toolbar** or **Button on Plugins toolbar** to change the main button location.
The selected location is saved between QGIS sessions.

The toggle affects vector layers only. If you switch to another vector layer
while form suppression is enabled, the plugin applies the same mode to the new
active layer.

For faster entry of similar features, select the **Reuse last entered attribute
values** checkbox under **Settings → Options → Digitizing**. QGIS will retain
previously entered attributes, while Attribute Form Toggle lets you decide
whether the form should open after each new feature.

When form pop-up suppression is already enabled globally in QGIS under
**Settings → Options → Digitizing**, the plugin action is disabled because the
attribute form is already suppressed by QGIS. The plugin does not turn off,
override, or otherwise modify this global setting.

## Localization

The `i18n` directory contains editable `.ts` sources and compiled `.qm` files
for every language shipped with the supported QGIS versions. QGIS loads the
translation matching its current interface locale automatically.

## License

This project is distributed under the [MIT License](LICENSE).
