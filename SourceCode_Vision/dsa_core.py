"""
===============================================================================
DSA Core Data Structures Module
===============================================================================
Enterprise-grade, zero-dependency implementations of fundamental Data Structures
built strictly from scratch for the In-Memory Versioning & Transaction Engine.

STRICT CONSTRAINTS ADHERENCE:
- NO `dict`
- NO `set`
- NO `collections.deque`

Implementations included:
  1. StackNode & Stack (LIFO Node-Based Stack)
  2. QueueNode & Queue (FIFO Linked Queue with Tail Pointer)
  3. HashNode & HashTable (Content-Addressable Storage with Separate Chaining,
     Polynomial Rolling Hash & DJB2, Dynamic Rehashing, and Collision Metrics)
  4. SyntaxValidator (Stack-based syntax and delimiter balance parser)
===============================================================================
"""

from typing import Any, Optional, Tuple, List


# =============================================================================
# CUSTOM EXCEPTIONS
# =============================================================================

class DSAError(Exception):
    """Base exception for all DSA core operations."""
    pass


class EmptyStackError(DSAError):
    """Raised when attempting to pop or peek from an empty stack."""
    pass


class EmptyQueueError(DSAError):
    """Raised when attempting to dequeue or peek from an empty queue."""
    pass


class KeyNotFoundError(DSAError):
    """Raised when a key is not found in the custom Hash Table."""
    pass


# =============================================================================
# 1. STACK IMPLEMENTATION (LIFO)
# =============================================================================

class StackNode:
    """
    Singly linked node representation for the Stack.
    Uses __slots__ for maximum memory efficiency and CPU cache locality.
    """
    __slots__ = ('value', 'next')

    def __init__(self, value: Any, next_node: Optional['StackNode'] = None) -> None:
        self.value: Any = value
        self.next: Optional['StackNode'] = next_node

    def __repr__(self) -> str:
        return f"StackNode({repr(self.value)})"


class Stack:
    """
    A low-level, high-performance Node-based Last-In-First-Out (LIFO) Stack.
    Time Complexity:
      - Push:    O(1)
      - Pop:     O(1)
      - Peek:    O(1)
      - IsEmpty: O(1)
      - Size:    O(1)
    Space Complexity: O(N)
    """

    def __init__(self) -> None:
        self._top: Optional[StackNode] = None
        self._size: int = 0

    def push(self, item: Any) -> None:
        """
        Pushes a new item onto the top of the stack.
        """
        new_node = StackNode(item, self._top)
        self._top = new_node
        self._size += 1

    def pop(self) -> Any:
        """
        Removes and returns the item at the top of the stack.
        Raises EmptyStackError if the stack is empty.
        """
        if self._top is None:
            raise EmptyStackError("Cannot pop from an empty Stack.")
        popped_value = self._top.value
        self._top = self._top.next
        self._size -= 1
        return popped_value

    def peek(self) -> Any:
        """
        Returns the item at the top of the stack without removing it.
        Raises EmptyStackError if the stack is empty.
        """
        if self._top is None:
            raise EmptyStackError("Cannot peek into an empty Stack.")
        return self._top.value

    def is_empty(self) -> bool:
        """
        Checks whether the stack contains any items.
        """
        return self._top is None

    def clear(self) -> None:
        """
        Clears all items from the stack in O(1) time by decoupling the head.
        """
        self._top = None
        self._size = 0

    def to_list(self) -> List[Any]:
        """
        Converts the stack items to a standard list from top to bottom.
        """
        elements: List[Any] = []
        curr = self._top
        while curr is not None:
            elements.append(curr.value)
            curr = curr.next
        return elements

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._top is not None

    def __iter__(self):
        curr = self._top
        while curr is not None:
            yield curr.value
            curr = curr.next

    def __repr__(self) -> str:
        items = [repr(x) for x in self.to_list()]
        return f"Stack(top -> [{', '.join(items)}])"


