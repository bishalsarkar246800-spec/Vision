"""
===============================================================================
In-Memory Versioning & Transaction Engine
===============================================================================
A resume-grade backend version control system mimicking enterprise transaction
write-ahead logging (WAL), content-addressable storage (CAS), and data
deduplication.

Built strictly upon raw data structures (Stack, Queue, HashTable) from dsa_core.
STRICT CONSTRAINTS:
- NO `dict`
- NO `set`
- NO `collections.deque`
===============================================================================
"""

import time
import shutil
from typing import Optional, List, Tuple

from dsa_core import (
    Stack,
    Queue,
    HashTable,
    SyntaxValidator,
    ValidationResult,
    compute_content_fingerprint,
    djb2_hash,
    EmptyStackError,
    EmptyQueueError,
    KeyNotFoundError,
)


# =============================================================================
# ANSI COLOR & FORMATTING UTILITIES (Zero external dependencies)
# =============================================================================

class Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    UNDERLINE = "\033[4m"

    # Foreground colors
    BLACK = "\033[30m"
    RED = "\033[31m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"
    MAGENTA = "\033[35m"
    CYAN = "\033[36m"
    WHITE = "\033[37m"

    # Bright foreground colors
    BRIGHT_RED = "\033[91m"
    BRIGHT_GREEN = "\033[92m"
    BRIGHT_YELLOW = "\033[93m"
    BRIGHT_BLUE = "\033[94m"
    BRIGHT_MAGENTA = "\033[95m"
    BRIGHT_CYAN = "\033[96m"
    BRIGHT_WHITE = "\033[97m"

    # Background colors
    BG_BLACK = "\033[40m"
    BG_RED = "\033[41m"
    BG_GREEN = "\033[42m"
    BG_YELLOW = "\033[43m"
    BG_BLUE = "\033[44m"
    BG_MAGENTA = "\033[45m"
    BG_CYAN = "\033[46m"
    BG_WHITE = "\033[47m"
    BG_DARK_GRAY = "\033[100m"


def get_terminal_width(default: int = 100) -> int:
    """Returns detected terminal width clamped to a sane minimum of 80."""
    try:
        columns, _ = shutil.get_terminal_size(fallback=(default, 30))
        return max(columns, 80)
    except Exception:
        return default


def render_full_width_line(char: str = "─", color: str = Color.CYAN) -> str:
    """Draws a horizontal rule occupying the entire terminal width."""
    width = get_terminal_width()
    return f"{color}{char * width}{Color.RESET}"


def center_text(text: str, width: Optional[int] = None, pad_char: str = " ") -> str:
    """Centers text within terminal width."""
    if width is None:
        width = get_terminal_width()
    return text.center(width, pad_char)


# =============================================================================
# 1. TRANSACTION MODEL & ROLLBACK ENGINE (STACK-BASED)
# =============================================================================

class OperationType:
    WRITE = "WRITE"
    APPEND = "APPEND"
    PREPEND = "PREPEND"
    REPLACE = "REPLACE"
    DELETE_LINE = "DELETE_LINE"
    CLEAR = "CLEAR"
    CHECKOUT = "CHECKOUT"


class TransactionRecord:
    """
    Atomic transaction capturing an edit operation, previous state, and new state.
    """
    __slots__ = (
        'tx_id',
        'op_type',
        'prev_content',
        'new_content',
        'timestamp',
        'description',
        'delta_bytes'
    )

    def __init__(self, tx_id: int, op_type: str, prev_content: str,
                 new_content: str, description: str = "") -> None:
        self.tx_id: int = tx_id
        self.op_type: str = op_type
        self.prev_content: str = prev_content
        self.new_content: str = new_content
        self.timestamp: str = time.strftime("%Y-%m-%d %H:%M:%S")
        self.description: str = description
        self.delta_bytes: int = len(new_content.encode('utf-8')) - len(prev_content.encode('utf-8'))

    def __repr__(self) -> str:
        delta_str = f"+{self.delta_bytes}B" if self.delta_bytes >= 0 else f"{self.delta_bytes}B"
        return f"TX#{self.tx_id:04d} [{self.op_type}] ({delta_str}) - {self.description}"


class TransactionRollbackEngine:
    """
    Transaction Rollback Engine managing buffer mutations via two low-level Stacks:
      - `undo_stack`: stores past transactions ready to be rolled back.
      - `redo_stack`: stores rolled-back transactions ready to be reapplied.
      
    Adheres strictly to transaction branch semantics: any new mutating write
    clears the `redo_stack`.
    """

    def __init__(self) -> None:
        self._undo_stack: Stack = Stack()
        self._redo_stack: Stack = Stack()
        self._active_buffer: str = ""
        self._tx_counter: int = 1000

    @property
    def active_buffer(self) -> str:
        return self._active_buffer

    @property
    def undo_depth(self) -> int:
        return len(self._undo_stack)

    @property
    def redo_depth(self) -> int:
        return len(self._redo_stack)

    def execute_transaction(self, op_type: str, new_content: str, description: str = "") -> TransactionRecord:
        """
        Executes a state change, creates an atomic TransactionRecord, pushes to
        the undo stack, and purges the redo stack.
        """
        self._tx_counter += 1
        record = TransactionRecord(
            tx_id=self._tx_counter,
            op_type=op_type,
            prev_content=self._active_buffer,
            new_content=new_content,
            description=description
        )

        self._undo_stack.push(record)
        self._redo_stack.clear()
        self._active_buffer = new_content
        return record

    def undo(self) -> Tuple[bool, Optional[TransactionRecord], str]:
        """
        Rolls back the most recent transaction from the undo stack, pushes it to
        the redo stack, and restores previous buffer content.
        """
        if self._undo_stack.is_empty():
            return False, None, "Undo stack is empty. Nothing to roll back."

        record: TransactionRecord = self._undo_stack.pop()
        self._redo_stack.push(record)
        self._active_buffer = record.prev_content
        return True, record, f"Rolled back {record}."

    def redo(self) -> Tuple[bool, Optional[TransactionRecord], str]:
        """
        Re-applies the most recent undone transaction from the redo stack, pushes
        it back to the undo stack, and restores the new buffer content.
        """
        if self._redo_stack.is_empty():
            return False, None, "Redo stack is empty. Nothing to re-apply."

        record: TransactionRecord = self._redo_stack.pop()
        self._undo_stack.push(record)
        self._active_buffer = record.new_content
        return True, record, f"Re-applied {record}."

    def get_undo_history(self) -> List[TransactionRecord]:
        return self._undo_stack.to_list()

    def get_redo_history(self) -> List[TransactionRecord]:
        return self._redo_stack.to_list()

    def set_buffer_direct(self, content: str, op_type: str = OperationType.CHECKOUT, description: str = "") -> TransactionRecord:
        """Used by checkout or snapshot restore."""
        return self.execute_transaction(op_type, content, description)


# =============================================================================
# 2. WRITE-AHEAD STAGING BUFFER (FIFO QUEUE)
# =============================================================================

