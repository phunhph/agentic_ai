# Implementation Guide: Agent Trace Display System

## Quick Reference

### Error That Was Fixed
```
AttributeError: 'dict' object has no attribute 'intent'
```

### Root Cause
Jinja2 template tried to access dictionary keys using Python dot notation:
```jinja2
{{ layers.ingest.intent }}  ❌ WRONG
{{ layers.ingest.get('intent', 'UNKNOWN') }}  ✅ CORRECT
```

---

## Architecture Overview

### 5-Agent Pipeline with Trace Display

```
USER QUERY
    ↓
① INGEST AGENT
  └─→ Extract: intent, entities, ambiguity
    ↓
② REASONING AGENT  
  └─→ Generate: thought, decision, confidence
    ↓
③ EXECUTION AGENT
  └─→ Execute: query, fetch records
    ↓
④ LEARNING AGENT
  └─→ Learn: update knowledge base
    ↓
⑤ RESPONSE → UI with Clickable Traces
```

### Each Agent Layer Has
```python
{
    # Agent-specific data
    "intent": "ACCOUNT_LIST",
    "entities": ["account"],
    ...
    
    # NEW: I/O Trace for debugging
    "io_trace": {
        "input": { /* what agent received */ },
        "output": { /* what agent produced */ }
    }
}
```

---

## Implementation Details

### 1. Template Fixes (trace_result.html)

**Before** (❌ Causes error):
```jinja2
<span class="text-indigo-400">{{ layers.ingest.intent | upper }}</span>
```

**After** (✅ Works):
```jinja2
<span class="text-indigo-400">{{ layers.ingest.get('intent', 'UNKNOWN') | upper }}</span>
```

**Pattern for all dict access in templates**:
```jinja2
{{ dict_var.get('key', 'default_value') }}
```

### 2. Service Layer Enhancement (v2/service.py)

**Added to `run_v2_pipeline()`**:

```python
# Ensure layers are dicts (safety check)
if not isinstance(ingest_layer, dict):
    ingest_layer = {"intent": "UNKNOWN", ...}

# Add I/O traces for each layer
ingest_layer["io_trace"] = {
    "input": {
        "raw_query": query,
        "role": role,
        "session_id": session_id
    },
    "output": {
        "intent": ingest_layer.get("intent", "UNKNOWN"),
        "entities": ingest_layer.get("entities", []),
        "ambiguity_score": ingest_layer.get("ambiguity_score", 0.0)
    }
}
```

### 3. Trace Modal Feature

**HTML Structure**:
```html
<!-- Clickable Agent Buttons -->
<button onclick="showAgentTrace('ingest', {{ layers.ingest|tojson|safe }})">
    ① INGEST AGENT
</button>

<!-- Modal for trace display -->
<div id="traceModal" class="hidden">
    <div id="traceModalContent">
        <!-- Formatted trace output -->
    </div>
</div>
```

**JavaScript Logic**:
```javascript
function showAgentTrace(agent, traceData) {
    // Build formatted output
    let output = '📊 AGENT: ' + agent.toUpperCase() + '\n';
    
    // Display I/O trace
    output += 'INPUT:\n' + JSON.stringify(traceData.io_trace.input, null, 4);
    output += 'OUTPUT:\n' + JSON.stringify(traceData.io_trace.output, null, 4);
    
    // Agent-specific details
    if (agent === 'ingest') {
        output += 'Intent: ' + traceData.intent;
        // ... etc
    }
    
    // Show modal
    document.getElementById('traceModalContent').textContent = output;
    document.getElementById('traceModal').classList.remove('hidden');
}
```

---

## Layer Details

### INGEST Layer Structure
```python
{
    "intent": "ACCOUNT_LIST",           # Detected intent
    "entities": ["account"],            # Extracted entities  
    "ambiguity_score": 0.25,           # Confidence (0-1)
    "request_filters": [               # Applied filters
        {"field": "name", "op": "contains", "value": "Acme"}
    ],
    "raw_query": "list accounts",       # Original query
    "io_trace": {
        "input": {...},
        "output": {...}
    }
}
```

### REASON Layer Structure
```python
{
    "thought_process": "User wants to list...",  # Agent's thinking
    "decision": "auto_execute",                  # Decision type
    "confidence": 0.85,                          # Confidence score
    "trace": {...},                              # Detailed trace
    "io_trace": {
        "input": {...},
        "output": {...}
    }
}
```

### EXECUTE Layer Structure
```python
{
    "status": "EXECUTED",               # Execution status
    "record_count": 42,                 # Records found
    "results": [                        # Retrieved data
        {"id": 1, "name": "Acme Corp", ...}
    ],
    "errors": [],                       # Any errors
    "io_trace": {
        "input": {...},
        "output": {...}
    }
}
```

### LEARN Layer Structure
```python
{
    "learning_summary": "Updated pattern for ACCOUNT_LIST",
    "learning_update": {
        "learning_decision": "appended",  # appended|skipped
        "evidence": {
            "score": 0.75,
            "eligible": true
        }
    },
    "io_trace": {
        "input": {...},
        "output": {...}
    }
}
```

---

## Debugging Guide

### Issue: Intent not being detected
1. Click **① INGEST AGENT**
2. Look at `INPUT.raw_query` - is it correct?
3. Check `OUTPUT.intent` - what was detected?
4. Review `OUTPUT.ambiguity_score` - is it too high?

### Issue: Wrong database records
1. Click **③ EXECUTION AGENT**
2. Check `INPUT.filters` - are they correct?
3. Review `OUTPUT.record_count` - how many records?
4. Look at first few in `OUTPUT.results` - correct type?

### Issue: Learning not updating
1. Click **④ LEARNING AGENT**
2. Check `OUTPUT.learning_decision` - was it appended/skipped?
3. Review evidence score and reasoning
4. Check `learning_summary` for explanation

---

## Common Issues & Solutions

| Issue | Solution |
|-------|----------|
| `'dict' object has no attribute X` | Use `.get('X', default)` instead of `.X` |
| Modal doesn't show | Check browser console for JS errors |
| No I/O trace displayed | Verify `io_trace` is added in v2/service.py |
| Traces empty/None | Ensure layer dicts are initialized, not None |

---

## Testing Checklist

- [ ] No "'dict' object has no attribute" errors
- [ ] Query executes successfully
- [ ] Click INGEST button - modal appears with intent
- [ ] Click REASON button - modal shows thought process
- [ ] Click EXECUTE button - modal shows results
- [ ] Click LEARN button - modal shows learning decision
- [ ] Press Escape key - modal closes
- [ ] Click outside modal - modal closes
- [ ] I/O traces are populated with actual data
- [ ] JSON formatting is readable

---

## Performance Notes

- Trace data includes I/O details (minimal overhead)
- Modal is client-side rendering (instant display)
- No additional database calls for traces
- Suitable for debugging and production use

---

## Future Enhancements

1. **Trace History**: Store traces for later analysis
2. **Export Traces**: Download trace data as JSON/CSV
3. **Trace Comparison**: Compare traces between runs
4. **Visualization**: Graph dependencies between agents
5. **Performance Metrics**: Show execution time for each agent
