# 🌸 GroupControler-FB

<p align="center">
  <strong>An intelligent Facebook Messenger automation bot powered by Python, AI, and asynchronous processing.</strong>
</p>

<p align="center">
  <a href="https://github.com/arafatlab/GroupControler-FB">
    <img src="https://img.shields.io/badge/Project-GroupControler--FB-1877F2?style=for-the-badge&logo=facebook&logoColor=white" alt="Project">
  </a>
  <img src="https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white" alt="Python">
  <img src="https://img.shields.io/badge/Async-Supported-00A67E?style=for-the-badge" alt="Async">
  <img src="https://img.shields.io/badge/AI-Groq-orange?style=for-the-badge" alt="Groq AI">
  <img src="https://img.shields.io/badge/Platform-Facebook_Messenger-0866FF?style=for-the-badge&logo=messenger&logoColor=white" alt="Messenger">
</p>

---

## ✨ Overview

**GroupControler-FB** is a Python-based Facebook Messenger automation bot designed to make group management and personal conversations smarter and easier.

It combines AI-powered conversations, group administration tools, conversation memory, native message replies, and Free Fire player lookup in one automation system.

Built with asynchronous processing and a modular architecture, the project is designed to be extensible and customizable.

## 🚀 Features

| Feature | Description |
|---|---|
| 🌸 **Anu AI** | AI-powered Messenger conversations using Groq. |
| 💬 **Group Chat Assistant** | Responds to the configured `/anu` command in groups. |
| 📩 **Private Chat** | Handles personal conversations without requiring a command prefix, depending on configuration. |
| 🛡️ **Group Management** | Administrative commands for managing group members and permissions. |
| 👥 **Member Synchronization** | Retrieves and maintains group member information. |
| 🔨 **Member Removal** | Provides the `/kick` command for authorized group administrators. |
| ⚠️ **Warning System** | Warn members and inspect warning records. |
| 👑 **Admin Controls** | Promote or demote group members. |
| 🎮 **Free Fire Checker** | Retrieves Free Fire player information through GamesKinbo. |
| ↩️ **Native Message Reply** | Replies directly to the original Messenger message. |
| 🧠 **Conversation Memory** | Maintains conversation context for more natural AI responses. |
| ⚡ **Async HTTP Requests** | Uses asynchronous HTTP communication for external services. |
| 🔐 **Credential Protection** | Keeps private configuration and Facebook session files out of the repository. |

## 🧰 Requirements

- Python 3.10 or newer
- Git
- Internet connection
- Facebook account with a valid Messenger session
- Groq API key for AI responses

> **Recommended:** Python 3.10–3.13. Python 3.14 compatibility depends on the installed dependencies.

## 📥 Installation

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

**Windows (PowerShell)**

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

## ⚙️ Configuration

Private configuration files and Facebook session cookies are intentionally excluded from this repository.

### 1. Create your configuration file

```bash
cp config.example.py config.py
```

Open it:

```bash
nano config.py
```

Configure the required settings using the exact variable names provided in `config.example.py`.

Typical settings include:

- Groq API key
- AI model
- Group command prefix
- Dry-run mode
- Other bot configuration options

**Important:** Do not rename configuration variables unless you also update the corresponding Python code.

### 2. Configure Facebook session cookies

Place your own valid `cookies.json` file in the project root.

Expected layout:

```text
GroupControler-FB/
├── config.py
├── config.example.py
├── cookies.json
├── main.py
└── ...
```

The cookie file must follow the format expected by the project's Facebook session loader.

<blockquote>
  🔐 **Security Notice**

  Never upload `cookies.json`, `config.py`, Facebook session data, or API keys to GitHub. These files can provide access to your accounts.
</blockquote>

## ▶️ Running the Bot

Activate the virtual environment if it is not already active.

```bash
source .venv/bin/activate
```

Start the bot:

```bash
python main.py
```

On Windows, use:

```powershell
.venv\Scripts\activate
python main.py
```

The bot should initialize its configuration, Facebook session, Messenger connection, and message listener.

Check the terminal output for login, connection, or API errors.

## 🎯 Commands

### 🌸 Anu AI

In a group conversation:

```text
/anu Hello Anu!
```

The bot responds using the configured group command.

