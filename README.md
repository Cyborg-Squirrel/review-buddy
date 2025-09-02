# Review Buddy

## Description

Review Buddy provides an AI-powered code reviews using Ollama.

## Requirements

*   Python 3.9 or newer
  

## Installation

1.  Install dependencies:
    ```bash
    pip install requests dataclasses-json
    ```
    
2. Create a GitHub access token. The easist setup is to check the repo box for classic tokens, though the API usage only likely requires the public_repo permission.
   
3. Install Ollama and make sure the "expose Ollama to network" setting is enabled. It is disabled by default.

4.  Configure the project:
    *   Create a configuration file config.json. See config_template.json for a starting point.
    *   Add your token, username, repositories, and models to the configuration.

## Usage

```bash
    python ai_review.py
```

## Contributing

* Create a pull request
* Explain your changes
* The GitHub workflow must pass
