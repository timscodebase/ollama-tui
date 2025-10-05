# Ollama TUI

A Textual app to interact with local Ollama models.

## Features

- List and select from available Ollama models.
- Chat with Ollama models.
- Install new models from the Ollama library.
- Load single files or entire directories into the chat to provide context for analysis.

## Usage

To run the application, use the following command:

```bash
uv run ollama-cli
```

You can also specify the host for the Ollama server:

```bash
uv run ollama-cli --host 'http://127.0.0.1:11434'
```

## Key Bindings

### Models Screen

- `q`: Quit the application.
- `r`: Refresh the list of models.
- `Enter`: Select a model and open the chat screen.

### Chat Screen

- `q`: Quit the application.
- `Ctrl+L`: Go back to the models screen.
- `Ctrl+O`: Toggle the file browser to load a file or directory for analysis.

### App-Level

- `Ctrl+O`: Toggle the file browser from anywhere in the app.

### Error Screen

- `q`: Quit the application.
- `b`: Go back to the previous screen.
