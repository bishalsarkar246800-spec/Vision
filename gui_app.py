"""
===============================================================================
 Vision GUI Application — PyWebView Desktop Wrapper
===============================================================================
 Bridges the Neo-Brutalist HTML/CSS/JS frontend (index.html) with the custom
 DSA version control engine (version_engine.py & dsa_core.py).
 Compilable into a standalone macOS .app bundle via PyInstaller.
===============================================================================
"""

import sys
import os
import webview

# Add current folder to path
_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:
    sys.path.insert(0, _HERE)

from version_engine import VersionControlEngine, OperationType


class VisionBridge:
    """
    Exposed JS-Python API.
    All methods are directly callable from JavaScript via `window.pywebview.api.<method>()`.
    """

    def __init__(self):
        self.engine = VersionControlEngine(author="Vision User")
        # Load initial sample code
        self.initial_code = (
            "def calculate_metrics():\n"
            "    dataset = [10, 20, 30]\n"
            "    return sum(dataset)"
        )
        self.engine.write_replace(self.initial_code, "Initial buffer load")

    def get_diff_text(self) -> str:
        head_id = self.engine.head_commit_id
        current = self.engine.working_buffer
        if head_id is None:
            return "Working buffer matches HEAD commit snapshot"
        head_commit = self.engine.get_commit_by_id(head_id)
        if not head_commit:
            return "Working buffer matches HEAD commit snapshot"
        head_content = self.engine.cas_storage.retrieve_payload(head_commit.blob_hash) or ""
        if head_content == current:
            return "Working buffer matches HEAD commit snapshot"

        lines_head = head_content.split('\n')
        lines_curr = current.split('\n')
        max_lines = max(len(lines_head), len(lines_curr))
        diff_lines = []
        for i in range(max_lines):
            lh = lines_head[i] if i < len(lines_head) else None
            lc = lines_curr[i] if i < len(lines_curr) else None
            if lh == lc:
                diff_lines.append(f"  {lh}")
            else:
                if lh is not None:
                    diff_lines.append(f"- {lh}")
                if lc is not None:
                    diff_lines.append(f"+ {lc}")
        return "\n".join(diff_lines)

    def get_state(self):
        """Returns the full serialization of the VCS state for UI rendering."""
        # Undo / Redo Stacks
        undo_list = []
        for rec in self.engine.rollback_engine.get_undo_history():
            undo_list.append({
                "id": rec.tx_id,
                "type": rec.op_type,
                "desc": rec.description,
                "delta": rec.delta_bytes
            })

        redo_list = []
        for rec in self.engine.rollback_engine.get_redo_history():
            redo_list.append({
                "id": rec.tx_id,
                "type": rec.op_type,
                "desc": rec.description,
                "delta": rec.delta_bytes
            })

        # Staging Queue (FIFO)
        staging_list = []
        for item in self.engine.staging_buffer.get_staged_entries():
            staging_list.append({
                "lsn": item.lsn,
                "hash": item.fingerprint,
                "size": item.byte_size,
                "lines": item.line_count,
                "time": item.timestamp
            })

        # Commit Log
        commits_list = []
        for c in self.engine.get_commit_log():
            commits_list.append({
                "id": c.commit_id,
                "parent": c.parent_id or "ROOT",
                "message": c.message,
                "author": c.author,
                "date": c.timestamp,
                "size": c.byte_size,
                "is_dedup": c.is_deduplicated,
                "seq": c.seq_num
            })

        # CAS Telemetry & Hash Table Buckets
        tele = self.engine.cas_storage.get_telemetry()
        diag = tele.ht_diagnostics

        buckets = []
        table = self.engine.cas_storage._blob_table
        for idx in range(min(table._capacity, 12)):  # display up to 12 buckets
            curr = table._buckets[idx]
            nodes = []
            while curr is not None:
                nodes.append({
                    "hash": curr.key,
                    "refs": curr.value.reference_count,
                    "bytes": curr.value.byte_size
                })
                curr = curr.next
            buckets.append({
                "index": idx,
                "nodes": nodes
            })

        return {
            "buffer": self.engine.working_buffer,
            "diff": self.get_diff_text(),
            "head": self.engine.head_commit_id,
            "branch": self.engine.branch,
            "undoStack": undo_list,
            "redoStack": redo_list,
            "stagingQueue": staging_list,
            "commits": commits_list,
            "telemetry": {
                "totalSnapshots": tele.total_commit_payloads,
                "uniqueBlobs": tele.unique_blobs,
                "dedupHits": tele.dedup_hits,
                "bytesSaved": tele.bytes_saved,
                "capacity": diag.capacity,
                "collisions": diag.collisions,
                "loadFactor": round(diag.load_factor, 3)
            },
            "buckets": buckets
        }

    def write(self, text: str, desc: str = "Editor update"):
        self.engine.write_replace(text, desc)
        return self.get_state()

    def update_buffer(self, text: str):
        self.engine.write_replace(text, "Live keystroke")
        return self.get_state()

    def stage(self):
        ok, staged, val, msg = self.engine.stage()
        return {
            "ok": ok,
            "message": msg if ok else f"Stage Rejected: {val.error_message}",
            "state": self.get_state()
        }

    def commit(self, message: str):
        ok, rec, msg = self.engine.commit(message)
        return {
            "ok": ok,
            "message": msg,
            "state": self.get_state()
        }

    def undo(self):
        ok, rec, msg = self.engine.undo()
        return {
            "ok": ok,
            "message": f"Undid: {rec.description}" if ok else msg,
            "state": self.get_state()
        }

    def redo(self):
        ok, rec, msg = self.engine.redo()
        return {
            "ok": ok,
            "message": f"Redid: {rec.description}" if ok else msg,
            "state": self.get_state()
        }

    def clear(self):
        self.engine.clear_buffer()
        return self.get_state()

    def reset(self):
        self.engine = VersionControlEngine(author="Vision User")
        self.engine.write_replace(self.initial_code, "Initial buffer load")
        return self.get_state()

    def checkout(self, commit_id: str):
        ok, rec, msg = self.engine.checkout(commit_id)
        return {
            "ok": ok,
            "message": msg,
            "state": self.get_state()
        }

    def run_demo(self):
        from version_engine import run_demo_simulation
        # Create fresh demo run
        self.engine = VersionControlEngine(author="Demo Engineer")
        run_demo_simulation(self.engine)
        return {
            "ok": True,
            "message": "Automated walkthrough completed successfully.",
            "state": self.get_state()
        }

    def run_cli_command(self, cmd_line: str):
        cmd_line = cmd_line.strip()
        if not cmd_line:
            return {"ok": True, "output": "", "state": self.get_state()}

        parts = cmd_line.split(maxsplit=1)
        cmd = parts[0].lower()
        args = parts[1].strip() if len(parts) > 1 else ""

        if cmd == "help":
            out = "Available: write <text>, append <text>, undo, redo, stage, commit <msg>, log, checkout <hash>, diff, clear, reset, status"
            return {"ok": True, "output": out, "state": self.get_state()}

        elif cmd == "write":
            if not args:
                return {"ok": False, "output": "Usage: write <text>", "state": self.get_state()}
            self.engine.write_replace(args, "CLI write")
            return {"ok": True, "output": f"Updated buffer ({len(args)} bytes).", "state": self.get_state()}

        elif cmd == "append":
            if not args:
                return {"ok": False, "output": "Usage: append <text>", "state": self.get_state()}
            prefix = "\n" if self.engine.working_buffer else ""
            self.engine.write_append(prefix + args, "CLI append")
            return {"ok": True, "output": f"Appended to buffer.", "state": self.get_state()}

        elif cmd == "undo":
            ok, rec, msg = self.engine.undo()
            return {"ok": ok, "output": msg, "state": self.get_state()}

        elif cmd == "redo":
            ok, rec, msg = self.engine.redo()
            return {"ok": ok, "output": msg, "state": self.get_state()}

        elif cmd == "stage":
            ok, staged, val, msg = self.engine.stage()
            return {"ok": ok, "output": msg if ok else f"Syntax Error: {val.error_message}", "state": self.get_state()}

        elif cmd == "commit":
            if not args:
                return {"ok": False, "output": "Usage: commit <message>", "state": self.get_state()}
            ok, rec, msg = self.engine.commit(args)
            return {"ok": ok, "output": msg, "state": self.get_state()}

        elif cmd == "checkout":
            if not args:
                return {"ok": False, "output": "Usage: checkout <commit_hash>", "state": self.get_state()}
            ok, rec, msg = self.engine.checkout(args)
            return {"ok": ok, "output": msg, "state": self.get_state()}

        elif cmd == "diff":
            return {"ok": True, "output": self.get_diff_text(), "state": self.get_state()}

        elif cmd == "clear":
            self.engine.clear_buffer()
            return {"ok": True, "output": "Buffer cleared.", "state": self.get_state()}

        elif cmd == "reset":
            self.reset()
            return {"ok": True, "output": "Engine reset to root state.", "state": self.get_state()}

        elif cmd == "status":
            staged = self.engine.staging_buffer.queue_size
            head = self.engine.head_commit_id[:8] if self.engine.head_commit_id else "ROOT"
            out = f"Branch: {self.engine.branch} | HEAD: {head} | Staged: {staged} | Buffer: {len(self.engine.working_buffer)} B"
            return {"ok": True, "output": out, "state": self.get_state()}

        else:
            return {"ok": False, "output": f"Unknown command: '{cmd}'. Type 'help' for commands.", "state": self.get_state()}


def get_html_path():
    """Resolves index.html whether running in dev mode or inside PyInstaller bundle."""
    if getattr(sys, 'frozen', False):
        base_dir = getattr(sys, '_MEIPASS', os.path.dirname(os.path.abspath(__file__)))
    else:
        base_dir = os.path.dirname(os.path.abspath(__file__))

    candidate = os.path.join(base_dir, 'index.html')
    if os.path.exists(candidate):
        return candidate

    # Fallback to current working directory
    cwd_candidate = os.path.join(os.getcwd(), 'index.html')
    if os.path.exists(cwd_candidate):
        return cwd_candidate

    return candidate


def main():
    bridge = VisionBridge()
    html_file = get_html_path()

    window = webview.create_window(
        title='Vision',
        url=html_file,
        js_api=bridge,
        width=1440,
        height=900,
        min_size=(1100, 700),
        resizable=True,
        text_select=True,
        background_color='#FDFBF7'
    )
    webview.start(debug=False)


if __name__ == '__main__':
    main()

