"""Modern PluginBase class for the Praxis pipeline system.

This module provides a clean, type-safe base class for all plugins using
modern Python patterns and Pydantic v2 exclusively.
"""

import logging
from abc import ABC, abstractmethod
from typing import TYPE_CHECKING, Any, ClassVar, Dict, Optional, Set, Type

from pydantic import BaseModel, ValidationError

from src.core.artifact_manager import ArtifactManager
from src.core.context import PipelineContext
from src.core.errors import PluginInputError
from src.core.plugin_types import PluginType

if TYPE_CHECKING:
    from src.core.providers import ChatProvider
    from src.core.type_registry import TypeRegistry

logger = logging.getLogger(__name__)


def get_model_fields(model_class: Type[BaseModel]) -> Dict[str, Any]:
    """Get model fields from a Pydantic v2 model."""
    return model_class.model_fields


def get_field_description(field: Any) -> Optional[str]:
    """Get field description from a Pydantic v2 field."""
    return getattr(field, "description", None)


def get_schema_extra(model_class: Type[BaseModel]) -> Dict[str, Any]:
    """Get schema extra information from a Pydantic v2 model."""
    if hasattr(model_class, "model_config"):
        # model_config is ConfigDict, which is always a dict-like object
        schema_extra = model_class.model_config.get("json_schema_extra", {})
        if isinstance(schema_extra, dict):
            return schema_extra
        return {}
    return {}


