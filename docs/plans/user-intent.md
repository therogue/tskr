Intents:
Current:
- Task operation -> JSON format

User query -> SYSTEM_PROMPT -> JSON response

Planned:
- Task operation -> JSON format | LLM question
- Answer question from LLM -> JSON format | LLM question
- Request automatic reschedule -> JSON format
- Ask LLM a question -> LLM response

Ask LLM a question:
User: Do I have a task to pick up cookies before I go to my friend's dinner?
LLM: Yes/No.

Answer question from LLM:
User: Schedule a task to have dinner with my friend.
LLM: I've scheduled this task. Do you also need to schedule a task to pick up cookies?
User: Yes.


User query -> INTENT_DETECT_PROMPT
    -> TASK_OPERATION_PROMPT -> JSON format
    -> ASK_QUESTION_PROMPT -> Text response