# =============================================================================
# 2. QUEUE IMPLEMENTATION (FIFO)
# =============================================================================

class QueueNode:
    """
    Singly linked node representation for the Queue.
    """
    __slots__ = ('value', 'next')

    def __init__(self, value: Any, next_node: Optional['QueueNode'] = None) -> None:
        self.value: Any = value
        self.next: Optional['QueueNode'] = next_node

    def __repr__(self) -> str:
        return f"QueueNode({repr(self.value)})"


class Queue:
    """
    A low-level First-In-First-Out (FIFO) Queue implemented with linked nodes
    and dedicated Head and Tail pointers.
    
    Time Complexity:
      - Enqueue: O(1)
      - Dequeue: O(1)
      - Peek:    O(1)
      - IsEmpty: O(1)
      - Size:    O(1)
    Space Complexity: O(N)
    """

    def __init__(self) -> None:
        self._head: Optional[QueueNode] = None
        self._tail: Optional[QueueNode] = None
        self._size: int = 0

    def enqueue(self, item: Any) -> None:
        """
        Appends an item to the tail of the queue in O(1) time.
        """
        new_node = QueueNode(item)
        if self._tail is None:
            self._head = new_node
            self._tail = new_node
        else:
            self._tail.next = new_node
            self._tail = new_node
        self._size += 1

    def dequeue(self) -> Any:
        """
        Removes and returns the item from the head of the queue in O(1) time.
        Raises EmptyQueueError if the queue is empty.
        """
        if self._head is None:
            raise EmptyQueueError("Cannot dequeue from an empty Queue.")
        dequeued_value = self._head.value
        self._head = self._head.next
        if self._head is None:
            self._tail = None
        self._size -= 1
        return dequeued_value

    def peek(self) -> Any:
        """
        Inspects the item at the head of the queue without removing it.
        Raises EmptyQueueError if the queue is empty.
        """
        if self._head is None:
            raise EmptyQueueError("Cannot peek into an empty Queue.")
        return self._head.value

    def is_empty(self) -> bool:
        """
        Checks whether the queue contains any items.
        """
        return self._head is None

    def clear(self) -> None:
        """
        Empties the queue in O(1) time.
        """
        self._head = None
        self._tail = None
        self._size = 0

    def to_list(self) -> List[Any]:
        """
        Returns a list of items from head (front) to tail (back).
        """
        elements: List[Any] = []
        curr = self._head
        while curr is not None:
            elements.append(curr.value)
            curr = curr.next
        return elements

    def __len__(self) -> int:
        return self._size

    def __bool__(self) -> bool:
        return self._head is not None

    def __iter__(self):
        curr = self._head
        while curr is not None:
            yield curr.value
            curr = curr.next

    def __repr__(self) -> str:
        items = [repr(x) for x in self.to_list()]
        return f"Queue(head -> [{', '.join(items)}] <- tail)"


# =============================================================================
# 3. HASH FUNCTIONS & CONTENT FINGERPRINTING
# =============================================================================

def djb2_hash(payload: str) -> int:
    """
    Classic DJB2 hash algorithm by Dan Bernstein.
    Produces a 64-bit integer hash by iterating through character bytes
    with hash = ((hash << 5) + hash) + c.
    """
    hash_val = 5381
    for char in payload:
        # hash * 33 + char_code & mask to 64 bits
        hash_val = (((hash_val << 5) + hash_val) + ord(char)) & 0xFFFFFFFFFFFFFFFF
    return hash_val


def polynomial_rolling_hash(payload: str, base: int = 131, mod: int = 18446744073709551557) -> int:
    """
    Polynomial rolling hash algorithm:
      H = sum( ord(char_i) * (base ^ (n - 1 - i)) ) mod (mod)
    Using prime modulus close to 2^64 for robust collision resistance.
    """
    hash_val = 0
    for char in payload:
        hash_val = (hash_val * base + ord(char)) % mod
    return hash_val


