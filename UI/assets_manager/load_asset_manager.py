from __future__ import absolute_import
'''
version: 1.0.0
date: 21/04/2020

#----------------
content:

#----------------
how to:

try:
    import importlib;from importlib import reload
except:
    import imp;from imp import reload

import Blue_Pipeline
from Blue_Pipeline.UI.assets_manager import load_asset_manager
reload(load_asset_manager)

try:cAssetsManagerUI.close()
except:pass
cAssetsManagerUI = load_asset_manager.AssetsManagerUI()
cAssetsManagerUI.show()

#----------------
dependencies:

QT FILE
ICONS
JSON FILES

#----------------
author:  Esteban Rodriguez <info@renderdemartes.com>

'''
# -------------------------------------------------------------------
try:
    from shiboken6 import wrapInstance
    from PySide6 import QtGui, QtCore
    from PySide6 import QtUiTools
    from PySide6 import QtWidgets
    from PySide6.QtWidgets import *
except:
    from shiboken2 import wrapInstance
    from PySide2 import QtGui, QtCore
    from PySide2 import QtUiTools
    from PySide2 import QtWidgets
    from PySide2.QtWidgets import *

import maya.OpenMayaUI as omui
from functools import partial
from maya import OpenMaya
import maya.cmds as cmds
import maya.mel as mel

import os
import re
import subprocess
import tempfile

try:
    import importlib;from importlib import reload
except:
    import imp;from imp import reload

import sys
import json
import glob
import pprint
from datetime import datetime
from pathlib import Path
from collections import defaultdict

from Blue_Pipeline.Utils.Helpers.decorators import undo


# -------------------------------------------------------------------

# QT WIndow!
FOLDER_NAME = 'assets_manager'
Title = 'Assets Manager'
UI_File = 'asset_manager.ui'

# QT WIndow!
PATH = os.path.dirname(__file__)
PATH = Path(PATH)
PATH_PARTS = PATH.parts[:-2]
FOLDER=''
for f in PATH_PARTS:
    FOLDER = os.path.join(FOLDER, f)

IconsPath = os.path.join(FOLDER, 'Icons')



# -------------------------------------------------------------------

import Blue_Pipeline
import Blue_Pipeline.UI
from Blue_Pipeline.UI import QtBlueWindow
reload(QtBlueWindow)
Qt_Blue = QtBlueWindow.Qt_Blue()

# -------------------------------------------------------------------

BUILD_DATA_QUERY_ENABLED = False
BUILD_DATA_QUERY_ROOT = None
BUILD_DATA_QUERY_FILES = {}
BUILD_DATA_COLOR_ENABLED = False


def maya_main_window():
    main_window_ptr = omui.MQtUtil.mainWindow()
    return wrapInstance(int(main_window_ptr), QtWidgets.QWidget)


def build_mutant_build_data(root_path="E:/BlueTape", keyword="mutant_build"):
    """
    Scan all .ma files under root_path and save a JSON report with files that
    contain keyword and files that do not.

    Args:
        root_path (str): Root folder that contains all show folders.
        keyword (str): Text to search inside .ma files.

    Returns:
        dict or None: Report dictionary if successful, otherwise None.
    """
    root_path = os.path.abspath(root_path)
    output_json_path = os.path.join(root_path, "Build_Data.json")

    if not os.path.isdir(root_path):
        cmds.warning(f"Invalid root path: {root_path}")
        return None

    ma_files = glob.glob(os.path.join(root_path, "**", "*.ma"), recursive=True)

    keyword_lower = (keyword or "").lower()

    report = {
        "root_path": root_path,
        "keyword": keyword_lower,
        "generated_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "files_with_mutant_build": [],
        "files_without_mutant_build": [],
        "read_errors": {},
        "files": {}
    }

    for file_path in ma_files:
        rel_path = os.path.relpath(file_path, root_path).replace("\\", "/")
        has_keyword = False

        try:
            with open(file_path, "r", encoding="utf-8", errors="ignore") as handle:
                for line in handle:
                    if keyword_lower in line.lower():
                        has_keyword = True
                        break
        except Exception as e:
            report["read_errors"][rel_path] = str(e)
            report["files"][rel_path] = None
            continue

        report["files"][rel_path] = has_keyword
        if has_keyword:
            report["files_with_mutant_build"].append(rel_path)
        else:
            report["files_without_mutant_build"].append(rel_path)

    report["files_with_mutant_build"].sort()
    report["files_without_mutant_build"].sort()
    report["summary"] = {
        "total_ma_files": len(ma_files),
        "with_mutant_build": len(report["files_with_mutant_build"]),
        "without_mutant_build": len(report["files_without_mutant_build"]),
        "read_errors": len(report["read_errors"]),
    }

    with open(output_json_path, "w", encoding="utf-8") as json_file:
        json.dump(report, json_file, indent=4, ensure_ascii=False)

    print(f"[INFO] Build data saved to: {output_json_path}")
    return report


def load_mutant_build_query_data(query_json_path="E:/BlueTape/Build_Data.json"):
    """
    Load Build_Data.json into memory for query-only UI highlighting.
    Returns parsed data when loaded, otherwise None.
    """
    global BUILD_DATA_QUERY_ENABLED
    global BUILD_DATA_QUERY_ROOT
    global BUILD_DATA_QUERY_FILES

    if not os.path.exists(query_json_path):
        return None

    try:
        with open(query_json_path, "r", encoding="utf-8") as json_file:
            data = json.load(json_file)
    except Exception:
        return None

    files_data = data.get("files", {})
    root_path = data.get("root_path", "")
    if not isinstance(files_data, dict) or not root_path:
        return None

    normalized_files = {}
    for rel_path, value in files_data.items():
        key = str(rel_path).replace("\\", "/").lower()
        normalized_files[key] = bool(value)

    BUILD_DATA_QUERY_ROOT = os.path.abspath(root_path)
    BUILD_DATA_QUERY_FILES = normalized_files
    BUILD_DATA_QUERY_ENABLED = True
    return data


def set_mutant_build_color_enabled(enabled=True):
    global BUILD_DATA_COLOR_ENABLED
    BUILD_DATA_COLOR_ENABLED = bool(enabled)


def get_mutant_build_flag_from_query(file_path):
    if not BUILD_DATA_COLOR_ENABLED:
        return False

    if not BUILD_DATA_QUERY_ENABLED:
        return False

    if not file_path.lower().endswith(".ma"):
        return False

    if not BUILD_DATA_QUERY_ROOT:
        return False

    abs_file_path = os.path.normcase(os.path.normpath(os.path.abspath(file_path)))
    abs_root_path = os.path.normcase(os.path.normpath(os.path.abspath(BUILD_DATA_QUERY_ROOT)))

    try:
        if os.path.commonpath([abs_root_path, abs_file_path]) != abs_root_path:
            return False
    except ValueError:
        return False

    rel_path = os.path.relpath(abs_file_path, abs_root_path).replace("\\", "/").lower()
    return bool(BUILD_DATA_QUERY_FILES.get(rel_path, False))


