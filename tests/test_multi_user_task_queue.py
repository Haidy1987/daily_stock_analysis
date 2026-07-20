# -*- coding: utf-8 -*-
"""Task queue user scoping for multi-user async analysis."""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from src.services.task_queue import AnalysisTaskQueue, TaskInfo, TaskStatus, _analyzing_dedupe_key


class MultiUserTaskQueueTestCase(unittest.TestCase):
    def setUp(self) -> None:
        AnalysisTaskQueue._instance = None
        self.queue = AnalysisTaskQueue(max_workers=1)
        self.queue._executor = MagicMock()

    def tearDown(self) -> None:
        AnalysisTaskQueue._instance = None

    def _put_task(self, task_id: str, user_id: int, code: str = "600519") -> TaskInfo:
        task = TaskInfo(
            task_id=task_id,
            stock_code=code,
            status=TaskStatus.PENDING,
            user_id=user_id,
        )
        with self.queue._data_lock:
            self.queue._tasks[task_id] = task
        return task

    def test_get_task_respects_user_id(self) -> None:
        self._put_task("t-alice", user_id=1)
        self.assertIsNotNone(self.queue.get_task("t-alice", user_id=1))
        self.assertIsNone(self.queue.get_task("t-alice", user_id=2))

    def test_list_and_stats_are_scoped(self) -> None:
        self._put_task("t-a", user_id=1)
        self._put_task("t-b", user_id=2, code="000001")
        self.assertEqual([t.task_id for t in self.queue.list_all_tasks(user_id=1)], ["t-a"])
        self.assertEqual([t.task_id for t in self.queue.list_all_tasks(user_id=2)], ["t-b"])
        self.assertEqual(self.queue.get_task_stats(user_id=1)["pending"], 1)
        self.assertEqual(self.queue.get_task_stats(user_id=2)["pending"], 1)
        self.assertEqual(self.queue.get_task_stats(user_id=1)["total"], 1)

    def test_analyzing_dedupe_is_per_user(self) -> None:
        with self.queue._data_lock:
            self.queue._analyzing_stocks[_analyzing_dedupe_key(1, "600519")] = "t-a"
        self.assertTrue(self.queue.is_analyzing("600519", user_id=1))
        self.assertFalse(self.queue.is_analyzing("600519", user_id=2))


if __name__ == "__main__":
    unittest.main()