def compute_content_fingerprint(payload: str) -> str:
    """
    Generates a deterministic 40-character hexadecimal content fingerprint
    combining DJB2 and high-degree polynomial rolling hash to mimic Git SHA-1.
    No built-in hashing libraries (like hashlib) are utilized.
    """
    # 64-bit DJB2
    h1 = djb2_hash(payload)
    # 64-bit Polynomial hash with prime base 137
    h2 = polynomial_rolling_hash(payload, base=137, mod=18446744073709551557)
    # Secondary polynomial hash with prime base 257
    h3 = polynomial_rolling_hash(payload, base=257, mod=18446744073709551533)

    # Fold and format into fixed 40-hex-character string
    part1 = f"{h1:016x}"
    part2 = f"{h2:016x}"
    part3 = f"{(h3 & 0xFFFFFFFF):08x}"
    return (part1 + part2 + part3)[:40]


# =============================================================================
# 4. CONTENT-ADDRESSABLE HASH TABLE (SEPARATE CHAINING)
# =============================================================================

class HashNode:
    """
    A single node in the separate-chaining bucket linked list.
    Stores key, value, precomputed 64-bit numeric hash, and link to next node.
    """
    __slots__ = ('key', 'value', 'hash_val', 'next')

    def __init__(self, key: str, value: Any, hash_val: int, next_node: Optional['HashNode'] = None) -> None:
        self.key: str = key
        self.value: Any = value
        self.hash_val: int = hash_val
        self.next: Optional['HashNode'] = next_node

    def __repr__(self) -> str:
        return f"HashNode(key={repr(self.key)}, value={repr(self.value)})"


class HashTableDiagnostics:
    """
    Enterprise health and telemetry snapshot for the custom Hash Table.
    """
    def __init__(self, capacity: int, size: int, collisions: int,
                 occupied_buckets: int, max_chain_length: int,
                 avg_chain_length: float, load_factor: float) -> None:
        self.capacity: int = capacity
        self.size: int = size
        self.collisions: int = collisions
        self.occupied_buckets: int = occupied_buckets
        self.max_chain_length: int = max_chain_length
        self.avg_chain_length: float = avg_chain_length
        self.load_factor: float = load_factor

    def __repr__(self) -> str:
        return (f"HashTableDiagnostics(capacity={self.capacity}, size={self.size}, "
                f"load_factor={self.load_factor:.3f}, collisions={self.collisions}, "
                f"occupied={self.occupied_buckets}, max_chain={self.max_chain_length}, "
                f"avg_chain={self.avg_chain_length:.2f})")