class AssetsManagerUI(QtBlueWindow.Qt_Blue):

    def __init__(self):
        super(AssetsManagerUI, self).__init__()

        self.current_show = None
        self.current_asset = None
        self.current_task = None
        self.scene_opened_job = None
        self.version_delete_dialog = None

        self.setWindowTitle(Title)
        self.where_to_save_files = None

        self.project_folder = self.check_if_project_exists()

        self.designer_loader_child(path=os.path.join(FOLDER, 'UI', FOLDER_NAME), ui_file=UI_File)
        self.set_title(Title)

        self.show_buttons = []

        self.create_layout()
        self.create_connections()

        self.find_name_conflicts()
        self.register_scene_opened_callback()
        QtCore.QTimer.singleShot(0, self.force_initial_resize)


    # -------------------------------------------------------------------

    def create_layout(self):
        """
        Initialize the UI layout and populate the first show and its assets.
        If no shows exist, prompt the user to create the first one.
        """
        self.create_menu()
        paths = self.populate_shows()
        last_path = self.read_last_used_show()

        # If there are no shows yet
        if not paths:
            self.create_new_show()
        else:
            # If we have a last used show, load it; otherwise default to first one
            if last_path:
                self.populate_assets(last_path)
            else:
                self.populate_assets(paths[0])

        self.set_blue_buttons()

    def force_initial_resize(self):
        # Fake a tiny resize to force Qt to recalc layouts + icon sizes
        size = self.size()
        self.resize(size.width() + 1, size.height() + 1)
        self.resize(size)

    def register_scene_opened_callback(self):
        self.unregister_scene_opened_callback()
        try:
            self.scene_opened_job = cmds.scriptJob(event=["SceneOpened", self.on_scene_opened], protected=True)
        except Exception as e:
            cmds.warning(f"Failed to register SceneOpened callback: {e}")

    def unregister_scene_opened_callback(self):
        if self.scene_opened_job and cmds.scriptJob(exists=self.scene_opened_job):
            try:
                cmds.scriptJob(kill=self.scene_opened_job, force=True)
            except Exception as e:
                cmds.warning(f"Failed to remove SceneOpened callback: {e}")
        self.scene_opened_job = None

    def on_scene_opened(self):
        scene_path = cmds.file(q=True, sn=True)
        if scene_path:
            self.set_project_from_scene(scene_path)

    def create_connections(self):
        """

        Returns:

        """

        self.ui.settings_button.clicked.connect(self.on_change_project_clicked)
        self.ui.add_show_button.clicked.connect(self.create_new_show)
        self.ui.add_asset_button.clicked.connect(self.create_new_asset)
        self.ui.add_task_button.clicked.connect(self.create_new_task)
        self.ui.save_wip_button.clicked.connect(self.save_wip)
        self.ui.publish_button.clicked.connect(self.publish_asset)
        self.ui.shows_search_line.textChanged.connect(self.filter_shows)

    def open_version_delete_dialog(self):
        if not self.project_folder or not os.path.isdir(self.project_folder):
            QtWidgets.QMessageBox.warning(self, "Project Folder", "Project folder is not valid.")
            return

        if self.version_delete_dialog is None:
            self.version_delete_dialog = VersionDeleteDialog(project_folder=self.project_folder, parent=self)
        else:
            self.version_delete_dialog.set_project_folder(self.project_folder)

        self.version_delete_dialog.show()
        self.version_delete_dialog.raise_()
        self.version_delete_dialog.activateWindow()

    def find_name_conflicts(self):
        """
        Fast duplicate name finder using glob pattern:
        /media/vancouver/BlueTape/*/*/*/{Wip,Publish}
        Shows a scrollable dialog if conflicts exist.
        """

        root = self.project_folder

        # Gather all Wip and Publish files fast
        wip_paths = glob.glob(os.path.join(root, "*", "*", "*", "WIP", "*conflict*"), recursive=False)
        pub_paths = glob.glob(os.path.join(root, "*", "*", "*", "Publish", "*conflicts*"), recursive=False)
        task_paths = glob.glob(os.path.join(root, "*", "*", "*", "*conflicts*"), recursive=False)
        conflicts_paths = wip_paths + pub_paths + task_paths

        if not conflicts_paths:
            return True

        conflicts = conflicts_paths

        if not conflicts:
            QtWidgets.QMessageBox.information(self, "No Conflicts", "✅ No duplicate file names found.")
            return

        # --- Scrollable dialog for conflicts ---
        def show_conflicts_dialog(conflicts):
            dialog = QtWidgets.QDialog(self)
            dialog.setWindowTitle("Conflicts File Names Found")
            layout = QtWidgets.QVBoxLayout(dialog)

            # Scrollable text area
            text_edit = QtWidgets.QPlainTextEdit(dialog)
            text_edit.setReadOnly(True)
            msg_text = "⚠ Found conflicting file names:\n\n"
            for name in conflicts:
                msg_text += f"• {name}\n"
            text_edit.setPlainText(msg_text)
            layout.addWidget(text_edit)

            # Yes / No buttons
            buttons = QtWidgets.QDialogButtonBox(
                QtWidgets.QDialogButtonBox.Yes | QtWidgets.QDialogButtonBox.No,
                parent=dialog
            )
            layout.addWidget(buttons)
            buttons.accepted.connect(dialog.accept)
            buttons.rejected.connect(dialog.reject)

            # Fixed reasonable size
            dialog.resize(600, 400)

            return dialog.exec_() == QtWidgets.QDialog.Accepted

        # Ask user for confirmation
        if show_conflicts_dialog(conflicts):
            failed = []
            for path in conflicts:
                try:
                    os.remove(path)
                except Exception:
                    failed.append(path)

            if failed:
                QtWidgets.QMessageBox.critical(
                    self,
                    "Permission Error",
                    "Some files could not be deleted.\n"
                    "Try reopening Maya as Administrator.\n\n"
                    "Failed files:\n" + "\n".join(failed[:10]) +
                    ("\n...and more" if len(failed) > 10 else "")
                )
            else:
                QtWidgets.QMessageBox.information(
                    self,
                    "Deletion Complete",
                    "🗑️ All conflicting files were deleted successfully."
                )

    #----------------------------------------------------------
    #-----------------------Folder Struct----------------------
    #----------------------------------------------------------

    def update_window_title(self):
        parts = []

        if self.current_show:
            parts.append(self.current_show)

        if self.current_asset:
            parts.append(self.current_asset)

        if hasattr(self, "current_task") and self.current_task:
            parts.append(self.current_task)

        new_title = "/".join(parts) if parts else ''
        self.setWindowTitle(new_title)
        self.set_title(new_title)
        self.where_to_save_files = new_title

    def set_blue_buttons(self):
        buttons = [
            self.ui.settings_button,
            self.ui.add_show_button,
            self.ui.add_asset_button,
            self.ui.add_task_button,
            self.ui.save_wip_button,
            self.ui.publish_button
        ]

        for btn in buttons:
            btn.setObjectName("BlueButton")
            btn.style().unpolish(btn)
            btn.style().polish(btn)

    def get_default_json_path(self):
        """
        Get the default path to the blue_pipeline JSON configuration file.

        Returns:
            str: The full path to the "blue_pipeline.json" file located in the user's Maya scripts directory.
        """
        scripts_folder = cmds.internalVar(userScriptDir=True)
        return os.path.join(scripts_folder, "blue_pipeline.json")

    def check_settings_json(self):
        """
        Check if the JSON settings file exists and contains the 'asset_manager' key.

        If the JSON file does not exist, it creates a new one with 'asset_manager' set to None.
        If the file exists but lacks the 'asset_manager' key, it adds the key with a None value.

        Returns:
            dict: The JSON data loaded from the file, guaranteed to have the 'asset_manager' key.
        """
        json_path = self.get_default_json_path()
        if os.path.exists(json_path):
            with open(json_path, 'r') as f:
                data = json.load(f)
            try:
                data['asset_manager']
                return data
            except:
                data["asset_manager"] = None
                with open(json_path, 'w') as f:
                    json.dump(data, f, indent=4)
                return data

        #If doesnt exists create new one
        print(f"JSON file does not exist, creating: {json_path}")
        data = {}
        data["asset_manager"] = None
        print("Added 'asset_manager': None to JSON.")

        # Save the updated data back to the file
        with open(json_path, 'w') as f:
            json.dump(data, f, indent=4)

        return data


    def check_if_project_exists(self):
        """
        Verify if a project folder is set in the 'asset_manager' key within the JSON settings.

        If 'asset_manager' is None or missing, prompt the user to select a project folder
        via a folder dialog. Updates the JSON file with the selected folder path.

        Returns:
            str or None: The path to the project folder if set or selected, otherwise None.
        """
        json_path = self.get_default_json_path()
        json_data = self.check_settings_json()

        # Check asset_manager key
        asset_manager = json_data.get("asset_manager", None)
        if asset_manager is None:
            # Ask user for folder
            folder = cmds.fileDialog2(dialogStyle=2, fileMode=3, okCaption='Select Project Folder')
            if folder:
                folder = folder[0]
                json_data["asset_manager"] = folder
                with open(json_path, 'w') as f:
                    json.dump(json_data, f, indent=4)
                print(f"Project folder set to: {folder}")
                return folder
            else:
                print("No folder selected, 'asset_manager' remains None.")
                return folder
        else:
            return asset_manager

    def change_project_folder(self):
        """
        Prompt the user to select a new project folder and update the JSON settings accordingly.

        Opens a folder dialog for the user to select a new project folder. Updates the
        'asset_manager' key in the JSON settings file with the new folder path.

        Returns:
            str or None: The new project folder path if selected, otherwise None.
        """
        json_path = self.get_default_json_path()
        folder = cmds.fileDialog2(dialogStyle=2, fileMode=3, okCaption='Select Project Folder')
        if folder:
            folder = folder[0]
            data = self.check_settings_json()  # <-- load existing json
            data["asset_manager"] = folder
            with open(json_path, 'w') as f:
                json.dump(data, f, indent=4)
            print(f"[INFO] Project folder changed to: {folder}")
            return folder

    def get_shows_folders(self):
        """
        Retrieve lists of show folder names and their full folder names matching the pattern 'b0001_name' inside the project folder.

        Only folders that start with 'b' followed by 4 digits, an underscore, and then the show name
        are included. The first returned list contains only the show name part (the text after the underscore),
        and the second list contains the full folder names matching the pattern.

        Returns:
            tuple:
                list[str]: A list of show folder names extracted from folder names in the project folder
                           (the part after the underscore).
                list[str]: A list of full folder names matching the pattern, including the prefix.
                           Returns two empty lists if the project folder doesn't exist or contains no matching folders.
        """
        pattern = re.compile(r"^b\d{4}_(.+)$", re.IGNORECASE)  # ignore case in case of B0001

        if not os.path.isdir(self.project_folder):
            print(f"Project folder does not exist or is not a folder: {self.project_folder}")
            folder = self.change_project_folder()
            self.project_folder = folder
            self.get_shows_folders()

        folder_names = []
        folder_paths = []
        for item in os.listdir(self.project_folder):
            if not item.startswith('b'):
                continue
            full_path = os.path.join(self.project_folder, item)
            if os.path.isdir(full_path):
                match = pattern.match(item.strip())
                if match:
                    print(item)
                    folder_names.append(match.group(1))
                    folder_paths.append(item)

        return folder_names, folder_paths

    def get_nice_name(self, folder_name):
        """
        Extracts a clean name from a folder name that follows the pattern 'b####_name'.

        Args:
            folder_name (str): A folder name like 'b0001_character_bird'.

        Returns:
            str: A human-readable name like 'Character Bird'.
        """
        pattern = re.compile(r"^b\d{4}_(.+)", re.IGNORECASE)
        match = pattern.match(folder_name)
        if not match:
            return folder_name  # fallback if pattern doesn't match

        raw_name = match.group(1)  # 'character_bird'
        nice_name = raw_name.replace('_', ' ') # 'Character Bird'
        return nice_name

    def on_change_project_clicked(self):
        new_path = self.change_project_folder()
        if new_path:
            self.project_folder = new_path
            self.populate_shows()  # Rebuild UI with new folder

    def get_show_root_from_scene(self, scene_path):
        if not scene_path:
            return None

        scene_path = os.path.abspath(scene_path)

        if self.project_folder:
            project_root = os.path.abspath(self.project_folder)
            try:
                if os.path.commonpath([project_root, scene_path]) == project_root:
                    rel_path = os.path.relpath(scene_path, project_root)
                    show_folder = rel_path.split(os.sep)[0]
                    if re.match(r"^b\d{4}_.+", show_folder, re.IGNORECASE):
                        return os.path.join(project_root, show_folder)
            except ValueError:
                pass

        current_dir = os.path.dirname(scene_path)
        while current_dir and current_dir != os.path.dirname(current_dir):
            workspace_file = os.path.join(current_dir, "workspace.mel")
            if os.path.exists(workspace_file):
                return current_dir
            current_dir = os.path.dirname(current_dir)

        return None

    def ensure_show_workspace(self, show_root):
        if not show_root or not os.path.isdir(show_root):
            return None

        workspace_file = os.path.join(show_root, "workspace.mel")
        if os.path.exists(workspace_file):
            return workspace_file

        workspace_lines = [
            "//Maya 2026 Project Definition\n",
            "workspace -fr \"scene\" \"scenes\";\n",
            "workspace -fr \"images\" \"images\";\n",
            "workspace -fr \"sourceImages\" \"sourceimages\";\n",
            "workspace -fr \"audio\" \"sound\";\n",
            "workspace -fr \"scripts\" \"scripts\";\n",
            "workspace -fr \"diskCache\" \"cache\";\n",
            "workspace -fr \"fileCache\" \"cache\";\n",
            "workspace -fr \"data\" \"data\";\n",
        ]

        with open(workspace_file, "w") as f:
            f.writelines(workspace_lines)

        print(f"[INFO] Created Maya workspace file: {workspace_file}")
        return workspace_file

    def set_project_from_scene(self, scene_path):
        show_root = self.get_show_root_from_scene(scene_path)
        if not show_root:
            print(f"[INFO] Could not resolve show root from scene path: {scene_path}")
            return False

        self.ensure_show_workspace(show_root)

        current_project = cmds.workspace(q=True, rootDirectory=True) or ""

        def _normalize_path(path):
            return os.path.normcase(os.path.normpath(os.path.abspath(path or "")))

        target_norm = _normalize_path(show_root)
        current_norm = _normalize_path(current_project)
        project_was_different = target_norm != current_norm

        maya_project_path = show_root.replace("\\", "/")
        try:
            mel.eval(f'setProject "{maya_project_path}";')
        except Exception:
            try:
                cmds.workspace(maya_project_path, openWorkspace=True)
            except Exception as e:
                cmds.warning(f"Failed to set project to {show_root}: {e}")
                return False

        if project_was_different:
            try:
                cmds.inViewMessage(
                    amg=f"Project has been set to: <hl>{os.path.basename(show_root)}</hl>",
                    pos="botCenter",
                    fade=True,
                    fadeStayTime=2000,
                )
            except Exception:
                pass

        print(f"[INFO] Maya project set to show workspace: {show_root}")
        return True

    #----------------------------------------------------------
    #-----------------------Add To UI -------------------------
    #----------------------------------------------------------
    def split_camel_case(self, name):
        """
        Split CamelCase words like 'CreatureGarage' into 'Creature\nGarage'
        """
        return re.sub(r'(?<=[a-z])(?=[A-Z])', '\n', name)

    def populate_shows(self):

        self.show_buttons = []

        folder_names, folder_paths = self.get_shows_folders()
        layout = self.ui.shows_layout

        #Check NDA mode:
        json_path = self.get_default_json_path()
        # Load or initialize settings
        with open(json_path, "r") as f:
            settings = json.load(f)
        nda_mode = settings.get("nda_mode", False)

        # Clear existing widgets in layout if needed
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()

        def extract_number(name):
            name = os.path.basename(name)
            name = name.split('_')[0]
            name = name.replace('b', '')
            print('Num', name)
            return int(name)

        combined = sorted(zip(folder_paths, folder_names), key=lambda x: extract_number(x[0]))

        for path, name in combined:
            print(name, path)
            pretty_label = self.split_camel_case(name)
            if nda_mode:
                pretty_label = f"{pretty_label[0]}*****{pretty_label[-1]}"

            button = QtWidgets.QPushButton(pretty_label)
            button._show_name = name.lower()  # searchable name
            button._show_path = path  # full folder

            button.setObjectName("BlueButton")
            button.setFixedSize(80, 40)
            if not nda_mode:
                button.setToolTip(f"{name}: {path}")

            # Use partial to bind 'path' without worrying about 'checked' arg
            button.clicked.connect(partial(self.populate_assets, path))

            layout.addWidget(button)
            self.show_buttons.append(button)

        self.clear_layout(self.ui.wip_layout)
        self.clear_layout(self.ui.publish_layout)
        self.clear_layout(self.ui.assest_layout)
        self.clear_layout(self.ui.tasks_layout)

        return folder_paths

    def set_last_used_show(self, current_show, current_asset=None, current_task=None):
        json_path = self.get_default_json_path()
        data = self.check_settings_json()
        data['last_show'] = current_show
        if current_asset:
            data['last_asset'] = current_asset
        if current_task:
            data['last_task'] = current_task
        with open(json_path, "w") as f:
            json.dump(data, f, indent=4)

    def read_last_used_show(self):
        data = self.check_settings_json()
        return data.get('last_show', None)

    def read_last_used_asset_task(self):
        data = self.check_settings_json()
        last_asset = data.get('last_asset', None)
        last_task = data.get('last_task', None)
        return last_asset, last_task

    def filter_shows(self, text):
        text = text.strip().lower()

        for button in self.show_buttons:
            button.setVisible(not text or text in button._show_name)

        self.ui.shows_layout.invalidate()

    def populate_assets(self, show_path):
        """
        Populate the asset_layout with buttons representing assets inside the given show folder,
        arranged in rows of 4 buttons each.

        Args:
            show_path (str): The folder name of the show inside the project folder.
        """

        self.current_show = show_path
        self.set_last_used_show(self.current_show)

        print(f"Current Show: {show_path}")
        self.clear_layout(self.ui.assest_layout)

        main_layout = self.ui.assest_layout

        # Clear existing widgets/layouts
        while main_layout.count():
            child = main_layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                # Also delete child layouts (important)
                child.layout().deleteLater()

        full_show_path = os.path.join(self.project_folder, show_path)

        if not os.path.isdir(full_show_path):
            print(f"Show path does not exist or is not a directory: {full_show_path}")
            return

        assets = [name for name in os.listdir(full_show_path)
                  if os.path.isdir(os.path.join(full_show_path, name))]

        def sort_key(name):
            match = re.search(r"b(\d{4})_", name, re.IGNORECASE)
            if match:
                return int(match.group(1))
            else:
                return float('inf')  # Push to end

        assets.sort(key=sort_key)

        row_layout = None
        buttons_in_row = 0
        max_per_row = 4

        for i, asset_name in enumerate(assets):
            if buttons_in_row == 0:
                # Create a new horizontal layout for the row
                row_layout = QtWidgets.QHBoxLayout()
                # Add some spacing between buttons if you want
                row_layout.setSpacing(10)
                main_layout.addLayout(row_layout)

            # Asset full path and image
            asset_full_path = os.path.join(full_show_path, asset_name)
            image_path = os.path.join(full_show_path, f"{asset_name}.png")

            # Container widget
            container = QtWidgets.QWidget()
            v_layout = QtWidgets.QVBoxLayout(container)
            v_layout.setContentsMargins(0, 0, 0, 0)
            v_layout.setSpacing(4)

            # Image button
            if os.path.exists(image_path):
                button = ImportButton("", asset_full_path, parent=self)
                icon = QtGui.QIcon(image_path)
                button.setIcon(icon)
                button.setIconSize(QtCore.QSize(64, 64))
            else:
                button = ImportButton(self.get_nice_name(asset_name), asset_full_path, parent=self)

            button.setFixedSize(80, 80)
            button.setToolTip(asset_name)
            button.setObjectName("BlueButton")
            button.clicked.connect(partial(self.populate_tasks, show_path, asset_name))

            # Label
            label = QtWidgets.QLabel(self.get_nice_name(asset_name))
            label.setAlignment(QtCore.Qt.AlignCenter)
            label.setStyleSheet("font-size: 10px;")
            label.setFixedWidth(80)
            label.setWordWrap(True)

            # Add button and label to layout
            v_layout.addWidget(button)
            v_layout.addWidget(label)

            # Add container to row
            row_layout.addWidget(container)
            buttons_in_row += 1

            if buttons_in_row == max_per_row:
                buttons_in_row = 0  # Reset for next row

        # Optional: if last row has fewer than max_per_row buttons, add stretch to right-align them
        if buttons_in_row > 0:
            row_layout.addStretch()

        self.clear_layout(self.ui.wip_layout)
        self.clear_layout(self.ui.publish_layout)
        self.clear_layout(self.ui.tasks_layout)

        self.current_asset = None
        self.current_task = None
        self.update_window_title()

        # Auto-populate last asset if exists
        last_asset, last_task = self.read_last_used_asset_task()
        if last_asset in assets:
            self.populate_tasks(self.current_show, last_asset)
            if last_task:
                self.populate_files(self.current_show, last_asset, last_task)

        return assets

    def populate_tasks(self, show_path, asset_name):
        """
        Populates self.ui.tasks_layout with one button per task found in the given asset folder.

        Args:
            show_path (str): The folder name of the show inside the project folder (e.g. 'b0001_myshow').
            asset_name (str): The name of the asset folder (e.g. 'character_A').
        """
        layout = self.ui.tasks_layout
        self.current_asset = asset_name
        self.current_asset = asset_name
        # Save the last asset
        self.set_last_used_show(self.current_show, current_asset=self.current_asset)

        # Clear previous buttons
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                child.layout().deleteLater()

        # Full path to the asset folder
        asset_path = os.path.join(self.project_folder, show_path, asset_name)

        if not os.path.isdir(asset_path):
            print(f"Asset path does not exist: {asset_path}")
            return

        # Get all task folders
        task_names = [name for name in os.listdir(asset_path)
                      if os.path.isdir(os.path.join(asset_path, name))]

        for task_name in task_names:
            task_path = os.path.join(asset_path, task_name)

            button = ImportButton(self.get_nice_name(task_name), task_path, parent=self)
            button.setFixedSize(80, 40)
            button.setObjectName("BlueButton")
            button.clicked.connect(partial(self.populate_files, show_path, asset_name, task_name))

            layout.addWidget(button)

        self.clear_layout(self.ui.wip_layout)
        self.clear_layout(self.ui.publish_layout)

        self.current_task = None
        self.update_window_title()

    def populate_files(self, show_path, asset_name, task_name):
        """
        Display files in the WIP and Publish folders under the given task.

        Args:
            show_path (str): Show folder name.
            asset_name (str): Asset folder name.
            task_name (str): Task folder name.
        """
        self.current_task = task_name
        # Save last task as well
        self.set_last_used_show(self.current_show, current_asset=self.current_asset, current_task=self.current_task)

        # Clear previous file buttons
        for layout in [self.ui.wip_layout, self.ui.publish_layout]:
            self.clear_layout(layout)

        # Define base path
        task_path = os.path.join(self.project_folder, show_path, asset_name, task_name)

        # Check if "scenes" folder exists under task_path
        scenes_path = os.path.join(task_path, "scenes")
        if os.path.isdir(scenes_path):
            # If it exists, adjust paths
            wip_path = os.path.join(scenes_path, "WIP")
            pub_path = os.path.join(scenes_path, "Publish")
        else:
            # If not, use direct paths
            wip_path = os.path.join(task_path, "WIP")
            pub_path = os.path.join(task_path, "Publish")

        def populate(layout, folder):
            self.clear_layout(layout)
            if not os.path.exists(folder):
                print(f"Folder does not exist: {folder}")
                return

            files = [f for f in os.listdir(folder) if os.path.isfile(os.path.join(folder, f))]
            files = [f for f in files if f.endswith(('.ma', '.mb', '.py', '.mel', '.fbx', '.abc'))]
            files.sort(reverse=True)

            for f in files:
                if f.startswith('.'):
                    continue

                full_path = os.path.join(folder, f)
                json_path = os.path.splitext(full_path)[0] + ".json"
                has_mutant_build = get_mutant_build_flag_from_query(full_path)

                tooltip_text = ""
                if os.path.exists(json_path):
                    try:
                        with open(json_path, "r") as jf:
                            data = json.load(jf)
                            tooltip_lines = [f"{key}: {value}" for key, value in data.items()]
                            tooltip_text = "\n".join(tooltip_lines)
                    except Exception as e:
                        tooltip_text = f"Error reading JSON: {e}"

                row = QtWidgets.QVBoxLayout()

                label = QtWidgets.QLabel(f)
                label_color = "#ff9f1a" if has_mutant_build else "white"
                label.setStyleSheet(f"font-size: 12px; font-weight: bold; color: {label_color};")
                label.setWordWrap(True)
                if has_mutant_build:
                    tooltip_text = (tooltip_text + "\n" if tooltip_text else "") + "Mutant Build: True"
                if tooltip_text:
                    label.setToolTip(tooltip_text)

                row.addWidget(label)

                # Show script contents for .py or .mel
                if f.endswith((".py", ".mel")):
                    try:
                        with open(full_path, "r") as script_file:
                            script_text = script_file.read()
                    except Exception as e:
                        script_text = f"Could not read file: {e}"

                    text_edit = QtWidgets.QTextEdit()
                    text_edit.setPlainText(script_text)
                    text_edit.setReadOnly(True)
                    text_edit.setFixedHeight(150)  # Adjust as needed
                    text_edit.setStyleSheet("font-size: 8px;")
                    text_edit.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOn)
                    row.addWidget(text_edit)
                else:
                    # Default Maya file handling → three buttons (Open, Import, Reference and settings)
                    btn_row = QtWidgets.QHBoxLayout()
                    btn_row.addStretch()

                    def create_icon_button(icon, tooltip, callback, size=(30, 30)):
                        btn = QtWidgets.QPushButton()
                        btn.setIcon(QtGui.QIcon(os.path.join(IconsPath, icon)))
                        btn.setIconSize(QtCore.QSize(size[0]/1.5, size[0]/1.5))
                        btn.setToolTip(tooltip)
                        btn.setFixedSize(*size)
                        btn.setObjectName("BlueButton")
                        btn.clicked.connect(callback)
                        return btn

                    # Open button
                    open_btn = create_icon_button(
                        "open.png", "Open", partial(self.open_maya_scene, full_path)
                    )
                    btn_row.addWidget(open_btn)

                    # Import button
                    import_btn = create_icon_button(
                        "import.png", "Import", partial(self.import_maya_scene, full_path)
                    )
                    btn_row.addWidget(import_btn)

                    # Reference button
                    ref_btn = create_icon_button(
                        "reference.png", "Reference", partial(self.reference_maya_scene, full_path)
                    )
                    btn_row.addWidget(ref_btn)

                    '''
                    if 'rig' in self.current_task.lower():
                        # Settings button
                        # Button function at the end of file
                        settings_btn = create_icon_button(
                            "settings.png", "Settings", partial(open_settings, full_path)
                        )
                        btn_row.addWidget(settings_btn)
                    '''

                    row.addLayout(btn_row)

                layout.addLayout(row)

        # Populate both layouts
        populate(self.ui.wip_layout, wip_path)
        if self.current_task.lower() == 'scripts':
            populate(self.ui.wip_layout, os.path.join(task_path))
        populate(self.ui.publish_layout, pub_path)

        self.update_window_title()

    def clear_layout(self, layout):
        while layout.count():
            child = layout.takeAt(0)
            if child.widget():
                child.widget().deleteLater()
            elif child.layout():
                self.clear_layout(child.layout())  # recursive clear child layouts
                child.layout().deleteLater()

    def import_maya_scene(self, file_path):
        try:
            file_path = file_path.replace("\\", "/")
            self.set_project_from_scene(file_path)
            cmds.file(file_path, i=True, ignoreVersion=True, ra=True, mergeNamespacesOnClash=False, namespace=":")
            print(f"Imported: {file_path}")
        except Exception as e:
            cmds.warning(f"Failed to import {file_path}: {e}")

    def reference_maya_scene(self, file_path):
        try:
            file_path = file_path.replace("\\", "/")
            self.set_project_from_scene(file_path)
            cmds.file(file_path, r=True, ignoreVersion=True, gl=True, mergeNamespacesOnClash=False,
                      namespace=os.path.splitext(os.path.basename(file_path))[0])
            print(f"Referenced: {file_path}")
        except Exception as e:
            cmds.warning(f"Failed to reference {file_path}: {e}")


    def open_maya_scene(self, file_path):
        """Safely opens a Maya scene, prompting to save if there are unsaved changes."""
        print(file_path)
        if not os.path.exists(file_path):
            print(f"[ERROR] File does not exist: {file_path}")
            return

        # Check for unsaved changes
        if cmds.file(q=True, modified=True):
            response = cmds.confirmDialog(
                title='Unsaved Changes',
                message='You have unsaved changes. What would you like to do?',
                button=['Save', "Don't Save", 'Cancel'],
                defaultButton='Save',
                cancelButton='Cancel',
                dismissString='Cancel'
            )

            if response == 'Cancel':
                print("[INFO] Open scene cancelled by user.")
                return

            elif response == 'Save':
                try:
                    cmds.file(save=True)
                except Exception as e:
                    print(f"[ERROR] Failed to save current scene: {e}")
                    return
        # If 'Don't Save' is selected, just continue

        self.set_project_from_scene(file_path)

        # Use MEL to open and add to recent files
        file_path = file_path.replace("\\", "/")
        mel_cmd = (
            f'file -f -options "v=0;" -ignoreVersion -typ "mayaAscii" -o "{file_path}";'
            f'if (!`file -q -errorStatus`) {{ addRecentFile("{file_path}", "mayaAscii"); }}'
        )
        mel.eval(mel_cmd)

    def reference_maya_scene(self, file_path):
        """References the Maya scene at the given path."""
        if os.path.exists(file_path):
            self.set_project_from_scene(file_path)
            cmds.file(file_path, reference=True, namespace=os.path.splitext(os.path.basename(file_path))[0])
        else:
            print(f"[ERROR] File does not exist: {file_path}")

    def open_folder_location(self, file_path):
        """Opens the folder that contains the given file path."""
        folder_path = os.path.dirname(file_path)
        if os.path.exists(folder_path):
            if os.name == "nt":  # Windows
                os.startfile(folder_path)
            elif os.name == "posix":  # macOS or Linux
                subprocess.Popen(["open", folder_path])  # use "xdg-open" for Linux
        else:
            print(f"[ERROR] Folder does not exist: {folder_path}")

        # -------------------------------------------------------------------
        # -------------------------------------------------------------------
        # -------------------------------------------------------------------

    def create_new_show(self):
        """
        Prompts the user for a show name and creates a new show folder
        in the project directory with a unique 'b####_' prefix.
        """
        if not self.project_folder or not os.path.isdir(self.project_folder):
            cmds.warning("Invalid project folder. Please set a valid project path first.")
            return

        # Prompt for show name
        name, ok = QtWidgets.QInputDialog.getText(self, "New Show", "Enter show name:")
        if not ok or not name.strip():
            return

        name = name.strip().replace(" ", "_")  # Clean up input
        existing = [f for f in os.listdir(self.project_folder) if
                    os.path.isdir(os.path.join(self.project_folder, f))]

        # Find the next index
        numbers = []
        pattern = re.compile(r"^b(\d{4})_", re.IGNORECASE)
        for folder in existing:
            match = pattern.match(folder)
            if match:
                numbers.append(int(match.group(1)))

        next_num = max(numbers) + 1 if numbers else 1
        new_folder_name = f"b{next_num:04d}_{name}"
        new_folder_path = os.path.join(self.project_folder, new_folder_name)

        # Create folder
        try:
            os.makedirs(new_folder_path)
            self.ensure_show_workspace(new_folder_path)
            print(f"[INFO] Created new show: {new_folder_path}")
            self.populate_shows()  # Refresh the UI
        except Exception as e:
            cmds.warning(f"Failed to create show folder: {e}")

    def create_new_asset(self):
        """
        Prompts the user for an asset name and creates a new asset folder
        inside the currently selected show folder. If the asset already exists,
        offers to update its screenshot.
        """
        if not self.current_show:
            cmds.warning("Please select a show first.")
            return

        self.current_show_path = self.current_show
        show_full_path = os.path.join(self.project_folder, self.current_show_path)
        if not os.path.isdir(show_full_path):
            cmds.warning(f"Show folder does not exist: {show_full_path}")
            return

        # Prompt for asset name
        name, ok = QtWidgets.QInputDialog.getText(self, "New Asset", "Enter asset name:")
        if not ok or not name.strip():
            return

        name = name.strip().replace(" ", "_")  # Clean name

        # List existing assets
        existing = [f for f in os.listdir(show_full_path) if os.path.isdir(os.path.join(show_full_path, f))]

        # Check if asset with name exists
        existing_asset_folder = None
        pattern = re.compile(r"^(b\d{4})_" + re.escape(name) + r"$", re.IGNORECASE)
        for folder in existing:
            if pattern.match(folder):
                existing_asset_folder = folder
                break

        if existing_asset_folder:
            # Asset exists, ask to update screenshot
            reply = QtWidgets.QMessageBox.question(
                self,
                "Asset Exists",
                f"The asset '{existing_asset_folder}' already exists.\nDo you want to update its screenshot?",
                QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No
            )

            if reply == QtWidgets.QMessageBox.Yes:
                self.capture_asset_screenshot(self.current_show_path, existing_asset_folder)
            else:
                print("[INFO] User chose not to update the screenshot.")
            return

        # Asset doesn't exist → create it
        numbers = []
        pattern = re.compile(r"^b(\d{4})_", re.IGNORECASE)
        for folder in existing:
            match = pattern.match(folder)
            if match:
                numbers.append(int(match.group(1)))

        next_num = max(numbers) + 1 if numbers else 1
        new_asset_folder = f"b{next_num:04d}_{name}"
        new_asset_path = os.path.join(show_full_path, new_asset_folder)

        try:
            os.makedirs(new_asset_path)
            self.capture_asset_screenshot(self.current_show_path, new_asset_folder)
            print(f"[INFO] Created new asset: {new_asset_path}")
            self.populate_assets(self.current_show_path)
        except Exception as e:
            cmds.warning(f"Failed to create asset folder: {e}")

    def capture_asset_screenshot(self, show_path, asset_name):
        """
        Takes a 512x512 screenshot using playblast and saves it as a clean PNG
        named 'asset_name.png' in the correct asset folder.
        """
        import shutil
        try:
            cmds.setAttr("Global_Ctrl.CtrlPlayback", 0)
        except Exception:
            pass


        asset_folder = os.path.join(self.project_folder, show_path)
        if not os.path.isdir(asset_folder):
            cmds.warning(f"Asset folder does not exist: {asset_folder}")
            return

        final_path = os.path.join(asset_folder, f"{asset_name}.png")

        # Use a temporary file base name with NO dots
        temp_base = os.path.join(asset_folder, "__temp_screenshot")

        # Run playblast
        cmds.playblast(
            format='image',
            filename=temp_base,
            forceOverwrite=True,
            showOrnaments=False,
            startTime=cmds.currentTime(query=True),
            endTime=cmds.currentTime(query=True),
            viewer=False,
            offScreen=True,
            framePadding=0,
            widthHeight=(2048, 2048),
            percent=100,
            sequenceTime=False,
            compression='png'
        )

        # Maya appends frame number → find it: __temp_screenshot.1.png
        temp_pattern = temp_base + ".*.png"
        matches = glob.glob(temp_pattern)

        if not matches:
            cmds.warning(f"[ERROR] Could not locate screenshot after playblast.")
            return

        temp_screenshot = matches[0]

        try:
            if os.path.exists(final_path):
                os.remove(final_path)
            shutil.move(temp_screenshot, final_path)
            print(f"[INFO] Screenshot saved: {final_path}")
        except Exception as e:
            cmds.warning(f"Failed to save screenshot: {e}")

    def create_new_task(self):
        if not self.current_show:
            cmds.warning("Please select a show first.")
            return

        # Get selected asset from current layout (assumes last populated asset is selected)
        asset_layout = self.ui.tasks_layout

        # Prompt for task names
        text, ok = QtWidgets.QInputDialog.getText(
            self,
            "Create Task(s)",
            "Enter task name(s) (comma-separated):",
            QtWidgets.QLineEdit.Normal,
            "Model, Rig"  # Default value
        )
        if not ok or not text.strip():
            return

        task_names = [t.strip() for t in text.split(",") if t.strip()]
        if not task_names:
            task_names = ["Model", "Rig"]  # Default tasks

        # Always include model and rig if no input or empty input
        if len(task_names) == 0:
            task_names = ["Model", "Rig"]

        # Paths
        show_path = os.path.join(self.project_folder, self.current_show)
        assets = [name for name in os.listdir(show_path) if os.path.isdir(os.path.join(show_path, name))]

        # Detect selected asset
        asset_widget = self.sender()
        if not asset_widget:
            cmds.warning("No asset selected.")
            return

        # This logic assumes only one asset is selected at a time and last populated asset is current
        # You might want to track selected asset in a variable instead
        selected_asset = getattr(self, "current_asset", None)
        if not selected_asset:
            cmds.warning("Asset not selected.")
            return

        asset_path = os.path.join(show_path, selected_asset)

        for task in task_names:
            task_path = os.path.join(asset_path, task)
            if not os.path.exists(task_path):
                os.makedirs(os.path.join(task_path, "WIP"))
                os.makedirs(os.path.join(task_path, "Publish"))
                print(f"[INFO] Created task: {task_path}")
            else:
                print(f"[INFO] Task already exists: {task_path}")

        self.populate_tasks(self.current_show, selected_asset)

    #----------------------------------------------------------------
    # ---------------------------------------------------------------
    # ---------------------Wip and Publish---------------------------
    def save_wip(self):
        import Blue_Pipeline
        from Blue_Pipeline.UI.assets_manager import load_save_wip
        reload(load_save_wip)

        full_save_path = os.path.join(self.project_folder, self.where_to_save_files)

        cSaveWIP = load_save_wip.SaveWIP(save_path=full_save_path, asset_name=self.current_asset, mode='WIP')
        cSaveWIP.setWindowModality(QtCore.Qt.ApplicationModal)
        cSaveWIP.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.WindowTitleHint | QtCore.Qt.CustomizeWindowHint)
        cSaveWIP.show()

    def publish_asset(self):
        import Blue_Pipeline
        from Blue_Pipeline.UI.assets_manager import load_publish_asset
        reload(load_publish_asset)

        full_save_path = os.path.join(self.project_folder, self.where_to_save_files)

        cSaveWIP = load_publish_asset.PublishAsset(save_path=full_save_path, asset_name=self.current_asset, mode='Publish')
        cSaveWIP.setWindowModality(QtCore.Qt.ApplicationModal)
        cSaveWIP.setWindowFlags(QtCore.Qt.Dialog | QtCore.Qt.WindowTitleHint | QtCore.Qt.CustomizeWindowHint)
        cSaveWIP.show()


    # CLOSE EVENTS _________________________________
    def closeEvent(self, event):
        self.unregister_scene_opened_callback()
        super(AssetsManagerUI, self).closeEvent(event)


