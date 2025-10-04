"""A Textual app to interact with local Ollama models."""

import os
import argparse
import ollama
from textual.app import App, ComposeResult
from textual.containers import Container
from textual.widgets import Header, Footer, DataTable, Static, RichLog, Input, Label
from textual.screen import Screen


class ModelsScreen(Screen):
    """A screen to display the list of Ollama models."""

    TITLE = "Ollama Models"

    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh_models", "Refresh")]

    def compose(self) -> ComposeResult:
        """Create child widgets for the screen."""
        yield Header()
        yield Static(f"Connected to: {self.app.ollama_host}", id="host_display")
        yield Label("Use arrow keys to navigate and Enter to select a model")
        yield Container(id="models_container")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is first mounted."""
        self.query_models()

    def on_data_table_row_selected(self, event) -> None:
        """Called when a row is selected in the DataTable."""
        model_name = event.row_key.value
        if model_name:
            self.app.push_screen(ChatScreen(model_name))

    def query_models(self) -> None:
        """Query the Ollama API for the list of models."""
        container = self.query_one("#models_container")
        container.query("*").remove()

        try:
            client = ollama.Client(host=self.app.ollama_host)
            models = client.list().get("models", [])

            if not models:
                container.mount(Static("No models found. Pull a model with 'ollama run <model_name>'"))
            else:
                # We remove the static ID to prevent crashes on refresh.
                table = DataTable()
                table.add_columns("Name", "Size (GB)", "Family", "Format")
                for model in models:
                    name = model.get("model")
                    if not name:
                        continue
                    size = model.get("size", 0)
                    details = model.get("details", {})
                    family = details.get("family", "unknown")
                    format_type = details.get("format", "unknown")
                    table.add_row(
                        name, f'{size / 1e9:.2f}', family, format_type, key=name
                    )
                container.mount(table)

        except ollama.ResponseError:
            error_message = f"Could not connect to Ollama server at {self.app.ollama_host}. Is it running?"
            self.app.push_screen(ErrorScreen(error_message))
        except Exception as e:
            self.app.push_screen(ErrorScreen(str(e)))

    def action_refresh_models(self) -> None:
        """Refresh the list of models."""
        self.query_models()

    def action_quit(self) -> None:
        """An action to quit the app."""
        self.app.exit()


class ChatScreen(Screen):
    """A screen for chatting with an Ollama model."""

    BINDINGS = [("q", "quit", "Quit"), ("b", "back", "Back")]

    def __init__(self, model_name: str) -> None:
        super().__init__()
        self.model_name = model_name
        self.title = f"Chat with {self.model_name}"

    def compose(self) -> ComposeResult:
        yield Header()
        yield RichLog(id="chat_log")
        yield Input(placeholder="Enter your message...")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        chat_log = self.query_one("#chat_log", RichLog)
        user_message = event.value
        chat_log.write(f"You: {user_message}")
        self.query_one(Input).clear()

        try:
            client = ollama.AsyncClient(host=self.app.ollama_host)
            response = await client.chat(
                model=self.model_name,
                messages=[{"role": "user", "content": user_message}],
            )
            chat_log.write(f"Model: {response['message']['content']}")
        except Exception as e:
            self.app.push_screen(ErrorScreen(str(e)))

    def action_back(self) -> None:
        """An action to go back to the previous screen."""
        self.app.pop_screen()

    def action_quit(self) -> None:
        """An action to quit the app."""
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
        """An action to go back to the previous screen."""
        self.app.pop_screen()

    def action_quit(self) -> None:
        """An action to quit the app."""
        self.app.exit()


class OllamaCLI(App):
    """A Textual app to interact with local Ollama models."""

    TITLE = "Ollama TUI"
    CSS_PATH = "style.css"

    def __init__(self, host: str):
        super().__init__()
        self.ollama_host = host

    def on_mount(self) -> None:
        self.push_screen(ModelsScreen())


def main():
    """Run the app."""
    parser = argparse.ArgumentParser(description="A TUI for interacting with local Ollama models.")
    parser.add_argument(
        "--host",
        default=os.environ.get("OLLAMA_HOST", "http://localhost:11434"),
        help="The host address for the Ollama server."
    )
    args = parser.parse_args()

    app = OllamaCLI(host=args.host)
    app.run()


if __name__ == "__main__":
    main()

