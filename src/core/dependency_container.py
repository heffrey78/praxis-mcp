import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Type, TypedDict, cast

import yaml

# For explicit override annotations and stricter typing in subclasses
from typing_extensions import override

from src.core.artifact_manager import ArtifactManager
from src.core.async_utils import AsyncFileOps
from src.core.checkpoint_manager import CheckpointManager
from src.core.container_base import ContainerBase
from src.core.orchestrator import PipelineOrchestrator
from src.core.pipeline_definition import ParamDefinition, PipelineDefinition
from src.core.pipeline_plugin_factory import PipelinePluginFactory
from src.core.plugin_loader_base import SecurityContext
from src.core.plugin_local_folder_loader import LocalFolderPluginLoader
from src.core.plugin_manager import PluginManager
from src.core.plugin_package_loader import PackagePluginLoader
from src.core.providers import ServiceRegistry
from src.core.step_config import LoopConfig, StepConfig
from src.core.step_registry import StepRegistry
from src.core.task_manager import TaskManager
from src.core.type_registry import TypeRegistry, create_type_registry
from src.services.plugin_execution_service import PluginExecutionService


class PipelineRegistry:
    """Registry for pipeline definitions with source tracking."""

    def __init__(self) -> None:
        self._pipelines: Dict[str, PipelineDefinition] = {}
        self._pipeline_sources: Dict[str, str] = {}  # pipeline_id -> source_path
        self._pipeline_metadata: Dict[
            str, Dict[str, Any]
        ] = {}  # pipeline_id -> metadata

    def register(
        self, pipeline: PipelineDefinition, source_path: str = "internal"
    ) -> None:
        """Register a pipeline definition with source tracking."""
        self._pipelines[pipeline.id] = pipeline
        self._pipeline_sources[pipeline.id] = source_path

    def register_with_metadata(
        self,
        pipeline: PipelineDefinition,
        source_path: str = "internal",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Register a pipeline definition with source tracking and metadata."""
        self._pipelines[pipeline.id] = pipeline
        self._pipeline_sources[pipeline.id] = source_path
        if metadata:
            self._pipeline_metadata[pipeline.id] = metadata

    def get(self, pipeline_id: str) -> Optional[PipelineDefinition]:
        """Get a pipeline definition by ID."""
        return self._pipelines.get(pipeline_id)

    def get_all(self) -> Dict[str, PipelineDefinition]:
        """Get all registered pipeline definitions."""
        return dict(self._pipelines)

    def get_source(self, pipeline_id: str) -> Optional[str]:
        """Get the source path for a pipeline."""
        return self._pipeline_sources.get(pipeline_id)

    def get_metadata(self, pipeline_id: str) -> Optional[Dict[str, Any]]:
        """Get metadata for a pipeline."""
        return self._pipeline_metadata.get(pipeline_id)

    def list_by_source(
        self, source_filter: Optional[str] = None
    ) -> List[Tuple[str, str]]:
        """List pipelines with their sources, optionally filtered by source."""
        results = []
        for pipeline_id, source_path in self._pipeline_sources.items():
            if source_filter is None or source_filter in source_path:
                results.append((pipeline_id, source_path))
        return results

    def get_external_pipelines(self) -> List[str]:
        """Get list of external pipeline IDs."""
        return [
            pipeline_id
            for pipeline_id, source_path in self._pipeline_sources.items()
            if source_path != "internal"
        ]

    def remove(self, pipeline_id: str) -> bool:
        """Remove a pipeline from the registry."""
        if pipeline_id in self._pipelines:
            del self._pipelines[pipeline_id]
            self._pipeline_sources.pop(pipeline_id, None)
            self._pipeline_metadata.pop(pipeline_id, None)
            return True
        return False


class DependencyContainer(ContainerBase):
    """Container for managing dependencies."""

    def __init__(self, config: Optional[Dict[str, Any]] = None) -> None:
        super().__init__()
        self._config = config or {}

        # Set default artifacts directory if not provided
        if "artifacts_dir" not in self._config:
            self._config["artifacts_dir"] = str(Path.cwd() / "artifacts")

        # Get OpenAI API key from environment or config
        if "openai_api_key" not in self._config:
            self._config["openai_api_key"] = os.environ.get("OPENAI_API_KEY", "")
        elif self._config["openai_api_key"]:
            os.environ.setdefault("OPENAI_API_KEY", self._config["openai_api_key"])

        # Initialize core components
        artifacts_dir = Path(self._config["artifacts_dir"])
        self._instances[ArtifactManager] = ArtifactManager(str(artifacts_dir))
        self._instances[TaskManager] = TaskManager(str(artifacts_dir), self)

        # Initialize CheckpointManager for suspend/resume support
        self._instances[CheckpointManager] = CheckpointManager(
            self._instances[ArtifactManager]
        )

        # Initialize TypeRegistry for field compatibility resolution
        self._instances[TypeRegistry] = create_type_registry()

        # Initialize PluginManager for external plugin support
        self._instances[PluginManager] = self._initialize_plugin_manager()

        # Pass PluginManager to StepRegistry for external plugin integration
        self._instances[StepRegistry] = StepRegistry(
            self, self._instances[PluginManager]
        )
        self._instances[PipelineRegistry] = PipelineRegistry()
        self._instances[ServiceRegistry] = ServiceRegistry()
        self._instances[PluginExecutionService] = PluginExecutionService(self)

        # Load configurations
        self._load_pipeline_definitions()
        self._load_provider_config()

        # Initialize pipeline plugin factory and register pipelines as plugins
        self._instances[PipelinePluginFactory] = PipelinePluginFactory(self)
        self._register_pipelines_as_plugins()

    async def _load_pipeline_definitions_async(self) -> None:
        """Load pipeline definitions from YAML files in the pipelines directory."""
        import json  # Ensure json is imported for this method
        import logging  # Ensure logging is imported for this method

        logger = logging.getLogger(__name__)  # Use the same logger pattern

        pipelines_dir = Path.cwd() / "src" / "pipelines"
        if not await AsyncFileOps.exists(pipelines_dir):
            logger.warning(f"Pipelines directory not found: {pipelines_dir}")
            return

        registry = self.get_pipeline_registry()
        logger.info(f"Asynchronously loading pipeline definitions from {pipelines_dir}")
        yaml_files = await AsyncFileOps.glob(str(pipelines_dir / "*.yaml"))
        for yaml_file in yaml_files:
            try:
                logger.debug(f"Async processing pipeline file: {yaml_file}")
                content = await AsyncFileOps.read_text(yaml_file)
                data = yaml.safe_load(content)

                # Type narrow the YAML data
                if not isinstance(data, dict):
                    logger.error(f"Invalid pipeline file {yaml_file}: not a dictionary")
                    continue

                # Cast to our expected structure
                typed_data = cast("DependencyContainer._RawPipelineData", data)

                # DIAGNOSTIC START for url_processor (in async)
                if "url_processor.yaml" in str(yaml_file):
                    logger.debug(
                        f"DIAGNOSTIC ASYNC (url_processor): Raw data loaded from YAML: {typed_data}"
                    )
                    if typed_data.get("steps") and len(typed_data["steps"]) > 0:
                        first_step_config_data: Optional[Dict[str, Any]] = typed_data[
                            "steps"
                        ][0].get("config")
                    else:
                        first_step_config_data = None
                    logger.debug(
                        f"DIAGNOSTIC ASYNC (url_processor): Config for first step (extract_urls_from_text): {first_step_config_data}"
                    )
                    if first_step_config_data:
                        try:
                            import tempfile

                            # Use a secure temporary file rather than a predictable path
                            with tempfile.NamedTemporaryFile(
                                delete=False,
                                mode="w",
                                suffix=".json",
                                prefix="url_processor_parsed_step0_config_ASYNC_",
                            ) as tmp_file:
                                json.dump(first_step_config_data, tmp_file, indent=2)
                                diag_yaml_path = tmp_file.name

                            logger.debug(
                                "DIAGNOSTIC ASYNC (url_processor): Saved first step config to %s",
                                diag_yaml_path,
                            )
                        except Exception as diag_yaml_e:
                            logger.debug(
                                f"DIAGNOSTIC ASYNC (url_processor): Error saving first step config: {diag_yaml_e}"
                            )
                    else:
                        logger.debug(
                            f"DIAGNOSTIC ASYNC (url_processor): 'steps' key not found or not as expected. Data type: {type(typed_data)}, Keys: {list(typed_data.keys())}"
                        )
                # DIAGNOSTIC END (in async)

                # Load params if defined
                params = self._build_param_definitions(typed_data.get("params", []))

                # Load steps with proper loop_config handling
                steps = self._parse_step_configs(typed_data.get("steps", []))

                pipeline = PipelineDefinition(
                    id=typed_data["id"],
                    name=typed_data.get("name", typed_data["id"]),
                    description=typed_data.get("description", ""),
                    params=params,
                    steps=steps,
                )

                registry.register(pipeline, source_path=f"internal:{yaml_file}")
                logger.debug(f"Loaded pipeline: {pipeline.id} from {yaml_file}")
            except Exception as e:
                logger.error(f"Error loading pipeline from {yaml_file}: {e}")

        # Load external pipelines
        await self._load_external_pipelines_async()

    async def _load_external_pipelines_async(self) -> None:
        """Asynchronously load pipeline definitions from external sources."""
        import logging

        logger = logging.getLogger(__name__)
        registry = self.get_pipeline_registry()

        # Get external pipeline paths
        external_paths = self._get_external_pipeline_paths()

        for base_path in external_paths:
            logger.info(f"Loading external pipeline definitions from {base_path}")

            # Search for pipeline files recursively
            for yaml_file in base_path.rglob("*.yaml"):
                # Skip hidden files and directories
                if any(part.startswith(".") for part in yaml_file.parts):
                    continue

                try:
                    logger.debug(f"Processing external pipeline file: {yaml_file}")

                    # Use async file operations
                    content = await AsyncFileOps.read_text(yaml_file)
                    data = yaml.safe_load(content)

                    # Type narrow the YAML data
                    if not isinstance(data, dict):
                        logger.error(
                            f"Invalid pipeline file {yaml_file}: not a dictionary"
                        )
                        continue

                    # Check if it has the basic pipeline structure
                    if not (
                        "id" in data
                        and "steps" in data
                        and isinstance(data["steps"], list)
                    ):
                        logger.debug(f"Skipping {yaml_file}: not a valid pipeline file")
                        continue

                    # Cast to our expected structure
                    typed_data = cast("DependencyContainer._RawPipelineData", data)

                    # Load params if defined
                    params = self._build_param_definitions(typed_data.get("params", []))

                    # Load steps with proper loop_config handling
                    steps = self._parse_step_configs(typed_data.get("steps", []))

                    pipeline = PipelineDefinition(
                        id=typed_data["id"],
                        name=typed_data.get("name", typed_data["id"]),
                        description=typed_data.get("description", ""),
                        params=params,
                        steps=steps,
                    )

                    # Register with external source tracking
                    allow_override = self._config.get("allow_pipeline_override", False)
                    if pipeline.id in registry._pipelines and not allow_override:
                        existing_source = registry.get_source(pipeline.id)
                        logger.warning(
                            f"Pipeline {pipeline.id} already exists from {existing_source}. "
                            f"Skipping external pipeline from {yaml_file}"
                        )
                        continue

                    registry.register(pipeline, source_path=f"external:{yaml_file}")
                    logger.debug(
                        f"Loaded external pipeline: {pipeline.id} from {yaml_file}"
                    )

                except Exception as e:
                    # Log but don't crash on pipeline loading errors
                    logger.error(
                        f"Error loading external pipeline from {yaml_file}: {e}"
                    )

    # For backwards compatibility, maintain a sync version that calls the async one if needed
    def _load_pipeline_definitions(self) -> None:
        """Synchronous wrapper for loading pipeline definitions."""
        try:
            import asyncio

            # Check if we're already in an event loop
            try:
                asyncio.get_running_loop()
                # We're already in an event loop, use sync version
                self._load_pipeline_definitions_sync()
            except RuntimeError:
                # No running event loop, use sync version anyway to avoid issues
                self._load_pipeline_definitions_sync()
        except ImportError:
            # If asyncio is not available, use sync loading
            self._load_pipeline_definitions_sync()

    def _load_pipeline_definitions_sync(self) -> None:
        """Synchronous implementation of pipeline loading."""
        import logging

        logger = logging.getLogger(__name__)

        # Get the absolute path to the pipelines directory
        pipelines_dir = Path.cwd() / "src" / "pipelines"
        if not pipelines_dir.exists():
            logger.warning(f"Pipelines directory not found: {pipelines_dir}")
            return

        logger.info(f"Loading pipeline definitions from {pipelines_dir}")

        registry = self.get_pipeline_registry()
        for yaml_file in pipelines_dir.glob("*.yaml"):
            try:
                logger.debug(f"Processing pipeline file: {yaml_file}")
                with yaml_file.open("r") as f:
                    # Use safe_load which is less prone to arbitrary code execution
                    data = yaml.safe_load(f)

                # Type narrow the YAML data
                if not isinstance(data, dict):
                    logger.error(f"Invalid pipeline file {yaml_file}: not a dictionary")
                    continue

                # Cast to our expected structure
                typed_data = cast("DependencyContainer._RawPipelineData", data)

                # DIAGNOSTIC START for url_processor
                if "url_processor.yaml" in str(yaml_file):
                    logger.debug(
                        f"DIAGNOSTIC (url_processor): Raw data loaded from YAML: {typed_data}"
                    )
                    if typed_data.get("steps") and len(typed_data["steps"]) > 0:
                        first_step_config_data: Optional[Dict[str, Any]] = typed_data[
                            "steps"
                        ][0].get("config")
                    else:
                        first_step_config_data = None
                    logger.debug(
                        f"DIAGNOSTIC (url_processor): Config for first step (extract_urls_from_text): {first_step_config_data}"
                    )
                    if first_step_config_data:
                        # Also dump this to a file for detailed inspection
                        try:
                            import json  # Ensure json is imported here if not globally
                            import tempfile

                            with tempfile.NamedTemporaryFile(
                                delete=False,
                                mode="w",
                                suffix=".json",
                                prefix="url_processor_parsed_step0_config_",
                            ) as tmp_file:
                                json.dump(first_step_config_data, tmp_file, indent=2)
                                diag_yaml_path = tmp_file.name

                            logger.debug(
                                "DIAGNOSTIC (url_processor): Saved first step config to %s",
                                diag_yaml_path,
                            )
                        except Exception as diag_yaml_e:
                            logger.debug(
                                f"DIAGNOSTIC (url_processor): Error saving first step config: {diag_yaml_e}"
                            )
                    else:
                        logger.debug(
                            f"DIAGNOSTIC (url_processor): 'steps' key not found or not as expected in parsed data. Data type: {type(typed_data)}, Keys: {list(typed_data.keys())}"
                        )
                # DIAGNOSTIC END

                # Load params if defined
                params = self._build_param_definitions(typed_data.get("params", []))

                # Load steps with proper loop_config handling
                steps = self._parse_step_configs(typed_data.get("steps", []))

                pipeline = PipelineDefinition(
                    id=typed_data["id"],
                    name=typed_data.get("name", typed_data["id"]),
                    description=typed_data.get("description", ""),
                    params=params,
                    steps=steps,
                )

                registry.register(pipeline, source_path=f"internal:{yaml_file}")
                logger.debug(f"Loaded pipeline: {pipeline.id} from {yaml_file}")
            except Exception as e:
                # Log but don't crash on pipeline loading errors
                logger.error(f"Error loading pipeline from {yaml_file}: {e}")

        # Load external pipelines
        self._load_external_pipelines_sync()

    def _load_external_pipelines_sync(self) -> None:
        """Load pipeline definitions from external sources."""
        import logging

        logger = logging.getLogger(__name__)
        registry = self.get_pipeline_registry()

        # Get external pipeline paths
        external_paths = self._get_external_pipeline_paths()

        for base_path in external_paths:
            logger.info(f"Loading external pipeline definitions from {base_path}")

            # Search for pipeline files recursively
            for yaml_file in base_path.rglob("*.yaml"):
                # Skip hidden files and directories
                if any(part.startswith(".") for part in yaml_file.parts):
                    continue

                try:
                    logger.debug(f"Processing external pipeline file: {yaml_file}")
                    with yaml_file.open("r") as f:
                        data = yaml.safe_load(f)

                    # Type narrow the YAML data
                    if not isinstance(data, dict):
                        logger.error(
                            f"Invalid pipeline file {yaml_file}: not a dictionary"
                        )
                        continue

                    # Check if it has the basic pipeline structure
                    if not (
                        "id" in data
                        and "steps" in data
                        and isinstance(data["steps"], list)
                    ):
                        logger.debug(f"Skipping {yaml_file}: not a valid pipeline file")
                        continue

                    # Cast to our expected structure
                    typed_data = cast("DependencyContainer._RawPipelineData", data)

                    # Load params if defined
                    params = self._build_param_definitions(typed_data.get("params", []))

                    # Load steps with proper loop_config handling
                    steps = self._parse_step_configs(typed_data.get("steps", []))

                    pipeline = PipelineDefinition(
                        id=typed_data["id"],
                        name=typed_data.get("name", typed_data["id"]),
                        description=typed_data.get("description", ""),
                        params=params,
                        steps=steps,
                    )

                    # Register with external source tracking
                    allow_override = self._config.get("allow_pipeline_override", False)
                    if pipeline.id in registry._pipelines and not allow_override:
                        existing_source = registry.get_source(pipeline.id)
                        logger.warning(
                            f"Pipeline {pipeline.id} already exists from {existing_source}. "
                            f"Skipping external pipeline from {yaml_file}"
                        )
                        continue

                    registry.register(pipeline, source_path=f"external:{yaml_file}")
                    logger.debug(
                        f"Loaded external pipeline: {pipeline.id} from {yaml_file}"
                    )

                except Exception as e:
                    # Log but don't crash on pipeline loading errors
                    logger.error(
                        f"Error loading external pipeline from {yaml_file}: {e}"
                    )

    def _parse_step_configs(
        self, step_data: List["DependencyContainer._RawStepConfigFull"]
    ) -> List[StepConfig]:
        """Parse step configurations from YAML data, handling loop_config recursively.

        Args:
            step_data: List of typed step configuration dictionaries from YAML

        Returns:
            List of StepConfig objects with properly parsed loop_config
        """
        import json  # Ensure json is imported for this method scope
        import logging  # Ensure logging is imported for this method scope

        logger = logging.getLogger(__name__)  # Use the same logger pattern
        steps: List[StepConfig] = []

        for _step_index, step in enumerate(step_data):
            # DIAGNOSTIC for specific step config within _parse_step_configs
            if step.get("name") == "extract_urls_from_text":
                parsed_config_for_step: Dict[str, Any] = step.get("config", {})
                logger.debug(
                    f"DIAGNOSTIC (_parse_step_configs for 'extract_urls_from_text'): Step data: {step}"
                )
                logger.debug(
                    f"DIAGNOSTIC (_parse_step_configs for 'extract_urls_from_text'): Config obtained by step.get('config', {{}}): {parsed_config_for_step}"
                )
                try:
                    import tempfile

                    with tempfile.NamedTemporaryFile(
                        delete=False,
                        mode="w",
                        suffix=".json",
                        prefix="parse_step_configs_extract_urls_",
                    ) as tmp_file:
                        json.dump(parsed_config_for_step, tmp_file, indent=2)
                        diag_path = tmp_file.name

                    logger.debug(
                        "DIAGNOSTIC (_parse_step_configs for 'extract_urls_from_text'): Saved config to %s",
                        diag_path,
                    )
                except Exception as e_diag_psc:
                    logger.debug(
                        f"DIAGNOSTIC (_parse_step_configs for 'extract_urls_from_text'): Error saving config: {e_diag_psc}"
                    )

            # Parse loop_config if present
            loop_config = None
            loop_data = step.get("loop_config")
            if loop_data:
                # Parse body steps recursively
                body_steps = []
                if loop_data and "body" in loop_data:
                    body_steps = self._parse_step_configs(loop_data["body"])

                # Create LoopConfig object
                loop_config = LoopConfig(
                    body=body_steps,
                    collection=loop_data.get("collection"),
                    item_name=loop_data.get("item_name"),
                    index_name=loop_data.get("index_name"),
                    result_name=loop_data.get("result_name"),
                    count=loop_data.get("count"),
                    delay=loop_data.get("delay"),
                    fail_fast=loop_data.get("fail_fast", False),
                    max_iterations=loop_data.get("max_iterations", 100),
                    condition=loop_data.get("condition"),
                )

            # Create StepConfig with optional loop_config and connections
            step_config = StepConfig(
                name=step["name"],
                plugin=step["plugin"],
                depends_on=step.get("depends_on", []),
                fail_on_error=step.get("fail_on_error", True),
                is_finally=bool(step.get("finally", False)),
                loop_config=loop_config,
                config=step.get("config", {}),
                connections=step.get("connections"),
            )

            steps.append(step_config)

        return steps

    def get_artifact_manager(self) -> ArtifactManager:
        """Get the artifact manager instance."""
        return self._instances[ArtifactManager]

    def get_task_manager(self) -> TaskManager:
        """Get the task manager instance."""
        return self._instances[TaskManager]

    def get_step_registry(self) -> StepRegistry:
        """Get the step registry instance."""
        return self._instances[StepRegistry]

    def get_plugin_registry(self) -> StepRegistry:
        """Get the plugin registry (alias for step registry)."""
        return self.get_step_registry()

    def get_pipeline_registry(self) -> PipelineRegistry:
        """Get the pipeline registry instance."""
        return self._instances[PipelineRegistry]

    def get_plugin_service(self) -> Any:
        """Get or create the plugin service instance."""
        # Import here to avoid circular imports
        from src.services.plugin_service import PluginService

        if PluginService not in self._instances:
            # Get all plugins from StepRegistry which includes both internal and external
            step_registry = self.get_step_registry()

            # Create a PluginService instance with unified plugin access
            service = PluginService(plugin_discovery=None)

            # Override the get_all_plugins method to use StepRegistry
            service._plugins_cache = step_registry.get_all_plugins()

            self._instances[PluginService] = service
        return self._instances[PluginService]

    def get_agent_info_service(self) -> Any:
        """Get or create the agent info service instance."""
        # Import here to avoid circular imports
        from src.services.agent_info_service import AgentInfoService

        if AgentInfoService not in self._instances:
            self._instances[AgentInfoService] = AgentInfoService(self._get_agents_dir())
        return self._instances[AgentInfoService]

    def _get_plugins_dir(self) -> Path:
        """Get the plugins directory path."""
        return Path.cwd() / "src" / "plugins"

    def _get_agents_dir(self) -> Path:
        """Get the agents directory path."""
        return Path.cwd() / "agents"

    @override
    def register_instance(self, cls: Type[Any], instance: Any) -> None:
        """Register a custom instance for a type.

        The `Type[Any]` annotation satisfies Pyright's requirement for a
        concrete type argument while preserving the generic nature of this
        helper.
        """
        self._instances[cls] = instance

    @override
    def get_instance(self, cls: Type[Any]) -> Optional[Any]:
        """Get a registered instance for a type, if any."""
        return self._instances.get(cls)

    def _load_provider_config(self) -> None:
        """Load provider configuration from YAML."""
        config_path = Path(__file__).parent.parent / "config" / "providers.yaml"
        if not config_path.exists():
            return
        registry = self.get_service_registry()
        registry.load_config(config_path)

    def get_service_registry(self) -> ServiceRegistry:
        """Get the service registry instance."""
        return self._instances[ServiceRegistry]

    def get_type_registry(self) -> TypeRegistry:
        """Get the type registry instance."""
        return self._instances[TypeRegistry]

    def get_plugin_manager(self) -> PluginManager:
        """Get the plugin manager instance."""
        return self._instances[PluginManager]

    def _initialize_plugin_manager(self) -> PluginManager:
        """Initialize plugin manager with appropriate loaders."""
        import logging

        logger = logging.getLogger(__name__)

        # Create plugin manager with security context
        plugin_manager = PluginManager(
            security_context=SecurityContext(),
            enable_dependency_isolation=False,  # Can be enabled later if needed
        )

        # Don't add internal plugin loader here - StepRegistry handles internal plugins
        # We only want PluginManager to handle external plugins

        # Add package-based plugin loader for pip-installed plugins
        package_loader = PackagePluginLoader(security_context=SecurityContext())
        plugin_manager.register_loader(package_loader)
        logger.info("Registered package-based plugin loader")

        # Add external plugin paths from environment or config
        external_paths = self._get_external_plugin_paths()
        for path in external_paths:
            if path.exists():
                loader = LocalFolderPluginLoader(
                    root_path=path, security_context=SecurityContext()
                )
                plugin_manager.register_loader(loader)
                logger.info(f"Registered external plugin path: {path}")

        return plugin_manager

    def _get_external_plugin_paths(self) -> List[Path]:
        """Get configured external plugin paths."""
        paths = []

        # Check environment variable
        env_paths = os.environ.get("PRAXIS_PLUGIN_PATHS", "")
        if env_paths:
            for path_str in env_paths.split(":"):
                path = Path(path_str).expanduser().resolve()
                if path.exists() and path.is_dir():
                    paths.append(path)

        # Check config
        config_paths = self._config.get("external_plugin_paths", [])
        for path_str in config_paths:
            path = Path(path_str).expanduser().resolve()
            if path.exists() and path.is_dir():
                paths.append(path)

        # Default path in user home
        default_path = Path.home() / ".praxis" / "plugins"
        if default_path.exists():
            paths.append(default_path)

        return paths

    def _get_external_pipeline_paths(self) -> List[Path]:
        """Get configured external pipeline paths."""
        paths = []

        # Check environment variable
        env_paths = os.environ.get("PRAXIS_PIPELINE_PATHS", "")
        if env_paths:
            for path_str in env_paths.split(":"):
                path = Path(path_str).expanduser().resolve()
                if path.exists() and path.is_dir():
                    paths.append(path)

        # Check config
        config_paths = self._config.get("external_pipeline_paths", [])
        for path_str in config_paths:
            path = Path(path_str).expanduser().resolve()
            if path.exists() and path.is_dir():
                paths.append(path)

        # Default path in user home
        default_path = Path.home() / ".praxis" / "pipelines"
        if default_path.exists():
            paths.append(default_path)

        return paths

    def get_orchestrator(self) -> PipelineOrchestrator:
        """Get or create the pipeline orchestrator instance."""
        if PipelineOrchestrator not in self._instances:
            self._instances[PipelineOrchestrator] = PipelineOrchestrator(self)
        return self._instances[PipelineOrchestrator]

    def get_plugin_execution_service(self) -> PluginExecutionService:
        """Get the plugin execution service instance."""
        return self._instances[PluginExecutionService]

    def get_pipeline_plugin_factory(self) -> PipelinePluginFactory:
        """Get the pipeline plugin factory instance."""
        return self._instances[PipelinePluginFactory]

    def get_checkpoint_manager(self) -> CheckpointManager:
        """Get the checkpoint manager instance."""
        return self._instances[CheckpointManager]

    def _register_pipelines_as_plugins(self) -> None:
        """Register all pipeline definitions as plugins in the step registry."""
        import logging

        logger = logging.getLogger(__name__)

        try:
            pipeline_plugin_factory = self.get_pipeline_plugin_factory()
            step_registry = self.get_step_registry()

            pipeline_plugin_factory.register_pipelines_as_plugins(step_registry)

            registered_plugins = (
                pipeline_plugin_factory.get_registered_pipeline_plugins()
            )
            logger.info(
                f"Successfully registered {len(registered_plugins)} pipeline plugins"
            )

        except Exception as e:
            logger.error(f"Failed to register pipelines as plugins: {e}")
            # Don't raise here to avoid breaking container initialization

    @staticmethod
    def _build_param_definitions(
        params_list: List["DependencyContainer._RawParamDefinition"],
    ) -> List[ParamDefinition]:
        """Build param definitions from raw YAML data."""
        return [
            ParamDefinition(
                name=param["name"],
                required=param.get("required", True),
                description=param.get("description", ""),
                type=param.get("type", "string"),
            )
            for param in params_list
        ]

    # ---------------------------------------------------------------------------
    # TypedDict classes for YAML structure parsing
    # ---------------------------------------------------------------------------

    class _RawParamDefinitionRequired(TypedDict):
        name: str

    class _RawParamDefinition(_RawParamDefinitionRequired, total=False):
        required: bool
        description: str
        type: str

    class _RawLoopConfig(TypedDict, total=False):
        body: List["DependencyContainer._RawStepConfigFull"]
        collection: str
        item_name: str
        index_name: str
        result_name: str
        count: int
        delay: int
        fail_fast: bool
        max_iterations: int
        condition: str

    # Split required and optional fields for step configs
    class _RawStepConfigRequired(TypedDict):
        name: str
        plugin: str

    class _RawStepConfigFull(_RawStepConfigRequired, total=False):
        depends_on: List[Any]
        fail_on_error: bool
        loop_config: "DependencyContainer._RawLoopConfig"
        config: Dict[str, Any]
        connections: Any

    # Split required and optional fields for _RawPipelineData
    class _RawPipelineDataRequired(TypedDict):
        id: str
        steps: List["DependencyContainer._RawStepConfigFull"]

    class _RawPipelineData(_RawPipelineDataRequired, total=False):
        name: str
        description: str
        params: List["DependencyContainer._RawParamDefinition"]