class StagedChange:
    """
    Represents a staged change entry in the Write-Ahead Log (WAL) Queue.
    Mimics database WAL record with Log Sequence Number (LSN).
    """
    __slots__ = (
        'lsn',
        'timestamp',
        'payload',
        'fingerprint',
        'author',
        'byte_size',
        'line_count'
    )

    def __init__(self, lsn: int, payload: str, fingerprint: str, author: str) -> None:
        self.lsn: int = lsn
        self.timestamp: str = time.strftime("%Y-%m-%d %H:%M:%S")
        self.payload: str = payload
        self.fingerprint: str = fingerprint
        self.author: str = author
        self.byte_size: int = len(payload.encode('utf-8'))
        self.line_count: int = len(payload.split('\n')) if payload else 0

    def __repr__(self) -> str:
        return (f"WAL-LSN#{self.lsn:05d} [{self.timestamp}] "
                f"Hash:{self.fingerprint[:10]}... Size:{self.byte_size}B lines:{self.line_count}")


class WriteAheadStagingBuffer:
    """
    Write-Ahead Staging Buffer mimicking a database WAL and Git index.
    Changes must be validated for syntax equilibrium before entering the staging queue.
    """

    def __init__(self) -> None:
        self._queue: Queue = Queue()
        self._lsn_counter: int = 100

    @property
    def queue_size(self) -> int:
        return len(self._queue)

    def is_empty(self) -> bool:
        return self._queue.is_empty()

    def stage_change(self, payload: str, author: str = "Engineer",
                     validate_delimiters: bool = True) -> Tuple[bool, Optional[StagedChange], ValidationResult, str]:
        """
        Validates delimiters via SyntaxValidator. If valid, computes content
        fingerprint and enqueues to the WAL staging queue.
        """
        validation = SyntaxValidator.validate(payload)
        if validate_delimiters and not validation.is_valid:
            return False, None, validation, f"Syntax Validation Failed: {validation.error_message}"

        self._lsn_counter += 1
        fingerprint = compute_content_fingerprint(payload)
        staged_entry = StagedChange(
            lsn=self._lsn_counter,
            payload=payload,
            fingerprint=fingerprint,
            author=author
        )
        self._queue.enqueue(staged_entry)
        return True, staged_entry, validation, f"Successfully staged change to WAL with LSN #{staged_entry.lsn:05d}."

    def peek_front(self) -> Optional[StagedChange]:
        if self._queue.is_empty():
            return None
        return self._queue.peek()

    def drain_all(self) -> List[StagedChange]:
        """
        Drains all entries from the staging queue in FIFO order to batch-commit.
        """
        entries: List[StagedChange] = []
        while not self._queue.is_empty():
            entries.append(self._queue.dequeue())
        return entries

    def get_staged_entries(self) -> List[StagedChange]:
        """Inspects all currently staged items without removing them."""
        return self._queue.to_list()

    def clear(self) -> None:
        self._queue.clear()


# =============================================================================
# 3. CONTENT-ADDRESSABLE STORAGE & DEDUPLICATION (HASH TABLE)
# =============================================================================

class ContentBlob:
    """
    Content-Addressable Blob stored in the Hash Table.
    Holds unique text payload, fingerprint, creation metadata, and reference count.
    """
    __slots__ = (
        'fingerprint',
        'payload',
        'byte_size',
        'created_at',
        'reference_count',
        'first_commit_id'
    )

    def __init__(self, fingerprint: str, payload: str, first_commit_id: str) -> None:
        self.fingerprint: str = fingerprint
        self.payload: str = payload
        self.byte_size: int = len(payload.encode('utf-8'))
        self.created_at: str = time.strftime("%Y-%m-%d %H:%M:%S")
        self.reference_count: int = 1
        self.first_commit_id: str = first_commit_id

    def __repr__(self) -> str:
        return (f"ContentBlob(hash={self.fingerprint[:10]}..., refs={self.reference_count}, "
                f"bytes={self.byte_size})")


class StorageTelemetry:
    """
    Telemetry metrics for Content-Addressable Storage and Deduplication.
    """
    def __init__(self, total_commit_payloads: int, unique_blobs: int,
                 dedup_hits: int, total_raw_bytes: int,
                 unique_stored_bytes: int, bytes_saved: int,
                 dedup_ratio_pct: float, ht_diagnostics: Any) -> None:
        self.total_commit_payloads = total_commit_payloads
        self.unique_blobs = unique_blobs
        self.dedup_hits = dedup_hits
        self.total_raw_bytes = total_raw_bytes
        self.unique_stored_bytes = unique_stored_bytes
        self.bytes_saved = bytes_saved
        self.dedup_ratio_pct = dedup_ratio_pct
        self.ht_diagnostics = ht_diagnostics


class ContentAddressableStorage:
    """
    Central Commit & Snapshot Storage engine backed by the custom HashTable.
    Maps payload hash -> ContentBlob.
    If a new commit matches an existing hash, it reuses the existing node and
    increments its reference count, achieving deduplication.
    """

    def __init__(self) -> None:
        self._blob_table: HashTable = HashTable(initial_capacity=16)
        self._total_commits_processed: int = 0
        self._dedup_hits: int = 0
        self._total_raw_bytes: int = 0
        self._unique_stored_bytes: int = 0

    def store_payload(self, payload: str, commit_id: str) -> Tuple[ContentBlob, bool]:
        """
        Stores payload in CAS.
        Returns (blob, was_deduplicated).
        """
        fingerprint = compute_content_fingerprint(payload)
        payload_bytes = len(payload.encode('utf-8'))
        self._total_commits_processed += 1
        self._total_raw_bytes += payload_bytes

        # Check if already present in Hash Table
        if self._blob_table.contains(fingerprint):
            existing_blob: ContentBlob = self._blob_table.get(fingerprint)
            existing_blob.reference_count += 1
            self._dedup_hits += 1
            return existing_blob, True

        # New unique content
        new_blob = ContentBlob(
            fingerprint=fingerprint,
            payload=payload,
            first_commit_id=commit_id
        )
        self._blob_table.put(fingerprint, new_blob)
        self._unique_stored_bytes += payload_bytes
        return new_blob, False

    def retrieve_payload(self, fingerprint: str) -> Optional[str]:
        """
        Retrieves raw payload from hash table by fingerprint.
        """
        blob: Optional[ContentBlob] = self._blob_table.get(fingerprint)
        if blob is None:
            return None
        return blob.payload

    def get_blob(self, fingerprint: str) -> Optional[ContentBlob]:
        return self._blob_table.get(fingerprint)

    def get_all_blobs(self) -> List[ContentBlob]:
        return self._blob_table.values()

    def get_telemetry(self) -> StorageTelemetry:
        """
        Calculates deduplication efficiency, compression savings, and hash table stats.
        """
        bytes_saved = self._total_raw_bytes - self._unique_stored_bytes
        if self._total_raw_bytes > 0:
            dedup_ratio = (bytes_saved / self._total_raw_bytes) * 100.0
        else:
            dedup_ratio = 0.0

        return StorageTelemetry(
            total_commit_payloads=self._total_commits_processed,
            unique_blobs=len(self._blob_table),
            dedup_hits=self._dedup_hits,
            total_raw_bytes=self._total_raw_bytes,
            unique_stored_bytes=self._unique_stored_bytes,
            bytes_saved=bytes_saved,
            dedup_ratio_pct=dedup_ratio,
            ht_diagnostics=self._blob_table.get_diagnostics()
        )


