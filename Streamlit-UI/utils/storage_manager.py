"""
Chat Storage Manager
Handles persistence of chat sessions and messages using JSON files
"""

import json
import os
import uuid
from datetime import datetime
from typing import List, Dict, Optional
from pathlib import Path


class ChatStorageManager:
    """Manages chat session storage using JSON files"""
    
    def __init__(self, storage_dir: str = "chat_history"):
        """
        Initialize storage manager
        
        Args:
            storage_dir: Directory to store chat history files
        """
        self.storage_dir = Path(storage_dir)
        self.storage_dir.mkdir(exist_ok=True)
        self.sessions_file = self.storage_dir / "sessions.json"
        
        # Initialize sessions file if it doesn't exist
        if not self.sessions_file.exists():
            self._save_sessions_metadata([])
    
    def create_session(self) -> str:
        """
        Create a new chat session
        
        Returns:
            str: New session ID (UUID)
        """
        session_id = str(uuid.uuid4())
        timestamp = datetime.now().isoformat()
        
        # Create session metadata
        session_metadata = {
            "session_id": session_id,
            "created_at": timestamp,
            "last_updated": timestamp,
            "preview": "",
            "message_count": 0
        }
        
        # Add to sessions list
        sessions = self._load_sessions_metadata()
        sessions.append(session_metadata)
        self._save_sessions_metadata(sessions)
        
        # Create empty session file
        session_file = self.storage_dir / f"session_{session_id}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump([], f, indent=2)
        
        return session_id
    
    def save_message(self, session_id: str, message: Dict):
        """
        Save a message to a session
        
        Args:
            session_id: Session ID to save message to
            message: Message dictionary with role, content, timestamp
        """
        # Load existing messages
        messages = self.load_session(session_id)
        
        # Add new message
        messages.append(message)
        
        # Save messages
        session_file = self.storage_dir / f"session_{session_id}.json"
        with open(session_file, 'w', encoding='utf-8') as f:
            json.dump(messages, f, indent=2, ensure_ascii=False)
        
        # Update session metadata
        self._update_session_metadata(session_id, messages)
    
    def load_session(self, session_id: str) -> List[Dict]:
        """
        Load all messages from a session
        
        Args:
            session_id: Session ID to load
            
        Returns:
            List of message dictionaries
        """
        session_file = self.storage_dir / f"session_{session_id}.json"
        
        if not session_file.exists():
            return []
        
        try:
            with open(session_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading session {session_id}: {e}")
            return []
    
    def get_all_sessions(self) -> List[Dict]:
        """
        Get metadata for all sessions
        
        Returns:
            List of session metadata dictionaries, sorted by last_updated (newest first)
        """
        sessions = self._load_sessions_metadata()
        # Sort by last_updated, newest first
        sessions.sort(key=lambda x: x.get('last_updated', ''), reverse=True)
        return sessions
    
    def delete_session(self, session_id: str):
        """
        Delete a session and its data
        
        Args:
            session_id: Session ID to delete
        """
        # Remove from sessions metadata
        sessions = self._load_sessions_metadata()
        sessions = [s for s in sessions if s['session_id'] != session_id]
        self._save_sessions_metadata(sessions)
        
        # Delete session file
        session_file = self.storage_dir / f"session_{session_id}.json"
        if session_file.exists():
            session_file.unlink()
    
    def _load_sessions_metadata(self) -> List[Dict]:
        """Load sessions metadata from file"""
        if not self.sessions_file.exists():
            return []
        
        try:
            with open(self.sessions_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return []
    
    def _save_sessions_metadata(self, sessions: List[Dict]):
        """Save sessions metadata to file"""
        with open(self.sessions_file, 'w', encoding='utf-8') as f:
            json.dump(sessions, f, indent=2, ensure_ascii=False)
    
    def _update_session_metadata(self, session_id: str, messages: List[Dict]):
        """Update session metadata after adding a message"""
        sessions = self._load_sessions_metadata()
        
        for session in sessions:
            if session['session_id'] == session_id:
                session['last_updated'] = datetime.now().isoformat()
                session['message_count'] = len(messages)
                
                # Update preview with first user message
                if messages and not session['preview']:
                    first_user_msg = next((m for m in messages if m['role'] == 'user'), None)
                    if first_user_msg:
                        preview_text = first_user_msg['content']
                        session['preview'] = preview_text[:50] + ('...' if len(preview_text) > 50 else '')
                
                break
        
        self._save_sessions_metadata(sessions)