# -------------------------------------------------------------------

if __name__ == "__main__":

    try:
        cAssetsManagerUI.close()  # pylint: disable=E0601
        cAssetsManagerUI.deleteLater()
    except:
        pass
    cAssetsManagerUI = AssetsManagerUI()
    cAssetsManagerUI.show()

#----------------------------------------

class ImportButton(QtWidgets.QPushButton):
    def __init__(self, label, file_path, parent=None):
        super().__init__(label, parent)
        self.file_path = file_path
        self.setFixedSize(30, 30)
        self.setObjectName("BlueButton")

        self.preview_widget = None
        self.preview_timer = QtCore.QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.timeout.connect(self.show_preview)

    def mousePressEvent(self, event):
        if event.button() == QtCore.Qt.RightButton:
            self.open_folder_location()
        else:
            # Let Qt handle left and other clicks (e.g., emit clicked)
            super().mousePressEvent(event)

    def enterEvent(self, event):
        # Start 4-second timer
        self.preview_timer.start(2000)
        super().enterEvent(event)

    def leaveEvent(self, event):
        # Cancel the preview if leaving early
        self.preview_timer.stop()
        if self.preview_widget:
            self.preview_widget.close()
            self.preview_widget = None
        super().leaveEvent(event)

    def show_preview(self):
        image_path = self.file_path + ".png"
        if os.path.exists(image_path):
            self.preview_widget = ImagePreview(image_path)
            cursor_pos = QtGui.QCursor.pos()
            self.preview_widget.move(cursor_pos + QtCore.QPoint(20, 20))
            self.preview_widget.show()

    def open_maya_scene(self):
        self.parent().open_maya_scene(self.file_path)

    def open_folder_location(self):
        folder_path = os.path.dirname(self.file_path)
        if os.path.exists(folder_path):
            if os.name == "nt":
                os.startfile(folder_path)
            elif os.name == "posix":
                subprocess.Popen(["open", folder_path])
        else:
            print(f"[ERROR] Folder does not exist: {folder_path}")

