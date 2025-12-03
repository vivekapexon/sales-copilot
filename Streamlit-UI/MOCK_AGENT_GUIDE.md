# Mock Agent Guide

## Overview

The mock agent now supports a wide range of queries and provides realistic sample responses to help you test the UI fully.

## Supported Query Types

### 1. Call Objective / Desired Outcome ✅ NEW!

**Example Queries:**
- "What is the objective for my call with HCP1001?"
- "What's the desired action/outcome from my call with this HCP?"
- "What should be my main goal for this visit?"
- "What's the priority for this HCP?"

**Response Includes:**
- Primary objective
- Desired action
- Key message
- Rationale
- Talking points
- Potential objections & responses
- Success metrics
- Supporting intelligence
- Recommended content

### 2. HCP Profile

**Example Queries:**
- "Give me the profile for HCP H123"
- "Who is Dr. Smith?"
- "Tell me about this HCP"

**Response Includes:**
- HCP ID
- Doctor name
- Specialty
- Practice type
- Years in practice
- Patient volume

### 3. Prescribing Trends

**Example Queries:**
- "How has Dr. Patel's prescribing changed?"
- "Show me prescribing trends"
- "What's the adoption stage?"

**Response Includes:**
- Total prescriptions (7d, 28d, 90d)
- New prescriptions
- Momentum (WoW, QoQ changes)
- Brand adoption journey

### 4. Access Intelligence

**Example Queries:**
- "Which plans cover our product?"
- "What's the formulary status?"
- "Tell me about access for this HCP"

**Response Includes:**
- Coverage status (tier, PA, step therapy)
- Copay information
- Recent changes
- Actionable opportunities

### 5. Interaction History

**Example Queries:**
- "When did I last meet Dr. X?"
- "Show me interaction history"
- "What were the previous discussions?"

**Response Includes:**
- Recent interactions
- Call dates and types
- Topics discussed
- Objections raised

### 6. Competitive Intelligence

**Example Queries:**
- "What are competitors doing?"
- "Show me competitive threats"
- "Any competitive pressure?"

**Response Includes:**
- Competitor activity level
- Main competitors
- Threat assessment
- Share trends

### 7. Content Recommendations

**Example Queries:**
- "What content should I use?"
- "Show me approved materials"
- "Which materials are recommended?"

**Response Includes:**
- Recommended materials
- Material types (PDF, slides, etc.)
- Relevance scores
- Last used dates

### 8. Full Pre-Call Brief

**Example Queries:**
- "Prepare me for my call with Dr. Rao"
- "Give me a full brief"
- "Get me ready for this visit"

**Response Includes:**
- All of the above (Profile, Prescribing, Access, History, Competitive, Content, Objective)

## How to Use

### Testing Call Objectives

Try these queries to see the enhanced call objective response:

```
What is the objective and desired action/outcome from my call with HCP1001?
```

```
What should be my main goal for visiting Dr. Smith?
```

```
What's the priority for this HCP?
```

### Testing Multiple Queries

You can ask follow-up questions in the same conversation:

```
User: Give me the profile for HCP1001
Agent: [Profile response]

User: What are the prescribing trends?
Agent: [Prescribing response]

User: What should be my call objective?
Agent: [Call objective response]
```

## Response Format

### Call Objective Response Format

The call objective response is beautifully formatted with:

- **Highlighted Primary Objective** - Yellow box with main goal
- **Desired Action** - Specific commitment to seek
- **Key Message** - Main talking point
- **Rationale** - Why this objective makes sense
- **Talking Points** - Bullet list of discussion topics
- **Objections & Responses** - Prepared responses for common objections
- **Success Metrics** - How to measure call success
- **Supporting Intelligence** - Expandable section with data
- **Recommended Content** - Materials to use

## Customizing Mock Responses

To customize the mock responses for your specific needs, edit:

`Strategy-Agent/mock_strategy_agent.py`

You can:
- Change HCP IDs
- Modify sample data
- Add new query patterns
- Adjust response content

## Switching to Real Agent

Once you resolve the strands dependency issue:

1. The app will automatically detect the real agent
2. All queries will use real data
3. No code changes needed
4. Mock agent becomes inactive

## Tips

1. **HCP ID Detection** - The mock agent extracts HCP IDs from your query (e.g., "HCP1001", "HCP123")
2. **Keyword Matching** - Uses keywords to determine query intent
3. **Realistic Data** - Mock responses mirror real agent structure
4. **Full UI Testing** - Test all features without backend dependencies

## Known Limitations

- Mock data is static (doesn't change based on actual HCP)
- No database queries
- Pre-defined responses only
- Limited to programmed query patterns

## Next Steps

1. **Test the UI** - Try all query types
2. **Verify Layout** - Check formatting and styling
3. **Test Features** - Chat history, follow-ups, sessions
4. **Fix strands** - Install Visual C++ Redistributable
5. **Switch to Real** - Enjoy actual data!

---

**Remember:** The mock agent is for UI testing only. Install strands to get real intelligence!