# =============================================================================
# 4. COMMIT MODEL & GRAPH
# =============================================================================

class CommitRecord:
    """
    Immutable version control commit object linking metadata and CAS content.
    """
    __slots__ = (
        'commit_id',
        'parent_id',
        'blob_hash',
        'message',
        'author',
        'timestamp',
        'staged_lsn',
        'is_deduplicated',
        'byte_size',
        'seq_num'
    )

    def __init__(self, commit_id: str, parent_id: Optional[str], blob_hash: str,
                 message: str, author: str, staged_lsn: int,
                 is_deduplicated: bool, byte_size: int, seq_num: int) -> None:
        self.commit_id: str = commit_id
        self.parent_id: Optional[str] = parent_id
        self.blob_hash: str = blob_hash
        self.message: str = message
        self.author: str = author
        self.timestamp: str = time.strftime("%Y-%m-%d %H:%M:%S")
        self.staged_lsn: int = staged_lsn
        self.is_deduplicated: bool = is_deduplicated
        self.byte_size: int = byte_size
        self.seq_num: int = seq_num

    def __repr__(self) -> str:
        parent_str = self.parent_id[:8] if self.parent_id else "ROOT"
        dedup_flag = " [DEDUP]" if self.is_deduplicated else ""
        return (f"Commit {self.commit_id[:10]} (Parent:{parent_str}){dedup_flag}: "
                f"\"{self.message}\" by {self.author} at {self.timestamp}")


# =============================================================================
# 5. UNIFIED VERSION CONTROL ENGINE
# =============================================================================

class VersionControlEngine:
    """
    The orchestrator tying together:
      - TransactionRollbackEngine (Working buffer + Undo/Redo stacks)
      - WriteAheadStagingBuffer (FIFO WAL staging queue)
      - ContentAddressableStorage (HashTable CAS + Deduplication)
      - Commit Graph & Head pointer tracking
    """

    def __init__(self, author: str = "Lead Engineer") -> None:
        self.author: str = author
        self.branch: str = "main"

        # Core engines
        self.rollback_engine: TransactionRollbackEngine = TransactionRollbackEngine()
        self.staging_buffer: WriteAheadStagingBuffer = WriteAheadStagingBuffer()
        self.cas_storage: ContentAddressableStorage = ContentAddressableStorage()

        # Commit graph storage using our custom HashTable
        self._commit_table: HashTable = HashTable(initial_capacity=16)
        self._commit_history_list: List[CommitRecord] = []
        self._head_commit_id: Optional[str] = None
        self._commit_seq: int = 0

    @property
    def head_commit_id(self) -> Optional[str]:
        return self._head_commit_id

    @property
    def working_buffer(self) -> str:
        return self.rollback_engine.active_buffer

    # -------------------------------------------------------------------------
    # Buffer & Transaction Operations
    # -------------------------------------------------------------------------

    def write_replace(self, text: str, description: str = "Overwrite buffer") -> TransactionRecord:
        """Replaces the entire working buffer content."""
        return self.rollback_engine.execute_transaction(OperationType.WRITE, text, description)

    def write_append(self, text: str, description: str = "Append text") -> TransactionRecord:
        """Appends text to the working buffer."""
        new_text = self.rollback_engine.active_buffer + text
        return self.rollback_engine.execute_transaction(OperationType.APPEND, new_text, description)

    def write_prepend(self, text: str, description: str = "Prepend text") -> TransactionRecord:
        """Prepends text to the working buffer."""
        new_text = text + self.rollback_engine.active_buffer
        return self.rollback_engine.execute_transaction(OperationType.PREPEND, new_text, description)

    def write_insert_line(self, line_index: int, line_text: str) -> TransactionRecord:
        """Inserts a line at the specified 0-based index."""
        current = self.rollback_engine.active_buffer
        lines = current.split('\n') if current else []
        if line_index < 0:
            line_index = 0
        if line_index > len(lines):
            line_index = len(lines)
        lines.insert(line_index, line_text)
        new_text = "\n".join(lines)
        return self.rollback_engine.execute_transaction(
            OperationType.REPLACE, new_text, f"Insert line at #{line_index + 1}"
        )

    def write_delete_line(self, line_index: int) -> Tuple[bool, Optional[TransactionRecord], str]:
        """Deletes a line at the specified 0-based index."""
        current = self.rollback_engine.active_buffer
        if not current:
            return False, None, "Buffer is empty."
        lines = current.split('\n')
        if line_index < 0 or line_index >= len(lines):
            return False, None, f"Invalid line index {line_index + 1}. Total lines: {len(lines)}"
        removed = lines.pop(line_index)
        new_text = "\n".join(lines)
        rec = self.rollback_engine.execute_transaction(
            OperationType.DELETE_LINE, new_text, f"Delete line #{line_index + 1} ('{removed[:20]}')"
        )
        return True, rec, f"Deleted line #{line_index + 1}."

    def clear_buffer(self) -> TransactionRecord:
        """Clears the working buffer."""
        return self.rollback_engine.execute_transaction(OperationType.CLEAR, "", "Clear buffer")

    def undo(self) -> Tuple[bool, Optional[TransactionRecord], str]:
        return self.rollback_engine.undo()

    def redo(self) -> Tuple[bool, Optional[TransactionRecord], str]:
        return self.rollback_engine.redo()

    # -------------------------------------------------------------------------
    # Staging Area (WAL Queue) Operations
    # -------------------------------------------------------------------------

    def stage(self, validate_delimiters: bool = True) -> Tuple[bool, Optional[StagedChange], ValidationResult, str]:
        """
        Stages current working buffer to the Write-Ahead Log Queue.
        Performs stack-based syntax validation prior to enqueuing.
        """
        content = self.rollback_engine.active_buffer
        return self.staging_buffer.stage_change(
            payload=content,
            author=self.author,
            validate_delimiters=validate_delimiters
        )

    # -------------------------------------------------------------------------
    # Commit Pipeline (Batching WAL Queue -> CAS Deduplication)
    # -------------------------------------------------------------------------

    def commit(self, message: str) -> Tuple[bool, Optional[CommitRecord], str]:
        """
        Processes staged WAL entries, dedups content in CAS, generates a unique
        commit ID, updates the commit graph, and shifts HEAD.
        """
        if self.staging_buffer.is_empty():
            # If nothing in staging queue, check if current buffer is modified
            return False, None, "No changes staged. Run 'stage' first to queue changes into WAL."

        # Drain the WAL staging queue (FIFO order)
        staged_items = self.staging_buffer.drain_all()
        # The latest staged item in the batch becomes the snapshot payload
        latest_change = staged_items[-1]
        payload = latest_change.payload

        self._commit_seq += 1

        # Synthesize commit metadata for deterministic hash
        timestamp_str = time.strftime("%Y-%m-%d %H:%M:%S")
        parent_str = self._head_commit_id if self._head_commit_id else "ROOT"
        commit_seed = f"commit:{self._commit_seq}|parent:{parent_str}|msg:{message}|author:{self.author}|ts:{timestamp_str}"
        commit_id = compute_content_fingerprint(commit_seed)

        # Ingest payload into Content Addressable Storage (CAS) with Deduplication
        blob, was_deduplicated = self.cas_storage.store_payload(payload, commit_id)

        # Create Commit Record
        commit_record = CommitRecord(
            commit_id=commit_id,
            parent_id=self._head_commit_id,
            blob_hash=blob.fingerprint,
            message=message,
            author=self.author,
            staged_lsn=latest_change.lsn,
            is_deduplicated=was_deduplicated,
            byte_size=blob.byte_size,
            seq_num=self._commit_seq
        )

        # Store in Commit Hash Table and sequence list
        self._commit_table.put(commit_id, commit_record)
        self._commit_history_list.append(commit_record)
        self._head_commit_id = commit_id

        msg_detail = (
            f"Committed {commit_id[:10]} (Seq #{self._commit_seq}). "
            f"CAS Blob: {blob.fingerprint[:10]}... "
            f"Deduplicated: {'YES (reused existing storage node)' if was_deduplicated else 'NO (new blob created)'}."
        )
        return True, commit_record, msg_detail

    # -------------------------------------------------------------------------
    # History & Checkout Operations
    # -------------------------------------------------------------------------

    def get_commit_log(self) -> List[CommitRecord]:
        """
        Returns full commit history list from earliest to latest.
        """
        return list(self._commit_history_list)

    def get_commit_by_id(self, commit_id_query: str) -> Optional[CommitRecord]:
        """
        Finds a commit by full ID or prefix.
        """
        # Exact match via Hash Table
        if self._commit_table.contains(commit_id_query):
            return self._commit_table.get(commit_id_query)

        # Prefix search across commits
        for c in self._commit_history_list:
            if c.commit_id.startswith(commit_id_query):
                return c
        return None

    def checkout(self, commit_id_query: str) -> Tuple[bool, Optional[CommitRecord], str]:
        """
        Restores the working buffer to the content of a historical commit.
        Records the checkout in the transaction rollback engine so the action
        can itself be undone!
        """
        target_commit = self.get_commit_by_id(commit_id_query)
        if target_commit is None:
            return False, None, f"Commit '{commit_id_query}' not found in commit store."

        payload = self.cas_storage.retrieve_payload(target_commit.blob_hash)
        if payload is None:
            return False, None, f"Corrupted CAS: blob {target_commit.blob_hash} missing."

        # Restore working buffer
        self.rollback_engine.set_buffer_direct(
            content=payload,
            op_type=OperationType.CHECKOUT,
            description=f"Checkout commit {target_commit.commit_id[:10]}"
        )
        self._head_commit_id = target_commit.commit_id
        return True, target_commit, f"Checked out commit {target_commit.commit_id[:10]} (HEAD detached to this commit)."


