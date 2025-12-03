# Implementation Plan

- [x] 1. Set up project structure and dependencies


  - Create `streamlit_app.py` as main entry point
  - Create `requirements.txt` with Streamlit and necessary dependencies
  - Create `chat_history/` directory for storage
  - Create `utils/` directory for helper modules
  - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [x] 2. Implement chat storage manager


  - [ ] 2.1 Create `utils/storage_manager.py` with ChatStorageManager class
    - Implement `__init__()` to initialize storage directory
    - Implement `create_session()` to generate new session with UUID
    - Implement `save_message()` to append messages to session file
    - Implement `load_session()` to retrieve all messages from session
    - Implement `get_all_sessions()` to list session metadata
    - Implement `delete_session()` to remove session files
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_

  - [ ]* 2.2 Write unit tests for storage manager
    - Test session creation and ID generation
    - Test message saving and loading
    - Test session deletion
    - Test handling of corrupted data
    - _Requirements: 7.1, 7.2, 7.3, 7.4, 7.5_



- [ ] 3. Implement agent integration module
  - [ ] 3.1 Create `utils/agent_integration.py` for strategy agent interface
    - Implement `call_strategy_agent()` to invoke run_strategy_agent()
    - Implement `parse_agent_response()` to structure raw responses
    - Implement `handle_agent_error()` to format error messages
    - Add timeout handling (30 seconds) for agent calls
    - _Requirements: 5.1, 5.2, 5.5, 5.6, 10.1, 10.2_

  - [ ]* 3.2 Write unit tests for agent integration
    - Mock strategy agent responses
    - Test error handling for agent failures
    - Test timeout scenarios


    - Test response parsing for different agent types
    - _Requirements: 5.5, 5.6, 10.1, 10.2_

- [ ] 4. Implement response formatter module
  - [ ] 4.1 Create `utils/response_formatter.py` for formatting agent outputs
    - Implement `format_json_response()` for general JSON formatting
    - Implement `format_profile_agent_response()` for Profile Agent data
    - Implement `format_prescribing_agent_response()` for Prescribing Agent data
    - Implement `format_multi_agent_response()` for multiple agent outputs
    - Implement `create_json_expander()` for expandable JSON sections
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

  - [ ]* 4.2 Write unit tests for response formatter
    - Test JSON formatting with various data structures


    - Test handling of empty responses
    - Test handling of malformed JSON
    - Test formatting for each agent type
    - _Requirements: 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 5. Create AWS-themed styling and CSS
  - [ ] 5.1 Create `utils/styles.py` with AWS color palette and CSS definitions
    - Define AWS_COLORS dictionary with brand colors
    - Create `get_custom_css()` function returning CSS string


    - Implement header styling with AWS theme
    - Implement user message styling (right-aligned, orange background)
    - Implement agent message styling (left-aligned, gray background with orange border)
    - Implement sidebar session styling
    - Implement fixed input box styling
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 3.2, 3.3, 3.4, 4.1, 4.2, 4.4_

- [x] 6. Implement session state initialization

  - [ ] 6.1 Create session state management in `streamlit_app.py`
    - Implement `initialize_session_state()` function
    - Initialize `current_session_id` in session state
    - Initialize `messages` list in session state
    - Initialize `chat_sessions` list in session state
    - Initialize `is_processing` flag in session state
    - Initialize storage_manager instance in session state


    - _Requirements: 6.1, 6.2, 6.3, 6.4, 7.3_

- [ ] 7. Implement header component
  - [ ] 7.1 Create `render_header()` function in `streamlit_app.py`
    - Use `st.markdown()` with custom HTML for header
    - Display "SALES-COPILOT" title with AWS styling
    - Apply fixed positioning at top of page
    - Add AWS orange accent border at bottom
    - _Requirements: 1.1, 1.2, 1.3, 1.4_



- [ ] 8. Implement sidebar component
  - [ ] 8.1 Create `render_sidebar()` function in `streamlit_app.py`
    - Add "New Chat" button at top of sidebar
    - Implement `create_new_chat()` to start fresh session
    - Display list of previous chat sessions from storage
    - Show session preview and timestamp for each session
    - Implement `load_chat_session()` to switch between sessions
    - Add delete button for each session with confirmation
    - Implement `delete_chat_session()` to remove sessions


    - Handle empty chat history state with informative message
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 9.1, 9.2, 9.3, 9.4, 9.5_

