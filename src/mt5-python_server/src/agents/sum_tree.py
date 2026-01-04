"""
SumTree data structure for Prioritized Experience Replay
Efficiently stores priorities and allows O(log n) sampling
"""

import numpy as np
from typing import List, Tuple


class SumTree:
    """
    Binary tree for efficient priority sampling
    Used in Prioritized Experience Replay (PER)
    """

    def __init__(self, capacity: int):
        """
        Initialize SumTree

        :param capacity: Maximum number of experiences to store
        """
        self.capacity = capacity
        # Tree structure: parent nodes store sum of children
        # Tree has capacity leaf nodes, so we need 2*capacity - 1 total nodes
        self.tree = np.zeros(2 * capacity - 1)
        # Data storage for experiences
        self.data = np.zeros(capacity, dtype=object)
        self.write = 0
        self.n_entries = 0

    def _propagate(self, idx: int, change: float):
        """
        Update tree after priority change
        Propagates change up the tree

        :param idx: Index of node to update
        :param change: Change in priority value
        """
        parent = (idx - 1) // 2
        self.tree[parent] += change
        if parent != 0:
            self._propagate(parent, change)

    def _retrieve(self, idx: int, s: float) -> int:
        """
        Find leaf node with given sum value

        :param idx: Current node index
        :param s: Sum value to search for
        :return: Leaf node index
        """
        left = 2 * idx + 1
        right = left + 1

        if left >= len(self.tree):
            return idx

        if s <= self.tree[left]:
            return self._retrieve(left, s)
        else:
            return self._retrieve(right, s - self.tree[left])

    def total(self) -> float:
        """
        Get total sum of all priorities

        :return: Total priority sum
        """
        return self.tree[0]

    def add(self, priority: float, data: Tuple):
        """
        Add experience with priority

        :param priority: Priority value (TD-error)
        :param data: Experience tuple (state, action, reward, next_state, done)
        """
        idx = self.write + self.capacity - 1

        self.data[self.write] = data
        self.update(idx, priority)

        self.write += 1
        if self.write >= self.capacity:
            self.write = 0

        if self.n_entries < self.capacity:
            self.n_entries += 1

    def update(self, idx: int, priority: float):
        """
        Update priority of experience at given index

        :param idx: Tree index (leaf node)
        :param priority: New priority value
        """
        change = priority - self.tree[idx]
        self.tree[idx] = priority
        self._propagate(idx, change)

    def get(self, s: float) -> Tuple[int, float, Tuple]:
        """
        Get experience with given sum value

        :param s: Sum value to search for
        :return: (tree_idx, priority, data)
        """
        idx = self._retrieve(0, s)
        data_idx = idx - self.capacity + 1
        return idx, self.tree[idx], self.data[data_idx]

    def sample(self, n: int) -> Tuple[List[int], List[Tuple], List[float]]:
        """
        Sample n experiences based on priority

        :param n: Number of experiences to sample
        :return: (indices, experiences, priorities)
        """
        batch_idx = []
        batch = []
        priorities = []

        segment = self.total() / n

        for i in range(n):
            a = segment * i
            b = segment * (i + 1)
            s = np.random.uniform(a, b)
            idx, priority, data = self.get(s)
            batch_idx.append(idx)
            batch.append(data)
            priorities.append(priority)

        return batch_idx, batch, priorities

    def __len__(self) -> int:
        """Get number of stored experiences"""
        return self.n_entries