class HashTable:
    """
    A custom Content-Addressable Hash Table implementation.
    Features:
      - Raw fixed-size bucket array (allocated with primitive list `[None] * capacity`).
      - Separate Chaining via singly linked `HashNode` lists.
      - Dynamic Rehashing when load factor exceeds threshold (default 0.75).
      - Collision telemetry tracking.
      - Zero usage of Python built-in `dict`, `set`, or `deque`.
    """

    INITIAL_CAPACITY: int = 16
    MAX_LOAD_FACTOR: float = 0.75

    def __init__(self, initial_capacity: int = INITIAL_CAPACITY,
                 load_factor_threshold: float = MAX_LOAD_FACTOR) -> None:
        if initial_capacity < 4:
            initial_capacity = 4
        self._capacity: int = initial_capacity
        self._load_factor_threshold: float = load_factor_threshold
        self._buckets: List[Optional[HashNode]] = [None] * self._capacity
        self._size: int = 0
        self._total_collisions: int = 0

    def _get_bucket_index(self, hash_val: int) -> int:
        """
        Maps a 64-bit integer hash to an index in [0, capacity - 1].
        """
        return hash_val % self._capacity

    def put(self, key: str, value: Any) -> Tuple[bool, bool]:
        """
        Inserts or updates a key-value pair.
        Returns a tuple of booleans: (is_new_insert, is_collision_encountered).
        """
        h_val = djb2_hash(key)
        index = self._get_bucket_index(h_val)

        curr = self._buckets[index]
        if curr is None:
            # Clean slot: no collision
            self._buckets[index] = HashNode(key, value, h_val)
            self._size += 1
            self._check_and_resize()
            return True, False

        # Collision or update in existing chain
        collision_detected = True
        self._total_collisions += 1

        prev = None
        while curr is not None:
            if curr.key == key:
                # Key already exists: update in-place
                curr.value = value
                return False, False
            prev = curr
            curr = curr.next

        # Key not in chain: append to chain
        prev.next = HashNode(key, value, h_val)
        self._size += 1
        self._check_and_resize()
        return True, collision_detected

    def get(self, key: str, default: Any = None) -> Any:
        """
        Retrieves the value associated with `key`.
        Returns `default` if the key is not present.
        """
        h_val = djb2_hash(key)
        index = self._get_bucket_index(h_val)

        curr = self._buckets[index]
        while curr is not None:
            if curr.key == key:
                return curr.value
            curr = curr.next
        return default

    def contains(self, key: str) -> bool:
        """
        Returns True if `key` exists in the Hash Table, False otherwise.
        """
        h_val = djb2_hash(key)
        index = self._get_bucket_index(h_val)

        curr = self._buckets[index]
        while curr is not None:
            if curr.key == key:
                return True
            curr = curr.next
        return False

    def delete(self, key: str) -> bool:
        """
        Removes `key` and its associated value.
        Returns True if the key was found and removed, False otherwise.
        """
        h_val = djb2_hash(key)
        index = self._get_bucket_index(h_val)

        curr = self._buckets[index]
        prev = None

        while curr is not None:
            if curr.key == key:
                if prev is None:
                    self._buckets[index] = curr.next
                else:
                    prev.next = curr.next
                self._size -= 1
                return True
            prev = curr
            curr = curr.next

        return False

    def _check_and_resize(self) -> None:
        """
        Doubles the table capacity and rehashes all elements when the load factor
        exceeds the configured threshold.
        """
        current_load = self._size / self._capacity
        if current_load <= self._load_factor_threshold:
            return

        new_capacity = self._capacity * 2
        new_buckets: List[Optional[HashNode]] = [None] * new_capacity

        # Rehash all active nodes across existing buckets
        for bucket_head in self._buckets:
            curr = bucket_head
            while curr is not None:
                next_node = curr.next
                # Calculate new index using cached 64-bit hash
                new_idx = curr.hash_val % new_capacity
                
                # Prepend to new chain
                curr.next = new_buckets[new_idx]
                new_buckets[new_idx] = curr
                
                curr = next_node

        self._capacity = new_capacity
        self._buckets = new_buckets

    def keys(self) -> List[str]:
        """
        Returns an ordered list of all keys currently stored.
        No built-in dict/set used.
        """
        res: List[str] = []
        for bucket_head in self._buckets:
            curr = bucket_head
            while curr is not None:
                res.append(curr.key)
                curr = curr.next
        return res

    def values(self) -> List[Any]:
        """
        Returns a list of all values stored.
        """
        res: List[Any] = []
        for bucket_head in self._buckets:
            curr = bucket_head
            while curr is not None:
                res.append(curr.value)
                curr = curr.next
        return res

    def items(self) -> List[Tuple[str, Any]]:
        """
        Returns a list of (key, value) pairs.
        """
        res: List[Tuple[str, Any]] = []
        for bucket_head in self._buckets:
            curr = bucket_head
            while curr is not None:
                res.append((curr.key, curr.value))
                curr = curr.next
        return res

    def get_diagnostics(self) -> HashTableDiagnostics:
        """
        Computes detailed bucket chain analysis and collision metrics.
        """
        occupied = 0
        max_chain = 0
        total_chain_len = 0

        for bucket_head in self._buckets:
            if bucket_head is not None:
                occupied += 1
                chain_len = 0
                curr = bucket_head
                while curr is not None:
                    chain_len += 1
                    curr = curr.next
                total_chain_len += chain_len
                if chain_len > max_chain:
                    max_chain = chain_len

        avg_chain = (total_chain_len / occupied) if occupied > 0 else 0.0
        load_factor = self._size / self._capacity

        return HashTableDiagnostics(
            capacity=self._capacity,
            size=self._size,
            collisions=self._total_collisions,
            occupied_buckets=occupied,
            max_chain_length=max_chain,
            avg_chain_length=avg_chain,
            load_factor=load_factor
        )

    def clear(self) -> None:
        """
        Resets the hash table back to initial state.
        """
        self._capacity = self.INITIAL_CAPACITY
        self._buckets = [None] * self._capacity
        self._size = 0
        self._total_collisions = 0

    def __len__(self) -> int:
        return self._size

    def __contains__(self, key: str) -> bool:
        return self.contains(key)

    def __getitem__(self, key: str) -> Any:
        h_val = djb2_hash(key)
        index = self._get_bucket_index(h_val)
        curr = self._buckets[index]
        while curr is not None:
            if curr.key == key:
                return curr.value
            curr = curr.next
        raise KeyNotFoundError(f"Key '{key}' not found in HashTable.")

    def __setitem__(self, key: str, value: Any) -> None:
        self.put(key, value)

    def __delitem__(self, key: str) -> None:
        if not self.delete(key):
            raise KeyNotFoundError(f"Key '{key}' not found in HashTable.")

    def __iter__(self):
        for k in self.keys():
            yield k

    def __repr__(self) -> str:
        return f"HashTable(size={self._size}, capacity={self._capacity}, load={self._size/self._capacity:.2f})"


