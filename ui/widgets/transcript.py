from __future__ import annotations

from datetime import datetime
from typing import Optional

from PySide6 import QtCore, QtGui, QtWidgets


class MessageBubble(QtWidgets.QWidget):
    save_text_requested = QtCore.Signal(str)
    def __init__(self, role: str, text: str, ts: Optional[float] = None, parent=None, display_name: Optional[str] = None,
                 width_ratio: float = 0.65, max_px: int = 900):
        super().__init__(parent)
        self.role = role
        self.ts = ts or datetime.now().timestamp()
        self.display_name = display_name
        self._width_ratio = float(width_ratio)
        # Hard cap so bubbles never exceed ~half the inner transcript width
        self._hard_max_ratio = 0.48
        self._max_px = int(max_px)

        # Layout: bubble aligned left or right
        outer = QtWidgets.QHBoxLayout(self)
        outer.setContentsMargins(4, 2, 4, 2)
        outer.setSpacing(0)

        self.bubble = QtWidgets.QWidget()
        self.bubble.setObjectName("bubble")
        vb = QtWidgets.QVBoxLayout(self.bubble)
        vb.setContentsMargins(12, 8, 12, 8)
        vb.setSpacing(4)

        # Quick actions row (hidden until hover)
        self._actions = QtWidgets.QWidget(self.bubble)
        _al = QtWidgets.QHBoxLayout(self._actions)
        _al.setContentsMargins(0, 0, 0, 0)
        _al.addStretch(1)
        self.btn_copy = QtWidgets.QToolButton(); self.btn_copy.setText("⧉"); self.btn_copy.setAutoRaise(True); self.btn_copy.setToolTip("Copy message")
        self.btn_save = QtWidgets.QToolButton(); self.btn_save.setText("⤓"); self.btn_save.setAutoRaise(True); self.btn_save.setToolTip("Save to Memory")
        _al.addWidget(self.btn_copy); _al.addWidget(self.btn_save)
        self._actions.setVisible(False)

        self.content = QtWidgets.QTextBrowser()
        self.content.setOpenExternalLinks(True)
        self.content.setReadOnly(True)
        self.content.setFrameShape(QtWidgets.QFrame.NoFrame)
        # Do not show scrollbars; we auto-fit by wrapping
        self.content.setHorizontalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        self.content.setVerticalScrollBarPolicy(QtCore.Qt.ScrollBarAlwaysOff)
        # Wrap text to the available widget width and break long words/URLs
        self.content.setLineWrapMode(QtWidgets.QTextEdit.WidgetWidth)
        self.content.setWordWrapMode(QtGui.QTextOption.WrapAtWordBoundaryOrAnywhere)
        # Let size adjust to contents while we still manually sync height
        try:
            self.content.setSizeAdjustPolicy(QtWidgets.QAbstractScrollArea.AdjustToContents)
        except Exception:
            pass
        # No hard-coded minimum that can force overflow on small windows
        self.content.setMinimumWidth(80)
        self.content.setMaximumWidth(self._max_px)
        self.content.setTextInteractionFlags(QtCore.Qt.TextSelectableByMouse | QtCore.Qt.LinksAccessibleByMouse)
        self.content.setSizePolicy(QtWidgets.QSizePolicy.Preferred, QtWidgets.QSizePolicy.Minimum)
        # Auto-resize with content
        self.content.installEventFilter(self)
        try:
            self.content.document().contentsChanged.connect(self._sync_content_height)
        except Exception:
            pass

        self.meta = QtWidgets.QLabel()
        self.meta.setObjectName("metaline")
        try:
            self.meta.setProperty("role", "meta")
        except Exception:
            pass
        self.meta.setWordWrap(True)

        vb.addWidget(self._actions)
        vb.addWidget(self.content)
        vb.addWidget(self.meta)

        # Avatar badge
        self.avatar = QtWidgets.QLabel()
        self.avatar.setObjectName("avatar")
        self.avatar.setFixedSize(32, 32)
        self.avatar.setAlignment(QtCore.Qt.AlignCenter)
        letter = 'Y' if role == 'user' else ((self.display_name or 'V')[0].upper())
        self.avatar.setText(letter)

        if role == "user":
            outer.addStretch(1)
            outer.addWidget(self.bubble, 0, QtCore.Qt.AlignRight)
            outer.addWidget(self.avatar, 0, QtCore.Qt.AlignRight)
        else:
            outer.addWidget(self.avatar, 0, QtCore.Qt.AlignLeft)
            outer.addWidget(self.bubble, 0, QtCore.Qt.AlignLeft)
            outer.addStretch(1)

        self.set_text(text)
        self._apply_style()
        self._sync_content_height()
        # actions
        self.btn_copy.clicked.connect(lambda: QtWidgets.QApplication.clipboard().setText(self.plain_text()))
        self.btn_save.clicked.connect(lambda: self.save_text_requested.emit(self.plain_text()))
        self.bubble.installEventFilter(self)
        self.content.installEventFilter(self)

    def set_text(self, text: str):
        # Render Markdown with Qt's built-in support, and add copy links for fenced code blocks
        md, mapping = self._augment_markdown_with_copy(text)
        self._code_map = mapping  # id -> code string
        self.content.setOpenLinks(False)
        # Try syntax highlight with pygments if available
        html = None
        try:
            html = self._to_highlighted_html(md)
        except Exception:
            html = None
        try:
            if html:
                self.content.setHtml(html)
            else:
                self.content.setMarkdown(md)
        except Exception:
            self.content.setPlainText(text)
        # Connect once to copy handler (avoid warnings)
        if not getattr(self, "_anchors_connected", False):
            try:
                self.content.anchorClicked.connect(self._on_anchor_clicked)  # type: ignore
                self._anchors_connected = True
            except Exception:
                pass
        dt = datetime.fromtimestamp(self.ts).strftime("%Y-%m-%d %H:%M:%S")
        if self.role == "user":
            who = "You"
        else:
            who = self.display_name or "Assistant"
        self.meta.setText(f"{who} • {dt}")
        self._sync_content_height()

    def _apply_style(self):
        # Bubble colors
        if self.role == "user":
            bg = QtGui.QColor(36, 84, 120)
            fg = QtGui.QColor(230, 240, 250)
        else:
            bg = QtGui.QColor(40, 44, 52)
            fg = QtGui.QColor(235, 235, 235)

        pal = self.bubble.palette()
        pal.setColor(QtGui.QPalette.Window, bg)
        pal.setColor(QtGui.QPalette.WindowText, fg)
        self.bubble.setAutoFillBackground(True)
        self.bubble.setPalette(pal)

        # Meta subdued
        self.meta.setStyleSheet("color: #9db0c2; font-size: 11px;")
        # Rounded background with subtle neon border; shadow effect for depth
        self.bubble.setStyleSheet(
            "#bubble { border-radius: 10px; border: 1px solid rgba(125,92,255,0.35); }"
        )
        try:
            eff = QtWidgets.QGraphicsDropShadowEffect(self.bubble)
            eff.setBlurRadius(14)
            eff.setOffset(0, 0)
            eff.setColor(QtGui.QColor(125, 92, 255, 80))
            self.bubble.setGraphicsEffect(eff)
        except Exception:
            pass

    def _augment_markdown_with_copy(self, text: str):
        import re
        code_map = {}
        idx = 0

        def repl(match):
            nonlocal idx
            lang = (match.group(1) or "").strip()
            code = match.group(2)
            cid = f"code{idx}"
            idx += 1
            code_map[cid] = code
            # Add a copy link after the block; Qt will render the link and we intercept it
            return f"```{lang}\n{code}\n```\n[Copy code](copy://{cid})\n"

        md = re.sub(r"```([A-Za-z0-9_+-]*)\n([\s\S]*?)\n```", repl, text)
        return md, code_map

    def _to_highlighted_html(self, md_text: str) -> Optional[str]:
        """Replace fenced code blocks with pygments-highlighted HTML and wrap rest as Markdown.
        Returns HTML string or None if pygments not available.
        """
        try:
            import re
            from pygments import highlight  # type: ignore
            from pygments.lexers import get_lexer_by_name, TextLexer  # type: ignore
            from pygments.formatters import HtmlFormatter  # type: ignore
        except Exception:
            return None

        fmt = HtmlFormatter(nowrap=False, cssclass="codehilite")
        css = fmt.get_style_defs('.codehilite')

        parts = []
        last = 0
        pattern = re.compile(r"```([A-Za-z0-9_+-]*)\n([\s\S]*?)\n```", re.M)
        for m in pattern.finditer(md_text):
            pre = md_text[last:m.start()]
            if pre:
                # let Qt handle this snippet as Markdown via <p> wrapper
                parts.append(f"<p>{QtWidgets.QTextDocument().toPlainText()}</p>")
                parts[-1] = pre.replace('\n', '<br/>')
            lang = (m.group(1) or '').strip() or 'text'
            code = m.group(2)
            try:
                lex = get_lexer_by_name(lang)
            except Exception:
                lex = TextLexer()
            hl = highlight(code, lex, fmt)
            parts.append(f"<div class='codewrap'>{hl}</div>")
            last = m.end()
        tail = md_text[last:]
        if tail:
            parts.append(tail.replace('\n', '<br/>'))

        # Make code blocks wrap when possible to avoid overflowing bubbles.
        # Fallback to scrollbar if Qt CSS support is limited.
        html = f"""
<html>
<head>
<style>
{css}
pre {{ background:#0f1318; border:1px solid #2b2b2b; border-radius:6px; padding:8px; white-space: pre-wrap; word-break: break-word; overflow-wrap: anywhere; }}
.codewrap {{ margin: 6px 0; }}
a {{ color:#59aaff; }}
</style>
</head>
<body>
{''.join(parts)}
</body>
</html>
"""
        return html

    def _on_anchor_clicked(self, url):
        try:
            qurl = url  # QUrl
            if qurl.scheme() == "copy":
                cid = qurl.path().lstrip('/')
                code = getattr(self, "_code_map", {}).get(cid, "")
                if code:
                    QtWidgets.QApplication.clipboard().setText(code)
                    self.meta.setText(self.meta.text() + "  •  copied")
        except Exception:
            pass

    def _sync_content_height(self):
        try:
            doc = self.content.document()
            # Determine available container width (scroll viewport propagated to parent container)
            cont_w = self.parentWidget().width() if self.parentWidget() else self.width()
            if cont_w <= 0:
                cont_w = self.content.viewport().width() or 600
            # Limit content width by ratio and absolute cap, but never exceed container width.
            # Apply a safety cap slightly under half the container for clear separation.
            effective_ratio = min(self._width_ratio, getattr(self, '_hard_max_ratio', 0.48))
            max_allow = int(cont_w * effective_ratio)
            w_lim = max(100, min(max_allow, self._max_px, cont_w - 8))
            # Natural content width for short messages so bubbles don't look oversized
            natural = int(max(1.0, self.content.document().idealWidth())) + 6
            target_w = max(80, min(w_lim, natural))
            # Bubble has inner margins (~24px). Keep bubble within container, then content inside bubble.
            bubble_w = max(100, min(target_w + 24, cont_w - 4))
            # Fix widths so the entire bubble panel scales to content (up to cap)
            self.content.setFixedWidth(target_w)
            self.bubble.setFixedWidth(bubble_w)
            doc.setTextWidth(target_w)
            # Height from document size
            h = int(doc.size().height()) + 8
            h = max(24, h)
            self.content.setFixedHeight(h)
            self.updateGeometry()
        except Exception:
            pass

    def eventFilter(self, obj, event):
        if obj is self.content and event.type() in (QtCore.QEvent.Resize, QtCore.QEvent.Show):
            QtCore.QTimer.singleShot(0, self._sync_content_height)
        if obj in (self.bubble, self.content):
            if event.type() == QtCore.QEvent.Enter:
                self._actions.setVisible(True)
            elif event.type() == QtCore.QEvent.Leave:
                self._actions.setVisible(False)
        return super().eventFilter(obj, event)

    def resizeEvent(self, event):
        # When the bubble/container resizes (e.g., window or splitter moves), re-sync sizes
        try:
            QtCore.QTimer.singleShot(0, self._sync_content_height)
        except Exception:
            pass
        super().resizeEvent(event)


