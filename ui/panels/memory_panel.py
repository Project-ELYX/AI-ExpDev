from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import List, Dict, Optional

from PySide6 import QtCore, QtWidgets


@dataclass
class _ItemsPage:
    collection: str
    limit: int = 100
    offset: int = 0


class MemoryPanel(QtWidgets.QWidget):
    def __init__(self, settings=None, parent=None) -> None:
        super().__init__(parent)
        self.settings = settings
        self.setLayout(QtWidgets.QVBoxLayout())

        split = QtWidgets.QSplitter()

        # Left: collections
        left = QtWidgets.QWidget(); ll = QtWidgets.QVBoxLayout(left)
        self.btn_refresh_cols = QtWidgets.QPushButton("Refresh")
        self.btn_clear_col = QtWidgets.QPushButton("Clear Collection")
        lrow = QtWidgets.QHBoxLayout(); lrow.addWidget(self.btn_refresh_cols); lrow.addWidget(self.btn_clear_col); lrow.addStretch(1)
        self.cols_list = QtWidgets.QListWidget()
        ll.addLayout(lrow)
        ll.addWidget(self.cols_list)
        split.addWidget(left)

        # Right: search, items table, actions
        right = QtWidgets.QWidget(); rl = QtWidgets.QVBoxLayout(right)
        srow = QtWidgets.QHBoxLayout()
        self.query_edit = QtWidgets.QLineEdit(); self.query_edit.setPlaceholderText("Search (semantic)")
        self.k_spin = QtWidgets.QSpinBox(); self.k_spin.setRange(1, 200); self.k_spin.setValue(10)
        self.btn_search = QtWidgets.QPushButton("Search")
        srow.addWidget(self.query_edit, 1); srow.addWidget(QtWidgets.QLabel("Top K")); srow.addWidget(self.k_spin); srow.addWidget(self.btn_search)
        rl.addLayout(srow)

        # Items table
        self.table = QtWidgets.QTableWidget(0, 3)
        self.table.setHorizontalHeaderLabels(["ID", "Text (preview)", "ts"])
        self.table.horizontalHeader().setStretchLastSection(True)
        rl.addWidget(self.table)

        # Meta preview
        self.meta_preview = QtWidgets.QPlainTextEdit(readOnly=True)
        rl.addWidget(QtWidgets.QLabel("Meta"))
        rl.addWidget(self.meta_preview)

        # Actions row
        arow = QtWidgets.QHBoxLayout()
        self.btn_delete = QtWidgets.QPushButton("Delete Selected")
        self.btn_export_sel = QtWidgets.QPushButton("Export Selected")
        self.btn_export_all = QtWidgets.QPushButton("Export All")
        self.btn_prev = QtWidgets.QPushButton("Prev")
        self.btn_next = QtWidgets.QPushButton("Next")
        arow.addWidget(self.btn_delete); arow.addWidget(self.btn_export_sel); arow.addWidget(self.btn_export_all)
        arow.addStretch(1); arow.addWidget(self.btn_prev); arow.addWidget(self.btn_next)
        rl.addLayout(arow)

        # Add/import area
        addg = QtWidgets.QGroupBox("Add to Collection")
        ag = QtWidgets.QVBoxLayout(addg)
        self.add_text = QtWidgets.QPlainTextEdit()
        addrow = QtWidgets.QHBoxLayout();
        self.btn_add = QtWidgets.QPushButton("Add Text")
        self.btn_import_files = QtWidgets.QPushButton("Import Files…")
        self.btn_import_dir = QtWidgets.QPushButton("Import Folder…")
        addrow.addWidget(self.btn_add); addrow.addWidget(self.btn_import_files); addrow.addWidget(self.btn_import_dir); addrow.addStretch(1)
        ag.addWidget(self.add_text)
        ag.addLayout(addrow)
        rl.addWidget(addg)

        split.addWidget(right)
        split.setStretchFactor(1, 1)
        self.layout().addWidget(split)

        # State
        self._page: Optional[_ItemsPage] = None

        # Events
        self.btn_refresh_cols.clicked.connect(self.refresh_cols)
        self.btn_clear_col.clicked.connect(self.clear_selected_collection)
        self.cols_list.itemSelectionChanged.connect(self.on_collection_selected)
        self.table.itemSelectionChanged.connect(self.on_row_selected)
        self.btn_search.clicked.connect(self.on_search)
        self.btn_prev.clicked.connect(self.on_prev)
        self.btn_next.clicked.connect(self.on_next)
        self.btn_delete.clicked.connect(self.on_delete_selected)
        self.btn_export_sel.clicked.connect(lambda: self.on_export(selected=True))
        self.btn_export_all.clicked.connect(lambda: self.on_export(selected=False))
        self.btn_add.clicked.connect(self.on_add_text)
        self.btn_import_files.clicked.connect(self.on_import_files)
        self.btn_import_dir.clicked.connect(self.on_import_dir)

        # Initial load
        self.refresh_cols()

    def current_collection(self) -> Optional[str]:
        it = self.cols_list.currentItem()
        return it.data(QtCore.Qt.UserRole) if it else None

    @QtCore.Slot()
    def refresh_cols(self):
        try:
            from vex_native.memory.store import ChromaStore
            store = ChromaStore()
            cols = store.list_collections()
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Memory", f"List collections failed: {e}")
            return
        self.cols_list.clear()
        for c in cols:
            name = c.get('name')
            count = c.get('count')
            it = QtWidgets.QListWidgetItem(f"{name} ({count if count is not None else '?'})")
            it.setData(QtCore.Qt.UserRole, name)
            self.cols_list.addItem(it)

    @QtCore.Slot()
    def on_collection_selected(self):
        name = self.current_collection()
        if not name:
            return
        self._page = _ItemsPage(collection=name)
        self.load_items()

    def load_items(self):
        if not self._page:
            return
        try:
            from vex_native.memory.store import ChromaStore
            store = ChromaStore()
            data = store.list_items(self._page.collection, limit=self._page.limit, offset=self._page.offset)
            items = data.get('items', [])
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Memory", f"List items failed: {e}")
            return
        self.table.setRowCount(0)
        for it in items:
            row = self.table.rowCount()
            self.table.insertRow(row)
            id_item = QtWidgets.QTableWidgetItem(str(it.get('id')))
            txt = (it.get('text') or '')
            preview = txt[:300].replace('\n', ' ')
            text_item = QtWidgets.QTableWidgetItem(preview)
            ts = (it.get('meta', {}) or {}).get('ts')
            ts_item = QtWidgets.QTableWidgetItem(str(ts or ''))
            self.table.setItem(row, 0, id_item)
            self.table.setItem(row, 1, text_item)
            self.table.setItem(row, 2, ts_item)
            # stash full meta for preview
            self.table.setRowHeight(row, 22)
            self.table.item(row, 0).setData(QtCore.Qt.UserRole, it)
        self.meta_preview.clear()

    @QtCore.Slot()
    def on_row_selected(self):
        sel = self.table.selectedItems()
        if not sel:
            self.meta_preview.clear(); return
        # fetch row meta
        row = sel[0].row()
        it = self.table.item(row, 0).data(QtCore.Qt.UserRole) or {}
        import json
        self.meta_preview.setPlainText(json.dumps(it.get('meta', {}) or {}, indent=2))

    @QtCore.Slot()
    def on_search(self):
        col = self.current_collection()
        if not col:
            QtWidgets.QMessageBox.information(self, "Memory", "Select a collection first")
            return
        q = self.query_edit.text().strip()
        if not q:
            return
        try:
            from vex_native.memory.embedder import get_embedder
            from vex_native.memory.store import ChromaStore
            emb = get_embedder()
            vec = QtCore.QThreadPool.globalInstance()
        except Exception:
            pass
        # Run async to avoid freezing UI
        QtCore.QThreadPool.globalInstance().start(_SearchTask(col, q, int(self.k_spin.value()), self.on_search_results))

    def on_search_results(self, ok: bool, items: List[Dict], msg: str = ""):
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Search", msg or "failed")
            return
        self.table.setRowCount(0)
        for it in items:
            row = self.table.rowCount(); self.table.insertRow(row)
            id_item = QtWidgets.QTableWidgetItem(str(it.get('id', '')))
            text_item = QtWidgets.QTableWidgetItem((it.get('text','')[:300]).replace('\n',' '))
            ts_item = QtWidgets.QTableWidgetItem(str((it.get('meta',{}) or {}).get('ts','')))
            self.table.setItem(row, 0, id_item)
            self.table.setItem(row, 1, text_item)
            self.table.setItem(row, 2, ts_item)
            self.table.item(row, 0).setData(QtCore.Qt.UserRole, it)
        self.meta_preview.clear()

    @QtCore.Slot()
    def on_prev(self):
        if self._page and self._page.offset > 0:
            self._page.offset = max(0, self._page.offset - self._page.limit)
            self.load_items()

    @QtCore.Slot()
    def on_next(self):
        if self._page:
            self._page.offset += self._page.limit
            self.load_items()

    @QtCore.Slot()
    def on_delete_selected(self):
        col = self.current_collection();
        if not col:
            return
        rows = self.table.selectionModel().selectedRows()
        if not rows:
            return
        ids = []
        # remove backing files if stored under memory root
        memroot = Path(getattr(self.settings, 'memory_root_dir', '')) if self.settings is not None else None
        for r in rows:
            it = self.table.item(r.row(), 0).data(QtCore.Qt.UserRole) or {}
            meta = (it.get('meta') or {})
            p = meta.get('path') or meta.get('source')
            if p and memroot and str(p).startswith(str(memroot)):
                try:
                    Path(p).unlink(missing_ok=True)
                except Exception:
                    pass
            ids.append(self.table.item(r.row(), 0).text())
        try:
            from vex_native.memory.store import ChromaStore
            store = ChromaStore(); store.delete_ids(col, ids)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Delete", f"Failed: {e}")
            return
        self.load_items()

    @QtCore.Slot()
    def clear_selected_collection(self):
        col = self.current_collection();
        if not col:
            return
        if QtWidgets.QMessageBox.question(self, "Clear", f"Clear collection '{col}'?") != QtWidgets.QMessageBox.Yes:
            return
        try:
            from vex_native.memory.store import ChromaStore
            store = ChromaStore(); store.clear_collection(col)
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Clear", f"Failed: {e}")
            return
        self.load_items(); self.refresh_cols()

    @QtCore.Slot()
    def on_export(self, selected: bool):
        col = self.current_collection();
        if not col:
            return
        path, _ = QtWidgets.QFileDialog.getSaveFileName(self, "Export JSONL", f"{col}.jsonl", "JSON Lines (*.jsonl)")
        if not path:
            return
        rows = self.table.selectionModel().selectedRows() if selected else [QtCore.QModelIndex() for _ in range(self.table.rowCount())]
        data: List[Dict] = []
        if selected:
            for r in rows:
                it = self.table.item(r.row(), 0).data(QtCore.Qt.UserRole) or {}
                data.append(it)
        else:
            # paginate all
            try:
                from vex_native.memory.store import ChromaStore
                store = ChromaStore()
                off = 0
                while True:
                    chunk = store.list_items(col, limit=500, offset=off).get('items', [])
                    if not chunk:
                        break
                    data.extend(chunk)
                    off += 500
            except Exception as e:
                QtWidgets.QMessageBox.warning(self, "Export", f"Failed: {e}")
                return
        try:
            import json
            with open(path, 'w', encoding='utf-8') as f:
                for it in data:
                    f.write(json.dumps(it, ensure_ascii=False) + "\n")
        except Exception as e:
            QtWidgets.QMessageBox.warning(self, "Export", f"Failed: {e}")

    @QtCore.Slot()
    def on_add_text(self):
        col = self.current_collection();
        if not col:
            QtWidgets.QMessageBox.information(self, "Add", "Select a collection first")
            return
        txt = self.add_text.toPlainText().strip()
        if not txt:
            return
        # write file for this memory
        meta = {}
        try:
            from vex_native.orchestrator import detect_domains
            ds = detect_domains([{ "role":"user", "content": txt }])
            if ds:
                meta["domains"] = ds
        except Exception:
            pass
        memroot = Path(getattr(self.settings, 'memory_root_dir', '')) if self.settings is not None else None
        if memroot:
            path = self._write_memory_file(col, txt, memroot)
            meta = {"path": str(path)}
            try:
                if 'domains' in meta:
                    pass
                else:
                    from vex_native.orchestrator import detect_domains
                    ds = detect_domains([{ "role":"user", "content": txt }])
                    if ds:
                        meta["domains"] = ds
            except Exception:
                pass
        QtCore.QThreadPool.globalInstance().start(_UpsertTask(col, [txt], [meta], self.on_upsert_done))

    def on_upsert_done(self, ok: bool, ids: List[str], docs: List[str], metas: List[Dict], msg: str = ""):
        if not ok:
            QtWidgets.QMessageBox.warning(self, "Add", msg or "failed")
            return
        # Emit on_memory_upserted for each item
        try:
            from vex_native.agents.manager import agent_manager
            col = self.current_collection() or ""
            for _id, d, m in zip(ids or [], docs or [], metas or []):
                agent_manager.emit_event("on_memory_upserted", {"collection": col, "id": _id, "text": d, "meta": m or {}})
        except Exception:
            pass
        self.add_text.clear(); self.load_items(); self.refresh_cols()

    @QtCore.Slot()
    def on_import_files(self):
        col = self.current_collection();
        if not col:
            QtWidgets.QMessageBox.information(self, "Import", "Select a collection first")
            return
        paths, _ = QtWidgets.QFileDialog.getOpenFileNames(self, "Select files to import", str(Path.home()), "Text files (*.txt *.md);;All files (*)")
        if not paths:
            return
        self._import_paths(col, [Path(p) for p in paths])

    @QtCore.Slot()
    def on_import_dir(self):
        col = self.current_collection();
        if not col:
            QtWidgets.QMessageBox.information(self, "Import", "Select a collection first")
            return
        d = QtWidgets.QFileDialog.getExistingDirectory(self, "Select folder", str(Path.home()))
        if not d:
            return
        folder = Path(d)
        paths: List[Path] = []
        for ext in ("*.txt", "*.md"):
            paths += list(folder.rglob(ext))
        if not paths:
            QtWidgets.QMessageBox.information(self, "Import", "No .txt/.md files found")
            return
        self._import_paths(col, paths)

    def _import_paths(self, collection: str, paths: List[Path]):
        docs = []
        metas = []
        for p in paths:
            try:
                text = p.read_text(encoding='utf-8')
                docs.append(text)
                # copy into memory root for unified management
                memroot = Path(getattr(self.settings, 'memory_root_dir', '')) if self.settings is not None else None
                if memroot:
                    newp = self._write_memory_file(collection, text, memroot, src=p)
                    meta = {"path": str(newp), "source": str(p)}
                    try:
                        from vex_native.orchestrator import detect_domains
                        ds = detect_domains([{ "role":"user", "content": text }])
                        if ds:
                            meta["domains"] = ds
                    except Exception:
                        pass
                    metas.append(meta)
                else:
                    meta = {"source": str(p)}
                    try:
                        from vex_native.orchestrator import detect_domains
                        ds = detect_domains([{ "role":"user", "content": text }])
                        if ds:
                            meta["domains"] = ds
                    except Exception:
                        pass
                    metas.append(meta)
            except Exception:
                continue
        if not docs:
            return
        QtCore.QThreadPool.globalInstance().start(_UpsertTask(collection, docs, metas, self.on_upsert_done, batch=True))

    def _write_memory_file(self, collection: str, text: str, root: Path, src: Optional[Path] = None) -> Path:
        import time, re
        col_dir = root / collection
        col_dir.mkdir(parents=True, exist_ok=True)
        ts = int(time.time())
        # slug from first words
        head = " ".join(text.split()[:6])
        slug = re.sub(r"[^a-zA-Z0-9_-]+", "_", head)[:40] or "mem"
        ext = ".md"
        path = col_dir / f"{ts}_{slug}{ext}"
        try:
            path.write_text(text, encoding='utf-8')
        except Exception:
            pass
        return path