# =============================================================================
# 5. SYNTAX & DELIMITER VALIDATOR (STACK-BASED)
# =============================================================================

class DelimiterToken:
    """
    Stores delimiter metadata: character, line index, column index.
    """
    __slots__ = ('char', 'line', 'col', 'index')

    def __init__(self, char: str, line: int, col: int, index: int) -> None:
        self.char: str = char
        self.line: int = line
        self.col: int = col
        self.index: int = index

    def __repr__(self) -> str:
        return f"DelimiterToken('{self.char}' at L{self.line}:C{self.col})"


class ValidationResult:
    """
    Immutable syntax validation diagnostic report.
    """
    def __init__(self, is_valid: bool, error_message: str = "",
                 line: int = 0, col: int = 0, snippet: str = "",
                 expected_char: str = "", found_char: str = "") -> None:
        self.is_valid: bool = is_valid
        self.error_message: str = error_message
        self.line: int = line
        self.col: int = col
        self.snippet: str = snippet
        self.expected_char: str = expected_char
        self.found_char: str = found_char

    def __bool__(self) -> bool:
        return self.is_valid

    def __repr__(self) -> str:
        if self.is_valid:
            return "ValidationResult(VALID: All delimiters strictly balanced)"
        return f"ValidationResult(INVALID: {self.error_message} at Line {self.line}, Col {self.col})"