- [ ] 9. Implement conversation display component
  - [ ] 9.1 Create `render_conversation()` function in `streamlit_app.py`
    - Create scrollable container for messages
    - Implement `render_user_message()` for user messages with right alignment
    - Implement `render_agent_message()` for agent responses with left alignment
    - Apply distinct styling for user vs agent messages
    - Implement auto-scroll to latest message
    - Format JSON responses using response_formatter module
    - Display agent names clearly when multiple agents respond
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.5, 8.1, 8.2, 8.3, 8.4, 8.5_

- [ ] 10. Implement input component with message handling
  - [ ] 10.1 Create `render_input_box()` function in `streamlit_app.py`
    - Create fixed input box at bottom using custom CSS
    - Add placeholder text: "Ask about HCP profiles, prescribing trends, or get pre-call briefs..."
    - Implement send button next to input box
    - Handle Enter key press for message submission
    - Implement `handle_message_submission()` function
    - Clear input box after submission
    - Disable input during agent processing
    - Display loading indicator while agent processes


    - Save user message to storage immediately

    - Call agent integration module to get response
    - Save agent response to storage
    - Re-enable input after response received
    - Handle errors and display error messages
    - _Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 6.1, 6.2, 6.3, 10.1, 10.2, 10.3, 10.4, 10.5_

- [ ] 11. Implement error handling and user feedback
  - [ ] 11.1 Create `utils/error_handler.py` for centralized error handling
    - Implement `handle_error()` function with error categorization
    - Define user-friendly error messages for each error type
    - Implement error logging for debugging
    - Create error display functions using `st.error()`, `st.warning()`, `st.info()`


    - Handle agent execution errors
    - Handle storage errors
    - Handle missing parameter errors
    - Handle network errors
    - _Requirements: 10.1, 10.2, 10.3, 10.4, 10.5_


- [ ] 12. Integrate all components in main application
  - [ ] 12.1 Complete `streamlit_app.py` main function
    - Set Streamlit page configuration (title, icon, layout)
    - Apply custom CSS using styles module
    - Initialize session state


    - Render header component
    - Render sidebar component
    - Render conversation display component
    - Render input component
    - Wire up all event handlers
    - Ensure proper component ordering and layout




    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7_

- [ ] 13. Add conversation context handling for follow-up questions
  - [ ] 13.1 Implement context management in agent integration
    - Modify `call_strategy_agent()` to accept conversation history
    - Pass previous messages as context to strategy agent
    - Ensure agent has access to full conversation for follow-ups
    - Maintain separate contexts for different sessions
    - _Requirements: 6.1, 6.2, 6.3, 6.4_

- [ ] 14. Create requirements.txt and documentation
  - [ ] 14.1 Create `requirements.txt` with all dependencies
    - Add streamlit>=1.28.0
    - Add dependencies from strategy_agent.py (strands, etc.)
    - Add any additional utility libraries
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

  - [ ] 14.2 Create README.md with setup and usage instructions
    - Document installation steps
    - Document how to run the application
    - Document configuration options
    - Add screenshots or usage examples
    - _Requirements: 1.1, 1.2, 1.3, 1.4_

- [ ] 15. Manual testing and refinement
  - [ ] 15.1 Perform end-to-end testing
    - Test complete user interaction flow from new chat to follow-up questions
    - Test session persistence by closing and reopening application
    - Test multi-turn conversations with context
    - Test all agent types (Profile, History, Prescribing, Access, Competitive, Content)
    - Test error scenarios (agent failures, missing parameters)
    - Test UI responsiveness and styling on different screen sizes
    - Test chat history management (create, load, delete sessions)
    - Verify AWS theme displays correctly
    - Verify JSON responses are formatted properly
    - Verify loading indicators appear during processing
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 2.1, 2.2, 2.3, 2.4, 2.5, 2.6, 3.1, 3.2, 3.3, 3.4, 3.5, 4.1, 4.2, 4.3, 4.4, 4.5, 5.1, 5.2, 5.3, 5.4, 5.5, 5.6, 5.7, 6.1, 6.2, 6.3, 6.4, 7.1, 7.2, 7.3, 7.4, 7.5, 8.1, 8.2, 8.3, 8.4, 8.5, 9.1, 9.2, 9.3, 9.4, 9.5, 10.1, 10.2, 10.3, 10.4, 10.5_
