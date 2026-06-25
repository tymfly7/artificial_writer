"""A polished Tkinter desktop front-end for Artificial Writer.

Long-running work (fetching, summarizing) runs on a background thread so the UI
stays responsive, with results marshalled back to the Tk main loop safely.
"""

from __future__ import annotations

import queue
import threading
import tkinter as tk
from tkinter import messagebox, scrolledtext, ttk

from .config import SummarizerType, configure_logging, get_settings
from .errors import ArtificialWriterError
from .fetcher import FetchedArticle
from .pipeline import Pipeline, PipelineResult

_BG = "#f7f5dd"
_ACCENT = "#9bdeac"
_FONT = "Segoe UI"
_PLACEHOLDER = "https://example.com/article"

# Font sizes (bumped up for readability / high-DPI displays).
_SIZE_BODY = 13
_SIZE_HEADER = 14
_SIZE_TEXT = 12


class App(tk.Tk):
    """Main application window."""

    def __init__(self) -> None:
        super().__init__()
        self.title("Artificial Writer")
        self.configure(bg=_BG, padx=16, pady=12)
        self.minsize(900, 560)

        self._settings = get_settings()
        self._article: FetchedArticle | None = None
        self._result: PipelineResult | None = None
        self._queue: queue.Queue = queue.Queue()

        self._build_widgets()
        self._poll_queue()

    # -- UI construction ---------------------------------------------------

    def _build_widgets(self) -> None:
        top = tk.Frame(self, bg=_BG)
        top.pack(fill="x", pady=(0, 8))

        tk.Label(top, text="URL:", bg=_BG, font=(_FONT, _SIZE_BODY)).pack(side="left")

        self.url_var = tk.StringVar(value=_PLACEHOLDER)
        self.url_entry = tk.Entry(top, textvariable=self.url_var, font=(_FONT, _SIZE_BODY))
        self.url_entry.pack(side="left", fill="x", expand=True, padx=8)
        self.url_entry.bind("<FocusIn>", self._clear_placeholder)
        self.url_entry.bind("<Return>", lambda _e: self._fetch())

        tk.Label(top, text="Backend:", bg=_BG, font=(_FONT, _SIZE_BODY)).pack(side="left")
        self.backend_var = tk.StringVar(value=self._settings.summarizer.value)
        ttk.Combobox(
            top,
            textvariable=self.backend_var,
            values=[s.value for s in SummarizerType],
            state="readonly",
            width=12,
            font=(_FONT, _SIZE_BODY),
        ).pack(side="left", padx=8)

        tk.Label(top, text="Model:", bg=_BG, font=(_FONT, _SIZE_BODY)).pack(side="left")
        self.model_var = tk.StringVar(value=self._settings.ollama_model)
        tk.Entry(top, textvariable=self.model_var, width=16, font=(_FONT, _SIZE_BODY)).pack(
            side="left", padx=8
        )

        self.fetch_btn = tk.Button(
            top,
            text="Fetch",
            bg=_ACCENT,
            font=(_FONT, _SIZE_BODY, "bold"),
            command=self._fetch,
        )
        self.fetch_btn.pack(side="left")

        self.go_btn = tk.Button(
            top,
            text="Summarize",
            bg=_ACCENT,
            font=(_FONT, _SIZE_BODY, "bold"),
            command=self._summarize,
            state="disabled",
        )
        self.go_btn.pack(side="left", padx=(8, 0))

        panes = tk.Frame(self, bg=_BG)
        panes.pack(fill="both", expand=True)
        panes.columnconfigure(0, weight=1)
        panes.columnconfigure(1, weight=1)
        panes.rowconfigure(1, weight=1)

        header_font = (_FONT, _SIZE_HEADER, "bold")
        tk.Label(panes, text="Original", bg=_BG, font=header_font).grid(row=0, column=0, sticky="w")
        tk.Label(panes, text="Summary", bg=_BG, font=header_font).grid(row=0, column=1, sticky="w")

        self.original = scrolledtext.ScrolledText(panes, wrap="word", font=(_FONT, _SIZE_TEXT))
        self.original.grid(row=1, column=0, sticky="nsew", padx=(0, 6))
        self.summary = scrolledtext.ScrolledText(panes, wrap="word", font=(_FONT, _SIZE_TEXT))
        self.summary.grid(row=1, column=1, sticky="nsew", padx=(6, 0))

        bottom = tk.Frame(self, bg=_BG)
        bottom.pack(fill="x", pady=(8, 0))
        self.save_btn = tk.Button(
            bottom,
            text="Save",
            bg=_ACCENT,
            font=(_FONT, _SIZE_BODY),
            command=self._save,
            state="disabled",
        )
        self.save_btn.pack(side="left")

        self.progress = ttk.Progressbar(bottom, mode="indeterminate", length=160)
        # Packed on demand while work runs; hidden otherwise.

        self.status = tk.StringVar(value="Ready.")
        tk.Label(
            bottom,
            textvariable=self.status,
            bg=_BG,
            anchor="w",
            fg="#555",
            font=(_FONT, _SIZE_BODY),
        ).pack(side="left", fill="x", expand=True, padx=12)

    # -- Loading indicator -------------------------------------------------

    def _start_loading(self) -> None:
        self.progress.pack(side="right", padx=(0, 4))
        self.progress.start(12)

    def _stop_loading(self) -> None:
        self.progress.stop()
        self.progress.pack_forget()

    # -- Event handlers ----------------------------------------------------

    def _clear_placeholder(self, _event: object) -> None:
        if self.url_var.get() == _PLACEHOLDER:
            self.url_var.set("")

    def _fetch(self) -> None:
        """Step one: fetch and display the original article text."""
        url = self.url_var.get().strip()
        if not url or url == _PLACEHOLDER:
            messagebox.showwarning("No URL", "Please enter a URL to fetch.")
            return

        self._article = None
        self._result = None
        self.fetch_btn.config(state="disabled")
        self.go_btn.config(state="disabled")
        self.save_btn.config(state="disabled")
        self.original.delete("1.0", "end")
        self.summary.delete("1.0", "end")
        self.status.set("Fetching...")
        self._start_loading()

        threading.Thread(target=self._fetch_worker, args=(url,), daemon=True).start()

    def _fetch_worker(self, url: str) -> None:
        try:
            article = Pipeline(self._settings).fetch(url)
            self._queue.put(("fetched", article))
        except ArtificialWriterError as exc:
            self._queue.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001 - keep the UI alive on any failure
            self._queue.put(("error", f"Unexpected error: {exc}"))

    def _summarize(self) -> None:
        """Step two: summarize the already-fetched text."""
        if self._article is None:
            messagebox.showwarning("Nothing to summarize", "Fetch a URL first.")
            return

        self.fetch_btn.config(state="disabled")
        self.go_btn.config(state="disabled")
        self.save_btn.config(state="disabled")
        self.summary.delete("1.0", "end")
        self.status.set("Summarizing...")
        self._start_loading()

        update: dict[str, object] = {"summarizer": self.backend_var.get()}
        model = self.model_var.get().strip()
        if model:
            # Applies to the Ollama backend; ignored by others.
            update["ollama_model"] = model
        settings = self._settings.model_copy(update=update)
        article = self._article
        threading.Thread(
            target=self._summarize_worker, args=(article, settings), daemon=True
        ).start()

    def _summarize_worker(self, article: FetchedArticle, settings: object) -> None:
        try:
            result = Pipeline(settings).summarize_text(  # type: ignore[arg-type]
                article.text, title=article.title
            )
            self._queue.put(("ok", result))
        except ArtificialWriterError as exc:
            self._queue.put(("error", str(exc)))
        except Exception as exc:  # noqa: BLE001 - keep the UI alive on any failure
            self._queue.put(("error", f"Unexpected error: {exc}"))

    def _poll_queue(self) -> None:
        try:
            kind, payload = self._queue.get_nowait()
        except queue.Empty:
            pass
        else:
            self._stop_loading()
            if kind == "fetched":
                self._show_article(payload)
            elif kind == "ok":
                self._show_result(payload)
            else:
                self.status.set("Failed.")
                messagebox.showerror("Error", str(payload))
            self.fetch_btn.config(state="normal")
            # Summarize stays available only once something has been fetched.
            self.go_btn.config(state="normal" if self._article else "disabled")
        self.after(100, self._poll_queue)

    def _show_article(self, article: FetchedArticle) -> None:
        self._article = article
        self.original.delete("1.0", "end")
        self.original.insert("end", article.text)
        self.status.set(f"Fetched {article.word_count} words. Ready to summarize.")

    def _show_result(self, result: PipelineResult) -> None:
        self._result = result
        self.summary.delete("1.0", "end")
        self.summary.insert("end", result.summary.summary)
        self.save_btn.config(state="normal")
        self.status.set(
            f"Done via {result.summary.backend} in {result.summary.elapsed_seconds:.2f}s."
        )

    def _save(self) -> None:
        if not self._result:
            return
        path = Pipeline(self._settings)._storage.save_summary(  # noqa: SLF001 - internal reuse
            self._result.article.title,
            self._result.article.text,
            self._result.summary.summary,
        )
        self.status.set(f"Saved to {path}")
        messagebox.showinfo("Saved", f"Summary saved to:\n{path}")


def main() -> None:
    """Launch the desktop GUI."""
    configure_logging()
    App().mainloop()


if __name__ == "__main__":  # pragma: no cover
    main()
