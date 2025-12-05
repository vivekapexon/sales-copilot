# Quick Start Guide - SALES-COPILOT

## 🚀 Getting Started in 3 Steps

### Step 1: Install Dependencies

**Windows (Recommended):**
```bash
install_dependencies.bat
```

**Manual:**
```bash
python -m pip install --upgrade pip setuptools wheel
pip install -r requirements.txt
```

### Step 2: Run the Application

**Windows:**
```bash
run_app.bat
```

**Manual:**
```bash
streamlit run streamlit_app.py
```

### Step 3: Open Your Browser

The app will automatically open at: `http://localhost:8501`

---

## ⚠️ If You See "DLL Load Failed" Error

**Don't worry!** The app will work with mock data for testing.

**To fix and use real agent:**

1. **Download and install Visual C++ Redistributable:**
   - 64-bit: https://aka.ms/vs/17/release/vc_redist.x64.exe
   - 32-bit: https://aka.ms/vs/17/release/vc_redist.x86.exe

2. **Restart your computer**

3. **Reinstall strands:**
   ```bash
   pip uninstall strands
   pip install strands --no-cache-dir
   ```

4. **Restart the app**

For more solutions, see `TROUBLESHOOTING.md`

---

## 💬 Using the App
Select between Post/Pre Call using the toggle given on left side.

### Example Queries

**Get HCP Profile:**
```
Give me the profile for HCP H123
```

**Check Prescribing Trends:**
```
How has Dr. Patel's prescribing changed?
```

**Full Pre-Call Brief:**
```
Prepare me for my call with Dr. Rao
```

**Access Intelligence:**
```
Which plans cover our product for Dr. Rao?
```

**Competitive Intel:**
```
What are competitors doing around Dr. Sharma?
```

**Sentiment Analsis:**
```
how did the doctor with hcp id HCP1001 feel after the recent interaction with sales person.
```

### Features

✅ **Chat History** - All conversations are saved  
✅ **Follow-Up Questions** - Ask related questions in the same chat  
✅ **Multiple Sessions** - Switch between different conversations  
✅ **Delete Chats** - Remove old conversations  

---

## 📁 Project Structure

```
.
├── streamlit_app.py              # Main app (start here)
├── run_app.bat                   # Quick start script
├── install_dependencies.bat      # Dependency installer
├── requirements.txt              # Python packages
├── README.md                     # Full documentation
├── TROUBLESHOOTING.md           # Detailed troubleshooting
├── QUICK_START.md               # This file
├── chat_history/                # Saved conversations
├── utils/                       # Helper modules
└── post_call/                   # Post Call Agent system
    ├── supervisor_agent.py        # Real agent
└── Strategy_Agent/              # Agent system
    ├── strategy_agent.py        # Real agent
    └── mock_strategy_agent.py   # Mock agent (fallback)
```

---

## 🆘 Need Help?

1. **Check the warning banner** in the app - it tells you what's wrong
2. **Read TROUBLESHOOTING.md** - detailed solutions for common issues
3. **Check README.md** - full documentation

---

## ✨ Tips

- **New Chat**: Click "➕ New Chat" in sidebar
- **Switch Chats**: Click on any previous chat in sidebar
- **Delete Chat**: Click 🗑️ next to a chat
- **Follow-Up**: Just keep typing in the same conversation
- **Mock Mode**: Yellow warning banner means you're using sample data

---

## 🎯 What's Working vs What's Not

### ✅ Working (Even with DLL Error)
- Streamlit UI loads
- Chat interface works
- Chat history saves
- Mock agent provides sample responses
- All UI features functional

### ⚠️ Limited (With DLL Error)
- Using sample/mock data instead of real agent
- Can't query actual HCP database
- Responses are pre-defined examples

### ✅ Working (After Fixing DLL Error)
- Everything above PLUS
- Real Strategy Agent integration
- Actual HCP data queries
- All 6 specialized agents
- Real-time intelligence

---

**Bottom Line:** The UI works perfectly even with the DLL error. You just see sample data instead of real data. Fix the DLL issue to get real agent responses.