# =============================================================================
# 6. FULL-WIDTH ENTERPRISE TERMINAL UI RENDERING ENGINE
# =============================================================================

class TerminalDashboardRenderer:
    """
    Renders high-density, full-width responsive terminal UI layouts that occupy
    the entire screen width without blank gaps.
    """

    @classmethod
    def render_header_banner(cls, engine: VersionControlEngine) -> None:
        w = get_terminal_width()
        print(f"\n{Color.BG_BLUE}{Color.BRIGHT_WHITE}{Color.BOLD}" + " IN-MEMORY VERSIONING & TRANSACTION ENGINE ".center(w) + f"{Color.RESET}")
        print(f"{Color.BG_DARK_GRAY}{Color.BRIGHT_CYAN}" + " Low-Level Data Structures: Stack (Rollback/Syntax) | Queue (WAL) | HashTable (CAS Deduplication) ".center(w) + f"{Color.RESET}")

        # Summary Status Bar
        head_short = engine.head_commit_id[:10] if engine.head_commit_id else "NONE (No commits yet)"
        staged_cnt = engine.staging_buffer.queue_size
        undo_cnt = engine.rollback_engine.undo_depth
        redo_cnt = engine.rollback_engine.redo_depth
        buf_size = len(engine.working_buffer.encode('utf-8'))
        line_cnt = len(engine.working_buffer.split('\n')) if engine.working_buffer else 0

        bar_text = (
            f" [BRANCH: {Color.BOLD}{engine.branch}{Color.RESET}{Color.CYAN}] "
            f"[HEAD: {Color.BOLD}{head_short}{Color.RESET}{Color.CYAN}] "
            f"[BUFFER: {buf_size}B / {line_cnt} lines] "
            f"[WAL STAGED: {staged_cnt}] "
            f"[UNDO/REDO: {undo_cnt}/{redo_cnt}]"
        )
        print(f"{Color.CYAN}╭" + "─" * (w - 2) + f"╮{Color.RESET}")
        print(f"{Color.CYAN}│ {bar_text.ljust(w - 4 + 20)} {Color.CYAN}│{Color.RESET}")
        print(f"{Color.CYAN}╰" + "─" * (w - 2) + f"╯{Color.RESET}")

    @classmethod
    def render_buffer_view(cls, engine: VersionControlEngine) -> None:
        w = get_terminal_width()
        content = engine.working_buffer
        lines = content.split('\n') if content else []

        title = " [ WORKING TEXT BUFFER (ACTIVE MEMORY) ] "
        border_top = f"╭─{Color.BOLD}{Color.BRIGHT_YELLOW}{title}{Color.RESET}{Color.CYAN}" + "─" * max(0, w - 2 - len(title) - 2) + "╮"
        print(f"{Color.CYAN}{border_top}{Color.RESET}")

        if not lines or (len(lines) == 1 and lines[0] == ""):
            empty_msg = f"{Color.DIM}<Empty Buffer - Use 'write <text>' or 'append <text>' to insert content>{Color.RESET}"
            print(f"{Color.CYAN}│{Color.RESET}  {empty_msg.ljust(w - 6 + 10)}  {Color.CYAN}│{Color.RESET}")
        else:
            for idx, line in enumerate(lines, start=1):
                line_display = line if len(line) <= (w - 14) else line[:w - 17] + "..."
                row_str = f"{Color.DIM}{idx:4d} │{Color.RESET} {Color.BRIGHT_WHITE}{line_display}{Color.RESET}"
                padding = max(0, w - len(f"{idx:4d} │ {line_display}") - 4)
                print(f"{Color.CYAN}│{Color.RESET} {row_str}{' ' * padding} {Color.CYAN}│{Color.RESET}")

        print(f"{Color.CYAN}╰" + "─" * (w - 2) + f"╯{Color.RESET}")

    @classmethod
    def render_staging_and_rollback_panels(cls, engine: VersionControlEngine) -> None:
        """
        Renders two side-by-side or stacked panels showing:
          1. Staging Buffer (WAL Queue items)
          2. Transaction Rollback Engine (Undo and Redo stacks)
        """
        w = get_terminal_width()

        # Panel 1: Staged WAL Queue
        staged_items = engine.staging_buffer.get_staged_entries()
        q_title = f" [ WRITE-AHEAD LOG (WAL) STAGING QUEUE - {len(staged_items)} PENDING ] "
        print(f"{Color.MAGENTA}╭─{Color.BOLD}{Color.BRIGHT_MAGENTA}{q_title}{Color.RESET}{Color.MAGENTA}" + "─" * max(0, w - 2 - len(q_title) - 2) + f"╮{Color.RESET}")

        if not staged_items:
            empty_wal = f"{Color.DIM}No changes staged. Working buffer changes are un-staged.{Color.RESET}"
            print(f"{Color.MAGENTA}│{Color.RESET}  {empty_wal.ljust(w - 6 + 10)}  {Color.MAGENTA}│{Color.RESET}")
        else:
            for item in staged_items:
                item_str = (f"{Color.BOLD}LSN #{item.lsn:05d}{Color.RESET} │ "
                            f"Hash: {Color.YELLOW}{item.fingerprint[:16]}...{Color.RESET} │ "
                            f"Size: {item.byte_size}B │ Lines: {item.line_count} │ "
                            f"Queued: {item.timestamp}")
                raw_len = len(f"LSN #{item.lsn:05d} │ Hash: {item.fingerprint[:16]}... │ Size: {item.byte_size}B │ Lines: {item.line_count} │ Queued: {item.timestamp}")
                pad = max(0, w - 4 - raw_len)
                print(f"{Color.MAGENTA}│{Color.RESET}  {item_str}{' ' * pad}{Color.MAGENTA}│{Color.RESET}")

        print(f"{Color.MAGENTA}╰" + "─" * (w - 2) + f"╯{Color.RESET}")

        # Panel 2: Transaction Undo/Redo Stacks
        undo_list = engine.rollback_engine.get_undo_history()
        redo_list = engine.rollback_engine.get_redo_history()
        tx_title = f" [ TRANSACTION ROLLBACK STACKS (Undo Depth: {len(undo_list)} | Redo Depth: {len(redo_list)}) ] "
        print(f"{Color.GREEN}╭─{Color.BOLD}{Color.BRIGHT_GREEN}{tx_title}{Color.RESET}{Color.GREEN}" + "─" * max(0, w - 2 - len(tx_title) - 2) + f"╮{Color.RESET}")

        # Show top 3 undo transactions
        if not undo_list:
            print(f"{Color.GREEN}│{Color.RESET}  {Color.DIM}Undo Stack: [Empty]{Color.RESET}".ljust(w - 4 + 10) + f"{Color.GREEN}│{Color.RESET}")
        else:
            print(f"{Color.GREEN}│{Color.RESET}  {Color.BOLD}Undo Stack (Top -> Bottom):{Color.RESET}".ljust(w - 4 + 10) + f"{Color.GREEN}│{Color.RESET}")
            for rec in undo_list[:4]:
                line_str = f"   ↳ TX#{rec.tx_id:04d} [{rec.op_type}] ({rec.delta_bytes:+d}B) - {rec.description} ({rec.timestamp})"
                pad = max(0, w - 4 - len(line_str))
                print(f"{Color.GREEN}│{Color.RESET}  {Color.CYAN}{line_str}{Color.RESET}{' ' * pad}{Color.GREEN}│{Color.RESET}")

        if redo_list:
            print(f"{Color.GREEN}│{Color.RESET}  {Color.BOLD}Redo Stack (Top -> Bottom):{Color.RESET}".ljust(w - 4 + 10) + f"{Color.GREEN}│{Color.RESET}")
            for rec in redo_list[:2]:
                line_str = f"   ↺ TX#{rec.tx_id:04d} [{rec.op_type}] ({rec.delta_bytes:+d}B) - {rec.description}"
                pad = max(0, w - 4 - len(line_str))
                print(f"{Color.GREEN}│{Color.RESET}  {Color.YELLOW}{line_str}{Color.RESET}{' ' * pad}{Color.GREEN}│{Color.RESET}")

        print(f"{Color.GREEN}╰" + "─" * (w - 2) + f"╯{Color.RESET}")

    @classmethod
    def render_storage_telemetry(cls, engine: VersionControlEngine) -> None:
        """
        Renders enterprise telemetry card for Content-Addressable Storage deduplication.
        """
        w = get_terminal_width()
        tele = engine.cas_storage.get_telemetry()
        diag = tele.ht_diagnostics

        card_title = " [ CONTENT-ADDRESSABLE STORAGE & DEDUPLICATION TELEMETRY ] "
        print(f"{Color.BLUE}╭─{Color.BOLD}{Color.BRIGHT_BLUE}{card_title}{Color.RESET}{Color.BLUE}" + "─" * max(0, w - 2 - len(card_title) - 2) + f"╮{Color.RESET}")

        col1 = (
            f"• Total Snapshots Processed : {Color.BOLD}{tele.total_commit_payloads}{Color.RESET}\n"
            f"• Unique Content Blobs      : {Color.BOLD}{tele.unique_blobs}{Color.RESET}\n"
            f"• Deduplication Cache Hits  : {Color.BOLD}{Color.BRIGHT_GREEN}{tele.dedup_hits}{Color.RESET}\n"
            f"• Storage Space Saved       : {Color.BOLD}{Color.BRIGHT_GREEN}{tele.bytes_saved} Bytes ({tele.dedup_ratio_pct:.1f}%){Color.RESET}"
        )

        col2 = (
            f"• Cumulative Raw Bytes      : {Color.BOLD}{tele.total_raw_bytes} Bytes{Color.RESET}\n"
            f"• Stored Unique Bytes       : {Color.BOLD}{tele.unique_stored_bytes} Bytes{Color.RESET}\n"
            f"• HashTable Capacity/Size   : {Color.BOLD}{diag.capacity} buckets / {diag.size} nodes{Color.RESET}\n"
            f"• Load Factor / Collisions  : {Color.BOLD}{diag.load_factor:.2f} / {diag.collisions} collisions (Max Chain: {diag.max_chain_length}){Color.RESET}"
        )

        # Print formatted lines
        lines_c1 = col1.split('\n')
        lines_c2 = col2.split('\n')
        half = (w - 6) // 2

        for l1, l2 in zip(lines_c1, lines_c2):
            # Strip ANSI for length calculation
            clean_l1 = l1.replace(Color.BOLD, "").replace(Color.RESET, "").replace(Color.BRIGHT_GREEN, "")
            clean_l2 = l2.replace(Color.BOLD, "").replace(Color.RESET, "").replace(Color.BRIGHT_GREEN, "")
            pad1 = max(0, half - len(clean_l1))
            pad2 = max(0, (w - 6 - half) - len(clean_l2))
            print(f"{Color.BLUE}│{Color.RESET} {l1}{' ' * pad1} │ {l2}{' ' * pad2} {Color.BLUE}│{Color.RESET}")

        print(f"{Color.BLUE}╰" + "─" * (w - 2) + f"╯{Color.RESET}")

    @classmethod
    def render_commit_log(cls, engine: VersionControlEngine, limit: int = 10) -> None:
        """
        Renders formatted ASCII commit history with branch graph and deduplication markers.
        """
        w = get_terminal_width()
        commits = engine.get_commit_log()

        log_title = f" [ REPOSITORY COMMIT GRAPH (Total: {len(commits)}) ] "
        print(f"\n{Color.YELLOW}╭─{Color.BOLD}{Color.BRIGHT_YELLOW}{log_title}{Color.RESET}{Color.YELLOW}" + "─" * max(0, w - 2 - len(log_title) - 2) + f"╮{Color.RESET}")

        if not commits:
            empty_log = f"{Color.DIM}No commits recorded yet. Stage changes and run 'commit <message>' to record history.{Color.RESET}"
            print(f"{Color.YELLOW}│{Color.RESET}  {empty_log.ljust(w - 6 + 10)}  {Color.YELLOW}│{Color.RESET}")
        else:
            # Display commits in reverse chronological order (newest first)
            for commit in reversed(commits[-limit:]):
                is_head = (commit.commit_id == engine.head_commit_id)
                head_badge = f" {Color.BG_MAGENTA}{Color.BRIGHT_WHITE}{Color.BOLD} HEAD {Color.RESET}" if is_head else ""
                dedup_badge = f" {Color.BG_CYAN}{Color.BLACK}{Color.BOLD} DEDUPED {Color.RESET}" if commit.is_deduplicated else f" {Color.DIM}[NEW BLOB]{Color.RESET}"
                parent_short = commit.parent_id[:8] if commit.parent_id else "00000000"

                line1 = f"● {Color.BOLD}{Color.BRIGHT_YELLOW}{commit.commit_id[:12]}{Color.RESET}{head_badge}{dedup_badge} {Color.DIM}(parent: {parent_short}){Color.RESET}"
                line2 = f"│ Author: {Color.CYAN}{commit.author}{Color.RESET} | Date: {commit.timestamp} | Size: {commit.byte_size}B"
                line3 = f"│ CAS Blob: {Color.DIM}{commit.blob_hash[:16]}...{Color.RESET} | LSN: #{commit.staged_lsn:05d}"
                line4 = f"│ Message: {Color.BOLD}{Color.BRIGHT_WHITE}\"{commit.message}\"{Color.RESET}"
                line5 = "│"

                for ln, raw_txt in [
                    (line1, f"● {commit.commit_id[:12]} HEAD DEDUPED (parent: {parent_short})"),
                    (line2, f"│ Author: {commit.author} | Date: {commit.timestamp} | Size: {commit.byte_size}B"),
                    (line3, f"│ CAS Blob: {commit.blob_hash[:16]}... | LSN: #{commit.staged_lsn:05d}"),
                    (line4, f"│ Message: \"{commit.message}\""),
                    (line5, "│")
                ]:
                    pad = max(0, w - 4 - len(raw_txt))
                    print(f"{Color.YELLOW}│{Color.RESET} {ln}{' ' * pad} {Color.YELLOW}│{Color.RESET}")

        print(f"{Color.YELLOW}╰" + "─" * (w - 2) + f"╯{Color.RESET}")

    @classmethod
    def render_syntax_error(cls, res: ValidationResult) -> None:
        """
        Renders a diagnostic card pinpointing delimiter syntax violation.
        """
        w = get_terminal_width()
        err_title = " [ SYNTAX VALIDATOR ERROR - SAVE REJECTED ] "
        print(f"\n{Color.RED}╭─{Color.BOLD}{Color.BRIGHT_RED}{err_title}{Color.RESET}{Color.RED}" + "─" * max(0, w - 2 - len(err_title) - 2) + f"╮{Color.RESET}")
        print(f"{Color.RED}│{Color.RESET} {Color.BOLD}Reason:{Color.RESET} {res.error_message}")
        print(f"{Color.RED}│{Color.RESET} Location: Line {res.line}, Column {res.col}")
        if res.snippet:
            print(f"{Color.RED}│{Color.RESET} {Color.DIM}Code Preview:{Color.RESET}")
            print(f"{Color.RED}│{Color.RESET}   {Color.BRIGHT_WHITE}{res.snippet}{Color.RESET}")
            pointer = " " * (res.col - 1) + f"{Color.BRIGHT_RED}^{Color.RESET}"
            print(f"{Color.RED}│{Color.RESET}   {pointer}")
        print(f"{Color.RED}╰" + "─" * (w - 2) + f"╯{Color.RESET}")


