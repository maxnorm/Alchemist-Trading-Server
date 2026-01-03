"""
GPU Optimization Utilities
Configures TensorFlow for optimal GPU usage
"""

import logging
import tensorflow as tf
from typing import Optional, List


class GPUConfig:
    """GPU configuration and optimization utilities"""

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.gpus_available: List[tf.config.PhysicalDevice] = []
        self.is_configured = False

    def configure_gpu(
        self,
        memory_growth: bool = True,
        mixed_precision: bool = True,
        xla_compilation: bool = False,
        gpu_ids: Optional[List[int]] = None,
    ):
        """
        Configure TensorFlow for optimal GPU usage

        :param memory_growth: Enable memory growth to prevent OOM
        :param mixed_precision: Enable mixed precision training (FP16)
        :param xla_compilation: Enable XLA compilation for faster execution
        :param gpu_ids: Optional list of GPU IDs to use (None = all)
        """
        if self.is_configured:
            self.logger.warning("GPU already configured. Skipping reconfiguration.")
            return

        # List available GPUs
        physical_gpus = tf.config.experimental.list_physical_devices("GPU")

        if not physical_gpus:
            self.logger.warning("No GPUs detected. Running on CPU.")
            return

        self.gpus_available = physical_gpus
        self.logger.info(f"Found {len(physical_gpus)} GPU(s)")

        # Filter GPUs if specific IDs requested
        if gpu_ids is not None:
            physical_gpus = [
                physical_gpus[i] for i in gpu_ids if i < len(physical_gpus)
            ]
            self.logger.info(f"Using GPU IDs: {gpu_ids}")

        try:
            # Configure memory growth
            if memory_growth:
                for gpu in physical_gpus:
                    tf.config.experimental.set_memory_growth(gpu, True)
                self.logger.info("GPU memory growth enabled")

            # Enable mixed precision
            if mixed_precision:
                policy = tf.keras.mixed_precision.Policy("mixed_float16")
                tf.keras.mixed_precision.set_global_policy(policy)
                self.logger.info("Mixed precision (FP16) enabled")

            # Enable XLA compilation
            if xla_compilation:
                tf.config.optimizer.set_jit(True)
                self.logger.info("XLA compilation enabled")

            self.is_configured = True
            self.logger.info("GPU configuration complete")

        except RuntimeError as e:
            self.logger.error(f"Error configuring GPU: {e}")
            raise

    def get_gpu_info(self) -> dict:
        """
        Get information about available GPUs

        :return: Dictionary with GPU information
        """
        gpu_info = {
            "gpus_available": len(self.gpus_available),
            "gpu_names": [],
            "memory_info": [],
        }

        for gpu in self.gpus_available:
            try:
                details = tf.config.experimental.get_device_details(gpu)
                gpu_info["gpu_names"].append(details.get("device_name", "Unknown"))

                # Get memory info if available
                memory_info = tf.config.experimental.get_memory_info(gpu.name)
                gpu_info["memory_info"].append(
                    {
                        "current": memory_info["current"] / (1024**3),  # GB
                        "peak": memory_info["peak"] / (1024**3),  # GB
                    }
                )
            except Exception as e:
                self.logger.warning(f"Could not get details for {gpu.name}: {e}")

        return gpu_info

    def check_gpu_availability(self) -> bool:
        """
        Check if GPU is available and configured

        :return: True if GPU is available and configured
        """
        return len(self.gpus_available) > 0 and self.is_configured


# Global GPU config instance
_gpu_config = GPUConfig()


def configure_gpu(
    memory_growth: bool = True,
    mixed_precision: bool = True,
    xla_compilation: bool = False,
    gpu_ids: Optional[List[int]] = None,
):
    """
    Configure GPU for optimal usage (convenience function)

    :param memory_growth: Enable memory growth
    :param mixed_precision: Enable mixed precision
    :param xla_compilation: Enable XLA compilation
    :param gpu_ids: Optional GPU IDs to use
    """
    _gpu_config.configure_gpu(
        memory_growth=memory_growth,
        mixed_precision=mixed_precision,
        xla_compilation=xla_compilation,
        gpu_ids=gpu_ids,
    )


def get_gpu_info() -> dict:
    """
    Get GPU information (convenience function)

    :return: GPU information dictionary
    """
    return _gpu_config.get_gpu_info()


def is_gpu_available() -> bool:
    """
    Check if GPU is available (convenience function)

    :return: True if GPU is available
    """
    return _gpu_config.check_gpu_availability()
