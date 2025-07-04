# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import json, importlib
from logging import getLogger

logger = getLogger(__name__)


class ReportPluginManager:
    """
    Manager for dynamically loading and instantiating report plugins.

    This class is responsible for loading report plugin configurations from a JSON file
    and dynamically instantiating the appropriate plugin classes or functions based on
    the requested report type. It uses Python's importlib to dynamically load modules
    and create plugin instances at runtime.
    """

    def __init__(self):
        """
        Initialize the ReportPluginManager.

        Sets up the configuration path and loads the plugin configuration data.
        """
        self.config_path = "app/services/plugins/plugins.json"
        self.config = self.__load_config(self.config_path)

    def __load_config(self, path):
        """
        Load plugin configuration from the specified JSON file.

        Args:
            path: Path to the plugin configuration JSON file

        Returns:
            Dictionary containing the plugin configuration
        """
        with open(path, "r") as file:
            return json.load(file)

    def load_plugins(self, plugin_name: str, **kwargs):
        """
        Dynamically load and instantiate plugins for the specified plugin name.

        This method reads the configuration for the specified plugin name and
        dynamically loads the corresponding modules. It then either instantiates
        classes or loads functions based on the configuration.

        Args:
            plugin_name: Name of the plugin category to load (e.g., 'report')
            **kwargs: Additional keyword arguments to pass to plugin constructors

        Returns:
            Dictionary mapping report types to their corresponding plugin instances
        """
        logger.debug(f"plugin manager kwargs params: {kwargs}")
        plugins = {}
        for report_type, plugin in self.config[plugin_name].items():
            module_name = plugin["module"]
            module = importlib.import_module(module_name)

            if "class" in plugin:
                class_name = plugin["class"]
                plugin_class = getattr(module, class_name)
                # Get constructor arguments
                args = [kwargs.get(arg.strip("<>"), arg) for arg in plugin.get("args", [])]
                logger.debug(f"plugin manager args: {args}")
                plugin_kwargs = plugin.get("kwargs", {})
                logger.debug(f"plugin manager kwargs: {plugin_kwargs}")
                # Create an instance of the class with arguments
                plugin_instance = plugin_class(*args, **plugin_kwargs)
                plugins[report_type] = plugin_instance
            elif "function" in plugin:
                function_name = plugin["function"]
                function = getattr(module, function_name)
                plugins[report_type] = function
        return plugins