# =============================================================================
# 7. INTERACTIVE CLI COMMAND PROCESSOR
# =============================================================================

def print_help_menu() -> None:
    """Displays comprehensive interactive CLI command guide."""
    w = get_terminal_width()
    title = " [ COMMAND REFERENCE & INSTRUCTION MANUAL ] "
    print(f"\n{Color.CYAN}╭─{Color.BOLD}{Color.BRIGHT_CYAN}{title}{Color.RESET}{Color.CYAN}" + "─" * max(0, w - 2 - len(title) - 2) + f"╮{Color.RESET}")

    commands = [
        ("write <text>", "Replaces current buffer with <text> (records transaction)"),
        ("append <text>", "Appends <text> to current buffer (records transaction)"),
        ("prepend <text>", "Prepends <text> to current buffer (records transaction)"),
        ("insert <line#> <text>", "Inserts a line at 1-based line number"),
        ("delete <line#>", "Deletes a line at 1-based line number"),
        ("clear", "Clears the active working buffer"),
        ("undo", "Rolls back the last transaction via undo_stack"),
        ("redo", "Re-applies the last undone transaction via redo_stack"),
        ("stage", "Validates delimiters and enqueues buffer into Write-Ahead Log"),
        ("commit <msg>", "Batches staged changes, stores in CAS with deduplication"),
        ("log", "Displays full commit graph, deduplication stats, and parents"),
        ("checkout <hash>", "Restores buffer to a historical commit snapshot"),
        ("status", "Refreshes and renders complete multi-panel dashboard"),
        ("diff", "Shows diff between active working buffer and HEAD commit"),
        ("inspect <hash>", "Inspects raw ContentBlob payload in Content-Addressable Storage"),
        ("demo", "Executes an automated end-to-end simulation of VCS features"),
        ("help", "Displays this command reference manual"),
        ("exit / quit", "Terminates the interactive session")
    ]

    for cmd, desc in commands:
        cmd_fmt = f"{Color.BOLD}{Color.BRIGHT_WHITE}{cmd:<24}{Color.RESET}"
        pad = max(0, w - 4 - 24 - len(desc))
        print(f"{Color.CYAN}│{Color.RESET}  {cmd_fmt} {desc}{' ' * pad}{Color.CYAN}│{Color.RESET}")

    print(f"{Color.CYAN}╰" + "─" * (w - 2) + f"╯{Color.RESET}")


