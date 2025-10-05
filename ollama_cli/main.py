"""A Textual app to interact with local Ollama models."""

import os
import argparse
import ollama
from textual.app import App, ComposeResult
from textual.containers import Container, Horizontal, ScrollableContainer
from textual.widgets import (
    Header,
    Footer,
    DataTable,
    Static,
    Markdown,
    Input,
    Label,
    DirectoryTree,
)
from textual.screen import Screen


class ModelsScreen(Screen):
    """A screen to display and select from a list of available Ollama models."""

    TITLE = "Ollama Models"
    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh_models", "Refresh")]

    def compose(self) -> ComposeResult:
        """Create child widgets for the screen."""
        yield Header()
        yield Label("Use arrow keys to navigate and Enter to select a model")
        yield DataTable(id="models_table")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is first mounted."""
        table = self.query_one(DataTable)
        table.add_columns("Name", "Size (GB)", "Family", "Format")
        self.query_models()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Handles the selection of a model from the DataTable."""
        model_name = event.row_key.value
        if model_name:
            self.app.push_screen(ChatScreen(model_name))

    def query_models(self) -> None:
        """Queries the Ollama API for the list of models and populates the table."""
        table = self.query_one(DataTable)
        table.clear()
        try:
            client = ollama.Client(host=self.app.ollama_host)
            models = client.list().get("models", [])
            if not models:
                self.app.push_screen(
                    ErrorScreen("No models found. Pull a model with 'ollama run <model_name>'")
                )
            else:
                for model in models:
                    name = model.get("model")
                    if not name:
                        continue
                    size = model.get("size", 0)
                    details = model.get("details", {})
                    family = details.get("family", "unknown")
                    format_type = details.get("format", "unknown")
                    table.add_row(
                        name, f"{size / 1e9:.2f}", family, format_type, key=name
                    )
                table.cursor_type = "row"
                table.focus()
        except Exception as e:
            self.app.push_screen(ErrorScreen(str(e)))

    def action_refresh_models(self) -> None:
        """Action to refresh the list of models."""
        self.query_models()

    def action_quit(self) -> None:
        """An action to quit the application."""
        self.app.exit()


