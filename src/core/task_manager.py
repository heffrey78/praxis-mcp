import json
import logging
import shutil
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, Dict, List, Optional, cast

from filelock import FileLock

from .artifact_manager import ArtifactManager
from .artifacts.commands import ArtifactCommand, CommandStatus
from .artifacts.middleware import MiddlewareHandler, create_middleware_handler

if TYPE_CHECKING:
    from src.core.dependency_container import DependencyContainer

logger = logging.getLogger(__name__)


class TaskManager:
    # _file_locks: Dict[Path, threading.Lock] = {}  # Class-level dictionary for file-specific locks
    # _lock_for_locks_dict = threading.Lock() # Lock for accessing/modifying _file_locks

    def __init__(
        self, base_dir: str, container: Optional["DependencyContainer"] = None
    ) -> None:
        self.base_dir: Path = Path(
            base_dir
        ).resolve()  # Ensure resolved path for consistent locking key
        self.history_file: Path = self.base_dir / "task_history.json"
        logger.info(f"TaskManager initialized. History file path: {self.history_file}")
        self._container: Optional[DependencyContainer] = container
        # self.artifact_manager = ArtifactManager(base_dir) # ArtifactManager might need resolved base_dir too

        # Use FileLock for inter-process locking
        # The lock file will be named self.history_file + ".lock"
        self._file_access_lock = FileLock(
            str(self.history_file) + ".lock", timeout=10
        )  # Changed
        logger.info(
            f"TaskManager instance ({id(self)}) using FileLock for {self.history_file}"
        )

        # The artifact manager should ideally also use resolved paths if it writes files
        # For now, focusing on TaskManager's history_file.
        # Assuming ArtifactManager is correctly instantiated elsewhere or its pathing is not the current issue.
        # Re-instantiate ArtifactManager here if it's specific to this TaskManager's scope and base_dir
        if container:  # Ensure container is provided
            self.artifact_manager: ArtifactManager = container.get_artifact_manager()
        else:
            # Fallback or error if container is essential for ArtifactManager
            logger.warning(
                "TaskManager initialized without a DependencyContainer. "
                "Artifact history middleware might not function correctly "
                "if a separate ArtifactManager instance is not explicitly set up."
            )
            # As a minimal fallback, create a local one, but this won't have shared middleware registration
            # from other services that might expect to get it via the container.
            # This path should ideally not be taken in normal operation.
            self.artifact_manager = ArtifactManager(str(self.base_dir))

        # Register artifact history middleware
        self._register_artifact_middleware()

        self._ensure_base_dir()

    def _ensure_base_dir(self) -> None:
        """Ensure the base directory exists."""
        with (
            self._file_access_lock
        ):  # Or lock just around file creation if that's more granular
            self.base_dir.mkdir(parents=True, exist_ok=True)
            # Touch history file to ensure it exists for initial reads if that's desired
            # if not self.history_file.exists():
            #     self.history_file.touch()

    def _register_artifact_middleware(self) -> None:
        """Register middleware handler for updating task history with artifacts."""
        self.artifact_manager.command_handler.middleware.use(
            self._create_artifact_history_handler()
        )

    def _create_artifact_history_handler(self) -> MiddlewareHandler:
        """Create middleware handler for updating task history with artifacts."""

        @create_middleware_handler("update_task_history")
        async def update_task_history(
            command: ArtifactCommand,
        ) -> Optional[ArtifactCommand]:
            logger.info(
                f"TaskManager._create_artifact_history_handler: Middleware called. Command ID='{command.id}', TaskID='{command.task_id}', File='{command.filename}', Status='{command.status}'"
            )
            if command.status == CommandStatus.COMPLETED:
                try:
                    # Read current task history
                    tasks = self._read_task_history()
                    if not tasks or command.task_id not in tasks:
                        logger.warning(
                            f"Task {command.task_id} not found in history for artifact middleware. Command File: {command.filename}"
                        )  # Added command file for context
                        return command

                    # Update artifacts in task history
                    task_record = tasks[command.task_id]
                    if "artifacts" not in task_record:
                        task_record["artifacts"] = {}

                    # Create artifact record
                    if command.subdir:
                        artifact_path = str(Path(command.subdir) / command.filename)
                    else:
                        artifact_path = command.filename

                    # Get current step from step_progress
                    current_step = None
                    step_progress = task_record.get("step_progress", {})
                    for step_name, step_info in step_progress.items():
                        if step_info.get("status") == "running":
                            current_step = step_name
                            break

                    task_record["artifacts"][command.filename] = {
                        "path": artifact_path,
                        "type": command.content_type,
                        "size": command.metadata.get("size"),
                        "created_at": command.timestamp.isoformat(),
                        "command_id": str(command.id),
                        "step": current_step,  # Associate artifact with current step
                    }

                    # Update task history
                    self._append_history_record(task_record)
                    logger.debug(
                        f"Updated task history with artifact: {command.filename}"
                    )

                except Exception as e:
                    logger.error(
                        f"Failed to update task history for artifact {command.filename}: {e}"
                    )

            return command

        # Type assertion to satisfy type checker
        handler: MiddlewareHandler = update_task_history  # type: ignore[assignment]
        return handler

    def create_task(self, pipeline_id: str, params: Dict[str, Any]) -> str:
        """Create a new task with a unique ID.

        Args:
            pipeline_id: The ID of the pipeline being run
            params: The parameters passed to the pipeline

        Returns:
            The unique task ID (UUID)
        """
        task_id: str = str(uuid.uuid4())
        # task_dir creation does not need the history_file lock
        task_dir: Path = self.base_dir / task_id
        task_dir.mkdir(parents=True, exist_ok=True)

        current_time: str = datetime.now(UTC).isoformat()
        record: Dict[str, Any] = {
            "task_id": task_id,
            "pipeline_id": pipeline_id,
            "params": params,
            "created_at": current_time,
            "updated_at": current_time,  # Add updated_at
            "status": "created",
            "artifacts": {},
            "step_progress": {},
        }

        self._append_history_record(record)  # This method is now locked
        return task_id

    def _append_history_record(self, record: Dict[str, Any]) -> None:
        """Append a task record to the history file, under lock."""
        logger.info(
            f"TaskManager._append_history_record: Called for TaskID='{record.get('task_id')}'. Record to append (excerpt): status='{record.get('status')}', artifacts_keys='{list(record.get('artifacts', {}).keys())}'"
        )
        with self._file_access_lock:
            history_data: Dict[str, Any] = {"tasks": {}}
            if self.history_file.exists():
                try:
                    with self.history_file.open("r", encoding="utf-8") as f:
                        content: str = f.read()
                        if content.strip():  # Handle empty or whitespace-only file
                            history_data = json.loads(content)
                        # Ensure "tasks" key exists
                        if "tasks" not in history_data:
                            history_data["tasks"] = {}
                except json.JSONDecodeError:
                    logger.error(
                        f"History file {self.history_file} is corrupted. Initializing with empty tasks.",
                        exc_info=True,
                    )
                    history_data = {"tasks": {}}  # Reset if corrupt
                except IOError as e:
                    logger.error(
                        f"IOError reading history file {self.history_file}: {e}",
                        exc_info=True,
                    )
                    # Decide if to proceed with empty or raise
                    history_data = {"tasks": {}}

            task_id = record["task_id"]
            # Ensure "tasks" key exists before trying to assign to it
            if "tasks" not in history_data:
                history_data["tasks"] = {}
            history_data["tasks"][task_id] = record

            try:
                with self.history_file.open("w", encoding="utf-8") as f:
                    json.dump(history_data, f, indent=2)
                logger.info(
                    f"TaskManager._append_history_record: Successfully wrote to {self.history_file} for TaskID='{record.get('task_id')}'"
                )
            except IOError as e:
                logger.error(
                    f"IOError writing history file {self.history_file}: {e}",
                    exc_info=True,
                )

    def get_task_dir(self, task_id: str) -> Path:
        """Get the directory for a specific task."""
        return self.base_dir / task_id

    def find_task_by_params(
        self, pipeline_id: str, param_key: str, param_value: str
    ) -> Optional[str]:
        """Find a task by pipeline ID and a specific parameter value."""
        with self._file_access_lock:
            if not self.history_file.exists():
                return None

            # _read_task_history handles file read and parse errors, returns dict or None/empty
            tasks_dict = self._read_task_history()
            if not tasks_dict:  # if None or empty
                return None

            for task_id_key, task_data in tasks_dict.items():
                if (
                    task_data.get("pipeline_id") == pipeline_id
                    and param_key in task_data.get("params", {})
                    and str(task_data["params"].get(param_key)) == param_value
                ):
                    return task_id_key
            return None

    def _format_task_record(self, task_id: str, task: Dict[str, Any]) -> Dict[str, Any]:
        """Format a task record for display/API use."""
        created_at: datetime = self._parse_iso_date(task["created_at"])

        # Get step information
        steps: List[Dict[str, Any]] = []
        self.get_task_dir(task_id)

        # Get step progress from task record
        step_progress: Dict[str, Any] = task.get("step_progress", {})

        # Get pipeline definition to get step info
        pipeline_def: Optional[Any] = None
        if self._container is not None:
            pipeline_registry = self._container.get_pipeline_registry()
            pipeline_def = pipeline_registry.get(task["pipeline_id"])

        if pipeline_def:
            for step in pipeline_def.steps:
                step_info: Dict[str, Any] = {
                    "name": step.name,
                    "plugin": step.plugin,
                    "status": step_progress.get(step.name, {}).get("status", "pending"),
                    "start_time": step_progress.get(step.name, {}).get("start_time"),
                    "end_time": step_progress.get(step.name, {}).get("end_time"),
                    "error": step_progress.get(step.name, {}).get("error"),
                    "artifacts": {},
                }

                # Include progress information if available
                if "progress" in step_progress.get(step.name, {}):
                    step_info["progress"] = step_progress[step.name]["progress"]
                if "message" in step_progress.get(step.name, {}):
                    step_info["message"] = step_progress[step.name]["message"]

                # Include artifacts from task history
                for artifact_name, artifact_info in task.get("artifacts", {}).items():
                    # Only include artifacts that belong to this step
                    if artifact_info.get("step") == step.name:
                        step_info["artifacts"][artifact_name] = artifact_info

                steps.append(step_info)

        return {
            "id": task_id[:8],
            "task_id": task_id,
            "pipeline_id": task["pipeline_id"],
            "created_at": created_at.strftime("%b %d, %Y %H:%M"),
            "params": task.get("params", {}),
            "status": task.get("status", "unknown"),
            "error": task.get("error"),
            "steps": steps,
            "artifacts": task.get(
                "artifacts", {}
            ),  # Include all artifacts at task level
            "step_progress": task.get(
                "step_progress", {}
            ),  # Include the raw step progress data
        }

    def _read_task_history(self) -> Dict[str, Dict[str, Any]]:
        """Read and parse the task history file, under lock."""
        with self._file_access_lock:
            if not self.history_file.exists():
                return {}  # Return empty dict

            try:
                with self.history_file.open("r", encoding="utf-8") as f:
                    content: str = f.read()
                    if not content.strip():  # Handle empty file
                        return {}
                    history: Dict[str, Any] = json.loads(content)

                # Get the actual tasks map
                actual_tasks: Dict[str, Any] = history.get("tasks", {})

                # Self-healing: If actual_tasks itself contains a "tasks" key (which is a dict)
                # and other task_ids at the same level, merge them.
                # This handles the {"tasks": {"tasks": {...}, "id1": {...}, "id2": {...}}} structure.
                if "tasks" in actual_tasks and isinstance(actual_tasks["tasks"], dict):
                    # Check if there are other keys at the same level as the inner "tasks" key
                    # These other keys are task_ids that are siblings to the problematic nested "tasks" map.
                    has_sibling_task_ids: bool = any(
                        key != "tasks" for key in actual_tasks
                    )

                    if has_sibling_task_ids:
                        logger.warning(
                            "Corrupted task_history.json structure detected (nested 'tasks' with sibling task IDs). Attempting to heal."
                        )
                        healed_tasks: Dict[str, Any] = {}
                        # Get the inner "tasks" map
                        nested_tasks_sub_map: Dict[str, Any] = actual_tasks.get(
                            "tasks", {}
                        )
                        healed_tasks.update(
                            nested_tasks_sub_map
                        )  # Add tasks from inner map

                        # Add tasks that were siblings to the inner "tasks" map
                        for key, value in actual_tasks.items():
                            if key != "tasks":
                                healed_tasks[key] = value

                        # To permanently fix the file, a write operation would be needed here,
                        # or ensure subsequent writes use this healed_tasks structure.
                        # For now, this method returns the corrected view.
                        # Subsequent TaskManager operations that read then write will fix the file.
                        return healed_tasks
                    # Structure is {"tasks": {"tasks": {...}}} but no siblings, so the inner "tasks" is the actual map
                    logger.warning(
                        "Task_history.json has nested 'tasks' key, using inner map."
                    )
                    # Cast the inner tasks to the proper type
                    inner_tasks: Dict[str, Dict[str, Any]] = cast(
                        "Dict[str, Dict[str, Any]]", actual_tasks["tasks"]
                    )
                    return inner_tasks

                return actual_tasks

            except json.JSONDecodeError:
                logger.error(
                    f"Task history file {self.history_file} is corrupted (JSONDecodeError).",
                    exc_info=True,
                )
                return {}
            except Exception as e:
                logger.error(
                    f"Failed to read task history from {self.history_file}: {e}",
                    exc_info=True,
                )
                return {}

    @staticmethod
    def _parse_iso_date(date_str: str) -> datetime:
        """Parse an ISO format date string to datetime."""
        # Python's fromisoformat handles 'Z' correctly from 3.11 onwards.
        # For <3.11, .replace('Z', '+00:00') is common.
        # date_str is already typed as str, no need for isinstance check
        if date_str.endswith("Z"):
            return datetime.fromisoformat(date_str[:-1] + "+00:00")
        return datetime.fromisoformat(date_str)

    def get_raw_task_history(self) -> Dict[str, Dict[str, Any]]:
        """Get raw task history data.

        Returns:
            Dictionary mapping task IDs to task data
        """
        return self._read_task_history()

    def get_task_history(self) -> List[Dict[str, Any]]:
        """Get all tasks from history, sorted by creation date (newest first).

        Returns:
            List of task records with formatted fields for display
        """
        with self._file_access_lock:
            tasks = self._read_task_history()
            if not tasks:
                return []

            # Create a list of (datetime_obj, formatted_record) an associatable structure
            # To ensure we sort on the actual datetime objects before formatting for display.

            parsed_tasks_for_sorting: List[Dict[str, Any]] = []
            for task_id, task_data in tasks.items():
                raw_created_at_str = task_data.get("created_at")
                if raw_created_at_str:
                    try:
                        # Parse the raw ISO date string to a datetime object for sorting
                        dt_obj = self._parse_iso_date(raw_created_at_str)
                        # The _format_task_record will use the same raw_created_at_str
                        # from task_data to produce its human-readable version.
                        # We store the dt_obj separately for sorting.
                        parsed_tasks_for_sorting.append(
                            {
                                "original_task_id": task_id,  # Keep original task_id for reference if needed
                                "original_task_data": task_data,  # Keep original data
                                "sortable_datetime": dt_obj,
                            }
                        )
                    except ValueError as e:
                        logger.warning(
                            f"Skipping task {task_id} in get_task_history sort preparation due to invalid created_at: '{raw_created_at_str}' - {e}"
                        )
                else:
                    logger.warning(
                        f"Skipping task {task_id} in get_task_history sort preparation due to missing created_at field."
                    )

            # Sort by the datetime object
            def sort_key(x: Dict[str, Any]) -> Any:
                return x["sortable_datetime"]  # datetime objects are sortable

            sorted_task_info: List[Dict[str, Any]] = sorted(
                parsed_tasks_for_sorting,
                key=sort_key,
                reverse=True,
            )

            # Now, format the sorted tasks for display
            final_task_list: List[Dict[str, Any]] = []
            for item_info in sorted_task_info:
                # Use the original task_id and task_data to format the record
                original_task_id: str = str(item_info["original_task_id"])
                original_task_data: Dict[str, Any] = item_info["original_task_data"]
                # original_task_data is already typed as Dict[str, Any]
                formatted_record = self._format_task_record(
                    original_task_id, original_task_data
                )
                final_task_list.append(formatted_record)

            return final_task_list

    def export_task(
        self, task_id: str, destination: Path, compress: bool = False
    ) -> Path:
        """Export a task's artifact directory to a destination.

        Args:
            task_id: The ID of the task to export
            destination: Path to export to
            compress: Whether to create a zip archive

        Returns:
            Path to the exported directory or zip file

        Raises:
            ValueError: If task doesn't exist or destination is invalid
        """
        task_dir = self.get_task_dir(task_id)
        if not task_dir.exists():
            raise ValueError(f"Task directory not found: {task_id}")

        # Ensure destination parent exists
        destination = Path(destination)
        destination.parent.mkdir(parents=True, exist_ok=True)

        if compress:
            # For zip archives, ensure we create the zip in the destination directory
            if destination.is_dir() or not destination.suffix:
                # If destination is a directory or has no extension, create zip inside it
                zip_path = destination / f"{task_id}.zip"
                base_name = str(destination / task_id)
            else:
                # If destination specifies a file name, use that
                zip_path = destination.with_suffix(".zip")
                base_name = str(destination.with_suffix(""))

            # Create zip archive
            shutil.make_archive(
                base_name,  # Base name for the archive
                "zip",
                task_dir,
            )
            return zip_path
        # For directory copy, ensure we create a subdirectory with the task ID
        if destination.is_dir() or not destination.suffix:
            # If destination is a directory, create task_id subdirectory
            target_dir = destination / task_id
        else:
            # If destination specifies a name, use that
            target_dir = destination

        if target_dir.exists():
            raise ValueError(f"Destination already exists: {target_dir}")

        # Copy directory
        shutil.copytree(task_dir, target_dir)
        return target_dir

    def get_task_details(self, task_id: str) -> Optional[Dict[str, Any]]:
        """Get formatted details for a specific task.

        Args:
            task_id: The ID of the task (can be full UUID or short 8-char version)

        Returns:
            Formatted task details or None if task not found

        Raises:
            ValueError: If task history file is corrupted or multiple tasks match
        """
        original_task_id_param = task_id  # Store original for logging if not found
        try:
            tasks = self._read_task_history()
            if not tasks:
                # ADDED LOGGING HERE
                logger.info(
                    f"TaskManager.get_task_details: No tasks found in history. Task {original_task_id_param} not found."
                )
                return None

            task_to_return_data = None
            task_id_to_return = None

            # First try exact match
            if task_id in tasks:
                task_to_return_data = tasks[task_id]
                task_id_to_return = task_id
            else:
                # Try to match against short ID (first 8 chars)
                matching_tasks = [
                    (tid, t)
                    for tid, t in tasks.items()
                    if tid.startswith(task_id) or tid[:8] == task_id
                ]

                if not matching_tasks:
                    # ADDED LOGGING HERE
                    logger.info(
                        f"TaskManager.get_task_details: Task {original_task_id_param} not found after exact and short ID match."
                    )
                    return None

                if len(matching_tasks) > 1:
                    # No change to logging here, error is raised
                    raise ValueError(
                        f"Multiple tasks match ID '{original_task_id_param}'. Please use a more specific ID."
                    )

                task_id_to_return, task_to_return_data = matching_tasks[0]

            # ADDED LOGGING HERE
            logger.info(
                f"TaskManager.get_task_details: Returning task {task_id_to_return} with status: {task_to_return_data.get('status') if task_to_return_data else 'N/A'}"
            )
            return self._format_task_record(task_id_to_return, task_to_return_data)

        except ValueError:
            # No change to logging here, error is re-raised
            raise
        except (
            Exception
        ) as e:  # Catch any other unexpected error during details retrieval
            logger.error(
                f"TaskManager.get_task_details: Unexpected error for task {original_task_id_param}: {e}",
                exc_info=True,
            )
            return None

    def update_task_status(self, task_id: str, status: str) -> None:
        """Update the status of a task, under lock."""
        with self._file_access_lock:
            tasks = self._read_task_history()  # This always returns a dict, never None

            if task_id not in tasks:
                # Attempt to match short ID if full ID not found
                matched_full_id = None
                if len(task_id) < 36:  # Heuristic for short ID
                    for tid_key in tasks:
                        if tid_key.startswith(task_id):
                            if matched_full_id is not None:  # Ambiguous short ID
                                logger.warning(
                                    f"Ambiguous short task ID {task_id} for status update. Aborting update."
                                )
                                return
                            matched_full_id = tid_key

                if matched_full_id:
                    task_to_update_id = matched_full_id
                else:
                    logger.warning(
                        f"Task {task_id} not found in history for status update."
                    )
                    return  # Task not found, even with short ID check
            else:
                task_to_update_id = task_id

            tasks[task_to_update_id]["status"] = status
            tasks[task_to_update_id]["updated_at"] = datetime.now(
                UTC
            ).isoformat()  # Add updated_at

            try:
                with self.history_file.open("w", encoding="utf-8") as f:
                    json.dump({"tasks": tasks}, f, indent=2)
            except IOError as e:
                logger.error(
                    f"IOError writing history file {self.history_file} in update_task_status: {e}",
                    exc_info=True,
                )

    def set_task_error(self, task_id: str, error: str) -> None:
        """Set an error message for a task, under lock."""
        with self._file_access_lock:
            tasks = self._read_task_history()  # Always returns a dict, never None

            task_to_update_id = task_id
            if task_id not in tasks:  # Check for short ID
                matched_full_id = None
                if len(task_id) < 36:
                    for tid_key in tasks:
                        if tid_key.startswith(task_id):
                            if matched_full_id is not None:
                                logger.warning(
                                    f"Ambiguous short task ID {task_id} for setting error. Aborting."
                                )
                                return
                            matched_full_id = tid_key
                if not matched_full_id:
                    logger.warning(
                        f"Task {task_id} not found in history for setting error."
                    )
                    return
                task_to_update_id = matched_full_id

            tasks[task_to_update_id]["error"] = error
            tasks[task_to_update_id]["status"] = "failed"
            tasks[task_to_update_id]["updated_at"] = datetime.now(
                UTC
            ).isoformat()  # Add updated_at

            try:
                with self.history_file.open("w", encoding="utf-8") as f:
                    json.dump({"tasks": tasks}, f, indent=2)
            except IOError as e:
                logger.error(
                    f"IOError writing history file {self.history_file} in set_task_error: {e}",
                    exc_info=True,
                )

    def update_step_progress(
        self,
        task_id: str,
        step_name: str,
        status: str,
        error: Optional[str] = None,
        start_time: Optional[float] = None,
        end_time: Optional[float] = None,
        progress: Optional[float] = None,
        message: Optional[str] = None,
        plugin: Optional[str] = None,
        artifacts: Optional[List[Dict[str, Any]]] = None,
    ) -> None:
        """Update the progress of a specific step.

        Args:
            task_id: The ID of the task
            step_name: The name of the step
            status: The new status value
            error: Optional error message
            start_time: Optional start time (Unix timestamp)
            end_time: Optional end time (Unix timestamp)
            progress: Optional progress percentage (0-100)
            message: Optional status message
            plugin: Optional plugin name used for this step
            artifacts: Optional list of artifact dictionaries ({name, path, type, size})
        """
        # ADDED LOGGING HERE - ENTRY
        logger.info(
            f"TaskManager.update_step_progress: ENTERED for task {task_id}, step {step_name}, status '{status}'"
        )

        with self._file_access_lock:
            tasks = self._read_task_history()  # Always returns a dict, never None

            task_to_update_id = task_id
            if task_id not in tasks:  # Check for short ID
                matched_full_id = None
                if len(task_id) < 36:
                    for tid_key in tasks:
                        if tid_key.startswith(task_id):
                            if matched_full_id is not None:
                                logger.warning(
                                    f"Ambiguous short task ID {task_id} for step progress. Aborting."
                                )
                                return
                            matched_full_id = tid_key
                if not matched_full_id:
                    logger.warning(
                        f"Task {task_id} not found in history for step progress."
                    )
                    return
                task_to_update_id = matched_full_id

            # Ensure "step_progress" and other nested structures exist
            if "step_progress" not in tasks[task_to_update_id]:
                tasks[task_to_update_id]["step_progress"] = {}

            step_data = tasks[task_to_update_id]["step_progress"].get(step_name, {})

            # Preserve existing data if we're just updating progress (original logic)
            if (
                status == "running"
                and step_name in tasks[task_to_update_id]["step_progress"]
                and tasks[task_to_update_id]["step_progress"][step_name].get("status")
                == "running"
            ):
                if start_time is None and "start_time" in step_data:
                    start_time = step_data["start_time"]
                if plugin is None and "plugin" in step_data:  # Preserve plugin
                    plugin = step_data["plugin"]

            step_data.update(
                {
                    "status": status,
                    "error": error,
                    # Ensure artifacts is initialized correctly if None
                    "artifacts": {a["name"]: a for a in artifacts}
                    if artifacts
                    else step_data.get("artifacts", {}),
                }
            )

            if plugin is not None:
                step_data["plugin"] = plugin
            if start_time is not None:
                step_data["start_time"] = start_time
            if end_time is not None:
                step_data["end_time"] = end_time
            # if progress is not None: step_data["progress"] = progress # Original had this
            # if message is not None: step_data["message"] = message   # Original had this

            tasks[task_to_update_id]["step_progress"][step_name] = step_data
            tasks[task_to_update_id]["updated_at"] = datetime.now(
                UTC
            ).isoformat()  # Update task's main timestamp

            # Get pipeline definition to check fail_on_error flags
            pipeline_id = tasks[task_to_update_id]["pipeline_id"]
            pipeline_def = None
            if self._container is not None:
                pipeline_registry = self._container.get_pipeline_registry()
                pipeline_def = pipeline_registry.get(pipeline_id)

            # ADDED LOGGING HERE - BEFORE OVERALL STATUS DETERMINATION BLOCK
            logger.info(
                f"TaskManager.update_step_progress: Task {task_to_update_id}, Step '{step_name}': About to determine overall task status. Current step_progress for task: {tasks[task_to_update_id].get('step_progress')}"
            )

            if pipeline_def:
                # Create a map of step names to their fail_on_error flags
                step_critical = {
                    step.name: step.fail_on_error for step in pipeline_def.steps
                }

                # Get all step statuses
                step_statuses: List[str] = []
                critical_failures: List[str] = []
                non_critical_failures: List[str] = []
                running_steps: List[str] = []
                completed_steps: List[str] = []
                suspended_steps: List[str] = []

                # Also collect all artifacts across steps
                all_artifacts: Dict[str, Any] = {}

                for step_name, step_data in tasks[task_to_update_id][
                    "step_progress"
                ].items():
                    step_status = step_data["status"]
                    is_critical = step_critical.get(
                        step_name, True
                    )  # Default to critical if not found

                    if step_status == "failed":
                        if is_critical:
                            critical_failures.append(step_name)
                        else:
                            non_critical_failures.append(step_name)
                    elif step_status == "running":
                        running_steps.append(step_name)
                    elif step_status == "completed":
                        completed_steps.append(step_name)
                    elif step_status == "suspended":
                        suspended_steps.append(step_name)

                    step_statuses.append(step_status)

                    # Add step's artifacts to all_artifacts
                    if "artifacts" in step_data:
                        all_artifacts.update(step_data["artifacts"])

                # ADDED LOGGING HERE - INSIDE OVERALL STATUS DETERMINATION BLOCK
                logger.info(
                    f"TaskManager.update_step_progress: Task {task_to_update_id}, Step '{step_name}': Determining overall status. Collected step_statuses: {step_statuses}, Critical failures: {critical_failures}, Non-critical: {non_critical_failures}, Running: {running_steps}, Completed steps: {completed_steps}"
                )

                # Update overall task status based on step statuses
                if critical_failures:
                    tasks[task_to_update_id]["status"] = "failed"
                    tasks[task_to_update_id]["error"] = (
                        f"Critical step(s) failed: {', '.join(critical_failures)}"
                    )
                elif suspended_steps:
                    # If any step is suspended, the task is suspended
                    tasks[task_to_update_id]["status"] = "suspended"
                    tasks[task_to_update_id]["suspended_steps"] = suspended_steps
                elif not running_steps and len(completed_steps) == len(
                    pipeline_def.steps
                ):
                    # All defined steps have completed and no steps are currently running.
                    tasks[task_to_update_id]["status"] = "completed"
                    if non_critical_failures:
                        tasks[task_to_update_id]["error"] = (
                            f"Non-critical step(s) failed: {', '.join(non_critical_failures)}"
                        )
                        # Optionally, set a more specific status like "completed_with_non_critical_errors"
                        # tasks[task_to_update_id]["status"] = "completed_with_errors"
                elif running_steps:
                    tasks[task_to_update_id]["status"] = "running"
                else:  # Not failed, not all completed, not running
                    # This could be 'pending' if no steps have completed yet,
                    # or a state indicating partial completion if some non-critical steps failed
                    # and others are completed, but not all steps defined in the pipeline are done.
                    if (
                        non_critical_failures
                        and not running_steps
                        and len(completed_steps) + len(non_critical_failures)
                        == len(pipeline_def.steps)
                    ):
                        # All steps attempted, some completed, some failed non-critically, none running
                        tasks[task_to_update_id]["status"] = "completed_with_errors"
                        tasks[task_to_update_id]["error"] = (
                            f"Non-critical step(s) failed: {', '.join(non_critical_failures)}"
                        )
                    elif (
                        not completed_steps and not non_critical_failures
                    ):  # No steps started or only pending steps
                        tasks[task_to_update_id]["status"] = (
                            "pending"  # Or tasks[task_to_update_id].get("status", "pending") to keep initial
                        )
                    else:
                        # Default to running if there's an ambiguity, implying some steps are still expected to run or report.
                        # This covers cases where some steps might be pending but not yet in step_progress.
                        tasks[task_to_update_id]["status"] = "running"

                # Store all artifacts at task level
                tasks[task_to_update_id]["artifacts"] = all_artifacts

            # ADDED LOGGING HERE
            logger.info(
                f"TaskManager.update_step_progress: Writing task {task_to_update_id} with overall status: {tasks[task_to_update_id].get('status')}"
            )

            try:
                with self.history_file.open("w", encoding="utf-8") as f:
                    json.dump({"tasks": tasks}, f, indent=2)
            except IOError as e:
                logger.error(
                    f"IOError writing history file {self.history_file} in update_step_progress: {e}",
                    exc_info=True,
                )

    def clear_history(self) -> int:
        """Clear all tasks from history and remove their artifact directories.

        Returns:
            Number of tasks that were cleared
        """
        with self._file_access_lock:
            # ... (original logic, but now under lock) ...
            # Ensure it reads tasks using self._read_task_history() and writes {"tasks": {}}
            tasks_to_clear = self._read_task_history()
            if not tasks_to_clear:
                return 0

            task_count = len(tasks_to_clear)
            # ... (artifact directory removal logic) ...
            for (
                task_id_key
            ) in tasks_to_clear:  # Iterate over keys from the read history
                task_dir = (
                    self.base_dir / task_id_key
                )  # Use base_dir for task specific dirs
                if task_dir.exists():
                    try:
                        shutil.rmtree(task_dir)
                        logger.debug(f"Removed artifact directory: {task_dir}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to remove artifact directory {task_dir}: {e}"
                        )

            try:
                with self.history_file.open("w", encoding="utf-8") as f:
                    json.dump({"tasks": {}}, f, indent=2)  # Write empty tasks dict
                return task_count
            except IOError as e:
                logger.error(
                    f"IOError clearing history file {self.history_file}: {e}",
                    exc_info=True,
                )
                return 0  # Or indicate failure

    def delete_task(self, task_id: str) -> bool:
        """Delete a specific task from history and remove its artifact directory.

        Args:
            task_id: The ID of the task to delete

        Returns:
            True if successful, False if task not found

        Raises:
            ValueError: If there is an error removing the task
        """
        with self._file_access_lock:
            # ... (original logic, but adapted for short ID and under lock) ...
            tasks = self._read_task_history()
            if not tasks:
                return False

            full_task_id_to_delete = None
            if task_id in tasks:
                full_task_id_to_delete = task_id
            else:  # Check short ID
                if len(task_id) < 36:
                    for tid_key in tasks:
                        if tid_key.startswith(task_id):
                            if full_task_id_to_delete is not None:  # Ambiguous
                                logger.warning(
                                    f"Ambiguous short task ID {task_id} for delete. Aborting."
                                )
                                return False
                            full_task_id_to_delete = tid_key

            if not full_task_id_to_delete:
                return False  # Not found

            # ... (artifact directory removal for full_task_id_to_delete) ...
            task_dir = self.base_dir / full_task_id_to_delete
            if task_dir.exists():
                try:
                    shutil.rmtree(task_dir)
                except Exception as e:
                    logger.warning(
                        f"Failed to remove task dir {task_dir} for {full_task_id_to_delete}: {e}"
                    )

            tasks.pop(full_task_id_to_delete)
            try:
                with self.history_file.open("w", encoding="utf-8") as f:
                    json.dump({"tasks": tasks}, f, indent=2)
                return True
            except IOError as e:
                logger.error(
                    f"IOError writing history file {self.history_file} in delete_task: {e}",
                    exc_info=True,
                )
                return False