class ImagePreview(QtWidgets.QLabel):
    def __init__(self, image_path, parent=None):
        super().__init__(parent, QtCore.Qt.ToolTip)
        self.setWindowFlags(QtCore.Qt.ToolTip)
        self.setAttribute(QtCore.Qt.WA_TransparentForMouseEvents)
        self.setScaledContents(True)

        pixmap = QtGui.QPixmap(image_path)
        if not pixmap.isNull():
            screen = QtWidgets.QApplication.primaryScreen()
            screen_size = screen.size()
            scale_factor = 0.75  # or 0.4 for 40%
            scale_width = int(screen_size.width() * scale_factor)
            scale_height = int(screen_size.height() * scale_factor)
            pixmap = pixmap.scaled(scale_width, scale_height, QtCore.Qt.KeepAspectRatio, QtCore.Qt.SmoothTransformation)

            self.setPixmap(pixmap)
            self.setFixedSize(pixmap.size())  # fix label size to pixmap size


class VersionDeleteDialog(QtWidgets.QDialog):
    VALID_EXTENSIONS = ('.ma', '.mb', '.py', '.mel', '.fbx', '.abc')
    SHOW_FOLDER_PATTERN = re.compile(r"^b\d{4}_.+", re.IGNORECASE)

    def __init__(self, project_folder, parent=None):
        super(VersionDeleteDialog, self).__init__(parent)
        self.project_folder = os.path.abspath(project_folder)
        self.setWindowTitle("Version Delete")
        self.resize(1300, 760)

        self.show_tabs = QtWidgets.QTabWidget(self)
        self.show_tabs.setTabPosition(QtWidgets.QTabWidget.North)
        self._all_tables = []

        self.info_label = QtWidgets.QLabel(
            "Orange = Has Build Data | Green = Latest in each WIP/Publish folder"
        )

        self.refresh_btn = QtWidgets.QPushButton("Refresh")
        self.delete_btn = QtWidgets.QPushButton("Delete Selected")
        self.close_btn = QtWidgets.QPushButton("Close")
        self.refresh_btn.setObjectName("BlueButton")
        self.delete_btn.setObjectName("BlueButton")
        self.close_btn.setObjectName("BlueButton")

        btn_row = QtWidgets.QHBoxLayout()
        btn_row.addWidget(self.refresh_btn)
        btn_row.addStretch()
        btn_row.addWidget(self.delete_btn)
        btn_row.addWidget(self.close_btn)

        main_layout = QtWidgets.QVBoxLayout(self)
        main_layout.addWidget(self.info_label)
        main_layout.addWidget(self.show_tabs)
        main_layout.addLayout(btn_row)

        self.refresh_btn.clicked.connect(self.refresh_table)
        self.delete_btn.clicked.connect(self.delete_selected_files)
        self.close_btn.clicked.connect(self.close)

        self.refresh_table()

    def set_project_folder(self, project_folder):
        self.project_folder = os.path.abspath(project_folder)
        self.refresh_table()

    def _ensure_build_data_loaded(self):
        query_json = os.path.join(self.project_folder, "Build_Data.json")
        if os.path.exists(query_json):
            load_mutant_build_query_data(query_json_path=query_json)

    def _has_build_data(self, file_path):
        if not BUILD_DATA_QUERY_ENABLED or not BUILD_DATA_QUERY_ROOT:
            return False

        abs_file_path = os.path.normcase(os.path.normpath(os.path.abspath(file_path)))
        abs_root_path = os.path.normcase(os.path.normpath(os.path.abspath(BUILD_DATA_QUERY_ROOT)))

        try:
            if os.path.commonpath([abs_root_path, abs_file_path]) != abs_root_path:
                return False
        except ValueError:
            return False

        rel_path = os.path.relpath(abs_file_path, abs_root_path).replace("\\", "/").lower()
        return bool(BUILD_DATA_QUERY_FILES.get(rel_path, False))

    def _collect_files(self):
        grouped = defaultdict(
            lambda: defaultdict(
                lambda: defaultdict(
                    lambda: {"WIP": [], "Publish": []}
                )
            )
        )
        latest_per_folder = {}

        if not os.path.isdir(self.project_folder):
            return grouped, latest_per_folder

        show_folders = [
            name for name in os.listdir(self.project_folder)
            if os.path.isdir(os.path.join(self.project_folder, name))
            and self.SHOW_FOLDER_PATTERN.match(name)
        ]

        for show_name in show_folders:
            show_path = os.path.join(self.project_folder, show_name)
            for root, _, files in os.walk(show_path):
                section = os.path.basename(root)
                section_lower = section.lower()
                if section_lower not in ("wip", "publish"):
                    continue

                folder_key = os.path.normcase(os.path.normpath(root))
                for file_name in files:
                    if file_name.startswith('.'):
                        continue
                    if not file_name.lower().endswith(self.VALID_EXTENSIONS):
                        continue

                    full_path = os.path.join(root, file_name)
                    try:
                        mtime = os.path.getmtime(full_path)
                    except Exception:
                        continue

                    rel_folder = os.path.relpath(root, show_path).replace("\\", "/")
                    asset_name, task_name = self._extract_asset_task(root, show_path)
                    section_name = "WIP" if section_lower == "wip" else "Publish"

                    row = {
                        "show": show_name,
                        "section": section_name,
                        "task": task_name,
                        "folder": rel_folder,
                        "file": file_name,
                        "date": datetime.fromtimestamp(mtime).strftime("%Y-%m-%d %H:%M:%S"),
                        "mtime": mtime,
                        "path": full_path,
                    }
                    grouped[show_name][asset_name][task_name][section_name].append(row)

                    current_latest = latest_per_folder.get(folder_key)
                    if current_latest is None or mtime > current_latest:
                        latest_per_folder[folder_key] = mtime

        return grouped, latest_per_folder

    def _extract_asset_task(self, section_folder_path, show_path):
        rel = os.path.relpath(section_folder_path, show_path)
        parts = [p for p in rel.replace("\\", "/").split("/") if p]

        if not parts:
            return "_root_asset_", "_root_task_"

        if parts[-1].lower() in ("wip", "publish"):
            parts = parts[:-1]

        if parts and parts[-1].lower() == "scenes":
            parts = parts[:-1]

        if not parts:
            return "_root_asset_", "_root_task_"

        asset_name = parts[0]
        task_name = "/".join(parts[1:]) if len(parts) > 1 else "_root_task_"
        return asset_name, task_name

    def _create_section_table(self):
        table = QtWidgets.QTableWidget(self)
        table.setColumnCount(5)
        table.setHorizontalHeaderLabels(["Select", "Folder", "File", "Date", "Path"])
        table.setSelectionBehavior(QtWidgets.QAbstractItemView.SelectRows)
        table.setSelectionMode(QtWidgets.QAbstractItemView.ExtendedSelection)
        table.setEditTriggers(QtWidgets.QAbstractItemView.NoEditTriggers)
        table.verticalHeader().setVisible(False)
        table.horizontalHeader().setStretchLastSection(True)
        table.setSortingEnabled(False)
        table.setContextMenuPolicy(QtCore.Qt.CustomContextMenu)
        table.customContextMenuRequested.connect(lambda pos, t=table: self._show_table_context_menu(t, pos))
        return table

    def _show_table_context_menu(self, table, position):
        index = table.indexAt(position)
        if not index.isValid():
            return

        row = index.row()
        path_item = table.item(row, 4)
        if not path_item:
            return

        file_path = path_item.text()
        if not file_path:
            return

        menu = QtWidgets.QMenu(table)
        open_file_action = menu.addAction("Open File")
        open_folder_action = menu.addAction("Open Folder")

        action = menu.exec_(table.viewport().mapToGlobal(position))
        if action == open_file_action:
            self._open_file(file_path)
        elif action == open_folder_action:
            self._open_file_folder(file_path)

    def _open_file(self, file_path):
        if not os.path.exists(file_path):
            QtWidgets.QMessageBox.warning(self, "Open File", f"File not found:\n{file_path}")
            return

        try:
            if os.name == "nt":
                os.startfile(file_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", file_path])
            else:
                subprocess.Popen(["xdg-open", file_path])
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Open File", f"Could not open file:\n{file_path}\n\n{exc}")

    def _open_file_folder(self, file_path):
        folder_path = os.path.dirname(file_path)
        if not os.path.isdir(folder_path):
            QtWidgets.QMessageBox.warning(self, "Open Folder", f"Folder not found:\n{folder_path}")
            return

        try:
            if os.name == "nt":
                os.startfile(folder_path)
            elif sys.platform == "darwin":
                subprocess.Popen(["open", folder_path])
            else:
                subprocess.Popen(["xdg-open", folder_path])
        except Exception as exc:
            QtWidgets.QMessageBox.warning(self, "Open Folder", f"Could not open folder:\n{folder_path}\n\n{exc}")

    def _populate_section_table(self, table, rows, latest_per_folder):
        table.setRowCount(0)
        rows = sorted(rows, key=lambda x: x["mtime"], reverse=True)

        orange = QtGui.QColor(255, 159, 26)
        green = QtGui.QColor(0, 220, 120)

        for row_data in rows:
            row_index = table.rowCount()
            table.insertRow(row_index)

            select_item = QtWidgets.QTableWidgetItem()
            select_item.setFlags(QtCore.Qt.ItemIsEnabled | QtCore.Qt.ItemIsUserCheckable | QtCore.Qt.ItemIsSelectable)
            select_item.setCheckState(QtCore.Qt.Unchecked)

            folder_item = QtWidgets.QTableWidgetItem(row_data["folder"])
            file_item = QtWidgets.QTableWidgetItem(row_data["file"])
            date_item = QtWidgets.QTableWidgetItem(row_data["date"])
            path_item = QtWidgets.QTableWidgetItem(row_data["path"])

            table.setItem(row_index, 0, select_item)
            table.setItem(row_index, 1, folder_item)
            table.setItem(row_index, 2, file_item)
            table.setItem(row_index, 3, date_item)
            table.setItem(row_index, 4, path_item)

            folder_abs = os.path.normcase(os.path.normpath(os.path.dirname(row_data["path"])))
            is_latest = row_data["mtime"] == latest_per_folder.get(folder_abs)
            has_build_data = self._has_build_data(row_data["path"])

            if has_build_data:
                color = orange
            elif is_latest:
                color = green
            else:
                color = None

            if color:
                for col in range(1, 5):
                    item = table.item(row_index, col)
                    if item:
                        item.setForeground(QtGui.QBrush(color))

        table.resizeColumnsToContents()
        table.setColumnWidth(0, 60)

    def _clear_show_tabs(self):
        self.show_tabs.clear()
        self._all_tables = []

    def refresh_table(self):
        self._ensure_build_data_loaded()
        grouped, latest_per_folder = self._collect_files()

        self._clear_show_tabs()

        for show_name in sorted(grouped.keys()):
            asset_tabs = QtWidgets.QTabWidget(self)
            asset_tabs.setTabPosition(QtWidgets.QTabWidget.North)
            assets_data = grouped[show_name]

            for asset_name in sorted(assets_data.keys()):
                task_tabs = QtWidgets.QTabWidget(self)
                task_tabs.setTabPosition(QtWidgets.QTabWidget.North)
                tasks_data = assets_data[asset_name]

                for task_name in sorted(tasks_data.keys()):
                    task_widget = QtWidgets.QWidget(self)
                    task_layout = QtWidgets.QHBoxLayout(task_widget)

                    wip_group = QtWidgets.QGroupBox("WIP", task_widget)
                    pub_group = QtWidgets.QGroupBox("Publish", task_widget)

                    wip_layout = QtWidgets.QVBoxLayout(wip_group)
                    pub_layout = QtWidgets.QVBoxLayout(pub_group)

                    wip_table = self._create_section_table()
                    pub_table = self._create_section_table()

                    wip_layout.addWidget(wip_table)
                    pub_layout.addWidget(pub_table)

                    task_layout.addWidget(wip_group)
                    task_layout.addWidget(pub_group)

                    self._populate_section_table(wip_table, tasks_data[task_name]["WIP"], latest_per_folder)
                    self._populate_section_table(pub_table, tasks_data[task_name]["Publish"], latest_per_folder)

                    self._all_tables.extend([wip_table, pub_table])
                    task_tabs.addTab(task_widget, task_name)

                asset_tabs.addTab(task_tabs, asset_name)

            self.show_tabs.addTab(asset_tabs, show_name)

        if self.show_tabs.count() == 0:
            empty = QtWidgets.QWidget(self)
            empty_layout = QtWidgets.QVBoxLayout(empty)
            empty_layout.addWidget(QtWidgets.QLabel("No WIP/Publish files found in project folder."))
            self.show_tabs.addTab(empty, "No Shows")

    def _get_selected_paths(self):
        paths = []

        for table in self._all_tables:
            for row in range(table.rowCount()):
                check_item = table.item(row, 0)
                path_item = table.item(row, 4)
                if not check_item or not path_item:
                    continue
                if check_item.checkState() == QtCore.Qt.Checked:
                    paths.append(path_item.text())

        if paths:
            return sorted(set(paths))

        for table in self._all_tables:
            selected_rows = table.selectionModel().selectedRows()
            for model_index in selected_rows:
                row = model_index.row()
                path_item = table.item(row, 4)
                if path_item:
                    paths.append(path_item.text())

        return sorted(set(paths))

    def delete_selected_files(self):
        paths = self._get_selected_paths()
        if not paths:
            QtWidgets.QMessageBox.information(self, "Delete Selected", "No files selected.")
            return

        confirm = QtWidgets.QMessageBox.question(
            self,
            "Confirm Delete",
            f"Delete {len(paths)} selected file(s)?\nThis cannot be undone.",
            QtWidgets.QMessageBox.Yes | QtWidgets.QMessageBox.No,
            QtWidgets.QMessageBox.No,
        )
        if confirm != QtWidgets.QMessageBox.Yes:
            return

        deleted = 0
        failed = []
        for path in paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
                    deleted += 1
            except Exception as exc:
                failed.append(f"{path} ({exc})")

        if failed:
            QtWidgets.QMessageBox.warning(
                self,
                "Delete Completed with Errors",
                f"Deleted {deleted} file(s).\nFailed: {len(failed)}\n\n" + "\n".join(failed[:8]),
            )
        else:
            QtWidgets.QMessageBox.information(self, "Delete Completed", f"Deleted {deleted} file(s).")

        self.refresh_table()


def open_settings(path):
    from Blue_Pipeline.UI.assets_manager import load_rig_settings
    reload(load_rig_settings)
    cRigSettingsUI = load_rig_settings.RigSettingsUI(file_path=path)
    cRigSettingsUI.show()


'''
#Notes






'''