"""
Checkpoint manager for training
Manages model checkpoints and metadata
"""

import os
import json
from datetime import datetime
from typing import Optional, Dict, Any

from agents.dqn_agent import DQNAgent


class CheckpointManager:
    """Manages model checkpoints"""

    def __init__(self, save_dir: str, save_freq_steps: int = 1000):
        """
        Initialize checkpoint manager
        :param save_dir: Directory to save checkpoints
        :param save_freq_steps: Frequency of checkpoint saves (in steps)
        """
        self.save_dir = save_dir
        self.save_freq_steps = save_freq_steps
        os.makedirs(save_dir, exist_ok=True)

    def should_save(self, step: int) -> bool:
        """
        Check if checkpoint should be saved
        :param step: Current step number
        :return: True if checkpoint should be saved
        """
        return step > 0 and step % self.save_freq_steps == 0

    def save_checkpoint(
        self,
        agent: DQNAgent,
        step: int,
        episode: int,
        metrics: Dict[str, Any],
        logger=None,
    ) -> str:
        """
        Save model checkpoint
        :param agent: DQN agent to save
        :param step: Current step number
        :param episode: Current episode number
        :param metrics: Metrics to save
        :param logger: Optional logger for logging
        :return: Path to saved checkpoint
        """
        checkpoint_dir = os.path.join(self.save_dir, f"live_checkpoint_step{step}")
        os.makedirs(checkpoint_dir, exist_ok=True)

        # Save agent model
        agent.save(checkpoint_dir)

        # Prepare metrics for saving
        checkpoint_metrics = {
            "total_steps": step,
            "current_episode": episode,
            "total_reward": metrics.get("total_reward", 0.0),
            "episode_rewards": metrics.get("episode_rewards", [])[
                -50:
            ],  # Last 50 episodes
            "episode_profits": metrics.get("episode_profits", [])[-50:],
            "experiences": len(agent.memory),
            "epsilon": agent.epsilon,
            "timestamp": datetime.now().isoformat(),
        }

        # Save metrics
        metrics_file = os.path.join(checkpoint_dir, "metrics.json")
        with open(metrics_file, "w") as f:
            json.dump(checkpoint_metrics, f, indent=2)

        if logger:
            logger.info(f"Checkpoint saved: {checkpoint_dir} (step {step})")
        else:
            print(f"Checkpoint saved: {checkpoint_dir}")

        return checkpoint_dir

    def save_final(
        self,
        agent: DQNAgent,
        step: int,
        episode: int,
        metrics: Dict[str, Any],
        logger=None,
    ) -> str:
        """
        Save final checkpoint
        :param agent: DQN agent to save
        :param step: Final step number
        :param episode: Final episode number
        :param metrics: Complete metrics to save
        :param logger: Optional logger for logging
        :return: Path to saved checkpoint
        """
        final_dir = os.path.join(self.save_dir, f"live_final_step{step}")
        os.makedirs(final_dir, exist_ok=True)

        # Save agent model
        agent.save(final_dir)

        # Prepare complete metrics
        final_metrics = {
            "total_steps": step,
            "total_episodes": episode,
            "total_reward": metrics.get("total_reward", 0.0),
            "episode_rewards": metrics.get("episode_rewards", []),
            "episode_profits": metrics.get("episode_profits", []),
            "experiences": len(agent.memory),
            "epsilon": agent.epsilon,
            "timestamp": datetime.now().isoformat(),
        }

        # Save metrics
        metrics_file = os.path.join(final_dir, "metrics.json")
        with open(metrics_file, "w") as f:
            json.dump(final_metrics, f, indent=2)

        if logger:
            logger.info(
                f"Final checkpoint saved: {final_dir} (step {step}, {episode} episodes)"
            )
        else:
            print(f"Final checkpoint saved: {final_dir}")

        return final_dir

    def get_latest_checkpoint(self) -> Optional[str]:
        """
        Get path to latest checkpoint
        :return: Path to latest checkpoint directory or None
        """
        if not os.path.exists(self.save_dir):
            return None

        checkpoints = [
            d
            for d in os.listdir(self.save_dir)
            if os.path.isdir(os.path.join(self.save_dir, d)) and "checkpoint" in d
        ]

        if not checkpoints:
            return None

        # Sort by step number
        checkpoints.sort(
            key=lambda x: int(x.split("step")[-1]) if "step" in x else 0, reverse=True
        )
        return os.path.join(self.save_dir, checkpoints[0])

    def load_checkpoint_metadata(
        self, checkpoint_path: str
    ) -> Optional[Dict[str, Any]]:
        """
        Load metadata from checkpoint
        :param checkpoint_path: Path to checkpoint directory
        :return: Metadata dictionary or None
        """
        metrics_file = os.path.join(checkpoint_path, "metrics.json")
        if not os.path.exists(metrics_file):
            return None

        try:
            with open(metrics_file, "r") as f:
                return json.load(f)
        except Exception:
            return None