class ChatTranscript(QtWidgets.QWidget):
    save_text_requested = QtCore.Signal(str)
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        lay = QtWidgets.QVBoxLayout(self)
        lay.setContentsMargins(0, 0, 0, 0)
        lay.setSpacing(0)

        self.scroll = QtWidgets.QScrollArea()
        self.scroll.setWidgetResizable(True)
        self.scroll.setFrameShape(QtWidgets.QFrame.NoFrame)

        self.container = QtWidgets.QWidget()
        self.vbox = QtWidgets.QVBoxLayout(self.container)
        self.vbox.setContentsMargins(8, 8, 8, 8)
        self.vbox.setSpacing(8)
        self.vbox.addStretch(1)

        self.scroll.setWidget(self.container)
        lay.addWidget(self.scroll)

        self._last_assistant: Optional[MessageBubble] = None
        self._width_ratio = 0.65
        self._max_px = 900

    def resizeEvent(self, event):
        # Propagate viewport size changes to bubbles so they can recompute limits
        super().resizeEvent(event)
        QtCore.QTimer.singleShot(0, self._resync_bubbles)

    def clear(self):
        # Remove all but stretch
        while self.vbox.count() > 1:
            item = self.vbox.takeAt(0)
            w = item.widget()
            if w is not None:
                w.deleteLater()
        self._last_assistant = None

    def add_message(self, role: str, text: str, ts: Optional[float] = None, display_name: Optional[str] = None) -> MessageBubble:
        # Insert above stretch
        bubble = MessageBubble(role, text, ts, display_name=display_name, width_ratio=self._width_ratio, max_px=self._max_px)
        self.vbox.insertWidget(self.vbox.count() - 1, bubble)
        try:
            bubble.save_text_requested.connect(self.save_text_requested.emit)
        except Exception:
            pass
        self._maybe_set_last_assistant(bubble)
        QtCore.QTimer.singleShot(0, self.scroll_to_bottom)
        return bubble

    def set_width_policy(self, ratio: float, max_px: int):
        self._width_ratio = float(ratio)
        self._max_px = int(max_px)
        # Update existing bubbles
        for i in range(self.vbox.count() - 1):
            w = self.vbox.itemAt(i).widget()
            if isinstance(w, MessageBubble):
                w._width_ratio = self._width_ratio
                w._max_px = self._max_px
                w.content.setMaximumWidth(self._max_px)
                w._sync_content_height()

    def _maybe_set_last_assistant(self, bubble: MessageBubble):
        if bubble.role == "assistant":
            self._last_assistant = bubble

    def set_last_assistant_text(self, text: str):
        if self._last_assistant is not None:
            self._last_assistant.set_text(text)
        QtCore.QTimer.singleShot(0, self.scroll_to_bottom)

    def scroll_to_bottom(self):
        bar = self.scroll.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _resync_bubbles(self):
        for i in range(self.vbox.count() - 1):
            w = self.vbox.itemAt(i).widget()
            if isinstance(w, MessageBubble):
                w._sync_content_height()
