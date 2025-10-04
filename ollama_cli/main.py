"""A Textual app to interact with local Ollama models."""

import os
import argparse
import ollama
from textual.app import App, ComposeResult
from textual.containers import Container, ScrollableContainer
from textual.widgets import Header, Footer, DataTable, Static, Markdown, Input, Label
from textual.screen import Screen


class ModelsScreen(Screen):
    """A screen to display the list of Ollama models."""

    TITLE = "Ollama Models"
    BINDINGS = [("q", "quit", "Quit"), ("r", "refresh_models", "Refresh")]

    def compose(self) -> ComposeResult:
        """Create child widgets for the screen."""
        yield Header()
        yield Label("Use arrow keys to navigate and Enter to select a model")
        # The DataTable is now a permanent part of the layout.
        yield DataTable(id="models_table")
        yield Footer()

    def on_mount(self) -> None:
        """Called when the screen is first mounted."""
        # Add columns to the table and then populate it.
        table = self.query_one(DataTable)
        table.add_columns("Name", "Size (GB)", "Family", "Format")
        self.query_models()

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        """Called when a row is selected in the DataTable."""
        model_name = event.row_key.value
        if model_name:
            self.app.push_screen(ChatScreen(model_name))

    def query_models(self) -> None:
        """Query the Ollama API for the list of models."""
        table = self.query_one(DataTable)
        table.clear()
        try:
            client = ollama.Client(host=self.app.ollama_host)
            models = client.list().get("models", [])
            if not models:
                # If there are no models, we can't add rows, so we show a message instead.
                # This part is simplified, as the table is already there.
                self.app.push_screen(ErrorScreen("No models found. Pull a model with 'ollama run <model_name>'"))
            else:
                for model in models:
                    name = model.get("model")
                    if not name:
                        continue
                    size = model.get("size", 0)
                    details = model.get("details", {})
                    family = details.get("family", "unknown")
                    format_type = details.get("format", "unknown")
                    table.add_row(name, f'{size / 1e9:.2f}', family, format_type, key=name)
                # Set cursor and focus after populating
                table.cursor_type = "row"
                table.focus()
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

    BINDINGS = [
        ("q", "quit", "Quit"),
        ("l", "list_models", "List Models"),
    ]

    def __init__(self, model_name: str) -> None:
        super().__init__()
        self.model_name = model_name
        self.title = f"Chat with {self.model_name}"
        self.messages = []

    def compose(self) -> ComposeResult:
        yield Header()
        yield ScrollableContainer(Markdown(id="chat_log"))
        yield Input(placeholder="Enter your message...")
        yield Footer()

    def on_mount(self) -> None:
        self.query_one(Input).focus()

    def _render_messages(self) -> None:
        """Renders the chat history to the Markdown widget."""
        markdown_widget = self.query_one("#chat_log", Markdown)
        markdown_content = ""
        for message in self.messages:
            role = "You" if message["role"] == "user" else "Model"
            content = message['content']
            markdown_content += f"**{role}**\n\n{content}\n\n---\n"
        markdown_widget.update(markdown_content)
        self.query_one(ScrollableContainer).scroll_end(animate=False)

    async def on_input_submitted(self, event: Input.Submitted) -> None:
        user_message = event.value
        if not user_message:
            return

        self.messages.append({"role": "user", "content": user_message})
        self.query_one(Input).clear()
        self.messages.append({"role": "assistant", "content": ""})
        self._render_messages()

        try:
            client = ollama.AsyncClient(host=self.app.ollama_host)
            full_response = ""
            async for part in await client.chat(
                model=self.model_name,
                messages=self.messages[:-1],
                stream=True,
            ):
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

    def action_list_models(self) -> None:
        """Switch to the model selection screen."""
        self.app.switch_screen(ModelsScreen())


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
        """Check for models and route to the appropriate screen."""
        try:
            client = ollama.Client(host=self.ollama_host)
            models = client.list().get("models", [])

            if len(models) == 1:
                model_name = models[0].get("model")
                if model_name:
                    self.push_screen(ChatScreen(model_name))
                else:
                    self.push_screen(ModelsScreen())
            else:
                self.push_screen(ModelsScreen())
        except ollama.ResponseError:
            error_message = f"Could not connect to Ollama server at {self.ollama_host}. Is it running?"
            self.app.push_screen(ErrorScreen(error_message))
        except Exception as e:
            self.app.push_screen(ErrorScreen(str(e)))


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

