"""
===============================================================================
Comprehensive Test Suite for Vision: In-Memory Versioning Engine
===============================================================================
Exhaustively tests:
  1. Low-level Data Structures (Stack, Queue, HashTable, HashNode)
  2. Syntax & Delimiter Validation Parser
  3. Transaction Rollback Engine (Dual-Stack undo/redo)
  4. Write-Ahead Log (WAL) Staging Queue
  5. Content-Addressable Storage (CAS) & Data Deduplication
  6. Commit Graph and Checkout Workflows
===============================================================================
"""

import unittest
from dsa_core import (
    Stack,
    Queue,
    HashTable,
    SyntaxValidator,
    compute_content_fingerprint,
    djb2_hash,
    polynomial_rolling_hash,
    EmptyStackError,
    EmptyQueueError,
    KeyNotFoundError,
)
from version_engine import (
    VersionControlEngine,
    OperationType,
    TransactionRecord,
    StagedChange,
    ContentBlob,
    CommitRecord,
)


class TestStackDataStructure(unittest.TestCase):
    """Rigorous verification of the custom Stack class."""

    def test_push_pop_lifo_order(self):
        s = Stack()
        self.assertTrue(s.is_empty())
        self.assertEqual(len(s), 0)

        s.push(10)
        s.push(20)
        s.push(30)

        self.assertFalse(s.is_empty())
        self.assertEqual(len(s), 3)
        self.assertEqual(s.peek(), 30)

        self.assertEqual(s.pop(), 30)
        self.assertEqual(s.pop(), 20)
        self.assertEqual(s.pop(), 10)
        self.assertTrue(s.is_empty())

    def test_empty_stack_exceptions(self):
        s = Stack()
        with self.assertRaises(EmptyStackError):
            s.pop()
        with self.assertRaises(EmptyStackError):
            s.peek()

    def test_clear_and_iteration(self):
        s = Stack()
        for i in range(5):
            s.push(i)
        self.assertEqual(len(s), 5)
        self.assertEqual(list(s), [4, 3, 2, 1, 0])

        s.clear()
        self.assertTrue(s.is_empty())
        self.assertEqual(len(s), 0)


class TestQueueDataStructure(unittest.TestCase):
    """Rigorous verification of the custom Queue class."""

    def test_enqueue_dequeue_fifo_order(self):
        q = Queue()
        self.assertTrue(q.is_empty())
        self.assertEqual(len(q), 0)

        q.enqueue("A")
        q.enqueue("B")
        q.enqueue("C")

        self.assertFalse(q.is_empty())
        self.assertEqual(len(q), 3)
        self.assertEqual(q.peek(), "A")

        self.assertEqual(q.dequeue(), "A")
        self.assertEqual(q.dequeue(), "B")
        self.assertEqual(q.dequeue(), "C")
        self.assertTrue(q.is_empty())

    def test_empty_queue_exceptions(self):
        q = Queue()
        with self.assertRaises(EmptyQueueError):
            q.dequeue()
        with self.assertRaises(EmptyQueueError):
            q.peek()

    def test_clear_and_iteration(self):
        q = Queue()
        for char in ["x", "y", "z"]:
            q.enqueue(char)
        self.assertEqual(list(q), ["x", "y", "z"])
        q.clear()
        self.assertTrue(q.is_empty())
        self.assertEqual(len(q), 0)


class TestHashTableDataStructure(unittest.TestCase):
    """Rigorous verification of custom HashTable, Separate Chaining & Rehashing."""

    def test_insert_lookup_update(self):
        ht = HashTable(initial_capacity=4)
        ht.put("key1", "val1")
        ht.put("key2", "val2")

        self.assertEqual(ht.get("key1"), "val1")
        self.assertEqual(ht.get("key2"), "val2")
        self.assertIsNone(ht.get("key3"))
        self.assertEqual(ht.get("key3", "default"), "default")

        # Update in-place
        ht.put("key1", "val1_updated")
        self.assertEqual(ht.get("key1"), "val1_updated")
        self.assertEqual(len(ht), 2)

    def test_dynamic_rehashing_expansion(self):
        # Initial capacity 4, threshold 0.75 -> resizing triggers at > 3 items
        ht = HashTable(initial_capacity=4, load_factor_threshold=0.75)
        for i in range(100):
            ht.put(f"item_{i}", i * 10)

        self.assertEqual(len(ht), 100)
        diag = ht.get_diagnostics()
        self.assertGreaterEqual(diag.capacity, 128)
        self.assertLessEqual(diag.load_factor, 0.75)

        # Verify all items remain accessible after dynamic resize
        for i in range(100):
            self.assertEqual(ht.get(f"item_{i}"), i * 10)

    def test_deletion_and_exceptions(self):
        ht = HashTable(initial_capacity=8)
        ht.put("alpha", 1)
        ht.put("beta", 2)

        self.assertTrue(ht.contains("alpha"))
        self.assertTrue(ht.delete("alpha"))
        self.assertFalse(ht.contains("alpha"))
        self.assertFalse(ht.delete("alpha"))

        with self.assertRaises(KeyNotFoundError):
            _ = ht["alpha"]


