Based on the given area of interest, please:

1. Dig around the codebase in terms of that given area of interest, gather general information such as keywords and architecture overview.
2. Spawn off n=10 (unless specified otherwise) task agents to dig deeper into the codebase in terms of that given area of interest, some of them should be out of the box for variance.
3. Once the task agents are done, use the information to do what the user wants.

If user is in plan mode, use the information to create the plan.

## Spawning Subagents

Available subagents are located in `.cursor/agents/`:

### Explorer Agent
**Purpose**: Broadly explores the codebase to gather information about architecture, patterns, components, and implementation details.

**How to spawn**: 
- Read `.cursor/agents/explorer.md` to understand the agent's capabilities
- Assign the explorer a specific area of interest or exploration task
- The explorer will use semantic search, file reading, and directory exploration to gather comprehensive information
- Reports are saved to `/docs/generated/`

**Use cases**:
- Initial codebase reconnaissance
- Architecture discovery
- Component mapping
- Pattern recognition
- Integration point identification

**Example**: "Spawn an Explorer agent to investigate the data collection pipeline architecture"

### Verifier Agent
**Purpose**: Validates completed work, checks implementations are functional, runs tests, and reports what passed vs what's incomplete.

**How to spawn**:
- Read `.cursor/agents/verifier.md` to understand the agent's verification workflow
- Assign the verifier a specific implementation or feature to validate
- The verifier will run tests, check functionality, and generate a comprehensive report
- Reports are saved to `/docs/generated/`

**Use cases**:
- Validating completed implementations
- Running test suites
- Checking code quality and linting
- Verifying functional requirements
- Generating pass/fail reports

**Example**: "Spawn a Verifier agent to validate the MT5 connector implementation"

### Spawning Instructions

To spawn a subagent:
1. Read the agent's file from `.cursor/agents/[agent-name].md`
2. Understand the agent's capabilities and workflow
3. Assign a specific task or area of interest
4. Let the agent execute its workflow
5. Review the agent's findings and reports
6. Use the information to complete the council's objectives

**Note**: Subagents are designed to work independently and report back with their findings. They can be spawned in parallel for different areas of investigation.