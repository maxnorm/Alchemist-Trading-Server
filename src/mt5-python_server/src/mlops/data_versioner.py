"""
Data Versioner Module

DVC automation for data versioning and reproducibility.
Provides tools for tracking datasets, managing versions,
and ensuring reproducible training runs.
"""

import subprocess
import hashlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict, Any, List


class DataVersioner:
    """
    DVC automation for data versioning.

    Provides methods for:
    - Adding data to DVC tracking
    - Pushing/pulling data to/from remote storage
    - Getting version information
    - Running reproducible pipelines

    Usage:
        versioner = DataVersioner(repo_root="/path/to/repo")

        # Track new data
        versioner.add_and_push("data/raw/ticks.parquet", "Add tick data v1.0")

        # Get version info
        version = versioner.get_version("data/raw/ticks.parquet")

        # Run pipeline
        versioner.run_pipeline()
    """

    def __init__(self, repo_root: Optional[str] = None):
        """
        Initialize data versioner.

        Args:
            repo_root: Root directory of the repository (default: current directory)
        """
        self.repo_root = Path(repo_root) if repo_root else Path.cwd()
        self.logger = logging.getLogger(__name__)

        # Check if DVC is installed
        self._dvc_available = self._check_dvc()

    def _check_dvc(self) -> bool:
        """Check if DVC is available"""
        try:
            result = subprocess.run(
                ["dvc", "version"],
                capture_output=True,
                text=True,
                cwd=str(self.repo_root),
            )
            return result.returncode == 0
        except FileNotFoundError:
            self.logger.warning("DVC not found. Install with: pip install dvc")
            return False

    def _run_command(
        self, command: List[str], check: bool = True
    ) -> subprocess.CompletedProcess:
        """Run a command in the repo root"""
        self.logger.debug(f"Running: {' '.join(command)}")
        result = subprocess.run(
            command, capture_output=True, text=True, cwd=str(self.repo_root)
        )
        if check and result.returncode != 0:
            self.logger.error(f"Command failed: {result.stderr}")
            raise RuntimeError(f"Command failed: {' '.join(command)}\n{result.stderr}")
        return result

    def init(self) -> bool:
        """
        Initialize DVC in the repository.

        Returns:
            True if successful
        """
        if not self._dvc_available:
            return False

        try:
            self._run_command(["dvc", "init"])
            self.logger.info("DVC initialized")
            return True
        except RuntimeError as e:
            if "already initialized" in str(e).lower():
                self.logger.info("DVC already initialized")
                return True
            raise

    def add(self, file_path: str) -> str:
        """
        Add a file or directory to DVC tracking.

        Args:
            file_path: Path to file or directory relative to repo root

        Returns:
            Path to the .dvc file
        """
        if not self._dvc_available:
            raise RuntimeError("DVC not available")

        self._run_command(["dvc", "add", file_path])

        dvc_file = f"{file_path}.dvc"
        self.logger.info(f"Added to DVC: {file_path}")

        return dvc_file

    def push(self, remote: Optional[str] = None) -> None:
        """
        Push tracked data to remote storage.

        Args:
            remote: Remote name (uses default if not specified)
        """
        if not self._dvc_available:
            raise RuntimeError("DVC not available")

        cmd = ["dvc", "push"]
        if remote:
            cmd.extend(["-r", remote])

        self._run_command(cmd)
        self.logger.info("DVC push completed")

    def pull(self, remote: Optional[str] = None) -> None:
        """
        Pull tracked data from remote storage.

        Args:
            remote: Remote name (uses default if not specified)
        """
        if not self._dvc_available:
            raise RuntimeError("DVC not available")

        cmd = ["dvc", "pull"]
        if remote:
            cmd.extend(["-r", remote])

        self._run_command(cmd)
        self.logger.info("DVC pull completed")

    def add_and_push(
        self, file_path: str, message: Optional[str] = None, commit_to_git: bool = True
    ) -> str:
        """
        Add file to DVC and push to remote.

        Args:
            file_path: Path to file or directory
            message: Git commit message
            commit_to_git: Whether to commit the .dvc file to git

        Returns:
            Path to the .dvc file
        """
        dvc_file = self.add(file_path)
        self.push()

        if commit_to_git:
            commit_msg = (
                message
                or f"Add data version: {file_path} ({datetime.now().isoformat()})"
            )

            # Stage .dvc file and .gitignore
            self._run_command(["git", "add", dvc_file])

            gitignore = Path(file_path).parent / ".gitignore"
            if gitignore.exists():
                self._run_command(["git", "add", str(gitignore)])

            # Commit
            self._run_command(["git", "commit", "-m", commit_msg], check=False)

        return dvc_file

    def get_version(self, file_path: str) -> Optional[str]:
        """
        Get the current version (hash) of a DVC-tracked file.

        Args:
            file_path: Path to the tracked file

        Returns:
            MD5 hash or None if not tracked
        """
        dvc_file = Path(self.repo_root) / f"{file_path}.dvc"

        if not dvc_file.exists():
            return None

        try:
            import yaml

            with open(dvc_file, "r") as f:
                data = yaml.safe_load(f)

            outs = data.get("outs", [])
            if outs:
                return outs[0].get("md5")
        except Exception as e:
            self.logger.error(f"Failed to read DVC file: {e}")

        return None

    def checkout(self, version: Optional[str] = None) -> None:
        """
        Checkout a specific version or latest data.

        Args:
            version: Git commit/tag to checkout (None for current)
        """
        if not self._dvc_available:
            raise RuntimeError("DVC not available")

        if version:
            self._run_command(["git", "checkout", version])

        self._run_command(["dvc", "checkout"])
        self.logger.info(f"DVC checkout completed (version: {version or 'current'})")

    def run_pipeline(self, force: bool = False) -> None:
        """
        Run the DVC pipeline (dvc repro).

        Args:
            force: Force re-run even if outputs are up to date
        """
        if not self._dvc_available:
            raise RuntimeError("DVC not available")

        cmd = ["dvc", "repro"]
        if force:
            cmd.append("--force")

        self._run_command(cmd)
        self.logger.info("DVC pipeline completed")

    def get_pipeline_status(self) -> Dict[str, Any]:
        """
        Get status of the DVC pipeline.

        Returns:
            Dictionary with stage statuses
        """
        if not self._dvc_available:
            return {"error": "DVC not available"}

        result = self._run_command(["dvc", "status"], check=False)

        return {
            "output": result.stdout,
            "up_to_date": "Data and pipelines are up to date" in result.stdout,
        }

    def list_files(self) -> List[str]:
        """
        List all DVC-tracked files.

        Returns:
            List of tracked file paths
        """
        tracked = []

        for dvc_file in self.repo_root.rglob("*.dvc"):
            # Get the actual file path from .dvc file
            try:
                import yaml

                with open(dvc_file, "r") as f:
                    data = yaml.safe_load(f)

                outs = data.get("outs", [])
                if outs:
                    path = outs[0].get("path")
                    if path:
                        tracked.append(path)
            except Exception:
                pass

        return tracked

    @staticmethod
    def compute_file_hash(file_path: str) -> str:
        """
        Compute MD5 hash of a file.

        Args:
            file_path: Path to file

        Returns:
            MD5 hash string
        """
        hasher = hashlib.md5()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                hasher.update(chunk)
        return hasher.hexdigest()

    def create_metadata(
        self, file_path: str, additional_info: Optional[Dict[Any, Any]] = None
    ) -> Dict:
        """
        Create metadata for a data file.

        Args:
            file_path: Path to data file
            additional_info: Additional metadata to include

        Returns:
            Metadata dictionary
        """
        path = Path(file_path)

        metadata = {
            "file_path": str(path),
            "file_name": path.name,
            "created_at": datetime.now().isoformat(),
            "file_size_bytes": path.stat().st_size if path.exists() else 0,
            "md5_hash": self.compute_file_hash(str(path)) if path.exists() else None,
            "dvc_version": self.get_version(str(path)),
        }

        if additional_info:
            metadata.update(additional_info)

        return metadata

    def save_metadata(self, file_path: str, metadata: Dict) -> str:
        """
        Save metadata to a JSON file alongside the data.

        Args:
            file_path: Path to data file
            metadata: Metadata dictionary

        Returns:
            Path to metadata file
        """
        metadata_path = Path(file_path).with_suffix(".metadata.json")

        with open(metadata_path, "w") as f:
            json.dump(metadata, f, indent=2)

        return str(metadata_path)

    def get_all_data_versions(self) -> Dict[str, str]:
        """
        Get versions for all DVC-tracked data files.

        Returns:
            Dictionary mapping file paths to their version hashes
        """
        versions = {}
        for file_path in self.list_files():
            version = self.get_version(file_path)
            if version:
                versions[file_path] = version
        return versions

    def get_data_version_summary(self) -> Dict[str, Any]:
        """
        Get summary of all data versions for MLflow tagging.

        Returns:
            Dictionary with data version summary including all tracked files,
            DVC repo root, availability status, and timestamp
        """
        versions = self.get_all_data_versions()
        return {
            "data_versions": versions,
            "dvc_repo_root": str(self.repo_root),
            "dvc_available": self._dvc_available,
            "timestamp": datetime.now().isoformat(),
        }

    def version_feature_code(
        self,
        feature_files: List[str],
        version: str,
        message: Optional[str] = None,
    ) -> Optional[str]:
        """
        Version feature computation code with DVC.

        Args:
            feature_files: List of file paths to feature computation code
            version: Version tag/identifier
            message: Optional commit message

        Returns:
            DVC commit hash or None if DVC not available
        """
        if not self._dvc_available:
            self.logger.warning("DVC not available - cannot version feature code")
            return None

        if not feature_files:
            self.logger.warning("No feature files provided for versioning")
            return None

        try:
            # Add all feature files to DVC tracking
            dvc_files = []
            for file_path in feature_files:
                # Convert to relative path if absolute
                rel_path = Path(file_path)
                if rel_path.is_absolute():
                    try:
                        rel_path = rel_path.relative_to(self.repo_root)
                    except ValueError:
                        # File is outside repo root, skip
                        self.logger.warning(
                            f"Feature file {file_path} is outside repo root, skipping"
                        )
                        continue

                if not (self.repo_root / rel_path).exists():
                    self.logger.warning(
                        f"Feature file {rel_path} does not exist, skipping"
                    )
                    continue

                # Add to DVC if not already tracked
                dvc_file = self.add(str(rel_path))
                dvc_files.append(dvc_file)

            if not dvc_files:
                self.logger.warning("No feature files were successfully added to DVC")
                return None

            # Commit to git with version tag
            commit_msg = (
                message
                or f"Feature pipeline version {version} - {datetime.now().isoformat()}"
            )

            # Stage all .dvc files
            for dvc_file in dvc_files:
                self._run_command(["git", "add", dvc_file], check=False)

            # Commit
            self._run_command(
                ["git", "commit", "-m", commit_msg],
                check=False,  # Don't fail if nothing to commit
            )

            # Get current git commit hash (this is the DVC commit reference)
            result = self._run_command(
                ["git", "rev-parse", "HEAD"],
                check=False,
            )

            if result.returncode == 0:
                commit_hash = result.stdout.strip()
                self.logger.info(
                    f"Versioned feature code for version {version} (commit: {commit_hash})"
                )
                return commit_hash
            else:
                self.logger.warning("Failed to get git commit hash")
                return None

        except Exception as e:
            self.logger.error(f"Error versioning feature code: {e}", exc_info=True)
            return None