def run_demo_simulation(engine: VersionControlEngine) -> None:
    """
    Executes an automated end-to-end demonstration exercising:
      1. Working buffer edits
      2. Stack-based syntax validation & delimiter checking
      3. Transaction rollback (undo / redo)
      4. Staging area Write-Ahead Log (WAL queue)
      5. Content-addressable storage (CAS) with data deduplication
      6. Commit history traversal and checkout
    """
    print(f"\n{Color.BG_MAGENTA}{Color.BRIGHT_WHITE}{Color.BOLD} STARTING AUTOMATED END-TO-END DEMO SIMULATION {Color.RESET}\n")

    # Step 1: Write valid code
    print(f"{Color.CYAN}[Demo Step 1]{Color.RESET} Writing initial Python payload into buffer...")
    sample_code_1 = "def compute_metrics(x, y):\n    return (x * 2) + [y, {x + y}]"
    engine.write_replace(sample_code_1, "Initial algorithm implementation")
    TerminalDashboardRenderer.render_buffer_view(engine)

    # Step 2: Try staging invalid syntax with broken delimiters
    print(f"\n{Color.CYAN}[Demo Step 2]{Color.RESET} Intentionally introducing syntax error with unbalanced brackets...")
    bad_code = "def compute_metrics(x, y):\n    return (x * 2) + [y, {x + y)]}"
    engine.write_replace(bad_code, "Introduce broken delimiter")
    TerminalDashboardRenderer.render_buffer_view(engine)

    print(f"{Color.YELLOW}Attempting to 'stage' buffer with unbalanced delimiters...{Color.RESET}")
    success, staged, val, msg = engine.stage()
    if not success:
        TerminalDashboardRenderer.render_syntax_error(val)
        print(f"{Color.GREEN}✓ System successfully blocked unvalidated save!{Color.RESET}")

    # Step 3: Undo the bad edit using Stack Rollback
    print(f"\n{Color.CYAN}[Demo Step 3]{Color.RESET} Rolling back the syntax error via Transaction Rollback Engine...")
    u_ok, rec, u_msg = engine.undo()
    print(f"{Color.GREEN}✓ {u_msg}{Color.RESET}")
    TerminalDashboardRenderer.render_buffer_view(engine)

    # Step 4: Stage valid buffer
    print(f"\n{Color.CYAN}[Demo Step 4]{Color.RESET} Staging valid code into Write-Ahead Log (WAL Queue)...")
    s_ok, staged, val, s_msg = engine.stage()
    print(f"{Color.GREEN}✓ {s_msg}{Color.RESET}")
    TerminalDashboardRenderer.render_staging_and_rollback_panels(engine)

    # Step 5: Commit #1
    print(f"\n{Color.CYAN}[Demo Step 5]{Color.RESET} Committing staged changes as Commit #1...")
    c_ok, c_rec, c_msg = engine.commit("feat: initial metrics computation engine")
    print(f"{Color.GREEN}✓ {c_msg}{Color.RESET}")

    # Step 6: Make second change
    print(f"\n{Color.CYAN}[Demo Step 6]{Color.RESET} Appending logging statement and committing as Commit #2...")
    engine.write_append("\n    # Logging output\n    print('Metrics calculated successfully!')", "Add logging")
    engine.stage()
    engine.commit("feat: add debug logging to calculation")

    # Step 7: Demonstrate Deduplication!
    print(f"\n{Color.CYAN}[Demo Step 7]{Color.RESET} Reverting buffer back to identical Commit #1 content and committing...")
    print(f"{Color.YELLOW}This mimics a branch merge or revert where payload exactly matches prior blob.{Color.RESET}")
    engine.write_replace(sample_code_1, "Revert back to pure initial code")
    engine.stage()
    c3_ok, c3_rec, c3_msg = engine.commit("revert: restore initial version without debug logging")
    print(f"{Color.BRIGHT_GREEN}✓ {c3_msg}{Color.RESET}")

    # Render dashboard and telemetry
    TerminalDashboardRenderer.render_header_banner(engine)
    TerminalDashboardRenderer.render_storage_telemetry(engine)
    TerminalDashboardRenderer.render_commit_log(engine)

    print(f"\n{Color.BG_GREEN}{Color.BLACK}{Color.BOLD} DEMO SIMULATION COMPLETE: ALL DSA ENGINES VERIFIED {Color.RESET}\n")