class SyntaxValidator:
    """
    Stack-based syntax validator for delimiter pairing.
    Validates (), {}, and [] brackets while correctly recognizing string literals
    and comments without using Python `dict` or `set`.
    """

    @staticmethod
    def _is_open_delimiter(ch: str) -> bool:
        return ch == '(' or ch == '[' or ch == '{'

    @staticmethod
    def _is_close_delimiter(ch: str) -> bool:
        return ch == ')' or ch == ']' or ch == '}'

    @staticmethod
    def _get_matching_open(close_ch: str) -> str:
        if close_ch == ')':
            return '('
        if close_ch == ']':
            return '['
        if close_ch == '}':
            return '{'
        return ''

    @staticmethod
    def _get_matching_close(open_ch: str) -> str:
        if open_ch == '(':
            return ')'
        if open_ch == '[':
            return ']'
        if open_ch == '{':
            return '}'
        return ''

    @classmethod
    def validate(cls, text: str, ignore_strings_and_comments: bool = False) -> ValidationResult:
        """
        Parses `text` using a custom Stack to verify delimiter equilibrium.
        
        If `ignore_strings_and_comments` is False (default for strict file validation),
        every delimiter in the payload must strictly balance.
        If True, delimiters inside string quotes or hash comments are skipped.
        
        Returns a ValidationResult object detailing status and error coordinates.
        """
        stack = Stack()
        lines = text.split('\n')

        line_num = 1
        col_num = 1
        idx = 0
        length = len(text)

        in_single_quote = False
        in_double_quote = False
        in_comment = False

        while idx < length:
            ch = text[idx]

            # Track lines and columns
            if ch == '\n':
                line_num += 1
                col_num = 1
                in_comment = False
                idx += 1
                continue

            if ignore_strings_and_comments:
                # Handle escaping
                if ch == '\\' and (in_single_quote or in_double_quote) and (idx + 1 < length):
                    idx += 2
                    col_num += 2
                    continue

                if ch == '#' and not in_single_quote and not in_double_quote:
                    in_comment = True

                if in_comment:
                    idx += 1
                    col_num += 1
                    continue

                if ch == "'" and not in_double_quote:
                    in_single_quote = not in_single_quote
                    idx += 1
                    col_num += 1
                    continue

                if ch == '"' and not in_single_quote:
                    in_double_quote = not in_double_quote
                    idx += 1
                    col_num += 1
                    continue

                if in_single_quote or in_double_quote:
                    idx += 1
                    col_num += 1
                    continue

            # Process open delimiters
            if cls._is_open_delimiter(ch):
                token = DelimiterToken(ch, line_num, col_num, idx)
                stack.push(token)

            # Process close delimiters
            elif cls._is_close_delimiter(ch):
                expected_open = cls._get_matching_open(ch)
                if stack.is_empty():
                    # Unmatched closing delimiter
                    snippet = lines[line_num - 1] if 0 <= (line_num - 1) < len(lines) else ""
                    return ValidationResult(
                        is_valid=False,
                        error_message=f"Extraneous closing delimiter '{ch}' with no preceding opening delimiter.",
                        line=line_num,
                        col=col_num,
                        snippet=snippet,
                        expected_char="",
                        found_char=ch
                    )

                popped_token: DelimiterToken = stack.pop()
                if popped_token.char != expected_open:
                    # Mismatched pair
                    expected_close = cls._get_matching_close(popped_token.char)
                    snippet = lines[line_num - 1] if 0 <= (line_num - 1) < len(lines) else ""
                    return ValidationResult(
                        is_valid=False,
                        error_message=(
                            f"Mismatched closing delimiter '{ch}'. Expected '{expected_close}' "
                            f"to match '{popped_token.char}' opened at line {popped_token.line}, col {popped_token.col}."
                        ),
                        line=line_num,
                        col=col_num,
                        snippet=snippet,
                        expected_char=expected_close,
                        found_char=ch
                    )

            col_num += 1
            idx += 1

        # Check for unclosed open delimiters remaining in the stack
        if not stack.is_empty():
            unclosed_token: DelimiterToken = stack.pop()
            expected_close = cls._get_matching_close(unclosed_token.char)
            snippet = lines[unclosed_token.line - 1] if 0 <= (unclosed_token.line - 1) < len(lines) else ""
            return ValidationResult(
                is_valid=False,
                error_message=(
                    f"Unclosed delimiter '{unclosed_token.char}' opened at line {unclosed_token.line}, "
                    f"col {unclosed_token.col}. Missing closing delimiter '{expected_close}'."
                ),
                line=unclosed_token.line,
                col=unclosed_token.col,
                snippet=snippet,
                expected_char=expected_close,
                found_char=""
            )

        return ValidationResult(is_valid=True)

