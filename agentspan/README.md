# Agentspan Demo Code

Fiddling with some sample use cases for Agentspan in Conductor, largely inspired from examples here: [https://github.com/agentspan-ai/agentspan/tree/main/sdk/python]

## Be sure to set the following in your shell's .shrc file first

```bash
# Pyenv support
export PYENV_ROOT="$HOME/.pyenv"
[[ -d $PYENV_ROOT/bin ]] && export PATH="$PYENV_ROOT/bin:$PATH"
eval "$(pyenv init - zsh)"

# AI dependencies: Google Gemini
export GEMINI_API_KEY="{YOUR_API_KEY_HERE}"
export GOOGLE_CLOUD_PROJECT="{YOUR_GCP_PROJECT_NAME_HERE}"
```