class PluginBase(ABC):
    """Modern base class for all pipeline plugins.

    All plugins must define Pydantic v2 models for their interface:
    - InputModel: Defines required input fields (optional)
    - OutputModel: Defines produced output fields (optional)
    - ConfigModel: Defines plugin configuration (optional)

    At least InputModel or OutputModel must be defined.

    Example:

        class MyPlugin(PluginBase):
            class InputModel(BaseModel):
                text: str
                options: dict[str, Any] = {}

            class OutputModel(BaseModel):
                processed_text: str
                metadata: dict[str, Any]

            class ConfigModel(BaseModel):
                model: str = "default"
                temperature: float = 0.7

            plugin_type = PluginType.TRANSFORM

            async def run(self, context: PipelineContext) -> OutputModel:
                # Implementation here
                pass
    """

    # Plugin type classification
    plugin_type: ClassVar[PluginType] = PluginType.DEFAULT

    # Pydantic v2 model interfaces
    InputModel: ClassVar[Optional[Type[BaseModel]]] = None
    OutputModel: ClassVar[Optional[Type[BaseModel]]] = None
    ConfigModel: ClassVar[Optional[Type[BaseModel]]] = None

    # Legacy compatibility (for gradual migration)
    INPUT_TYPES: ClassVar[Set[str]] = set()
    OUTPUT_TYPES: ClassVar[Set[str]] = set()
    TYPE_DESCRIPTIONS: ClassVar[Dict[str, str]] = {}

    # Provider management
    _is_shutting_down: ClassVar[bool] = False

    # Type registry for field compatibility (injected via set_type_registry)
    _type_registry: Optional["TypeRegistry"] = None

    def __init__(
        self,
        artifact_manager: Optional[ArtifactManager] = None,
        config: Optional[Dict[str, Any]] = None,
        provider_manager: Optional[Any] = None,
    ) -> None:
        """Initialize the plugin with modern architecture.

        Args:
            artifact_manager: Manager for saving/loading artifacts
            config: Configuration dictionary
            provider_manager: Provider manager for AI services
        """
        self.artifact_manager = artifact_manager
        self.provider_manager = provider_manager
        self.logger = logging.getLogger(f"praxis.plugins.{self.__class__.__name__}")

        # Validate and parse configuration
        self.config = self._validate_config(config or {})

        # Set up type system integration
        self._register_with_type_system()

    def _validate_config(self, config: Dict[str, Any]) -> BaseModel | Dict[str, Any]:
        """Validate configuration using ConfigModel if defined."""
        if self.ConfigModel is None:
            return config

        try:
            return self.ConfigModel(**config)
        except ValidationError as e:
            self.logger.error(f"Configuration validation failed: {e}")
            # Return default config in case of validation failure
            return self.ConfigModel()

    def _register_with_type_system(self) -> None:
        """Register plugin models with the type system."""
        # Use injected registry if available
        registry = self._type_registry

        if registry is None:
            self.logger.debug("Type registry not available - skipping registration")
            return

        if self.InputModel:
            registry.register_model_class(self.InputModel)
            self._update_types_from_model(self.InputModel, is_input=True)

        if self.OutputModel:
            registry.register_model_class(self.OutputModel)
            self._update_types_from_model(self.OutputModel, is_input=False)

    def _update_types_from_model(
        self, model_class: Type[BaseModel], is_input: bool
    ) -> None:
        """Update legacy type information from Pydantic model."""
        fields = model_class.model_fields
        type_set = self.INPUT_TYPES if is_input else self.OUTPUT_TYPES

        # Add field names to type set
        type_set.update(fields.keys())

        # Add descriptions from field info
        for field_name, field_info in fields.items():
            if field_info.description:
                self.TYPE_DESCRIPTIONS[field_name] = field_info.description

    @classmethod
    def set_type_registry(cls, registry: Optional["TypeRegistry"]) -> None:
        """Set the type registry for this plugin class.

        This should be called by the plugin loading system to inject
        the type registry before plugin instances are created.

        Args:
            registry: The type registry to use for field compatibility
        """
        cls._type_registry = registry

    async def get_provider(self, context: PipelineContext) -> "ChatProvider":
        """Get AI provider for chat operations.

        Args:
            context: Pipeline context

        Returns:
            ChatProvider instance

        Raises:
            ValueError: If no provider is configured
        """
        # Try context first
        if provider := context.get_provider():
            return provider

        # Try provider manager
        if self.provider_manager:
            try:
                return self.provider_manager.get_chat_provider()
            except Exception as e:
                self.logger.warning(f"Failed to get provider from manager: {e}")

        raise ValueError("No AI provider configured")

    async def chat(
        self, context: PipelineContext, messages: list[dict[str, Any]], **params: Any
    ) -> dict[str, Any]:
        """Execute chat completion using configured provider.

        Args:
            context: Pipeline context
            messages: Chat messages
            **params: Additional chat parameters

        Returns:
            Chat completion response
        """
        provider = await self.get_provider(context)

        # Handle model parameter
        if "model_name" in params and (model_value := params.pop("model_name")):
            params["model"] = model_value

        return await provider.chat(messages, **params)

    @classmethod
    def is_shutting_down(cls) -> bool:
        """Check if the plugin system is shutting down."""
        return cls._is_shutting_down

    @classmethod
    async def cleanup_all_providers(cls) -> None:
        """Clean up all active providers."""
        cls._is_shutting_down = True
        # In the simplified version, we don't track providers globally
        # This method exists for API compatibility

    def validate_requirements(self, context: PipelineContext) -> None:
        """Validate that plugin requirements are met.

        Args:
            context: Pipeline context to validate

        Raises:
            PluginInputError: If validation fails
        """
        if not self.InputModel:
            return

        try:
            # Gather input data from context
            input_data = {}
            for field_name, field_info in self.InputModel.model_fields.items():
                # Check for alias first, then field name
                context_key = field_info.alias or field_name
                if context_key in context:
                    input_data[field_name] = context[context_key]
                elif field_name in context:
                    input_data[field_name] = context[field_name]

            # Validate using Pydantic model
            self.InputModel(**input_data)

        except ValidationError as e:
            self.logger.error(f"Input validation failed: {e}")
            raise PluginInputError(
                f"Input validation failed for {self.__class__.__name__}: {e}"
            ) from e

    @abstractmethod
    async def run(self, context: PipelineContext) -> Any:
        """Execute the plugin's main functionality.

        Args:
            context: Pipeline context containing input/output data

        Returns:
            Plugin output (BaseModel instance, dict, or None)
        """

    async def initialize(self) -> None:
        """Initialize plugin resources.

        Called when the plugin is being prepared for use.
        Override this method to perform async initialization.

        This is optional - plugins that don't need initialization
        don't need to override this method.
        """
        return

    async def cleanup(self) -> None:
        """Clean up plugin resources.

        Called when the plugin is being shut down.
        Override this method to clean up resources like
        connections, temporary files, etc.

        This is optional - plugins that don't need cleanup
        don't need to override this method.
        """
        return

    async def health_check(self) -> bool:
        """Check plugin health.

        Called periodically to verify the plugin is functioning correctly.
        Override this method to implement custom health checks.

        Returns:
            True if healthy, False otherwise

        This is optional - plugins that don't need health checks
        can use the default implementation.
        """
        return True

    @property
    def cfg(self) -> BaseModel | Dict[str, Any]:
        """Access to validated configuration.

        Returns the parsed ConfigModel instance if available,
        otherwise returns the raw config dict.
        """
        return self.config

    def get_config(self, key: str, default: Any = None) -> Any:
        """Get a configuration value safely.

        Args:
            key: Configuration key
            default: Default value if key not found

        Returns:
            Configuration value or default
        """
        if isinstance(self.config, BaseModel):
            return getattr(self.config, key, default)
        return self.config.get(key, default)