class _SearchTask(QtCore.QRunnable):
    def __init__(self, collection: str, query: str, k: int, cb):
        super().__init__()
        self.collection = collection
        self.query = query
        self.k = k
        self.cb = cb

    def run(self):
        import asyncio
        async def _run():
            try:
                from vex_native.memory.embedder import get_embedder
                from vex_native.memory.store import ChromaStore
                emb = get_embedder()
                qvec = await emb.embed_one(self.query)
                store = ChromaStore()
                hits = await store.query(collection=self.collection, query_embedding=qvec, n_results=self.k)
                QtCore.QMetaObject.invokeMethod(self.cb.__self__, self.cb.__name__, QtCore.Qt.QueuedConnection,
                                                QtCore.Q_ARG(bool, True), QtCore.Q_ARG(list, hits), QtCore.Q_ARG(str, ""))
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(self.cb.__self__, self.cb.__name__, QtCore.Qt.QueuedConnection,
                                                QtCore.Q_ARG(bool, False), QtCore.Q_ARG(list, []), QtCore.Q_ARG(str, str(e)))
        try:
            asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.new_event_loop(); loop.run_until_complete(_run())


class _UpsertTask(QtCore.QRunnable):
    def __init__(self, collection: str, docs: List[str], metas: List[Dict], cb, batch: bool = False):
        super().__init__()
        self.collection = collection
        self.docs = docs
        self.metas = metas
        self.cb = cb
        self.batch = batch

    def run(self):
        import asyncio
        async def _run():
            try:
                from vex_native.memory.embedder import get_embedder
                from vex_native.memory.store import ChromaStore
                emb = get_embedder()
                if self.batch:
                    from typing import List as _List
                    embs = await emb.embed_batch(self.docs)
                else:
                    embs = []
                    for d in self.docs:
                        embs.append(await emb.embed_one(d))
                store = ChromaStore()
                ids = await store.upsert(collection=self.collection, embeddings=embs, documents=self.docs, metadatas=self.metas)
                QtCore.QMetaObject.invokeMethod(self.cb.__self__, self.cb.__name__, QtCore.Qt.QueuedConnection,
                                                QtCore.Q_ARG(bool, True), QtCore.Q_ARG(list, ids), QtCore.Q_ARG(list, self.docs), QtCore.Q_ARG(list, self.metas), QtCore.Q_ARG(str, ""))
            except Exception as e:
                QtCore.QMetaObject.invokeMethod(self.cb.__self__, self.cb.__name__, QtCore.Qt.QueuedConnection,
                                                QtCore.Q_ARG(bool, False), QtCore.Q_ARG(list, []), QtCore.Q_ARG(list, []), QtCore.Q_ARG(list, []), QtCore.Q_ARG(str, str(e)))
        try:
            asyncio.run(_run())
        except RuntimeError:
            loop = asyncio.new_event_loop(); loop.run_until_complete(_run())
