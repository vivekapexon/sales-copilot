# SALES-COPILOT

An AWS-themed Streamlit web interface for the Strategy Agent system that orchestrates 6 specialized agents to provide comprehensive sales intelligence.

## Features

- 🎨 **AWS-Themed Interface** - Professional orange and dark gray color scheme
- 💬 **ChatGPT-Style Conversation** - Familiar chat interface with message history
- 📝 **Persistent Chat History** - All conversations are saved and can be revisited
- 🤖 **Multi-Agent Intelligence** - Integrates Profile, History, Prescribing, Access, Competitive, and Content agents
- 🔄 **Follow-Up Questions** - Maintains conversation context for natural interactions
- 📊 **Formatted Responses** - Clean display of JSON data with expandable sections

## Architecture

The application consists of:

- **Strategy Agent** - Orchestrates 6 specialized agents based on user intent
- **Profile Agent** - HCP demographics and practice details
- **History Agent** - Past interactions and call notes
- **Prescribing Agent** - TRx/NRx trends and adoption metrics
- **Access Agent** - Formulary status and coverage information
- **Competitive Agent** - Competitor activity and threats
- **Content Agent** - Approved materials and messaging

## Installation

### Prerequisites

- Python 3.8 or higher
- pip package manager

### Setup Steps

1. **Clone or navigate to the project directory**

```bash
cd /path/to/project
```

2. **Install dependencies**

**Option A: Automated (Windows)**
```bash
install_dependencies.bat
```

**Option B: Manual**
```bash
# Upgrade pip first
python -m pip install --upgrade pip setuptools wheel

# Install dependencies
pip install -r requirements.txt
```

**If you encounter DLL errors with strands on Windows:**
- Install Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe
- See `TROUBLESHOOTING.md` for detailed solutions
- The app will automatically use a mock agent for testing if strands fails to load

3. **Verify Strategy Agent is available**

Make sure the `Strategy-Agent` directory exists with all required agent modules:
- `strategy_agent.py`
- `Agents/profile_agent.py`
- `Agents/history_agent.py`
- `Agents/prescribe_agent.py`
- `Agents/access_agent.py`
- `Agents/competitive_agent.py`
- `Agents/content_agent.py`

**Note:** If the real agent can't load, a mock agent will be used automatically for UI testing.

## Running the Application

### Start the Streamlit App

```bash
streamlit run streamlit_app.py
```

The application will open in your default web browser at `http://localhost:8501`

### Alternative Port

If port 8501 is already in use:

```bash
streamlit run streamlit_app.py --server.port 8502
```

## Usage

### Starting a New Chat

1. Click the **"➕ New Chat"** button in the sidebar
2. Type your question in the input box at the bottom
3. Press Enter or click Send

### Example Queries

**Pre-Call Brief (Full Intelligence)**
```
Prepare me for my call with Dr. Rao
```

**HCP Profile**
```
Give me the profile for HCP H123
```

**Prescribing Trends**
```
How has Dr. Patel's prescribing changed?
```

**Access Intelligence**
```
Which plans cover our product for Dr. Rao?
```

**Competitive Intel**
```
What are competitors doing around Dr. Sharma?
```

**Content Recommendations**
```
Which approved materials should I show Dr. Verma?
```

**History & Interactions**
```
When did I last meet Dr. X?
```

### Follow-Up Questions

After receiving a response, you can ask follow-up questions in the same conversation:

```
User: Give me the profile for HCP H123
Agent: [Profile information]
User: What are their prescribing trends?
Agent: [Prescribing information with context]
```

### Managing Chat History

- **View Previous Chats** - Click on any chat in the sidebar to load it
- **Delete Chats** - Click the 🗑️ button next to a chat to delete it
- **Chat Metadata** - Each chat shows timestamp and message count

## Project Structure

```
.
├── streamlit_app.py          # Main application entry point
├── requirements.txt           # Python dependencies
├── README.md                  # This file
├── chat_history/              # Stored chat sessions (JSON files)
├── utils/                     # Utility modules
│   ├── __init__.py
│   ├── storage_manager.py    # Chat persistence
│   ├── agent_integration.py  # Strategy agent interface
│   ├── response_formatter.py # Response formatting
│   ├── styles.py             # AWS theme CSS
│   └── error_handler.py      # Error handling
└── Strategy-Agent/            # Strategy agent and sub-agents
    ├── strategy_agent.py
    └── Agents/
        ├── profile_agent.py
        ├── history_agent.py
        ├── prescribe_agent.py
        ├── access_agent.py
        ├── competitive_agent.py
        └── content_agent.py
```

## Configuration

### Storage Location

Chat history is stored in the `chat_history/` directory as JSON files:
- `sessions.json` - Metadata for all sessions
- `session_<uuid>.json` - Individual conversation messages

To change the storage location, modify the `ChatStorageManager` initialization in `streamlit_app.py`:

```python
st.session_state.storage_manager = ChatStorageManager(storage_dir="custom_path")
```

### Theme Customization

To customize the AWS theme colors, edit `utils/styles.py`:

```python
AWS_COLORS = {
    "primary_orange": "#FF9900",  # Change to your brand color
    "dark_gray": "#232F3E",
    # ... other colors
}
```

## Troubleshooting

### DLL Load Failed Error (Windows)

**Error:** `DLL load failed while importing strands: The specified module could not be found.`

**Quick Fix:**
1. Install Visual C++ Redistributable: https://aka.ms/vs/17/release/vc_redist.x64.exe
2. Restart your computer
3. Run: `pip install strands --no-cache-dir`

**Alternative:** The app will automatically use a mock agent for testing the UI. See `TROUBLESHOOTING.md` for detailed solutions.

### Strategy Agent Not Found

**Error:** `Strategy agent not available. Please check installation.`

**Solution:** Ensure the `Strategy-Agent` directory is in the project root and contains all required files.

### Import Errors

**Error:** `ModuleNotFoundError: No module named 'strands'`

**Solution:** Install missing dependencies:
```bash
pip install strands
```

**For detailed troubleshooting, see `TROUBLESHOOTING.md`**

### Port Already in Use

**Error:** `Address already in use`

**Solution:** Use a different port:
```bash
streamlit run streamlit_app.py --server.port 8502
```

### Chat History Not Persisting

**Issue:** Chats disappear after closing the app

**Solution:** Check that the `chat_history/` directory exists and has write permissions.

## Development

### Adding New Agent Types

To add support for a new agent type:

1. Add the agent to `Strategy-Agent/Agents/`
2. Update `response_formatter.py` with a new formatting function
3. Update the agent list in `strategy_agent.py`

### Modifying Response Format

Edit `utils/response_formatter.py` to customize how agent responses are displayed.

### Changing UI Layout

Modify `streamlit_app.py` and `utils/styles.py` to adjust the layout and styling.

## Support

For issues or questions:
1. Check the troubleshooting section above
2. Review the Strategy Agent documentation
3. Check Streamlit documentation: https://docs.streamlit.io

## License

[Add your license information here]

## Version

Current Version: 1.0.0

## Changelog

### v1.0.0 (Initial Release)
- AWS-themed interface with SALES-COPILOT branding
- Integration with Strategy Agent and 6 sub-agents
- Persistent chat history with session management
- Follow-up question support with conversation context
- Formatted JSON responses with expandable sections
- Error handling and user feedback
