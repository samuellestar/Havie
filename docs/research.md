# Research sources

Reviewed official upstream documentation on 2026-10-07. Direct documentation
sites were blocked by the cloud network policy; these official GitHub sources
were successfully retrieved instead.

- [Python Tkinter documentation](https://github.com/python/cpython/blob/3.12/Doc/library/tkinter.rst): standard-library desktop UI, threading and Tk dependencies.
- [Python SQLite documentation](https://github.com/python/cpython/blob/3.12/Doc/library/sqlite3.rst): local persistence and parameterized queries.
- [Ollama API documentation](https://github.com/ollama/ollama/blob/main/docs/api.md): local `/api/chat`, message arrays and non-streaming requests.
- [Microsoft SpeechSynthesizer documentation](https://github.com/dotnet/dotnet-api-docs/blob/main/xml/System.Speech.Synthesis/SpeechSynthesizer.xml): Windows System.Speech synthesis.

These sources guided the implementation. They do not establish that Windows
speech, app launching, screenshots or Tk rendering work in this Linux cloud
machine. Ollama API tests use a mocked response; real local model inference
requires an installed and running model on the user's PC.
