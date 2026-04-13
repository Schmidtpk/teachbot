# teachbot

## Context

I am a university professor in economics working on decision theory, microeconomics, and forecast evaluation.
For my lectures, and other educators, I want to build an open-source tool that sets up an online chat environment for students, where an LLM API is used for interactions that are enriched by the lecture content. The key functionality should be

- **QA**: Ask questions the chatbot answers based on lecture content
- **Learn**: Chatbot explains and makes test questions with Socratic dialogue to teach students a certain topic
- **Eval**: Chatbot evaluates chat and gives qualitative feedback and grade to student

All interactions should have a simple feedback mechanism, where students can immediately give feedback to the lecturer if something went wrong or the agent misbehaves/makes errors.

## Development plan / experience

Plan/documentation should be intention-first: 

- intentions.md lists the intended functionality of the code base

    - IID-SEMANTIC-TAG (for Intention ID). Use semantic tags (e.g., IID-QNA-CORE)
    - In code scripts, always reference the IID if code snippet connected to fulfilling this intention 
    - SID-SEMANTIC-TAG (standard ID) for standards fixed across the codebase.
    - In code scripts, always reference the SID if code needs to adhere here to this standard
    - intentions.md should only contain intentions and standards, and if they are already implemented or still to do (TODO)
    - Should allow new coding agents to reconstruct functionality
    - Should allow coding agent instances to find code (search IIDs or SIDs) and make sure to adhere to agreed standards


- README.md lists instructions for users of codebase

## Coding instructions

- **Refactoring Rule:** When refactoring or moving code, you must preserve any linked IID or SID comment tags.

- Coding workflow
        - Plan
    - Discuss/ask questions/propose alternatives
    - Focus on all mentioned connected intentions and standards
        - Propose changes to intentions or standards if suitable
        - Write plan, mention IID and SID where appropriate
        - Implement
        - Test
        - Save plan and execution in agent/done/short_plan_name.md
            - should contain: Linked IID/SID, Decisions taken, 
        - Commit
            - should name linked IID/SID and plan_name
    - Track only code and key .md files: intentions.md, CLAUDE.md, README.md, but do not track lecture content or done plans, etc.



## List of files



## Things to discuss


## Intentions draft

- Intentions have **lifecycles CANDO, TODO, v1, IN_PROGRESS, EXPERIMENTAL, DONE, DEPRECATED**.
    - v1 refers to aspects that should work in next version. TODO only at some point. CANDO only potentially.
    - intentions can mention No-Goals: Things that are not planned, used to reduce complexity.

- **Safety + Privacy** Standards

    - What can be stored?
    - Guardrails for harmful or unsafe requests?

- Data Baseline
    - Minimum entities to expect?

- Define QA, Learn, Evaluate in operational terms:
    - QA:
        - Inputs:
            - Question (obligartory): Student question
        - Outputs:
            - Answer: md text rendered for chat
        - Success criteria:
            - Answer correct
            - Answer reflects lecture content
            - Answer related to question
        