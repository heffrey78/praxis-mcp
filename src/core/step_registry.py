import contextlib
import copy
import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Optional, Protocol, Type

from pydantic import BaseModel

from src.core.plugin_discovery import PluginDiscovery
from src.plugins.plugin_base import PluginBase

logger = logging.getLogger(__name__)


class ContainerProtocol(Protocol):
    """Protocol defining the required methods for a container."""

    def get_artifact_manager(self) -> Any: ...
    def get_service_registry(self) -> Any: ...


@dataclass
class PluginInfo:
    """Stores information about a registered plugin."""

    plugin_class: Type[PluginBase]
    input_model: Optional[Type[BaseModel]] = None
    output_model: Optional[Type[BaseModel]] = None


class StepRegistry:
    """Registry for plugin classes and their resolved interfaces."""

    def __init__(
        self, container: ContainerProtocol, plugin_manager: Optional[Any] = None
    ) -> None:
        self._container = container
        self._plugin_info: Dict[str, PluginInfo] = {}
        self._plugin_manager = plugin_manager
        self.discover_and_register()

    def discover_and_register(self) -> None:
        """Discover and register all available plugins."""
        # First, discover and register internal plugins
        plugin_root = Path(__file__).parent.parent / "plugins"
        discovery = PluginDiscovery(plugin_root)
        plugins = discovery.discover_plugins()

        for name, plugin_class in plugins.items():
            self.register_plugin(name, plugin_class)

        # Then, register external plugins from PluginManager if available
        if self._plugin_manager:
            try:
                # Initialize plugin manager asynchronously if needed
                import asyncio

                try:
                    asyncio.get_running_loop()
                    # We're in an async context, create a task
                    asyncio.create_task(self._register_external_plugins_async())
                except RuntimeError:
                    # No event loop, run sync then create new default loop to keep asyncio happy
                    asyncio.run(self._register_external_plugins_async())
                    # asyncio.run() closes the loop and leaves the policy marked as set;
                    # create a fresh event loop so later code expecting one (pytest-asyncio, etc.) works.
                    with contextlib.suppress(Exception):
                        asyncio.set_event_loop(asyncio.new_event_loop())
            except Exception as e:
                logger.warning(f"Failed to register external plugins: {e}")
                # Continue without external plugins rather than failing

    def register_plugin(self, name: str, plugin_class: Type[PluginBase]) -> None:
        """Register a plugin, analyze its interface, and store PluginInfo."""
        # Type annotation already ensures plugin_class is Type[PluginBase]
        # Runtime validation for test compatibility
        # Check inheritance using MRO to avoid pyright complaints
        try:
            # Access __mro__ to check inheritance chain
            if not hasattr(plugin_class, "__mro__"):
                raise TypeError(
                    f"Plugin '{name}' must be a class, got {type(plugin_class).__name__}"
                )
            # Check if PluginBase is in the inheritance chain
            if PluginBase not in plugin_class.__mro__:
                raise TypeError(
                    f"Plugin '{name}' must be a class that inherits from PluginBase"
                )
        except AttributeError:
            raise TypeError(
                f"Plugin '{name}' must be a class that inherits from PluginBase"
            ) from None

        if name in self._plugin_info:
            raise ValueError(f"Plugin '{name}' is already registered")

        input_model: Optional[Type[BaseModel]] = None
        output_model: Optional[Type[BaseModel]] = None

        # Check for PascalCase attributes FIRST
        input_attr = getattr(plugin_class, "InputModel", None)
        output_attr = getattr(plugin_class, "OutputModel", None)

        is_modern_input_pascal = False
        if input_attr is not None:
            is_modern_input_pascal = isinstance(input_attr, type) and issubclass(
                input_attr, BaseModel
            )

        is_modern_output_pascal = False
        if output_attr is not None:
            is_modern_output_pascal = isinstance(output_attr, type) and issubclass(
                output_attr, BaseModel
            )

        # Fallback check for lowercase 'input'/'output' attributes
        input_attr_lower = getattr(plugin_class, "input", None)
        output_attr_lower = getattr(plugin_class, "output", None)

        is_modern_input_lower = False
        if input_attr_lower is not None:
            is_modern_input_lower = isinstance(input_attr_lower, type) and issubclass(
                input_attr_lower, BaseModel
            )

        is_modern_output_lower = False
        if output_attr_lower is not None:
            is_modern_output_lower = isinstance(output_attr_lower, type) and issubclass(
                output_attr_lower, BaseModel
            )

        # Determine final input_model and output_model
        if is_modern_input_pascal:
            input_model = input_attr
        elif is_modern_input_lower:
            input_model = input_attr_lower
        # else: input_model remains None

        if is_modern_output_pascal:
            output_model = output_attr
        elif is_modern_output_lower:
            output_model = output_attr_lower
        # else: output_model remains None

        # Check if plugin has input/output models
        if not input_model and not output_model:
            raise ValueError(
                f"Plugin '{name}' must define either InputModel or OutputModel attribute. "
                f"Legacy plugins without Pydantic models are no longer supported."
            )

        if input_model and output_model:
            logger.debug(f"Plugin '{name}' has both input and output models")
        elif input_model:
            logger.debug(f"Plugin '{name}' has input model only")
        elif output_model:
            logger.debug(f"Plugin '{name}' has output model only")

        self._plugin_info[name] = PluginInfo(
            plugin_class=plugin_class,
            input_model=input_model,
            output_model=output_model,
        )

    def get_plugin(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> PluginBase:
        """Get an instantiated plugin by name."""
        # # DIAGNOSTIC: Log received config in StepRegistry.get_plugin
        # if name == "data_extractor":
        #     logger.debug(
        #         f"DIAGNOSTIC (StepRegistry.get_plugin for '{name}'): Received config: {config}"
        #     )
        #     try:
        #         import tempfile

        #         with tempfile.NamedTemporaryFile(
        #             delete=False,
        #             mode="w",
        #             suffix=".json",
        #             prefix="step_registry_data_extractor_received_config_",
        #         ) as tmp_file:
        #             json.dump(config, tmp_file, indent=2)  # Log the config it received
        #             diag_path_rcvd = tmp_file.name
        #         logger.debug(
        #             "DIAGNOSTIC (StepRegistry.get_plugin for '%s'): Saved received config to %s",
        #             name,
        #             diag_path_rcvd,
        #         )
        #     except Exception as e_diag_sr:
        #         logger.debug(
        #             f"DIAGNOSTIC (StepRegistry.get_plugin for '{name}'): Error saving received config: {e_diag_sr}"
        #         )
        # # END DIAGNOSTIC

        plugin_info = self._plugin_info.get(name)
        if not plugin_info:
            raise ValueError(f"Plugin '{name}' not found")

        artifact_manager = self._container.get_artifact_manager()
        service_registry = self._container.get_service_registry()

        try:
            # DIAGNOSTIC: Log config being passed to plugin constructor
            config_to_pass = config  # Default to original
            if name == "data_extractor":
                logger.debug(
                    f"DIAGNOSTIC (StepRegistry.get_plugin for '{name}'): Original config BEFORE potential copy: {config}"
                )
                try:
                    config_to_pass = copy.deepcopy(config)  # Force a deep copy
                    logger.debug(
                        f"DIAGNOSTIC (StepRegistry.get_plugin for '{name}'): DEEPCOPIED config BEING PASSED to {plugin_info.plugin_class.__name__}.__init__: {config_to_pass}"
                    )
                except Exception as e_copy:
                    logger.error(
                        f"DIAGNOSTIC (StepRegistry.get_plugin for '{name}'): Error deepcopying config, passing original: {e_copy}"
                    )
                    config_to_pass = config  # Fallback to original if copy fails

                # Logging the config that will actually be passed, whether original or copy
                try:
                    import tempfile

                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        mode="w",
                        suffix=".json",
                        prefix="step_registry_data_extractor_config_provided_",
                    ) as tmp_file:
                        json.dump(config_to_pass, tmp_file, indent=2)
                        diag_sr_prov_path = tmp_file.name

                    logger.debug(
                        "DIAGNOSTIC (StepRegistry.get_plugin for '%s'): Saved config_to_pass to %s",
                        name,
                        diag_sr_prov_path,
                    )
                except Exception as e_diag_sr_pass:
                    logger.debug(
                        f"DIAGNOSTIC (StepRegistry.get_plugin for '{name}'): Error saving config_to_pass: {e_diag_sr_pass}"
                    )
            # END DIAGNOSTIC FOR DATA_EXTRACTOR

            plugin_instance = plugin_info.plugin_class(
                artifact_manager=artifact_manager,
                config=config_to_pass,  # Pass the (potentially copied) config
                provider_manager=service_registry,
            )
        except Exception as e:
            logger.error(
                f"Failed to instantiate plugin class '{name}': {e}", exc_info=True
            )
            raise ValueError(f"Failed to instantiate plugin class '{name}': {e}") from e

        return plugin_instance

    def create_plugin_instance(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> PluginBase:
        """Create an instance of a plugin with the given configuration."""
        config = config or {}
        return self.get_plugin(name, config)

    def getPlugin(
        self, name: str, config: Optional[Dict[str, Any]] = None
    ) -> PluginBase:
        """Backward compatibility method for get_plugin."""
        return self.get_plugin(name, config)

    def hasPlugin(self, name: str) -> bool:
        """Check if a plugin exists."""
        return name in self._plugin_info

    def get_plugin_class(self, name: str) -> Type[PluginBase]:
        """Get the original plugin CLASS by name."""
        plugin_info = self._plugin_info.get(name)
        if not plugin_info:
            raise ValueError(f"Plugin class '{name}' not found")
        return plugin_info.plugin_class

    def get_input_model(self, name: str) -> Optional[Type[BaseModel]]:
        """Get the resolved input model (Pydantic) for a plugin."""
        plugin_info = self._plugin_info.get(name)
        return plugin_info.input_model if plugin_info else None

    def get_output_model(self, name: str) -> Optional[Type[BaseModel]]:
        """Get the resolved output model (Pydantic) for a plugin."""
        plugin_info = self._plugin_info.get(name)
        return plugin_info.output_model if plugin_info else None

    def register_or_override_plugin(
        self, name: str, plugin_class: Type[PluginBase]
    ) -> None:
        """Register a plugin, overriding any existing registration. Used for testing."""
        # Type annotation already ensures plugin_class is Type[PluginBase]

        if name in self._plugin_info:
            logger.info(f"Overriding existing registration for plugin '{name}'")
        else:
            logger.info(f"Registering new plugin '{name}' via override method.")

        input_model: Optional[Type[BaseModel]] = None
        output_model: Optional[Type[BaseModel]] = None

        input_attr = getattr(plugin_class, "InputModel", None)
        output_attr = getattr(plugin_class, "OutputModel", None)

        is_modern_input = isinstance(input_attr, type) and issubclass(
            input_attr, BaseModel
        )
        is_modern_output = isinstance(output_attr, type) and issubclass(
            output_attr, BaseModel
        )

        if is_modern_input:
            input_model = input_attr
        if is_modern_output:
            output_model = output_attr

        if not input_model and not output_model:
            raise ValueError(
                f"Plugin '{name}' must define either InputModel or OutputModel attribute. "
            )

        self._plugin_info[name] = PluginInfo(
            plugin_class=plugin_class,
            input_model=input_model,
            output_model=output_model,
        )

    async def _register_external_plugins_async(self) -> None:
        """Register external plugins from PluginManager."""
        if not self._plugin_manager:
            return

        try:
            # Initialize the plugin manager
            await self._plugin_manager.initialize()

            # Get all external plugins
            external_plugins = self._plugin_manager.get_all_plugins()

            for plugin_name, plugin_class in external_plugins.items():
                # Skip if already registered (internal plugins take precedence)
                if plugin_name in self._plugin_info:
                    logger.debug(
                        f"Skipping external plugin '{plugin_name}' - already registered internally"
                    )
                    continue

                try:
                    self.register_plugin(plugin_name, plugin_class)
                    logger.info(f"Registered external plugin: {plugin_name}")
                except Exception as e:
                    logger.error(
                        f"Failed to register external plugin '{plugin_name}': {e}"
                    )
                    # Continue with other plugins

        except Exception as e:
            logger.error(f"Error during external plugin registration: {e}")

    def get_all_plugins(self) -> Dict[str, Type[PluginBase]]:
        """Get all registered plugins (both internal and external).

        Returns:
            Dictionary mapping plugin names to plugin classes.
        """
        return {name: info.plugin_class for name, info in self._plugin_info.items()}