class ChatScreen(Screen):
    """A screen for chatting with a selected Ollama model."""

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("ctrl+l", "list_models", "List Models"),
    ]

    def __init__(self, model_name: str) -> None:
        """Initializes the ChatScreen."""
        super().__init__()
        self.model_name = model_name
        self.title = f"Chat with {self.model_name}"
        self.messages = []
        self.file_context = None

    def compose(self) -> ComposeResult:
        """Create child widgets for the screen."""
        yield Header()
        with Horizontal():
            yield DirectoryTree(".", id="file_browser")
            with Container(id="chat_wrapper"):
                yield ScrollableContainer(Markdown(), id="chat_log_container")
                with Horizontal():
                    yield Label("", id="file_status")
                    yield Static("🤔 Model is thinking...", id="loading_status")
                yield Input(placeholder="Press Ctrl+O to open file browser...")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is first mounted."""
        self.query_one("#file_browser").display = False
        self.query_one("#loading_status").display = False
        self.query_one(Input).focus()

    def _render_messages(self) -> None:
        """Renders the chat history to the Markdown widget."""
        markdown_widget = self.query_one(Markdown)
        markdown_content = ""
        for message in self.messages:
            role = "You" if message["role"] == "user" else "Model"
            content = message["content"]
            markdown_content += f"**{role}**\n\n{content}\n\n---\n"
        markdown_widget.update(markdown_content)
        self.query_one("#chat_log_container").scroll_end(animate=False)

    async def on_directory_tree_file_selected(
        self, event: DirectoryTree.FileSelected
    ) -> None:
        """Called when a file is selected in the directory tree."""
        event.stop()
        file_path = str(event.path)
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                file_content = f.read()
            prompt_content = f"--- FILE: {file_path} ---\n{file_content}"
            self.file_context = (f"file '{os.path.basename(file_path)}'", prompt_content)
            self.query_one("#file_status").update(f"Context: {os.path.basename(file_path)}")
            self.query_one("#file_browser").display = False
            self.query_one(Input).focus()
        except Exception as e:
            self.query_one("#file_status").update(f"Error: {e}")

    async def on_directory_tree_directory_selected(
        self, event: DirectoryTree.DirectorySelected
    ) -> None:
        """Called when a directory is selected in the directory tree."""
        event.stop()
        dir_path = str(event.path)
        ignored_dirs = {".git", ".venv", "__pycache__"}
        ignored_extensions = {".pyc", ".lock"}
        full_context, file_count = "", 0
        try:
            for root, dirs, files in os.walk(dir_path):
                dirs[:] = [d for d in dirs if d not in ignored_dirs]
                for file in files:
                    if os.path.splitext(file)[1] in ignored_extensions:
                        continue
                    file_path = os.path.join(root, file)
                    try:
                        with open(file_path, "r", encoding="utf-8") as f:
                            file_content = f.read()
                        full_context += f"--- FILE: {file_path} ---\n{file_content}\n\n"
                        file_count += 1
                    except (IOError, UnicodeDecodeError):
                        continue
            self.file_context = (f"{file_count} files from '{os.path.basename(dir_path)}'", full_context)
            self.query_one("#file_status").update(f"Context: {file_count} files loaded")
            self.query_one("#file_browser").display = False
            self.query_one(Input).focus()
        except Exception as e:
            self.query_one("#file_status").update(f"Error: {e}")

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handles the submission of a user message."""
        user_message = event.value
        if not user_message:
            return

        input_widget = self.query_one(Input)
        loading_status = self.query_one("#loading_status")
        
        input_widget.disabled = True
        loading_status.display = True

        self.messages.append({"role": "user", "content": user_message})
        input_widget.clear()
        self.messages.append({"role": "assistant", "content": ""})
        self._render_messages()

        prompt_for_model = user_message
        if self.file_context:
            context_name, file_content = self.file_context
            prompt_for_model = (
                f"The user has provided context from {context_name}.\n{file_content}\n\n"
                f"Based on this, respond to: {user_message}"
            )
            self.file_context = None
            self.query_one("#file_status").update("")

        api_messages = self.messages[:-2] + [{"role": "user", "content": prompt_for_model}]
        full_response = ""
        try:
            client = ollama.AsyncClient(host=self.app.ollama_host)
            async for part in await client.chat(model=self.model_name, messages=api_messages, stream=True):
                chunk = part["message"]["content"]
                if chunk:
                    full_response += chunk
                    self.messages[-1]["content"] = full_response + " ▋"
                    self._render_messages()
            self.messages[-1]["content"] = full_response
        except Exception as e:
            self.messages[-1]["content"] = f"An error occurred: {e}"
        finally:
            self._render_messages()
            loading_status.display = False
            input_widget.disabled = False
            input_widget.focus()

    def action_toggle_file_browser(self) -> None:
        """Toggles the visibility of the file browser."""
        file_browser = self.query_one("#file_browser")
        file_browser.display = not file_browser.display
        if file_browser.display:
            file_browser.focus()
        else:
            self.query_one(Input).focus()

    def action_list_models(self) -> None:
        """Switches to the model selection screen."""
        self.app.switch_screen(ModelsScreen())

    def action_quit(self) -> None:
        """An action to quit the application."""
        self.app.exit()


class ErrorScreen(Screen):
    """A screen to display an error message."""
    TITLE = "Error"
    BINDINGS = [("q", "quit", "Quit"), ("b", "back", "Back")]

    def __init__(self, error_message: str) -> None:
        super().__init__()
        self.error_message = error_message

    def compose(self) -> ComposeResult:
        yield Header()
        yield Container(Static(f"Error: {self.error_message}"), id="error_container")
        yield Footer()

    def action_back(self) -> None:
        self.app.pop_screen()

    def action_quit(self) -> None:
        self.app.exit()


class OllamaCLI(App):
    """The main application class for the Ollama TUI."""
    TITLE = "Ollama TUI"
    CSS_PATH = "style.css"
    BINDINGS = [("ctrl+o", "toggle_file_browser_app", "Open File Browser")]

    def __init__(self, host: str):
        super().__init__()
        self.ollama_host = host

    def on_mount(self) -> None:
        """Checks for available models and routes to the appropriate screen."""
        try:
            client = ollama.Client(host=self.ollama_host)
            models = client.list().get("models", [])
            if len(models) == 1:
                model_name = models[0].get("model")
                self.push_screen(ChatScreen(model_name) if model_name else ModelsScreen())
            else:
                self.push_screen(ModelsScreen())
        except ollama.ResponseError:
            self.push_screen(ErrorScreen(f"Could not connect to Ollama at {self.ollama_host}"))
        except Exception as e:
            self.push_screen(ErrorScreen(str(e)))

    def action_toggle_file_browser_app(self) -> None:
        """App-level action to toggle the file browser."""
        if isinstance(self.screen, ChatScreen):
            self.screen.action_toggle_file_browser()


def main():
    """Parses command-line arguments and runs the application."""
    parser = argparse.ArgumentParser(description="A TUI for interacting with local Ollama models.")
    parser.add_argument(
        "--host",
        default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        help="The host address for the Ollama server.",
    )
    args = parser.parse_args()
    app = OllamaCLI(host=args.host)
    app.run()


if __name__ == "__main__":
    main()