In private conversations, the bot can respond without a command prefix, depending on the message handler configuration.

### 🎮 Free Fire Player Checker

```text
/ff 11121171716
```

Requests player information from GamesKinbo and replies to the original Messenger message.

> The `/ff` command is intended for group conversations.

### 🛡️ Group Management

The following commands are available to authorized group administrators:

| Command | Description |
|---|---|
| `/groupinfo` | View group information |
| `/admins` | List group administrators |
| `/members` | List group members |
| `/info @name or ID` | View member information |
| `/addrules text` | Set or update group rules |
| `/removerules` | Remove group rules |
| `/up @name or ID` | Promote a member to admin |
| `/down @name or ID` | Demote an admin |
| `/warn @name or ID reason` | Warn a member |
| `/warnings` | View group warnings |
| `/warns @name or ID` | View a member's warnings |
| `/kick @name or ID` | Remove a member from the group |

### 👥 General Commands

| Command | Description |
|---|---|
| `/help` | Display the command guide |
| `/rules` | Show group rules |
| `/report @name or ID reason` | Report a member |
| `/remind 10m message` | Set a reminder |
| `/reminders` | View pending reminders |
| `/cancelremind ID` | Cancel your reminder |

**Member identification:** Use an exact displayed name or Facebook ID. Name matching must be unique. If multiple members have the same name, use the Facebook ID.

**Administrative restrictions:** Group management commands require the appropriate permissions. The bot must also have the required group permissions. Actual Facebook API behavior may vary.

## 📂 Project Structure

```text
GroupControler-FB/
│
├── main.py
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
│   ├── ff_checker.py
│   ├── groups.py
│   ├── group_api.py
│   ├── group_store.py
│   └── members.py
│
├── utils/
│
├── data/
│
└── logs/
```

*Note: The structure above represents the main project components; additional files may exist in the repository.*

## 🔧 Troubleshooting

### `ModuleNotFoundError`

Make sure your virtual environment is activated and all dependencies are installed.

```bash
python -m pip install -r requirements.txt
```

### Facebook Login or Session Error

- Check whether `cookies.json` exists.
- Verify that the Facebook session is still valid.
- Check your internet connection.
- Never share your session cookies.

### Groq API Error

- Verify the API key in `config.py`.
- Check whether the selected model is available.
- Review your API usage limits.

### GamesKinbo HTTP 403 Error

GamesKinbo may block requests from certain hosting environments through Cloudflare.

Possible solutions:

- Try running the bot from your Mac or another local device.
- Check whether GamesKinbo is accessible from your network.
- Remember that success on one network does not guarantee success on another.

### Messenger Connection Problems

- Check your Facebook session.
- Verify your internet connection.
- Review the terminal logs.
- Make sure your installed `fbchat-v2` version matches `requirements.txt`.

## 🔐 Security

The following files and directories must remain private:

```text
config.py
cookies.json
cookies.json.bak
.venv/
__pycache__/
logs/
```

Keep API keys and Facebook session information secure.

If a session cookie or API key is accidentally exposed, revoke or replace it immediately.

## 🧪 Development

Check Python syntax:

```bash
python -m compileall .
```

Check repository changes:

```bash
git status
```

Review the latest commit:

```bash
git log -1 --oneline
```

## ⚠️ Disclaimer

This project is developed for educational and personal automation purposes.

- Use the software responsibly.
- Follow Facebook's applicable terms and policies.
- Automated access may be restricted.
- Facebook sessions can expire or become invalid.
- The project does not guarantee uninterrupted access to third-party services.

The author is not responsible for misuse, account restrictions, or service interruptions resulting from automated access.

## 👨‍💻 Author

<p align="center">
  <strong>Arafat Hoshen Zihad</strong>
  <br>
  <a href="https://github.com/arafatlab">@arafatlab</a>
</p>

<p align="center">
  <a href="https://github.com/arafatlab/GroupControler-FB">
    <strong>⭐ Explore GroupControler-FB on GitHub</strong>
  </a>
</p>

---

<p align="center">
  <strong>🌸 HINATA — Your Friendly Group Assistant</strong>
  <br>
  <sub>Built with Python • Powered by AI • Designed for Messenger</sub>
</p>