class TestSyntaxValidator(unittest.TestCase):
    """Verification of the Stack-based delimiter validation engine."""

    def test_valid_bracket_structures(self):
        cases = [
            "()",
            "[]",
            "{}",
            "({[]})",
            "def foo(x): return [y for y in {1, 2, (3, 4)}]",
            "a = [(1 + 2) * {3 - 4}]",
            ""
        ]
        for c in cases:
            res = SyntaxValidator.validate(c)
            self.assertTrue(res.is_valid, f"Failed for valid case: {c}")

    def test_unmatched_closing_delimiter(self):
        res = SyntaxValidator.validate("def foo(): return 1)")
        self.assertFalse(res.is_valid)
        self.assertIn("Extraneous closing delimiter ')'", res.error_message)

    def test_mismatched_pair_delimiter(self):
        res = SyntaxValidator.validate("def foo(): return (1 + 2]")
        self.assertFalse(res.is_valid)
        self.assertIn("Mismatched closing delimiter ']'", res.error_message)

    def test_unclosed_delimiter(self):
        res = SyntaxValidator.validate("def foo(): return {1, 2, 3")
        self.assertFalse(res.is_valid)
        self.assertIn("Unclosed delimiter '{'", res.error_message)


class TestTransactionRollbackEngine(unittest.TestCase):
    """Verification of dual-stack rollback and redo mechanics."""

    def test_undo_and_redo_cycle(self):
        engine = VersionControlEngine()

        # Step 1: Write initial
        engine.write_replace("Initial Line", "Initial")
        self.assertEqual(engine.working_buffer, "Initial Line")

        # Step 2: Append line
        engine.write_append("\nSecond Line", "Append")
        self.assertEqual(engine.working_buffer, "Initial Line\nSecond Line")

        # Step 3: Undo append
        ok, rec, msg = engine.undo()
        self.assertTrue(ok)
        self.assertEqual(engine.working_buffer, "Initial Line")

        # Step 4: Redo append
        ok, rec, msg = engine.redo()
        self.assertTrue(ok)
        self.assertEqual(engine.working_buffer, "Initial Line\nSecond Line")

    def test_redo_invalidation_on_new_write(self):
        engine = VersionControlEngine()
        engine.write_replace("Version A")
        engine.write_replace("Version B")
        engine.undo()
        self.assertEqual(engine.working_buffer, "Version A")
        self.assertEqual(engine.rollback_engine.redo_depth, 1)

        # New write must clear redo stack
        engine.write_replace("Version C")
        self.assertEqual(engine.rollback_engine.redo_depth, 0)
        ok, rec, msg = engine.redo()
        self.assertFalse(ok)


class TestCASAndDeduplication(unittest.TestCase):
    """Verification of content-addressable storage, hashing, and deduplication."""

    def test_deduplication_exact_match(self):
        engine = VersionControlEngine()

        code_snippet = "function calculateTotal(items) {\n    return items.reduce((a, b) => a + b, 0);\n}"

        # Commit 1
        engine.write_replace(code_snippet)
        engine.stage()
        ok, c1, _ = engine.commit("Commit 1")
        self.assertTrue(ok)
        self.assertFalse(c1.is_deduplicated)

        # Commit 2 (modified)
        engine.write_append("\n// added comment")
        engine.stage()
        ok, c2, _ = engine.commit("Commit 2")
        self.assertTrue(ok)
        self.assertFalse(c2.is_deduplicated)

        # Commit 3 (revert to exact Commit 1 code)
        engine.write_replace(code_snippet)
        engine.stage()
        ok, c3, _ = engine.commit("Commit 3 Revert")
        self.assertTrue(ok)
        self.assertTrue(c3.is_deduplicated, "Commit 3 must be deduplicated against Commit 1")
        self.assertEqual(c1.blob_hash, c3.blob_hash)

        # Telemetry verification
        tele = engine.cas_storage.get_telemetry()
        self.assertEqual(tele.total_commit_payloads, 3)
        self.assertEqual(tele.unique_blobs, 2)
        self.assertEqual(tele.dedup_hits, 1)
        self.assertGreater(tele.bytes_saved, 0)


class TestCheckoutAndHistory(unittest.TestCase):
    """Verification of commit checkout and history restoration."""

    def test_checkout_restores_buffer(self):
        engine = VersionControlEngine()

        engine.write_replace("State 1: Root Alpha")
        engine.stage()
        _, c1, _ = engine.commit("Init Alpha")

        engine.write_replace("State 2: Beta Features")
        engine.stage()
        _, c2, _ = engine.commit("Feature Beta")

        # Verify current buffer
        self.assertEqual(engine.working_buffer, "State 2: Beta Features")

        # Checkout c1
        ok, checked_c, msg = engine.checkout(c1.commit_id)
        self.assertTrue(ok)
        self.assertEqual(engine.working_buffer, "State 1: Root Alpha")
        self.assertEqual(engine.head_commit_id, c1.commit_id)

        # Undo the checkout itself (since checkout is recorded as a transaction!)
        ok, undo_rec, _ = engine.undo()
        self.assertTrue(ok)
        self.assertEqual(engine.working_buffer, "State 2: Beta Features")


if __name__ == "__main__":
    unittest.main()

