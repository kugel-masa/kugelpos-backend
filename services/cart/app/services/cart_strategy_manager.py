# Copyright 2025 masa@kugel  # # Licensed under the Apache License, Version 2.0 (the "License");  # you may not use this file except in compliance with the License.  # You may obtain a copy of the License at  # #     http://www.apache.org/licenses/LICENSE-2.0  # # Unless required by applicable law or agreed to in writing, software  # distributed under the License is distributed on an "AS IS" BASIS,  # WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.  # See the License for the specific language governing permissions and  # limitations under the License.
import json, importlib


class CartStrategyManager:
    """
    Strategy manager for loading and managing cart plugins.

    This class is responsible for loading different strategy implementations
    (plugins) from a configuration file. It uses dynamic module loading to
    instantiate strategy classes or functions based on the plugin configuration.

    The class supports both class-based strategies and function-based strategies.
    """

    def __init__(self):
        """
        Initialize the strategy manager.

        Loads the plugin configuration file.
        """
        self.config_path = "app/services/strategies/plugins.json"
        self.config = self.__load_config(self.config_path)

    # Load the plugin configuration file
    def __load_config(self, path):
        """
        Load strategy configuration from a JSON file.

        Args:
            path: Path to the plugin configuration JSON file

        Returns:
            dict: The loaded configuration
        """
        with open(path, "r") as file:
            return json.load(file)

    # Load strategies from the plugin configuration file
    def load_strategies(self, strategy_name: str):
        """
        Load a set of strategy implementations by name.

        Dynamically loads and instantiates strategy implementations based on
        the configuration specified for the given strategy name.

        Args:
            strategy_name: Name of the strategy group to load (e.g., "payment_strategies")

        Returns:
            list: List of instantiated strategy objects or functions
        """
        strategies = []
        for strategy in self.config[strategy_name]:
            module_name = strategy["module"]
            module = importlib.import_module(module_name)

            if "class" in strategy:
                class_name = strategy["class"]
                strategy_class = getattr(module, class_name)
                # Get constructor arguments
                args = strategy.get("args", [])
                kwargs = strategy.get("kwargs", {})
                # Create class instance with arguments
                strategy_instance = strategy_class(*args, **kwargs)
                strategies.append(strategy_instance)
            elif "function" in strategy:
                function_name = strategy["function"]
                function = getattr(module, function_name)
                strategies.append(function)
        return strategies