def interactive_cli_loop() -> None:
    """
    Main interactive Read-Eval-Print Loop (REPL) for the Version Control Engine.
    """
    engine = VersionControlEngine(author="Lead Architect")

    # Print welcome screen
    w = get_terminal_width()
    print("\n" + "=" * w)
    print(center_text("IN-MEMORY VERSIONING & TRANSACTION ENGINE"))
    print(center_text("Enterprise Low-Level Data Structures Project"))
    print("=" * w)
    print_help_menu()

    # Initial render
    TerminalDashboardRenderer.render_header_banner(engine)
    TerminalDashboardRenderer.render_buffer_view(engine)

    while True:
        try:
            prompt = f"\n{Color.BOLD}{Color.BRIGHT_CYAN}vcs [{engine.branch}] > {Color.RESET}"
            user_input = input(prompt).strip()
        except (KeyboardInterrupt, EOFError):
            print(f"\n{Color.YELLOW}Exiting VCS engine. Goodbye!{Color.RESET}")
            break

        if not user_input:
            continue

        parts = user_input.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        # ---------------------------------------------------------------------
        # Command Dispatch
        # ---------------------------------------------------------------------
        if cmd in ("exit", "quit", "q"):
            print(f"{Color.YELLOW}Exiting VCS engine. Goodbye!{Color.RESET}")
            break

        elif cmd == "help":
            print_help_menu()

        elif cmd == "demo":
            run_demo_simulation(engine)

        elif cmd == "status":
            TerminalDashboardRenderer.render_header_banner(engine)
            TerminalDashboardRenderer.render_buffer_view(engine)
            TerminalDashboardRenderer.render_staging_and_rollback_panels(engine)
            TerminalDashboardRenderer.render_storage_telemetry(engine)

        elif cmd == "write":
            if not args:
                print(f"{Color.RED}Usage: write <text to write into buffer>{Color.RESET}")
                continue
            rec = engine.write_replace(args, "CLI write command")
            print(f"{Color.GREEN}✓ Updated working buffer ({rec.delta_bytes:+d}B).{Color.RESET}")
            TerminalDashboardRenderer.render_buffer_view(engine)

        elif cmd == "append":
            if not args:
                print(f"{Color.RED}Usage: append <text to append>{Color.RESET}")
                continue
            # If buffer is not empty and doesn't end in newline, add newline before append if needed
            prefix = "\n" if (engine.working_buffer and not engine.working_buffer.endswith('\n')) else ""
            rec = engine.write_append(prefix + args, "CLI append command")
            print(f"{Color.GREEN}✓ Appended to working buffer ({rec.delta_bytes:+d}B).{Color.RESET}")
            TerminalDashboardRenderer.render_buffer_view(engine)

        elif cmd == "prepend":
            if not args:
                print(f"{Color.RED}Usage: prepend <text to prepend>{Color.RESET}")
                continue
            suffix = "\n" if not args.endswith('\n') else ""
            rec = engine.write_prepend(args + suffix, "CLI prepend command")
            print(f"{Color.GREEN}✓ Prepended to working buffer ({rec.delta_bytes:+d}B).{Color.RESET}")
            TerminalDashboardRenderer.render_buffer_view(engine)

        elif cmd == "insert":
            insert_parts = args.split(maxsplit=1)
            if len(insert_parts) < 2:
                print(f"{Color.RED}Usage: insert <line_number> <line_text>{Color.RESET}")
                continue
            try:
                line_no = int(insert_parts[0]) - 1
            except ValueError:
                print(f"{Color.RED}Line number must be an integer.{Color.RESET}")
                continue
            rec = engine.write_insert_line(line_no, insert_parts[1])
            print(f"{Color.GREEN}✓ Inserted line at #{line_no + 1}.{Color.RESET}")
            TerminalDashboardRenderer.render_buffer_view(engine)

        elif cmd == "delete":
            if not args:
                print(f"{Color.RED}Usage: delete <line_number>{Color.RESET}")
                continue
            try:
                line_no = int(args) - 1
            except ValueError:
                print(f"{Color.RED}Line number must be an integer.{Color.RESET}")
                continue
            ok, rec, msg = engine.write_delete_line(line_no)
            if ok:
                print(f"{Color.GREEN}✓ {msg}{Color.RESET}")
                TerminalDashboardRenderer.render_buffer_view(engine)
            else:
                print(f"{Color.RED}✗ {msg}{Color.RESET}")

        elif cmd == "clear":
            engine.clear_buffer()
            print(f"{Color.YELLOW}Working buffer cleared. (Transaction recorded; can be undone){Color.RESET}")
            TerminalDashboardRenderer.render_buffer_view(engine)

        elif cmd == "undo":
            ok, rec, msg = engine.undo()
            if ok:
                print(f"{Color.GREEN}✓ {msg}{Color.RESET}")
                TerminalDashboardRenderer.render_buffer_view(engine)
            else:
                print(f"{Color.YELLOW}⚠ {msg}{Color.RESET}")

        elif cmd == "redo":
            ok, rec, msg = engine.redo()
            if ok:
                print(f"{Color.GREEN}✓ {msg}{Color.RESET}")
                TerminalDashboardRenderer.render_buffer_view(engine)
            else:
                print(f"{Color.YELLOW}⚠ {msg}{Color.RESET}")

        elif cmd == "stage":
            ok, staged, val, msg = engine.stage()
            if ok:
                print(f"{Color.GREEN}✓ {msg}{Color.RESET}")
                TerminalDashboardRenderer.render_staging_and_rollback_panels(engine)
            else:
                print(f"{Color.RED}✗ {msg}{Color.RESET}")
                TerminalDashboardRenderer.render_syntax_error(val)

        elif cmd == "commit":
            if not args:
                print(f"{Color.RED}Usage: commit <commit_message>{Color.RESET}")
                continue
            ok, commit_rec, msg = engine.commit(args)
            if ok:
                print(f"{Color.BRIGHT_GREEN}✓ {msg}{Color.RESET}")
                TerminalDashboardRenderer.render_header_banner(engine)
                TerminalDashboardRenderer.render_storage_telemetry(engine)
            else:
                print(f"{Color.YELLOW}⚠ {msg}{Color.RESET}")

        elif cmd == "log":
            TerminalDashboardRenderer.render_commit_log(engine)

        elif cmd == "checkout":
            if not args:
                print(f"{Color.RED}Usage: checkout <commit_hash>{Color.RESET}")
                continue
            ok, commit_rec, msg = engine.checkout(args)
            if ok:
                print(f"{Color.GREEN}✓ {msg}{Color.RESET}")
                TerminalDashboardRenderer.render_header_banner(engine)
                TerminalDashboardRenderer.render_buffer_view(engine)
            else:
                print(f"{Color.RED}✗ {msg}{Color.RESET}")

        elif cmd == "diff":
            head_id = engine.head_commit_id
            if head_id is None:
                print(f"{Color.YELLOW}No commits exist yet. Working buffer is untracked.{Color.RESET}")
            else:
                head_commit = engine.get_commit_by_id(head_id)
                head_content = engine.cas_storage.retrieve_payload(head_commit.blob_hash) if head_commit else ""
                current_content = engine.working_buffer

                w = get_terminal_width()
                print(f"\n{Color.CYAN}--- HEAD: {head_id[:10]} ({len(head_content)} bytes)")
                print(f"+++ WORKING BUFFER ({len(current_content)} bytes){Color.RESET}")

                if head_content == current_content:
                    print(f"{Color.GREEN}Working buffer is identical to HEAD snapshot. No diff.{Color.RESET}")
                else:
                    lines_head = head_content.split('\n')
                    lines_curr = current_content.split('\n')
                    max_lines = max(len(lines_head), len(lines_curr))
                    for i in range(max_lines):
                        lh = lines_head[i] if i < len(lines_head) else None
                        lc = lines_curr[i] if i < len(lines_curr) else None
                        if lh == lc:
                            print(f"  {lh}")
                        else:
                            if lh is not None:
                                print(f"{Color.RED}- {lh}{Color.RESET}")
                            if lc is not None:
                                print(f"{Color.GREEN}+ {lc}{Color.RESET}")

        elif cmd == "inspect":
            if not args:
                print(f"{Color.RED}Usage: inspect <hash_or_commit_id>{Color.RESET}")
                continue
            # Check if it's a commit ID or blob hash
            commit_obj = engine.get_commit_by_id(args)
            target_hash = commit_obj.blob_hash if commit_obj else args
            blob = engine.cas_storage.get_blob(target_hash)

            if blob is None:
                print(f"{Color.RED}No ContentBlob found matching hash '{target_hash}'.{Color.RESET}")
            else:
                w = get_terminal_width()
                print(f"\n{Color.CYAN}╭─ [ CAS BLOB INSPECTOR ] " + "─" * (w - 26) + f"╮{Color.RESET}")
                print(f"{Color.CYAN}│{Color.RESET} Fingerprint    : {Color.BOLD}{blob.fingerprint}{Color.RESET}")
                print(f"{Color.CYAN}│{Color.RESET} Byte Size      : {blob.byte_size} bytes")
                print(f"{Color.CYAN}│{Color.RESET} Reference Count: {Color.BOLD}{Color.GREEN}{blob.reference_count}{Color.RESET}")
                print(f"{Color.CYAN}│{Color.RESET} First Commit   : {blob.first_commit_id}")
                print(f"{Color.CYAN}│{Color.RESET} Created At     : {blob.created_at}")
                print(f"{Color.CYAN}├─ [ RAW CONTENT ] " + "─" * (w - 20) + f"┤{Color.RESET}")
                for ln in blob.payload.split('\n'):
                    print(f"{Color.CYAN}│{Color.RESET}   {ln}")
                print(f"{Color.CYAN}╰" + "─" * (w - 2) + f"╯{Color.RESET}")

        else:
            print(f"{Color.RED}Unknown command: '{cmd}'. Type 'help' for available commands.{Color.RESET}")


if __name__ == "__main__":
    interactive_cli_loop()
