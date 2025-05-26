from tkinter import Tk, messagebox, scrolledtext, Label, Entry, Button, END
from file_handler import FileHandler
from text_fetcher import TextFetcher
from writer import Writer

GREEN = "#9bdeac"
YELLOW = "#f7f5dd"
FONT_NAME = "Courier"

class App(Tk):
    """Main application class. It inherits from the Tk module of the tkinter package"""

    def __init__(self):
        super().__init__()
        self.title("Artificial Writer")
        self.config(padx=50, pady=10, bg=YELLOW)
        self.resizable(False, False)
        self.fetched_text = ''
        # URL input
        self.url_label = Label(self, text="Enter URL:", bg=YELLOW, font=(FONT_NAME, 20, 'normal'))
        self.url_label.grid(column=0, row=0)

        self.url_entry = Entry(self, width=50)
        self.url_entry.grid(column=0, row=1, padx=2, pady=2)
        # Placeholder text
        self.placeholder_text = "https://example.com"
        self.url_entry.insert(0, self.placeholder_text)
        self.url_entry.bind("<FocusIn>", self.on_entry_click)
        self.url_entry.bind("<FocusOut>", self.on_focusout)
        self.fetch_btn = Button(self, text="Fetch", font=(FONT_NAME, 10, 'normal'), bg=GREEN,
                                command=self.fetch_text)
        self.fetch_btn.grid(column=1, row=1, padx=2, pady=2, sticky='w')

        self.summarize_btn = Button(self, text="Summarize", font=(FONT_NAME, 10, 'normal'), bg=GREEN,
                                command=self.summarize)
        self.summarize_btn.grid(column=2, row=1, sticky='w')

        self.url_label = Label(self, text="", bg=YELLOW)
        self.url_label.grid(column=0, row=2)

        self.url_label = Label(self, text="Original", bg=YELLOW)
        self.url_label.grid(column=0, row=4)

        self.url_label = Label(self, text="Summary", bg=YELLOW)
        self.url_label.grid(column=1, row=4)


        self.txt_area_original = scrolledtext.ScrolledText(self, width=60, height=20)
        self.txt_area_original.grid(column=0, row=5, padx=8)

        self.txt_area_summary = scrolledtext.ScrolledText(self, width=60, height=20)
        self.txt_area_summary.grid(column=1, row=5, padx=8)

        self.url_label = Label(self, text="", bg=YELLOW)
        self.url_label.grid(column=0, row=6)


        self.save_button = Button(self, text="Save to File", font=(FONT_NAME, 10, 'normal'), bg=GREEN,
                                  command=self.save_to_file)
        self.save_button.grid(column=0, row=7)

        self.read_button = Button(self, text="Read from File", font=(FONT_NAME, 10, 'normal'), bg=GREEN,
                                  command=self.read_from_file)
        self.read_button.grid(column=1, row=7)

        self.url_label = Label(self, text="", bg=YELLOW)
        self.url_label.grid(column=0, row=8)

    def on_entry_click(self, event):
        """Function to handle the focus in event."""
        if self.url_entry.get() == self.placeholder_text:
            self.url_entry.delete(0, END)
            self.url_entry.config(fg='black')

    def on_focusout(self, event):
        """Function to handle the focus out event."""
        if self.url_entry.get() == '':
            self.url_entry.insert(0, self.placeholder_text)
            self.url_entry.config(fg='grey')

    def fetch_text(self):
        """Fetch text from URL and summarize it using OpenAI API."""
        url = self.url_entry.get()
        fetcher = TextFetcher(url)
        try:
            fetcher.fetch_text()
            self.fetched_text = fetcher.text[:6000]
            
            self.txt_area_original.delete(1.0, END) 
            self.txt_area_original.insert(END, self.fetched_text)
        except Exception as e:
            messagebox.showerror("Error", str(e))

    def summarize(self):
        """Get fetched text from scrolled text and then feed it to open ai function to for summarization"""
        text = self.txt_area_original.get("1.0", END).strip()
        if text:
            self.summarize_btn.config(state='disabled')
            self.txt_area_summary.delete(1.0, END)
            self.txt_area_summary.insert(END, "Processing...")
            self.update()

            summary = Writer(text).ai_text()

            if summary:
                self.txt_area_summary.delete(1.0, END)
                self.txt_area_summary.insert(END, summary)
            else:
                messagebox.showerror("Error", "Failed to summarize text. Please check the API key and try again.")

            self.summarize_btn.config(state='normal')  # Re-enable the button
        else:
            messagebox.showwarning("Warning", "No text available")

    def save_to_file(self):
        """Save generated text to a file."""
        generated_text = self.txt_area_summary.get(1.0, END).strip()
        original_text = self.fetched_text
        if generated_text:
            FileHandler.save_to_file('original_text.txt', original_text)
            FileHandler.save_to_file('generated_text.txt', generated_text)
            messagebox.showinfo("Success", "Both Texts saved to Files\nOriginal text and Generated text.")
        else:
            messagebox.showwarning("Warning", "No text to save.")

    def read_from_file(self):
        """Read text from a file and display it."""
        content = FileHandler.read_from_file('generated_text.txt')
        if content:
            self.txt_area_summary.delete(1.0, END)  # Clear previous text
            self.txt_area_summary.insert(END, content)  # Insert read text
        else:
            messagebox.showwarning("Warning", "No content found in the file.")

    def main_loop(self):
        """Start the main loop of the application."""
        self.mainloop()

