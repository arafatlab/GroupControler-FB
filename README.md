# GroupControler-FB

A Python-based Facebook Messenger automation bot with AI-powered replies, group commands, conversation memory, and Free Fire player lookup.

## Features

- **Anu AI:** AI-powered Messenger replies.
- **Group Command:** Responds to `/anu` in group conversations.
- **Private Chat:** Responds to messages in personal conversations.
- **Free Fire Checker:** Retrieves Free Fire player information using GamesKinbo.
- **Native Message Reply:** Replies directly to the original Messenger message.
- **Conversation Memory:** Maintains conversation context.
- **Async HTTP Requests:** Uses asynchronous HTTP requests for external API communication.

## Requirements

- Python 3.10 or newer
- Git
- Internet connection
- Facebook account with a valid Messenger session
- Groq API key for AI responses

> Python 3.10–3.13 is recommended. Python 3.14 compatibility depends on the installed dependencies.

## Installation

### 1. Clone the repository

```bash
git clone https://github.com/arafatlab/GroupControler-FB.git
cd GroupControler-FB
```

### 2. Create a virtual environment

**macOS / Linux / Termux**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

**Windows**

```powershell
py -m venv .venv
.venv\Scripts\activate
```

### 3. Upgrade pip

```bash
python -m pip install --upgrade pip
```

### 4. Install dependencies

```bash
python -m pip install -r requirements.txt
```

## Configuration

The repository does not include your private configuration or Facebook cookies. This is intentional to protect account credentials.

### 1. Create config.py

```bash
cp config.example.py config.py
```

Open the configuration file:

```bash
nano config.py
```

Update the settings according to your setup.

Typical settings include:

- Groq API key
- AI model
- Group command
- Dry-run mode
- Other bot configuration options

Use the actual variable names and structure provided in `config.example.py`. Do not rename configuration variables unless you also update the corresponding Python code.

### 2. Configure Facebook cookies

Create or copy your own `cookies.json` into the project root.

The expected location is:

```text
GroupControler-FB/
├── config.py
├── cookies.json
├── main.py
└── ...
```

Use a valid session in the format expected by the project's Facebook session loader.

**Important:** Never publish your Facebook cookies, API keys, or private configuration files on GitHub.

## Running the Bot

Activate the virtual environment if it is not already active.

```bash
source .venv/bin/activate
```

Start the bot:

```bash
python main.py
```

The bot should initialize its configuration, Facebook session, Messenger connection, and message listener.

Follow the terminal output to identify any login or connection errors.

## Commands

### Anu AI

In a group conversation:

```text
/anu Hello Anu!
```

The bot responds to the configured group command.

In a personal conversation, the bot can respond without the group command, depending on the message handler configuration.

### Free Fire Player Checker

In a group conversation:

```text
/ff 11121171716
```

The bot requests the player's information from GamesKinbo and replies to the original message.

The `/ff` command is intended for group conversations.

## Project Structure

```text
GroupControler-FB/
│
├── main.py
├── config.py
├── config.example.py
├── requirements.txt
├── README.md
│
├── core/
│   ├── connection.py
│   ├── messenger.py
│   └── session.py
│
├── modules/
│   ├── ai_engine.py
│   ├── memory.py
│   ├── messages.py
│   ├── role.py
│   └── ff_checker.py
│
├── utils/
│
├── data/
│
└── logs/
```

## Troubleshooting

### ModuleNotFoundError

Make sure your virtual environment is activated and dependencies are installed:

```bash
python -m pip install -r requirements.txt
```

### Facebook Login or Session Error

- Check whether `cookies.json` exists.
- Verify that the session is still valid.
- Check your internet connection.
- Do not share your cookies with anyone.

### Groq API Error

- Verify your API key in `config.py`.
- Check whether the selected model is available.
- Check your API usage limits.

### GamesKinbo HTTP 403 Error

GamesKinbo may block requests from certain hosting environments through Cloudflare.

If you receive an HTTP 403 response:

- Try running the bot from your Mac or another local device.
- Check whether GamesKinbo is accessible from that network.
- Remember that successful requests from one network do not guarantee success from another.

### Messenger Connection Problems

- Check your Facebook session.
- Verify your internet connection.
- Review the terminal logs.
- Make sure your installed `fbchat-v2` version matches `requirements.txt`.

## Security

Never commit these files to GitHub:

```text
config.py
cookies.json
cookies.json.bak
.venv/
__pycache__/
logs/
```

Keep your API keys and Facebook session private.

If a Facebook session cookie or API key is accidentally exposed, revoke or replace it.

## Development

To check Python syntax:

```bash
python -m compileall .
```

To check Git changes:

```bash
git status
```

## Disclaimer

This project is provided for educational and personal automation purposes.

Use it responsibly and comply with Facebook's applicable terms and policies. Automated access may be restricted, and account sessions can expire.

## Author

**Arafat Hoshen Zihad**

GitHub: [@arafatlab](https://github.com/arafatlab)

Repository: [GroupControler-FB](https://github.com/arafatlab/GroupControler-FB)
